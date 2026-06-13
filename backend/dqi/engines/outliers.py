"""Outliers engine: IQR rule + robust z-score (median/MAD) on numeric columns."""
from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine

_HEAVY_TAIL_RE = re.compile(config.HEAVY_TAIL_FIELD_PATTERN, re.IGNORECASE)


def _numeric_series(df: pd.DataFrame, col: str, profile: dict) -> Optional[pd.Series]:
    if profile.get("dtype_inferred") != "numeric":
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return s if len(s) >= 10 else None


def _looks_network_heavy_tail(col: str) -> bool:
    name = re.sub(r"[^a-z0-9]+", "_", str(col).lower())
    return bool(_HEAVY_TAIL_RE.search(name))


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

            network_heavy_tail = _looks_network_heavy_tail(col)
            sev = Severity.MEDIUM if rate >= config.OUTLIER_HIGH_RATE else Severity.LOW
            pct = round(rate * 100, 1)
            title = f"'{col}' is highly heavy-tailed" if network_heavy_tail else f"'{col}' has a heavy tail"
            detail = (
                f"{n_outliers} of {n} values ({pct}%) fall outside the IQR fence or "
                f"robust z>|{config.OUTLIER_Z}| (median={median:.3g})."
            )
            impact = (
                "This may affect distance-based or gradient-based models, but may also "
                "contain useful signal for attack detection."
                if network_heavy_tail
                else (
                    "Extreme values can dominate distance-based or gradient-based models "
                    "and can distort scaling. They may still be real signal."
                )
            )
            findings.append(
                Finding(
                    engine=self.name,
                    code="HEAVY_TAILED_NUMERIC" if network_heavy_tail else "OUTLIERS",
                    severity=sev,
                    title=title,
                    detail=detail,
                    impact=impact,
                    column=col,
                    fix_snippet=(
                        f"# Review distribution before changing values\n"
                        f"# Do not blindly remove these rows\n"
                        f"df[{col!r}] = np.log1p(df[{col!r}].clip(lower=0))\n"
                        f"# Alternative: RobustScaler, domain-reviewed winsorization, or tree-based models"
                    ),
                    metrics={
                        "outlier_rate": round(rate, 4),
                        "n_outliers": n_outliers,
                        "modeling_warning": True,
                        "heavy_tailed": True,
                    },
                    category="modeling_warning",
                )
            )
        return findings
