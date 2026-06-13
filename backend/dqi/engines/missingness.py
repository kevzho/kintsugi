"""Missingness engine: per-column null rates + co-missing column groups."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine


def _severity_for_null_rate(rate: float) -> Optional[Severity]:
    if rate >= config.MISSING_CRITICAL:
        return Severity.CRITICAL
    if rate >= config.MISSING_HIGH:
        return Severity.HIGH
    if rate >= config.MISSING_MEDIUM:
        return Severity.MEDIUM
    return None


def _time_period_series(df: pd.DataFrame, schema: dict) -> Optional[tuple[str, pd.Series]]:
    cols = schema.get("columns", {})
    for col, prof in cols.items():
        name = str(col).lower()
        dtype = prof.get("dtype_inferred")
        if dtype == "datetime" or any(token in name for token in ("year", "date", "time", "period")):
            raw = df[col]
            if dtype == "datetime" or any(token in name for token in ("date", "time", "period")):
                parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
                if parsed.notna().sum() >= 10:
                    return col, parsed.dt.year.astype("float")
            numeric = pd.to_numeric(raw, errors="coerce")
            if numeric.notna().sum() >= 10 and numeric.nunique(dropna=True) >= 2:
                return col, numeric
    return None


class MissingnessEngine(Engine):
    name = "missingness"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        n = len(df)
        if n == 0:
            return findings

        for col in df.columns:
            rate = float(df[col].isna().mean())
            sev = _severity_for_null_rate(rate)
            if sev is None:
                continue
            pct = round(rate * 100, 1)
            if rate >= config.MISSING_CRITICAL:
                fix = f"# Mostly empty — usually safe to drop\ndf = df.drop(columns=[{col!r}])"
                impact = (
                    f"With {pct}% missing, '{col}' carries almost no signal; "
                    "imputing it fabricates data and most models will treat it as noise."
                )
            else:
                fix = (
                    f"# Impute (median for numeric, mode for categorical)\n"
                    f"df[{col!r}] = df[{col!r}].fillna(df[{col!r}].median())"
                )
                impact = (
                    f"{pct}% of '{col}' is missing; rows get silently dropped or "
                    "naively imputed, biasing the model if missingness is non-random."
                )
            findings.append(
                Finding(
                    engine=self.name,
                    code="MISSING_VALUES",
                    severity=sev,
                    title=f"Column '{col}' is {pct}% missing",
                    detail=f"{int(rate * n)} of {n} values are null in '{col}'.",
                    impact=impact,
                    column=col,
                    fix_snippet=fix,
                    metrics={"null_rate": round(rate, 4), "n_missing": int(rate * n)},
                )
            )

        # Missing values concentrated in a time period or historical regime.
        # This is distinct from random row-level missingness and should be
        # handled with time-aware imputation or regime flags.
        try:
            period = _time_period_series(df, schema)
            if period is not None:
                period_col, periods = period
                for col in df.columns:
                    if col == period_col:
                        continue
                    missing = df[col].isna()
                    n_missing = int(missing.sum())
                    if n_missing < 10:
                        continue
                    missing_periods = periods[missing & periods.notna()]
                    if missing_periods.empty:
                        continue
                    shares = missing_periods.value_counts(normalize=True)
                    top_period = shares.index[0]
                    top_share = float(shares.iloc[0])
                    if top_share >= config.STRUCTURAL_MISSINGNESS_TIME_CONCENTRATION:
                        findings.append(
                            Finding(
                                engine=self.name,
                                code="STRUCTURAL_MISSINGNESS_TIME_REGIME",
                                severity=Severity.MEDIUM,
                                title=f"'{col}' is mostly missing in one time period",
                                detail=(
                                    f"{top_share*100:.1f}% of missing '{col}' values occur where "
                                    f"'{period_col}' is {top_period:g}."
                                ),
                                impact=(
                                    "This looks like historical or regime-based missingness, not random noise. "
                                    "Use a period flag or time-aware imputation so the model can learn the gap."
                                ),
                                column=col,
                                fix_snippet=(
                                    f"df[{(str(col) + '_missing')!r}] = df[{col!r}].isna().astype(int)\n"
                                    f"# Impute within {period_col!r} groups after reviewing the historical gap"
                                ),
                                metrics={
                                    "period_column": period_col,
                                    "period": float(top_period),
                                    "missing_share_in_period": round(top_share, 3),
                                },
                            )
                        )
        except Exception:
            pass

        # Co-missing groups: correlated isna() masks (structural missingness).
        try:
            cols_with_nulls = [c for c in df.columns if 0 < df[c].isna().mean() < 1]
            if len(cols_with_nulls) >= 2:
                mask = df[cols_with_nulls].isna().astype(int)
                corr = mask.corr()
                seen: set[frozenset[str]] = set()
                for i, a in enumerate(cols_with_nulls):
                    for b in cols_with_nulls[i + 1 :]:
                        val = corr.loc[a, b]
                        if pd.notna(val) and val >= config.COMISSING_CORR:
                            pair = frozenset((a, b))
                            if pair in seen:
                                continue
                            seen.add(pair)
                            findings.append(
                                Finding(
                                    engine=self.name,
                                    code="CO_MISSING_GROUP",
                                    severity=Severity.MEDIUM,
                                    title=f"'{a}' and '{b}' go missing together",
                                    detail=(
                                        f"isna() masks of '{a}' and '{b}' correlate at "
                                        f"{val:.2f} — they are missing in the same rows."
                                    ),
                                    impact=(
                                        "Structural (non-random) missingness like this leaks "
                                        "information and breaks naive imputation; the missingness "
                                        "pattern itself may be predictive."
                                    ),
                                    column=a,
                                    fix_snippet=(
                                        f"# Encode the shared missingness as a feature\n"
                                        f"df['{a}_missing'] = df[{a!r}].isna().astype(int)"
                                    ),
                                    metrics={"comissing_corr": round(float(val), 3), "with": b},
                                )
                            )
        except Exception:
            pass

        return findings
