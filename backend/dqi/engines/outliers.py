"""Outliers engine: IQR rule + robust z-score (median/MAD) on numeric columns."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine


def _numeric_series(df: pd.DataFrame, col: str, profile: dict) -> Optional[pd.Series]:
    if profile.get("dtype_inferred") != "numeric":
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return s if len(s) >= 10 else None


class OutliersEngine(Engine):
    name = "outliers"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        cols = schema.get("columns", {})

        for col, prof in cols.items():
            if prof.get("is_id_like"):
                continue
            s = _numeric_series(df, col, prof)
            if s is None:
                continue
            n = len(s)

            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lo, hi = q1 - config.OUTLIER_IQR_K * iqr, q3 + config.OUTLIER_IQR_K * iqr
                iqr_mask = (s < lo) | (s > hi)
            else:
                iqr_mask = pd.Series(False, index=s.index)

            median = s.median()
            mad = (s - median).abs().median()
            if mad > 0:
                robust_z = 0.6745 * (s - median) / mad
                z_mask = robust_z.abs() > config.OUTLIER_Z
            else:
                z_mask = pd.Series(False, index=s.index)

            outlier_mask = iqr_mask | z_mask
            n_outliers = int(outlier_mask.sum())
            rate = n_outliers / n if n else 0.0
            if rate < config.OUTLIER_MEDIUM_RATE:
                continue

            sev = Severity.HIGH if rate >= config.OUTLIER_HIGH_RATE else Severity.MEDIUM
            pct = round(rate * 100, 1)
            findings.append(
                Finding(
                    engine=self.name,
                    code="OUTLIERS",
                    severity=sev,
                    title=f"'{col}' has {pct}% outliers",
                    detail=(
                        f"{n_outliers} of {n} values fall outside the IQR fence or "
                        f"robust z>|{config.OUTLIER_Z}| (median={median:.3g})."
                    ),
                    impact=(
                        "Extreme values dominate distance/gradient-based models and distort "
                        "scaling; left unhandled they can swamp the loss and hurt convergence."
                    ),
                    column=col,
                    fix_snippet=(
                        f"# Winsorize, or use a robust scaler\n"
                        f"lo, hi = df[{col!r}].quantile([0.01, 0.99])\n"
                        f"df[{col!r}] = df[{col!r}].clip(lo, hi)"
                    ),
                    metrics={"outlier_rate": round(rate, 4), "n_outliers": n_outliers},
                )
            )
        return findings
