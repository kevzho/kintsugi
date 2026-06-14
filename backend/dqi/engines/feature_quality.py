"""Feature quality engine: constant/quasi-constant, high-cardinality categoricals,
near-duplicate numeric columns, mixed-type columns, numeric-stored-as-string.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine


class FeatureQualityEngine(Engine):
    name = "feature_quality"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        cols = schema.get("columns", {})
        dataset_type = schema.get("dataset_type", "unknown")
        target_provided = bool(schema.get("target_provided", target is not None))
        n = len(df)
        if n == 0:
            return findings

        for col, prof in cols.items():
            if col == target:
                continue
            dtype = prof.get("dtype_inferred")

            # Constant / quasi-constant. Skip near-empty columns — that's a
            # missingness story, not a variance story (avoid double-penalizing).
            if prof.get("null_rate", 0.0) >= config.MISSING_HIGH:
                continue
            if prof.get("is_constant"):
                findings.append(
                    Finding(
                        engine=self.name,
                        code="CONSTANT_COLUMN",
                        severity=Severity.MEDIUM,
                        title=f"'{col}' is constant",
                        detail=f"'{col}' has a single distinct value across all rows.",
                        impact="Zero variance — carries no information and just adds noise/compute.",
                        column=col,
                        fix_snippet=f"df = df.drop(columns=[{col!r}])",
                        metrics={"n_unique": prof.get("n_unique", 0)},
                    )
                )
                continue
            else:
                try:
                    top_share = float(df[col].value_counts(normalize=True, dropna=False).iloc[0])
                    if top_share >= config.NEAR_ZERO_VARIANCE_RATIO and prof.get("n_unique", 0) > 1:
                        findings.append(
                            Finding(
                                engine=self.name,
                                code="QUASI_CONSTANT_COLUMN",
                                severity=Severity.LOW,
                                title=f"'{col}' is quasi-constant ({top_share*100:.1f}% one value)",
                                detail=f"A single value covers {top_share*100:.1f}% of '{col}'.",
                                impact="Near-zero variance contributes almost nothing and can destabilize scaling.",
                                column=col,
                                fix_snippet=f"# Drop near-zero-variance feature\ndf = df.drop(columns=[{col!r}])",
                                metrics={"top_value_share": round(top_share, 4)},
                            )
                        )
                except Exception:
                    pass

            # High-cardinality categoricals.
            if dtype in ("categorical", "text") and prof.get("is_high_cardinality") and not prof.get("is_id_like"):
                if dataset_type == "historical_archive" and not target_provided:
                    continue
                findings.append(
                    Finding(
                        engine=self.name,
                        code="HIGH_CARDINALITY_CATEGORICAL",
                        severity=Severity.LOW,
                        title=f"'{col}' is a high-cardinality categorical ({prof.get('n_unique')} values)",
                        detail=f"'{col}' has {prof.get('n_unique')} distinct categories.",
                        impact=(
                            "One-hot encoding explodes dimensionality and sparsifies the data; "
                            "consider target/hashing encoding or grouping rare levels."
                        ),
                        column=col,
                        fix_snippet=(
                            f"# Group rare levels\n"
                            f"top = df[{col!r}].value_counts().nlargest(20).index\n"
                            f"df[{col!r}] = df[{col!r}].where(df[{col!r}].isin(top), 'other')"
                        ),
                        metrics={"n_unique": prof.get("n_unique", 0)},
                        category="modeling_warning",
                    )
                )

            # Numeric stored as string.
            if dtype == "numeric" and df[col].dtype == object:
                findings.append(
                    Finding(
                        engine=self.name,
                        code="NUMERIC_STORED_AS_STRING",
                        severity=Severity.MEDIUM,
                        title=f"'{col}' is numeric but stored as text",
                        detail=f"'{col}' parses as numbers yet has an object dtype.",
                        impact="String-typed numbers won't be scaled or compared correctly and break most models.",
                        column=col,
                        fix_snippet=f"df[{col!r}] = pd.to_numeric(df[{col!r}], errors='coerce')",
                        metrics={},
                    )
                )

            # Mixed-type object column (numbers + non-numbers interleaved).
            if df[col].dtype == object and dtype not in ("numeric",):
                try:
                    sample = df[col].dropna().head(500)
                    if len(sample) >= 20:
                        as_num = pd.to_numeric(sample, errors="coerce").notna().mean()
                        cleaned = sample.astype(str).str.replace(r"[^0-9.\-]+", "", regex=True)
                        cleaned = cleaned.mask(cleaned == "")
                        as_clean_num = pd.to_numeric(cleaned, errors="coerce").notna().mean()
                        numericish_name = prof.get("name_kind") == "measurement" or prof.get("column_role") == "measurement"
                        if numericish_name and as_clean_num >= 0.5 and as_clean_num > as_num + 0.2:
                            invalid_rate = 1.0 - float(as_clean_num)
                            findings.append(
                                Finding(
                                    engine=self.name,
                                    code="MESSY_NUMERIC_TEXT",
                                    severity=Severity.HIGH if invalid_rate >= 0.10 else Severity.MEDIUM,
                                    title=f"'{col}' contains messy numeric text",
                                    detail=(
                                        f"Raw numeric parse rate is {as_num*100:.0f}%, but {as_clean_num*100:.0f}% "
                                        "parses after removing units, commas, or currency text."
                                    ),
                                    impact=(
                                        "Models cannot compare or scale this column reliably until units and invalid "
                                        "tokens are cleaned."
                                    ),
                                    column=col,
                                    fix_snippet=(
                                        f"df[{col!r}] = pd.to_numeric(\n"
                                        f"    df[{col!r}].astype(str).str.replace(r'[^0-9.\\-]+', '', regex=True),\n"
                                        f"    errors='coerce'\n"
                                        f")"
                                    ),
                                    metrics={
                                        "raw_numeric_parse_rate": round(float(as_num), 3),
                                        "cleaned_numeric_parse_rate": round(float(as_clean_num), 3),
                                    },
                                )
                            )
                            continue
                        if 0.1 < as_num < 0.9:
                            findings.append(
                                Finding(
                                    engine=self.name,
                                    code="MIXED_TYPE_COLUMN",
                                    severity=Severity.MEDIUM,
                                    title=f"'{col}' mixes numeric and non-numeric values",
                                    detail=f"~{as_num*100:.0f}% of '{col}' parses as numeric, the rest does not.",
                                    impact="Mixed types force everything to string and silently corrupt feature encoding.",
                                    column=col,
                                    fix_snippet=(
                                        f"# Decide on a type; coerce the rest to NaN\n"
                                        f"df[{col!r}] = pd.to_numeric(df[{col!r}], errors='coerce')"
                                    ),
                                    metrics={"numeric_parse_rate": round(float(as_num), 3)},
                                )
                            )
                except Exception:
                    pass

        # Near-duplicate numeric columns (|corr| > NEAR_DUPLICATE_CORR).
        try:
            num_cols = [
                c for c, p in cols.items()
                if p.get("dtype_inferred") == "numeric" and not p.get("is_id_like") and c != target
            ]
            if len(num_cols) >= 2:
                num_df = df[num_cols].apply(pd.to_numeric, errors="coerce")
                corr = num_df.corr().abs()
                seen: set[frozenset[str]] = set()
                for i, a in enumerate(num_cols):
                    for b in num_cols[i + 1 :]:
                        val = corr.loc[a, b]
                        if pd.notna(val) and val >= config.NEAR_DUPLICATE_CORR:
                            pair = frozenset((a, b))
                            if pair in seen:
                                continue
                            seen.add(pair)
                            findings.append(
                                Finding(
                                    engine=self.name,
                                    code="NEAR_DUPLICATE_COLUMNS",
                                    severity=Severity.LOW,
                                    title=f"'{a}' and '{b}' are near-duplicates (|corr|={val:.3f})",
                                    detail=f"'{a}' and '{b}' are almost perfectly correlated.",
                                    impact="Redundant features waste capacity and destabilize linear-model coefficients (collinearity).",
                                    column=a,
                                    fix_snippet=f"df = df.drop(columns=[{b!r}])",
                                    metrics={"corr": round(float(val), 4), "with": b},
                                    category="modeling_warning",
                                )
                            )
        except Exception:
            pass

        return findings
