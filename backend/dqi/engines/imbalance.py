"""Imbalance engine: class proportions of a categorical target."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine


class ImbalanceEngine(Engine):
    name = "imbalance"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        if not target or target not in df.columns:
            return findings

        prof = schema.get("columns", {}).get(target, {})
        dtype = prof.get("dtype_inferred")
        n_unique = prof.get("n_unique", 0)
        # Only meaningful for categorical / boolean / low-cardinality targets.
        if dtype not in ("categorical", "boolean", "id") and not (
            dtype == "numeric" and n_unique <= 20
        ):
            return findings
        if n_unique < 2 or n_unique > 50:
            return findings

        counts = df[target].value_counts(dropna=True)
        total = int(counts.sum())
        if total == 0:
            return findings
        proportions = {str(k): round(v / total, 4) for k, v in counts.items()}
        ratio = float(counts.max() / counts.min()) if counts.min() > 0 else float("inf")

        if ratio >= config.IMBALANCE_CRITICAL_RATIO:
            sev = Severity.CRITICAL
        elif ratio >= config.IMBALANCE_HIGH_RATIO:
            sev = Severity.HIGH
        else:
            return findings

        minority = str(counts.idxmin())
        minority_pct = round(counts.min() / total * 100, 2)
        findings.append(
            Finding(
                engine=self.name,
                code="CLASS_IMBALANCE",
                severity=sev,
                title=f"Target '{target}' is imbalanced ({ratio:.0f}:1)",
                detail=(
                    f"Majority/minority ratio is {ratio:.1f}. Smallest class "
                    f"'{minority}' is only {minority_pct}% of rows."
                ),
                impact=(
                    "A model can score high accuracy by always predicting the majority "
                    "class while being useless on the minority. Use PR-AUC/F1, not accuracy, "
                    "and rebalance."
                ),
                column=target,
                fix_snippet=(
                    "# Stratify the split and weight the classes\n"
                    "from sklearn.model_selection import train_test_split\n"
                    f"X_tr, X_te, y_tr, y_te = train_test_split(X, y, stratify=y, random_state=42)\n"
                    "# model = LogisticRegression(class_weight='balanced')"
                ),
                metrics={"class_proportions": proportions, "ratio": round(ratio, 2)},
            )
        )
        return findings
