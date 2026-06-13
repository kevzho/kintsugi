"""Schema inference: profile each column so engines can reason about types
without re-deriving everything. Pure pandas/numpy — no web framework imports.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import config


def _stringify_samples(series: pd.Series, k: int = 3) -> list[str]:
    vals = series.dropna().unique()[:k]
    out = []
    for v in vals:
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        out.append(s)
    return out


def _looks_numeric_string(series: pd.Series) -> bool:
    """Object column whose values are actually parseable as numbers."""
    sample = series.dropna().head(200)
    if sample.empty:
        return False
    coerced = pd.to_numeric(sample, errors="coerce")
    return coerced.notna().mean() >= 0.9


def _looks_datetime(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return parsed.notna().mean() >= 0.9


def _looks_boolean(series: pd.Series) -> bool:
    uniq = set(str(v).strip().lower() for v in series.dropna().unique())
    if not uniq:
        return False
    bool_sets = [
        {"true", "false"},
        {"0", "1"},
        {"yes", "no"},
        {"y", "n"},
        {"t", "f"},
    ]
    return uniq <= max(bool_sets, key=lambda s: len(uniq & s)) and len(uniq) <= 2 and any(uniq <= b for b in bool_sets)


def _infer_dtype(series: pd.Series, n_unique: int, n_total: int) -> str:
    """Return one of: numeric, categorical, datetime, boolean, text, id."""
    non_null = series.dropna()
    if non_null.empty:
        return "categorical"

    # boolean check first (2 distinct meaningful values)
    if n_unique <= 2 and _looks_boolean(series):
        return "boolean"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        # integer near-unique -> id
        ratio = n_unique / max(n_total, 1)
        if ratio >= config.ID_CARDINALITY_RATIO and pd.api.types.is_integer_dtype(series):
            return "id"
        return "numeric"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    # object/string: probe for numeric-stored-as-string, datetime, id, text
    if _looks_numeric_string(series):
        return "numeric"
    if _looks_datetime(series):
        return "datetime"

    ratio = n_unique / max(n_total, 1)
    if ratio >= config.ID_CARDINALITY_RATIO:
        return "id"

    # long free text vs categorical
    avg_len = non_null.astype(str).str.len().mean()
    if avg_len is not None and avg_len > 40 and ratio > 0.5:
        return "text"
    return "categorical"


def infer_schema(df: pd.DataFrame) -> dict[str, Any]:
    n_total = len(df)
    columns: dict[str, Any] = {}
    n_numeric = n_categorical = n_datetime = n_id_like = 0

    for col in df.columns:
        series = df[col]
        n_unique = int(series.nunique(dropna=True))
        null_rate = float(series.isna().mean()) if n_total else 0.0
        cardinality_ratio = float(n_unique / n_total) if n_total else 0.0
        dtype_inferred = _infer_dtype(series, n_unique, n_total)

        # id-like = near-unique AND not a continuous float (floats are rarely true ids).
        is_float_continuous = (
            dtype_inferred == "numeric"
            and pd.api.types.is_float_dtype(pd.to_numeric(series, errors="coerce"))
        )
        is_id_like = dtype_inferred == "id" or (
            cardinality_ratio >= config.ID_CARDINALITY_RATIO and not is_float_continuous
        )
        is_high_cardinality = (
            dtype_inferred in ("categorical", "text")
            and (
                n_unique >= config.HIGH_CARDINALITY_ABS
                or cardinality_ratio >= config.HIGH_CARDINALITY_RATIO
            )
        )
        is_constant = n_unique <= 1

        profile = {
            "dtype_inferred": dtype_inferred,
            "n_unique": n_unique,
            "cardinality_ratio": round(cardinality_ratio, 4),
            "null_rate": round(null_rate, 4),
            "sample_values": _stringify_samples(series),
            "is_id_like": bool(is_id_like),
            "is_high_cardinality": bool(is_high_cardinality),
            "is_constant": bool(is_constant),
        }
        columns[col] = profile

        if dtype_inferred == "numeric":
            n_numeric += 1
        elif dtype_inferred in ("categorical", "text", "boolean"):
            n_categorical += 1
        elif dtype_inferred == "datetime":
            n_datetime += 1
        if is_id_like:
            n_id_like += 1

    return {
        "columns": columns,
        "n_numeric": n_numeric,
        "n_categorical": n_categorical,
        "n_datetime": n_datetime,
        "n_id_like": n_id_like,
    }
