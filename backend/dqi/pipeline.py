"""End-to-end analysis pipeline: parse -> sample -> profile -> engines -> score
-> fingerprint -> AI summary. Engines run via safe_run so none can crash the run.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Optional

import pandas as pd

from . import config
from .ai import summarizer
from .engines import ALL_ENGINES
from .meta import classify_columns, classify_dataset
from .report import Report
from .schema import infer_schema
from .scoring import score_report
from .utils.hashing import fingerprint
from .utils.sampling import maybe_sample

logger = logging.getLogger("dqi")

_TARGET_NAME_RE = re.compile(
    r"^(target|label|y|class|outcome|churn|churned|converted|default|defaulted|"
    r"fraud|is_fraud|response|click|clicked)$",
    re.IGNORECASE,
)


def _infer_target(df: pd.DataFrame, schema: dict) -> Optional[str]:
    """Best-effort target guess when the caller didn't specify one.

    Prefers a low-cardinality column whose name looks like a label. This keeps
    the zero-config headless path meaningful (e.g. detecting leakage) without
    forcing the user to name a target.
    """
    cols = schema.get("columns", {})

    def is_label_like(col: str) -> bool:
        p = cols.get(col, {})
        if p.get("is_id_like") or p.get("is_constant"):
            return False
        dtype = p.get("dtype_inferred")
        n_unique = p.get("n_unique", 0)
        return dtype in ("boolean", "categorical") or (dtype == "numeric" and 2 <= n_unique <= 20)

    # 1) name match, scanning right-to-left (targets are usually the last column).
    for col in reversed(list(df.columns)):
        if _TARGET_NAME_RE.match(str(col)) and is_label_like(col):
            return col
    # 2) otherwise the last label-like column.
    for col in reversed(list(df.columns)):
        if is_label_like(col):
            return col
    return None


def analyze(df: pd.DataFrame, dataset_name: str, target: Optional[str] = None) -> Report:
    n_rows = len(df)
    n_cols = df.shape[1]

    if target and target not in df.columns:
        target = None  # ignore an invalid target rather than failing

    work, sampled = maybe_sample(df)
    schema = infer_schema(work)

    if target is None:
        target = _infer_target(work, schema)
        if target:
            logger.info("auto-detected target column: %s", target)

    column_roles = classify_columns(work, schema, target)
    for col, role in column_roles.items():
        if col in schema.get("columns", {}):
            schema["columns"][col]["column_role"] = role
    dataset_type = classify_dataset(work, schema, target)
    schema["dataset_type"] = dataset_type

    findings = []
    for engine in ALL_ENGINES:
        findings.extend(engine.safe_run(work, schema, target))

    scores = score_report(findings, n_rows=len(work), sampled=sampled)
    fp = fingerprint(schema, [f.code for f in findings], shape=(n_rows, n_cols))

    report = Report(
        dataset_name=dataset_name,
        n_rows=n_rows,
        n_cols=n_cols,
        n_rows_analyzed=len(work),
        sampled=sampled,
        target_column=target,
        health_score=scores.overall_score,
        grade=scores.overall_grade,
        integrity_score=scores.integrity_score,
        integrity_grade=scores.integrity_grade,
        readiness_score=scores.readiness_score,
        readiness_grade=scores.readiness_grade,
        overall_score=scores.overall_score,
        overall_grade=scores.overall_grade,
        verdict=scores.verdict,
        integrity_confidence=scores.integrity_confidence,
        integrity_confidence_reason=scores.integrity_confidence_reason,
        readiness_confidence=scores.readiness_confidence,
        readiness_confidence_reason=scores.readiness_confidence_reason,
        overall_confidence=scores.overall_confidence,
        overall_confidence_reason=scores.overall_confidence_reason,
        dataset_type=dataset_type,
        dataset_purpose=scores.dataset_purpose,
        findings=findings,
        modeling_warnings=[f for f in findings if f.category == "modeling_warning"],
        schema=schema,
        fingerprint=fp,
        severity_counts=scores.severity_counts,
    )

    try:
        exec_summary, recommendations, ai_available = summarizer.summarize(report)
    except Exception as exc:  # defensive: summarizer already degrades, but never crash analysis
        logger.warning("summarizer failed hard: %s", type(exc).__name__)
        exec_summary, recommendations, ai_available = "", [], False
    report.exec_summary = exec_summary
    report.recommendations = recommendations
    report.ai_available = ai_available

    logger.info(
        "analyzed name=%s rows=%d cols=%d score=%s grade=%s findings=%d",
        dataset_name, n_rows, n_cols, scores.overall_score, scores.overall_grade, len(findings),
    )
    return report


def analyze_csv_bytes(raw: bytes, name: str, target: Optional[str] = None) -> Report:
    if not raw:
        raise ValueError("Uploaded file is empty.")
    if len(raw) > config.MAX_FILE_BYTES:
        mb = config.MAX_FILE_BYTES / (1024 * 1024)
        raise ValueError(f"File too large. Limit is {mb:.0f} MB.")

    df = None
    last_err: Optional[Exception] = None
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=encoding)
            break
        except Exception as exc:
            last_err = exc
    if df is None:
        raise ValueError(f"Could not parse CSV: {last_err}")

    if df.shape[1] == 0:
        raise ValueError("CSV has no columns.")
    if df.shape[1] > config.MAX_COLS:
        raise ValueError(
            f"Too many columns ({df.shape[1]}). Limit is {config.MAX_COLS}."
        )
    if len(df) == 0:
        raise ValueError("CSV has no data rows.")

    return analyze(df, name, target)
