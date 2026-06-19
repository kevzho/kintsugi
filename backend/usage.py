"""Privacy-light usage event logging for the Kintsugi API.

Usage events are intentionally aggregate-only: no raw rows, cell values, column
names, or uploaded filenames are recorded.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Request

from dqi.report import Report

logger = logging.getLogger("dqi.usage")

DEFAULT_USAGE_LOG_PATH = ".usage/kintsugi_usage_events.jsonl"


def _hash(value: Optional[str]) -> Optional[str]:
    trimmed = (value or "").strip()
    if not trimmed:
        return None
    return hashlib.sha256(trimmed.encode("utf-8")).hexdigest()[:24]


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (
        request.headers.get("x-real-ip")
        or request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else None)
    )


def _extension_for(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    return suffix or "unknown"


def _clean_header(value: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    trimmed = (value or "").strip()
    if not trimmed:
        return fallback
    return trimmed[:128]


def _usage_log_path() -> Optional[Path]:
    raw = os.getenv("KINTSUGI_USAGE_LOG_PATH", DEFAULT_USAGE_LOG_PATH).strip()
    if raw.lower() in {"", "off", "false", "0", "none"}:
        return None
    return Path(raw)


def _write_jsonl(event: dict[str, Any]) -> None:
    path = _usage_log_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("usage file write failed: %s", type(exc).__name__)


def track_analysis_usage(
    *,
    request: Request,
    report: Report,
    source: str,
    file_name: str,
    target_provided: bool,
    demo_id: Optional[str] = None,
) -> None:
    """Record one completed analysis event."""
    event: dict[str, Any] = {
        "event": "analysis_completed",
        "product": "kintsugi",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "anonymousUserId": _clean_header(
            request.headers.get("x-kintsugi-visitor-id"), "anonymous"
        ),
        "sessionId": _clean_header(request.headers.get("x-kintsugi-session-id")),
        "fileExtension": _extension_for(file_name),
        "demoId": demo_id,
        "targetProvided": target_provided,
        "rowCount": report.n_rows,
        "columnCount": report.n_cols,
        "rowsAnalyzed": report.n_rows_analyzed,
        "sampled": report.sampled,
        "healthScore": report.health_score,
        "grade": report.grade,
        "integrityScore": report.integrity_score,
        "readinessScore": report.readiness_score,
        "findingCount": len(report.findings),
        "modelingWarningCount": len(report.modeling_warnings),
        "severityCounts": report.severity_counts,
        "aiAvailable": report.ai_available,
        "ipHash": _hash(_client_ip(request)),
        "userAgentHash": _hash(request.headers.get("user-agent")),
    }

    logger.info("kintsugi_usage_event %s", json.dumps(event, sort_keys=True))
    _write_jsonl(event)
