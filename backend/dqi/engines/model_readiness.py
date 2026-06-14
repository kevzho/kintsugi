"""Model-readiness diagnostics.

These checks are intentionally separate from integrity diagnostics. A dataset
can be clean CSV data while still being too small, too sparse, or too likely to
leak post-outcome information for reliable supervised learning.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Optional

import pandas as pd

from ..report import Finding, Severity
from .base import Engine


_TARGET_OUTCOME_RE = re.compile(
    r"(result|outcome|winner|rank|placement|churn|default|admitted|diagnosis)",
    re.IGNORECASE,
)
_POST_OUTCOME_FEATURE_RE = re.compile(
    r"(goals?|assists?|matches?_played|final_score|points?|total|"
    r"revenue_after|after_|post_|outcome_derived)",
    re.IGNORECASE,
)
_GENERIC_TOTAL_RE = re.compile(r"(^|_)total($|_)", re.IGNORECASE)


class ModelReadinessEngine(Engine):
    name = "model_readiness"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        n_rows = len(df)
        if n_rows == 0:
            return findings

        cols = schema.get("columns", {})
        dataset_type = schema.get("dataset_type", "unknown")
        target_provided = bool(schema.get("target_provided", target is not None))
        feature_cols = [c for c in df.columns if c != target]
        n_features = max(len(feature_cols), 1)
        rows_per_feature = n_rows / n_features

        if not target_provided:
            findings.append(
                Finding(
                    engine=self.name,
                    code="NO_TARGET_SUPERVISED_READINESS_NA",
                    severity=Severity.INFO,
                    title="No target column selected",
                    detail=(
                        "Supervised ML readiness requires a target column. Since no target was selected, "
                        "this report focuses on data integrity and likely dataset use cases."
                    ),
                    impact="Leakage, target support, class imbalance, and split feasibility are not scored until a target is selected.",
                    metrics={"readiness_applicability": "N/A", "possible_targets": schema.get("possible_targets", [])},
                    category="modeling_warning",
                )
            )

        sample_band = self._sample_size_finding(n_rows)
        if sample_band:
            findings.append(sample_band)

        rpf_finding = self._rows_per_feature_finding(rows_per_feature, n_rows, n_features)
        if rpf_finding:
            findings.append(rpf_finding)

        high_card_count = 0
        clustered_high_card: list[tuple[str, int, float]] = []
        for col in feature_cols:
            prof = cols.get(col, {})
            dtype = prof.get("dtype_inferred")
            if prof.get("is_id_like") or dtype not in ("categorical", "text", "id"):
                continue
            nunique = int(prof.get("n_unique", df[col].nunique(dropna=True)))
            unique_ratio = nunique / max(n_rows, 1)
            if unique_ratio < 0.5:
                continue
            high_card_count += 1
            if not target_provided and dataset_type == "historical_archive":
                clustered_high_card.append((str(col), nunique, unique_ratio))
                continue
            if unique_ratio >= 0.9:
                sev = Severity.HIGH
                penalty = 8.0
                cap = 50 if n_rows < 100 else None
            elif unique_ratio >= 0.7:
                sev = Severity.MEDIUM
                penalty = 5.0
                cap = None
            else:
                sev = Severity.LOW
                penalty = 2.0
                cap = None
            findings.append(
                Finding(
                    engine=self.name,
                    code="HIGH_CARDINALITY_GENERALIZATION",
                    severity=sev,
                    title=f"'{col}' is near-unique for this dataset",
                    detail=(
                        f"'{col}' has {nunique} unique values across {n_rows} rows "
                        f"(unique ratio {unique_ratio:.2f})."
                    ),
                    impact=(
                        "This feature is likely to cause memorization rather than "
                        "generalizable learning."
                    ),
                    column=col,
                    fix_snippet=(
                        "# Treat near-unique categories as identifiers or group rare levels after domain review\n"
                        f"# df = df.drop(columns=[{col!r}])"
                    ),
                    metrics={
                        "n_unique": nunique,
                        "n_rows": n_rows,
                        "unique_ratio": round(unique_ratio, 4),
                        "readiness_penalty": penalty,
                        **({"readiness_cap": cap} if cap is not None else {}),
                    },
                    category="modeling_warning",
                )
            )

        if clustered_high_card:
            columns = [c for c, _, _ in clustered_high_card]
            findings.append(
                Finding(
                    engine=self.name,
                    code="NEAR_UNIQUE_FEATURE_CLUSTER",
                    severity=Severity.LOW,
                    title="Near-unique feature cluster",
                    detail=(
                        "Several categorical fields are near-unique in this small archive: "
                        f"{', '.join(columns)}."
                    ),
                    impact=(
                        "These columns are useful for lookup, filtering, and historical comparison, "
                        "but they do not provide enough repeated examples for reliable supervised learning."
                    ),
                    metrics={"columns": columns, "readiness_penalty": 6.0},
                    category="modeling_warning",
                )
            )

        weak_target = False
        leakage_finding = None
        if target_provided and target and target in df.columns:
            weak_target = self._add_target_support_findings(df, schema, target, findings)
            leakage_finding = self._post_outcome_leakage_finding(df, target)
            if leakage_finding:
                findings.append(leakage_finding)

        purpose = self._dataset_purpose(
            n_rows=n_rows,
            rows_per_feature=rows_per_feature,
            high_card_count=high_card_count,
            weak_target=weak_target,
            leakage_high=bool(leakage_finding and leakage_finding.severity == Severity.HIGH),
        )
        if purpose != "Strong ML candidate":
            overall_cap = 60 if purpose == "Not suitable for supervised ML" else 70 if purpose == "EDA-only / visualization dataset" else None
            findings.append(
                Finding(
                    engine=self.name,
                    code="DATASET_PURPOSE_CLASSIFICATION",
                    severity=Severity.INFO if purpose == "Trainable with caution" else Severity.LOW,
                    title=f"Dataset purpose: {purpose}",
                    detail=f"Deterministic readiness checks classify this dataset as '{purpose}'.",
                    impact=(
                        "Use this label to separate data cleanliness from whether a model "
                        "can realistically learn and generalize."
                    ),
                    metrics={
                        "dataset_purpose": purpose,
                        **({"overall_cap": overall_cap} if overall_cap is not None else {}),
                    },
                    category="modeling_warning",
                )
            )

        return findings

    def _sample_size_finding(self, n_rows: int) -> Finding | None:
        if n_rows < 30:
            sev = Severity.CRITICAL
            penalty = 35.0
            cap = 40
            purpose_cap = "Not suitable for supervised ML"
        elif n_rows < 100:
            sev = Severity.HIGH
            penalty = 25.0
            cap = None
            purpose_cap = "Toy ML / demo only"
        elif n_rows < 500:
            sev = Severity.MEDIUM
            penalty = 12.0
            cap = None
            purpose_cap = "Trainable with caution"
        else:
            return None
        return Finding(
            engine=self.name,
            code="SMALL_SAMPLE_SIZE",
            severity=sev,
            title=f"Dataset has only {n_rows} rows",
            detail=(
                f"Dataset has only {n_rows} rows. This is too small for reliable "
                "supervised machine learning and is better suited for exploratory "
                "analysis unless more data is added."
            ),
            impact="Small samples make train/test splits noisy and generalization estimates unstable.",
            fix_snippet="# Add more rows before relying on supervised model validation.",
            metrics={
                "n_rows": n_rows,
                "readiness_penalty": penalty,
                "dataset_purpose_cap": purpose_cap,
                **({"readiness_cap": cap} if cap is not None else {}),
            },
            category="modeling_warning",
        )

    def _rows_per_feature_finding(self, rows_per_feature: float, n_rows: int, n_features: int) -> Finding | None:
        if rows_per_feature < 5:
            sev = Severity.HIGH
            penalty = 20.0
            cap = 55
        elif rows_per_feature < 10:
            sev = Severity.MEDIUM
            penalty = 10.0
            cap = None
        elif rows_per_feature < 20:
            sev = Severity.LOW
            penalty = 5.0
            cap = None
        else:
            return None
        return Finding(
            engine=self.name,
            code="LOW_ROWS_PER_FEATURE",
            severity=sev,
            title=f"Only {rows_per_feature:.1f} rows per feature",
            detail=(
                f"The dataset has only {rows_per_feature:.1f} rows per feature "
                f"({n_rows} rows over {n_features} candidate features)."
            ),
            impact="This increases overfitting risk and makes model evaluation unstable.",
            fix_snippet="# Add rows, remove weak features, or treat this as an EDA/toy-model dataset.",
            metrics={
                "rows_per_feature": round(rows_per_feature, 3),
                "n_rows": n_rows,
                "n_features": n_features,
                "readiness_penalty": penalty,
                **({"readiness_cap": cap} if cap is not None else {}),
            },
            category="modeling_warning",
        )

    def _add_target_support_findings(
        self,
        df: pd.DataFrame,
        schema: dict,
        target: str,
        findings: list[Finding],
    ) -> bool:
        prof = schema.get("columns", {}).get(target, {})
        dtype = prof.get("dtype_inferred")
        n_unique = int(prof.get("n_unique", df[target].nunique(dropna=True)))
        is_classification = dtype in ("categorical", "boolean", "id") or (
            dtype == "numeric" and 2 <= n_unique <= 20
        )
        if not is_classification or n_unique < 2:
            return False

        counts = df[target].value_counts(dropna=True)
        if counts.empty:
            return False
        min_count = int(counts.min())
        med_count = float(median([int(v) for v in counts.tolist()]))
        ratio = float(counts.max() / min_count) if min_count > 0 else float("inf")
        weak = False
        if min_count < 2:
            sev = Severity.CRITICAL
            penalty = 30.0
            cap = 45
            weak = True
        elif min_count < 5:
            sev = Severity.HIGH
            penalty = 20.0
            cap = None
            weak = True
        else:
            sev = None
            penalty = 0.0
            cap = None
        if sev:
            findings.append(
                Finding(
                    engine=self.name,
                    code="WEAK_CLASSIFICATION_TARGET_SUPPORT",
                    severity=sev,
                    title=f"Target '{target}' has weak class support",
                    detail=(
                        f"Target '{target}' has classes with very few examples "
                        f"(minimum class count {min_count}, median {med_count:.1f})."
                    ),
                    impact="Train/test splits may drop classes or produce meaningless validation scores.",
                    column=target,
                    fix_snippet="# Collect more examples per class or merge rare classes after domain review.",
                    metrics={
                        "n_classes": int(n_unique),
                        "min_class_count": min_count,
                        "median_class_count": med_count,
                        "class_imbalance_ratio": round(ratio, 3),
                        "readiness_penalty": penalty,
                        **({"readiness_cap": cap} if cap is not None else {}),
                    },
                    category="modeling_warning",
                )
            )
        if n_unique > len(df) / 10:
            findings.append(
                Finding(
                    engine=self.name,
                    code="TOO_MANY_TARGET_CLASSES",
                    severity=Severity.HIGH,
                    title=f"Target '{target}' has too many classes for the row count",
                    detail=f"Target '{target}' has {n_unique} classes across {len(df)} rows.",
                    impact="The effective sample per class is too small for reliable supervised learning.",
                    column=target,
                    fix_snippet="# Use more data, simplify the target, or treat this as descriptive analysis.",
                    metrics={
                        "n_classes": int(n_unique),
                        "n_rows": len(df),
                        "readiness_penalty": 15.0,
                    },
                    category="modeling_warning",
                )
            )
            weak = True
        return weak

    def _post_outcome_leakage_finding(self, df: pd.DataFrame, target: str) -> Finding | None:
        if not _TARGET_OUTCOME_RE.search(str(target)):
            return None
        suspicious = [
            c for c in df.columns
            if c != target and self._looks_post_outcome_feature(str(c), target)
        ]
        if not suspicious:
            return None
        sev = Severity.HIGH if len(suspicious) >= 3 else Severity.MEDIUM
        penalty = 25.0 if sev == Severity.HIGH else 15.0
        cap = 60 if sev == Severity.HIGH else None
        shown = ", ".join(str(c) for c in suspicious[:5])
        return Finding(
            engine=self.name,
            code="POST_OUTCOME_LEAKAGE_RISK",
            severity=sev,
            title="Possible post-outcome leakage",
            detail=(
                f"Some features may be measured after the target outcome is known. "
                f"If predicting {target}, columns such as {shown} may leak outcome information."
            ),
            impact="Post-outcome features can make validation scores look real while failing before the outcome exists.",
            fix_snippet="# Verify feature timing and drop post-outcome columns before training.",
            metrics={
                "target": target,
                "feature_columns": suspicious[:10],
                "readiness_penalty": penalty,
                **({"readiness_cap": cap} if cap is not None else {}),
            },
            category="modeling_warning",
        )

    def _looks_post_outcome_feature(self, column: str, target: str) -> bool:
        if not _POST_OUTCOME_FEATURE_RE.search(column):
            return False
        if (
            (_GENERIC_TOTAL_RE.search(column) or column.lower().startswith("total"))
            and re.search(r"(churn|default|admitted|diagnosis)", target, re.IGNORECASE)
        ):
            return False
        return True

    def _dataset_purpose(
        self,
        *,
        n_rows: int,
        rows_per_feature: float,
        high_card_count: int,
        weak_target: bool,
        leakage_high: bool,
    ) -> str:
        if n_rows < 30 or (n_rows < 50 and rows_per_feature < 5 and weak_target):
            return "Not suitable for supervised ML"
        if n_rows < 50 and (high_card_count > 0 or weak_target or rows_per_feature < 5):
            return "EDA-only / visualization dataset"
        if n_rows < 100 or (n_rows < 100 and high_card_count > 0):
            return "Toy ML / demo only"
        if n_rows < 500 or rows_per_feature < 20 or weak_target or leakage_high:
            return "Trainable with caution"
        return "Strong ML candidate"
