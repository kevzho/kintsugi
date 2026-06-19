"""Privacy-light usage event logging for the Kintsugi API.

Usage events are intentionally aggregate-only: no raw rows, cell values, column
names, or uploaded filenames are recorded.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Request

from dqi.report import Report

logger = logging.getLogger("dqi.usage")

DEFAULT_USAGE_LOG_PATH = ".usage/kintsugi_usage_events.jsonl"
MEMORY_EVENTS: list[dict[str, Any]] = []


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
    MEMORY_EVENTS.append(event)
    path = _usage_log_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("usage file write failed: %s", type(exc).__name__)


def _identity_fields(request: Request) -> dict[str, Any]:
    return {
        "anonymousUserId": _clean_header(
            request.headers.get("x-kintsugi-visitor-id"), "anonymous"
        ),
        "sessionId": _clean_header(request.headers.get("x-kintsugi-session-id")),
        "ipHash": _hash(_client_ip(request)),
        "userAgentHash": _hash(request.headers.get("user-agent")),
    }


def _record_event(event: dict[str, Any]) -> None:
    logger.info("kintsugi_usage_event %s", json.dumps(event, sort_keys=True))
    _write_jsonl(event)


def track_page_view_usage(*, request: Request, path: str) -> None:
    event: dict[str, Any] = {
        "event": "page_view",
        "eventId": str(uuid.uuid4()),
        "product": "kintsugi",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "path": (path or "/")[:240],
        **_identity_fields(request),
    }
    _record_event(event)


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
        "eventId": report.fingerprint,
        "product": "kintsugi",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        **_identity_fields(request),
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
    }

    _record_event(event)


def _read_jsonl_events() -> list[dict[str, Any]]:
    path = _usage_log_path()
    if not path or not path.exists():
        return MEMORY_EVENTS
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.warning("usage file read failed: %s", type(exc).__name__)
        return MEMORY_EVENTS
    return events


def get_usage_stats() -> dict[str, Any]:
    events = _read_jsonl_events()
    visitors: set[str] = set()
    users: set[str] = set()
    page_views = 0
    submissions = 0

    for event in events:
        anonymous_user_id = event.get("anonymousUserId")
        if anonymous_user_id and anonymous_user_id != "anonymous":
            visitors.add(str(anonymous_user_id))
        if event.get("event") == "page_view":
            page_views += 1
        if event.get("event") == "analysis_completed":
            submissions += 1
            if anonymous_user_id and anonymous_user_id != "anonymous":
                users.add(str(anonymous_user_id))

    return {
        "uniqueVisitors": len(visitors),
        "uniqueUsers": len(users),
        "pageViews": page_views,
        "submissions": submissions,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "storage": "jsonl" if _usage_log_path() else "memory",
    }
