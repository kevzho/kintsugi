"""Correlation engine: numeric Pearson matrix + strongly-correlated pairs.
Ships the full matrix in metrics for the frontend heatmap.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine

_MAX_HEATMAP_COLS = 30


class CorrelationEngine(Engine):
    name = "correlation"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        cols = schema.get("columns", {})
        dataset_type = schema.get("dataset_type", "unknown")
        target_provided = bool(schema.get("target_provided", target is not None))
        num_cols = [
            c for c, p in cols.items()
            if p.get("dtype_inferred") == "numeric" and not p.get("is_id_like")
        ]
        if len(num_cols) < 2:
            return findings

        num_cols = num_cols[:_MAX_HEATMAP_COLS]
        num_df = df[num_cols].apply(pd.to_numeric, errors="coerce")
        corr = num_df.corr(method="pearson")

        labels = list(corr.columns)
        matrix = [[round(float(v) if pd.notna(v) else 0.0, 3) for v in row] for row in corr.to_numpy()]

        # One INFO finding carrying the full matrix for the heatmap.
        findings.append(
            Finding(
                engine=self.name,
                code="CORRELATION_MATRIX",
                severity=Severity.INFO,
                title=f"Correlation matrix over {len(labels)} numeric columns",
                detail="Pearson correlation across numeric features (for the heatmap).",
                impact="Use this to spot redundant or collinear features at a glance.",
                column=None,
                fix_snippet=None,
                metrics={"matrix": matrix, "labels": labels},
                category="modeling_warning",
            )
        )

        # Strongly-correlated pairs -> redundancy findings.
        seen: set[frozenset[str]] = set()
        for i, a in enumerate(labels):
            for j in range(i + 1, len(labels)):
                b = labels[j]
                val = abs(matrix[i][j])
                if val >= config.STRONG_CORR:
                    pair = frozenset((a, b))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    if dataset_type == "historical_archive" and not target_provided:
                        sev = Severity.INFO
                    else:
                        sev = Severity.MEDIUM if val >= config.NEAR_DUPLICATE_CORR else Severity.INFO
                    impact = (
                        "This appears to be a historical trend or archive structure. It is useful context for EDA, not a data-integrity failure."
                        if dataset_type == "historical_archive" and not target_provided
                        else (
                            "Collinear features inflate variance of linear-model coefficients "
                            "and add little independent signal; consider dropping one."
                        )
                    )
                    findings.append(
                        Finding(
                            engine=self.name,
                            code="STRONG_CORRELATION_PAIR",
                            severity=sev,
                            title=f"'{a}' and '{b}' are strongly correlated (|r|={val:.2f})",
                            detail=f"Pearson |r|={val:.3f} between '{a}' and '{b}'.",
                            impact=impact,
                            column=a,
                            fix_snippet=None if dataset_type == "historical_archive" and not target_provided else f"df = df.drop(columns=[{b!r}])  # keep one of the pair",
                            metrics={"corr": round(val, 4), "with": b},
                            category="modeling_warning",
                        )
                    )
        return findings
