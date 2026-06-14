"""Target leakage diagnostics.

Detects features that leak the target. Heuristic stack (run in order):
  1. High mutual information / |corr| with target  -> CRITICAL perfect predictor
  2. Suspicious column name AND corr-with-target high -> HIGH
  3. Column equal to / monotonic transform of target -> CRITICAL
  4. id-like column used as a feature -> HIGH (memorization)
  5. Duplicates + target present -> warn random splits leak

Handles both classification and regression targets. Categoricals are factorized
before mutual information.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine

_NAME_RE = re.compile(config.LEAKAGE_NAME_PATTERN, re.IGNORECASE)
_LEAKAGE_EVIDENCE_RE = re.compile(
    r"(final|after|outcome|result|status|post|label|target|actual|realized|"
    r"cancellation|churn_date|revenue_after|default_status|diagnosis_confirmed)",
    re.IGNORECASE,
)


def _has_leakage_evidence(feature: str, target: str) -> bool:
    name = str(feature)
    target_name = str(target)
    return bool(_LEAKAGE_EVIDENCE_RE.search(name)) or bool(_LEAKAGE_EVIDENCE_RE.search(target_name) and _NAME_RE.search(name))


def _encode(series: pd.Series, is_numeric: bool) -> np.ndarray:
    """Factorize categoricals, coerce numeric-as-string. Returns float array."""
    if is_numeric:
        return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    codes, _ = pd.factorize(series, use_na_sentinel=True)
    return codes.astype(float)


def _is_target_categorical(df: pd.DataFrame, target: str, schema: dict) -> bool:
    prof = schema.get("columns", {}).get(target, {})
    dtype = prof.get("dtype_inferred")
    n_unique = prof.get("n_unique", 0)
    if dtype in ("categorical", "boolean", "id"):
        return True
    if dtype == "numeric" and n_unique <= 20:
        return True
    return False


class LeakageEngine(Engine):
    name = "leakage"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        cols = schema.get("columns", {})

        if not target or target not in df.columns:
            # Heuristic 2 (name only, no target): still flag suspiciously named cols as INFO.
            for col, prof in cols.items():
                if _NAME_RE.search(col):
                    findings.append(
                        Finding(
                            engine=self.name,
                            code="SUSPICIOUS_COLUMN_NAME_NO_TARGET",
                            severity=Severity.INFO,
                            title=f"'{col}' has a leakage-prone name",
                            detail=(
                                f"'{col}' matches a pattern often used for outcomes/labels. "
                                "Select a target column to check it for leakage."
                            ),
                            impact=(
                                "If this column is computed after the prediction time, using it "
                                "as a feature would leak the future into training."
                            ),
                            column=col,
                            fix_snippet=f"# Verify timing of {col!r}; drop if post-outcome.\n# df = df.drop(columns=[{col!r}])",
                            metrics={},
                        )
                    )
            return findings

        target_is_cat = _is_target_categorical(df, target, schema)

        # Build an analysis frame, capped for speed.
        work = df
        if len(df) > config.LEAKAGE_SAMPLE_ROWS:
            work = df.sample(config.LEAKAGE_SAMPLE_ROWS, random_state=config.SAMPLE_RANDOM_STATE)

        y_raw = work[target]
        y_prof = cols.get(target, {})
        y_numeric_kind = y_prof.get("dtype_inferred") == "numeric"
        y_enc = _encode(y_raw, is_numeric=y_numeric_kind and not target_is_cat)

        # Precompute MI for all eligible feature columns in one call (robust + fast).
        # id-like / near-unique columns are handled separately (memorization,
        # heuristic 4); a near-unique feature trivially has MI~1 with any target,
        # which is memorization not leakage, so exclude them from MI/corr checks.
        HIGH_CARD_GUARD = 0.5

        def _eligible(c: str, p: dict) -> bool:
            if c == target or p.get("is_id_like") or p.get("is_high_cardinality"):
                return False
            if p.get("cardinality_ratio", 0.0) >= HIGH_CARD_GUARD and p.get("dtype_inferred") != "numeric":
                return False
            return p.get("dtype_inferred") in ("numeric", "categorical", "boolean")

        feature_cols = [c for c, p in cols.items() if _eligible(c, p)]

        mi_scores: dict[str, float] = {}
        try:
            from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

            mask = np.asarray(~pd.isna(y_enc))
            if int(mask.sum()) >= 20 and feature_cols:
                X_parts = {}
                discrete_flags = []
                for c in feature_cols:
                    p = cols[c]
                    is_num = p.get("dtype_inferred") == "numeric"
                    enc = _encode(work[c], is_numeric=is_num)
                    X_parts[c] = enc
                    discrete_flags.append(not is_num)
                X = pd.DataFrame(X_parts)
                # impute NaNs with column medians so sklearn won't choke
                X = X.fillna(X.median(numeric_only=True)).fillna(-1)
                Xv = X.to_numpy(dtype=float)[mask]
                yv = np.asarray(y_enc)[mask]
                if len(np.unique(yv)) >= 2 or not target_is_cat:
                    if target_is_cat:
                        raw_mi = mutual_info_classif(
                            Xv, yv.astype(int), discrete_features=discrete_flags,
                            random_state=config.SAMPLE_RANDOM_STATE,
                        )
                    else:
                        raw_mi = mutual_info_regression(
                            Xv, yv, discrete_features=discrete_flags,
                            random_state=config.SAMPLE_RANDOM_STATE,
                        )
                    # Normalize by the target's own entropy/variance proxy so values land in ~[0,1].
                    if target_is_cat:
                        _, ycounts = np.unique(yv.astype(int), return_counts=True)
                        p_ = ycounts / ycounts.sum()
                        ent = -np.sum(p_ * np.log(p_ + 1e-12))
                        denom = ent if ent > 1e-9 else 1.0
                    else:
                        # self-MI proxy via variance is unstable; normalize by max observed MI.
                        denom = max(raw_mi.max(), 1e-9)
                    for c, m in zip(feature_cols, raw_mi):
                        mi_scores[c] = float(m / denom)
        except Exception:
            mi_scores = {}

        # Pearson corr with target (numeric or factorized) as a fallback/confirmation signal.
        corr_scores: dict[str, float] = {}
        try:
            y_series = pd.Series(y_enc, index=work.index)
            for c in feature_cols:
                p = cols[c]
                is_num = p.get("dtype_inferred") == "numeric"
                x_series = pd.Series(_encode(work[c], is_numeric=is_num), index=work.index)
                joined = pd.concat([x_series, y_series], axis=1).dropna()
                if len(joined) >= 10 and joined.iloc[:, 0].nunique() > 1 and joined.iloc[:, 1].nunique() > 1:
                    corr_scores[c] = float(abs(joined.iloc[:, 0].corr(joined.iloc[:, 1])))
        except Exception:
            corr_scores = {}

        flagged: set[str] = set()

        # Heuristic 3 first: exact equality / monotonic transform of the target.
        for c in feature_cols:
            try:
                p = cols[c]
                is_num = p.get("dtype_inferred") == "numeric"
                xs = pd.Series(_encode(work[c], is_numeric=is_num), index=work.index)
                pair = pd.concat([xs, pd.Series(y_enc, index=work.index)], axis=1).dropna()
                if len(pair) < 10:
                    continue
                a, b = pair.iloc[:, 0], pair.iloc[:, 1]
                exact = bool((a.values == b.values).all())
                mono = False
                if not exact and a.nunique() > 1 and b.nunique() > 1:
                    sp = abs(a.corr(b, method="spearman"))
                    mono = bool(sp >= 0.999)
                if exact or mono:
                    flagged.add(c)
                    kind = "identical to" if exact else "a monotonic transform of"
                    plausible = _has_leakage_evidence(c, target)
                    findings.append(
                        Finding(
                            engine=self.name,
                            code="TARGET_LEAKAGE_TARGET_COPY" if plausible else "TARGET_PROXY_RISK",
                            severity=Severity.CRITICAL if plausible else Severity.MEDIUM,
                            title=f"'{c}' is {kind} the target" if plausible else f"'{c}' is a target proxy risk",
                            detail=f"'{c}' reproduces '{target}' ({'exact match' if exact else 'spearman~1.0'}).",
                            impact=(
                                "This column reproduces the answer and appears to be post-outcome."
                                if plausible else
                                "This column has target-like association, but no timing or semantic leakage evidence was found. Review whether it is a legitimate feature."
                            ),
                            column=c,
                            fix_snippet=f"df = df.drop(columns=[{c!r}])",
                            metrics={"mi": round(mi_scores.get(c, 0.0), 4), "corr": round(corr_scores.get(c, 0.0), 4)},
                            category="data_integrity" if plausible else "modeling_warning",
                        )
                    )
            except Exception:
                continue

        # Heuristic 1: near-perfect predictor by MI or |corr|.
        for c in feature_cols:
            if c in flagged:
                continue
            mi = mi_scores.get(c, 0.0)
            corr = corr_scores.get(c, 0.0)
            if mi >= config.LEAKAGE_MI_CRITICAL or corr >= config.LEAKAGE_MI_CRITICAL:
                flagged.add(c)
                plausible = _has_leakage_evidence(c, target)
                findings.append(
                    Finding(
                        engine=self.name,
                        code="TARGET_LEAKAGE_PERFECT_PREDICTOR" if plausible else "TARGET_PROXY_RISK",
                        severity=Severity.CRITICAL if plausible else Severity.MEDIUM,
                        title=f"'{c}' almost perfectly predicts the target" if plausible else f"'{c}' is highly associated with the target",
                        detail=(
                            f"Normalized MI={mi:.3f}, |corr|={corr:.3f} between '{c}' and "
                            f"'{target}'."
                        ),
                        impact=(
                            "Near-perfect single-feature predictive power plus timing/name evidence suggests leakage."
                            if plausible else
                            "High association alone is not enough to call leakage. Treat this as a target proxy risk and review feature timing."
                        ),
                        column=c,
                        fix_snippet=f"# Confirm timing and availability before training\n# df = df.drop(columns=[{c!r}])",
                        metrics={"mi": round(mi, 4), "corr": round(corr, 4)},
                        category="data_integrity" if plausible else "modeling_warning",
                    )
                )

        # Heuristic 2: suspicious name AND elevated corr -> HIGH.
        for c in feature_cols:
            if c in flagged:
                continue
            if _NAME_RE.search(c) and _has_leakage_evidence(c, target):
                corr = corr_scores.get(c, 0.0)
                mi = mi_scores.get(c, 0.0)
                if corr >= config.LEAKAGE_CORR_SUSPICIOUS or mi >= config.LEAKAGE_CORR_SUSPICIOUS:
                    flagged.add(c)
                    findings.append(
                        Finding(
                            engine=self.name,
                            code="TARGET_LEAKAGE_SUSPICIOUS_NAME",
                            severity=Severity.HIGH,
                            title=f"'{c}' is suspiciously named and correlates with the target",
                            detail=(
                                f"'{c}' matches an outcome-like naming pattern and has "
                                f"|corr|={corr:.3f} (MI={mi:.3f}) with '{target}'."
                            ),
                            impact=(
                                "Columns named like outcomes/scores are frequently derived from "
                                "the label or computed post-hoc; using them leaks the target."
                            ),
                            column=c,
                            fix_snippet=f"# Verify feature timing, then drop if post-outcome\ndf = df.drop(columns=[{c!r}])",
                            metrics={"mi": round(mi, 4), "corr": round(corr, 4)},
                        )
                    )

        # Heuristic 4: near-unique confirmed identifier used as a feature -> HIGH (memorization).
        for c, p in cols.items():
            if c == target or c in flagged:
                continue
            if p.get("is_id_like") and p.get("cardinality_ratio", 0.0) >= config.ID_CARDINALITY_RATIO:
                findings.append(
                    Finding(
                        engine=self.name,
                        code="ID_USED_AS_FEATURE",
                        severity=Severity.HIGH,
                        title=f"id-like column '{c}' would be memorized",
                        detail=f"'{c}' is near-unique ({p.get('cardinality_ratio', 0):.2f} distinct ratio).",
                        impact=(
                            "Near-unique identifiers let tree/embedding models memorize individual "
                            "rows, which hurts performance on unseen ids."
                        ),
                        column=c,
                        fix_snippet=f"df = df.drop(columns=[{c!r}])",
                        metrics={"cardinality_ratio": p.get("cardinality_ratio", 0)},
                        category="modeling_warning",
                    )
                )

        # Heuristic 5: duplicates + target -> random splits leak.
        try:
            dup_count = int(df.duplicated().sum())
            if dup_count > 0:
                findings.append(
                    Finding(
                        engine=self.name,
                        code="DUPLICATES_SPLIT_LEAK",
                        severity=Severity.MEDIUM,
                        title="Duplicate rows can leak across a random split",
                        detail=f"{dup_count} duplicate rows present while a target is set.",
                        impact=(
                            "Identical rows landing in both train and test inflate validation "
                            "scores. Deduplicate before splitting, or split on a group key."
                        ),
                        column=None,
                        fix_snippet="df = df.drop_duplicates().reset_index(drop=True)",
                        metrics={"dup_count": dup_count},
                    )
                )
        except Exception:
            pass

        return findings
