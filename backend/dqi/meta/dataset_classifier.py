"""Dataset type classifier with deterministic heuristic fallback."""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd


def _has(cols: list[str], pattern: str) -> bool:
    return any(re.search(pattern, c, re.IGNORECASE) for c in cols)


def classify_dataset(df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> str:
    cols = [str(c) for c in df.columns]
    lower = [c.lower() for c in cols]
    n = max(len(cols), 1)
    n_numeric = schema.get("n_numeric", 0)
    percent_numeric = n_numeric / n

    has_year = _has(lower, r"(^year$|_year$|year_)")
    has_date = _has(lower, r"(date|time|timestamp|period)")
    has_location = _has(lower, r"(state|county|city|location|country|region)")

    if _has(lower, r"(src_?bytes|dst_?bytes|packet|protocol|failed_?login|attack|payload|traffic)"):
        return "network_logs"
    if has_year and has_location:
        return "panel_data"
    if has_date and percent_numeric >= 0.5:
        return "time_series"
    if _has(lower, r"(customer|contract|tenure|charges|churn|subscription)"):
        return "business_tabular"
    if _has(lower, r"(price|kms?_driven|fuel|seller|company|brand|model)"):
        return "ecommerce"
    if _has(lower, r"(survey|response|question|rating|satisfaction)"):
        return "survey"
    if percent_numeric >= 0.75:
        return "scientific_measurements"
    return "unknown"
