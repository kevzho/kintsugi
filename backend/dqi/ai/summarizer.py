"""Builds the LLM context (diagnostics only), calls Groq, and falls back to a
deterministic summary so the product is fully usable with the LLM OFF.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .. import config
from ..report import Severity
from . import groq_client, prompts

if TYPE_CHECKING:
    from ..report import Report

logger = logging.getLogger("dqi.ai")


def _trim_metrics(metrics: dict) -> dict:
    """Drop the heavy correlation matrix and oversized values before sending."""
    out = {}
    for k, v in metrics.items():
        if k in ("matrix", "labels"):
            continue
        if isinstance(v, (list, dict)) and len(str(v)) > 300:
            continue
        out[k] = v
    return out


def build_context(report: "Report") -> dict:
    schema = report.schema
    sorted_findings = sorted(report.findings, key=lambda f: f.severity.rank)
    top = sorted_findings[: config.TOP_FINDINGS_FOR_LLM]
    return {
        "dataset": {
            "name": report.dataset_name,
            "rows": report.n_rows,
            "cols": report.n_cols,
        },
        "health_score": report.health_score,
        "grade": report.grade,
        "integrity_score": report.integrity_score,
        "integrity_grade": report.integrity_grade,
        "readiness_score": report.readiness_score,
        "readiness_grade": report.readiness_grade,
        "overall_score": report.overall_score,
        "overall_grade": report.overall_grade,
        "verdict": report.verdict,
        "score_confidence": {
            "integrity": report.integrity_confidence,
            "readiness": report.readiness_confidence,
            "overall": report.overall_confidence,
        },
        "dataset_type": report.dataset_type,
        "target_column": report.target_column,
        "schema_summary": {
            "n_numeric": schema.get("n_numeric", 0),
            "n_categorical": schema.get("n_categorical", 0),
            "n_datetime": schema.get("n_datetime", 0),
            "n_id_like": schema.get("n_id_like", 0),
        },
        "severity_counts": report.severity_counts,
        "top_findings": [
            {
                "code": f.code,
                "severity": f.severity.value,
                "category": f.category,
                "column": f.column,
                "title": f.title,
                "impact": f.impact,
                "metrics": _trim_metrics(f.metrics),
            }
            for f in top
        ],
    }


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _deterministic_summary(report: "Report") -> tuple[str, list[str]]:
    findings = sorted(report.findings, key=lambda f: f.severity.rank)
    counts = report.severity_counts
    n_crit = counts.get("critical", 0)
    n_high = counts.get("high", 0)

    fit = "fit to train on"
    if n_crit:
        fit = "NOT fit to train on until the critical issues are resolved"
    elif n_high:
        fit = "trainable, but address the high-severity issues first"

    lead = findings[0] if findings else None
    headline = lead.title if lead else "no material issues detected"
    summary = (
        f"'{report.dataset_name}' has integrity {report.integrity_score}/100 "
        f"({report.integrity_grade}, {report.integrity_confidence} confidence) and model readiness "
        f"{report.readiness_score}/100 ({report.readiness_grade}, {report.readiness_confidence} confidence) "
        f"across {report.n_rows} rows and {report.n_cols} columns. "
        f"Overall verdict: {report.verdict}. Found {n_crit} critical and {n_high} high-severity issues; "
        f"the top concern is {headline}. This dataset is {fit}."
    )

    recs: list[str] = []
    for f in findings:
        if f.severity in (Severity.INFO,):
            continue
        snippet = (f.fix_snippet or "").splitlines()
        snippet = next((ln for ln in snippet if ln and not ln.strip().startswith("#")), "")
        what = f.title
        why = f.impact
        rec = f"{what} — {why}"
        if snippet:
            rec += f" — `{snippet.strip()}`"
        recs.append(rec)
        if len(recs) >= 5:
            break
    if not recs:
        recs = ["No high-impact issues found — the dataset looks ready for a baseline model."]
    return summary, recs


def summarize(report: "Report") -> tuple[str, list[str], bool]:
    context = build_context(report)
    user = prompts.build_user_prompt(context)
    raw = groq_client.chat(prompts.SYSTEM, user)

    if raw:
        parsed = _extract_json(raw)
        if parsed and isinstance(parsed.get("exec_summary"), str):
            recs = parsed.get("recommendations") or []
            recs = [str(r) for r in recs][:5]
            if not recs:
                _, recs = _deterministic_summary(report)
            return parsed["exec_summary"].strip(), recs, True
        logger.warning("groq response unparseable — falling back to deterministic summary")

    summary, recs = _deterministic_summary(report)
    return summary, recs, False
