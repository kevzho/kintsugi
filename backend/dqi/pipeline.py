"""End-to-end analysis pipeline.

Parse, sample, profile, run diagnostics, score, fingerprint, and summarize.
Engines run through safe_run so a single check cannot interrupt analysis.
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
    r"^(target|label|y|class|outcome|result|churn|churned|converted|default|defaulted|"
    r"fraud|is_fraud|response|click|clicked|winner|champion)$",
    re.IGNORECASE,
)


def _possible_targets(df: pd.DataFrame, schema: dict, dataset_type: str = "unknown") -> list[str]:
    """Suggest likely targets without selecting one for the user."""
    if dataset_type == "fixture_schedule":
        return []
    cols = schema.get("columns", {})

    def is_label_like(col: str) -> bool:
        p = cols.get(col, {})
        if p.get("is_id_like") or p.get("is_constant"):
            return False
        dtype = p.get("dtype_inferred")
        n_unique = p.get("n_unique", 0)
        if n_unique < 2:
            return False
        return dtype in ("boolean", "categorical") or (dtype == "numeric" and 2 <= n_unique <= 20)

    suggestions: list[str] = []
    for col in reversed(list(df.columns)):
        if _TARGET_NAME_RE.match(str(col)) and is_label_like(col):
            suggestions.append(str(col))
    if dataset_type == "historical_archive":
        return suggestions[:4]
    for col in reversed(list(df.columns)):
        if str(col) not in suggestions and is_label_like(col):
            suggestions.append(str(col))
    return suggestions[:6]


def analyze(df: pd.DataFrame, dataset_name: str, target: Optional[str] = None) -> Report:
    n_rows = len(df)
    n_cols = df.shape[1]

    if target and target not in df.columns:
        target = None  # ignore an invalid target rather than failing
    target_provided = target is not None

    work, sampled = maybe_sample(df)
    schema = infer_schema(work)
    dataset_type = classify_dataset(work, schema, target)
    possible_targets = _possible_targets(work, schema, dataset_type) if target is None else []

    column_roles = classify_columns(work, schema, target)
    for col, role in column_roles.items():
        if col in schema.get("columns", {}):
            schema["columns"][col]["column_role"] = role
    schema["dataset_type"] = dataset_type
    schema["target_provided"] = target_provided
    schema["possible_targets"] = possible_targets

    findings = []
    for engine in ALL_ENGINES:
        findings.extend(engine.safe_run(work, schema, target))

    scores = score_report(
        findings,
        n_rows=len(work),
        sampled=sampled,
        dataset_type=dataset_type,
        target_provided=target_provided,
    )
    fp = fingerprint(schema, [f.code for f in findings], shape=(n_rows, n_cols))

    report = Report(
        dataset_name=dataset_name,
        n_rows=n_rows,
        n_cols=n_cols,
        n_rows_analyzed=len(work),
        sampled=sampled,
        target_column=target,
        possible_targets=possible_targets,
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
        supervised_ml_readiness=scores.supervised_ml_readiness,
        findings=findings,
        modeling_warnings=[f for f in findings if f.category == "modeling_warning"],
        schema=schema,
        fingerprint=fp,
        severity_counts=scores.severity_counts,
    )

    try:
        exec_summary, recommendations, ai_available = summarizer.summarize(report)
    except Exception as exc:  # defensive: summarizer should not interrupt analysis
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
