"""Builds the LLM context (diagnostics only), calls Groq, and falls back to a
deterministic summary so the product is fully usable with the LLM OFF.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .. import config
from ..report import FixCode, Recommendation, Severity
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
        "dataset_purpose": report.dataset_purpose,
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
                "deterministic_fix": {
                    "type": "python",
                    "code": f.fix_snippet,
                } if f.fix_snippet else None,
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


def _recommendation_from_finding(f) -> Recommendation:
    snippet = (f.fix_snippet or "").strip()
    return Recommendation(
        title=f.title,
        why=f.impact,
        fix=FixCode(type="python", code=snippet) if snippet else None,
    )


def _coerce_recommendation(item) -> Recommendation | None:
    if isinstance(item, Recommendation):
        return item
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("action") or item.get("what") or "").strip()
        why = str(item.get("why") or item.get("impact") or item.get("reason") or "").strip()
        fix_obj = item.get("fix")
        fix = None
        if isinstance(fix_obj, dict):
            code = str(fix_obj.get("code") or "").strip()
            lang = str(fix_obj.get("type") or fix_obj.get("language") or "python").strip() or "python"
            if code:
                fix = FixCode(type=lang, code=code)
        elif isinstance(fix_obj, str) and fix_obj.strip():
            fix = FixCode(type="python", code=fix_obj.strip().strip("`"))
        if not title and why:
            title = why
            why = ""
        return Recommendation(title=title, why=why, fix=fix) if title else None
    if isinstance(item, str):
        raw = item.strip()
        if not raw:
            return None
        parts = [p.strip() for p in raw.split(" — ")]
        title = parts[0]
        why = parts[1] if len(parts) > 1 else ""
        fix = None
        if len(parts) > 2:
            code = parts[2].strip().strip("`")
            if code:
                fix = FixCode(type="python", code=code)
        return Recommendation(title=title, why=why, fix=fix)
    return None


def _coerce_recommendations(items) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for item in items or []:
        rec = _coerce_recommendation(item)
        if rec:
            recs.append(rec)
        if len(recs) >= 5:
            break
    return recs


def _deterministic_summary(report: "Report") -> tuple[str, list[Recommendation]]:
    findings = sorted(report.findings, key=lambda f: f.severity.rank)
    counts = report.severity_counts
    n_crit = counts.get("critical", 0)
    n_high = counts.get("high", 0)

    lead = findings[0] if findings else None
    headline = lead.title if lead else "no material issues detected"
    if report.dataset_purpose in {"Not suitable for supervised ML", "EDA-only / visualization dataset"}:
        purpose_sentence = (
            "It is structurally clean enough to inspect, but not suitable for reliable "
            "supervised machine learning; use it for exploratory analysis, visualization, "
            "historical analysis, or a toy demo unless more data is added."
            if report.integrity_score >= 80
            else "Its current purpose is limited by both quality and readiness concerns."
        )
    elif report.dataset_purpose == "Toy ML / demo only":
        purpose_sentence = "It can support a toy/demo model, but reliable validation needs more data."
    elif report.dataset_purpose == "Trainable with caution":
        purpose_sentence = "It may support baseline modeling, but validation should be treated cautiously."
    else:
        purpose_sentence = "It looks like a strong candidate for baseline modeling."
    summary = (
        f"'{report.dataset_name}' has integrity {report.integrity_score}/100 "
        f"({report.integrity_grade}, {report.integrity_confidence} confidence) and model readiness "
        f"{report.readiness_score}/100 ({report.readiness_grade}, {report.readiness_confidence} confidence) "
        f"across {report.n_rows} rows and {report.n_cols} columns. "
        f"Purpose: {report.dataset_purpose}. Overall verdict: {report.verdict}. "
        f"Found {n_crit} critical and {n_high} high-severity issues; "
        f"the top concern is {headline}. {purpose_sentence}"
    )

    recs: list[Recommendation] = []
    for f in findings:
        if f.severity in (Severity.INFO,):
            continue
        recs.append(_recommendation_from_finding(f))
        if len(recs) >= 5:
            break
    if not recs:
        recs = [
            Recommendation(
                title="No high-impact issues found",
                why="The dataset looks ready for a baseline model.",
                fix=None,
            )
        ]
    return summary, recs


def summarize(report: "Report") -> tuple[str, list[Recommendation], bool]:
    context = build_context(report)
    user = prompts.build_user_prompt(context)
    raw = groq_client.chat(prompts.SYSTEM, user)

    if raw:
        parsed = _extract_json(raw)
        if parsed and isinstance(parsed.get("exec_summary"), str):
            recs = _coerce_recommendations(parsed.get("recommendations") or [])
            if not recs:
                _, recs = _deterministic_summary(report)
            return parsed["exec_summary"].strip(), recs, True
        logger.warning("groq response unparseable — falling back to deterministic summary")

    summary, recs = _deterministic_summary(report)
    return summary, recs, False
