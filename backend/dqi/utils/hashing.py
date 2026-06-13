"""Deterministic fingerprint of an analysis for caching."""
from __future__ import annotations

import hashlib
import json


def fingerprint(schema: dict, finding_codes: list[str], shape: tuple[int, int] | None = None) -> str:
    cols = schema.get("columns", {})
    dtypes = sorted(f"{c}:{p.get('dtype_inferred')}" for c, p in cols.items())
    payload = {
        "dtypes": dtypes,
        "codes": sorted(finding_codes),
        "shape": list(shape) if shape else [len(cols), 0],
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
