"""Column role classifier.

This module deliberately keeps scoring deterministic. If a trained model is
added later it may predict context labels, but numeric scores remain rule-based.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def _targetish(name: str) -> bool:
    tokens = ("target", "label", "class", "outcome", "churn", "default", "attack", "fraud")
    return any(t in name for t in tokens)


def _role_for(col: str, profile: dict, target: Optional[str]) -> str:
    name = str(col).lower()
    dtype = profile.get("dtype_inferred")
    name_kind = profile.get("name_kind")
    n_unique = profile.get("n_unique", 0)

    if target and col == target:
        return "target"
    if name_kind == "identifier":
        return "identifier"
    if dtype == "datetime" or any(t in name for t in ("date", "time", "timestamp", "year", "period")):
        return "timestamp"
    if dtype == "boolean" or (dtype == "numeric" and n_unique <= 2):
        return "binary_flag" if not _targetish(name) else "target"
    if name_kind == "measurement" or dtype == "numeric":
        return "measurement"
    if dtype == "text":
        return "text"
    if any(t in name for t in ("score", "ratio", "per_", "pct", "percent", "log_")):
        return "derived_feature"
    return "categorical"


def classify_columns(df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> dict[str, str]:
    cols = schema.get("columns", {})
    return {col: _role_for(col, profile, target) for col, profile in cols.items()}
