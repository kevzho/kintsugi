"""Deterministic two-score architecture.

Groq and meta-classifiers never assign scores. Findings from rule engines are
mapped into integrity and readiness penalties here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from . import config
from .report import Finding, Severity


@dataclass(frozen=True)
class ScoreResult:
    integrity_score: float
    integrity_grade: str
    readiness_score: float
    readiness_grade: str
    overall_score: float
    overall_grade: str
    verdict: str
    severity_counts: dict[str, int]


READINESS_WEIGHTS = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 12.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.5,
}

READINESS_ENGINE_CAPS = {
    "outliers": 12.0,
    "correlation": 8.0,
    "feature_quality": 7.0,
    "feature_quality:MESSY_NUMERIC_TEXT": 24.0,
    "imbalance": 18.0,
}

INTEGRITY_ENGINE_CAPS = {
    "outliers": 3.0,
}

STRUCTURAL_MISSINGNESS_CODES = {"STRUCTURAL_MISSINGNESS_TIME_REGIME", "CO_MISSING_GROUP"}
CORRUPTION_CODES = {"MIXED_TYPE_COLUMN", "NUMERIC_STORED_AS_STRING", "MESSY_NUMERIC_TEXT"}


def _grade(score: float) -> str:
    return config.grade_for(score)


def _overall_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 85:
        return "A-"
    if score >= 80:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "B-"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _integrity_weight(f: Finding) -> float:
    if f.engine == "outliers":
        return min(1.0, config.OUTLIER_FINDING_MAX_SCORE_PENALTY)
    if f.category == "modeling_warning":
        return 0.0
    weight = config.SEVERITY_WEIGHTS.get(f.severity, 0.0)
    if f.code in STRUCTURAL_MISSINGNESS_CODES:
        weight = min(weight, 2.0)
    if f.code == "MISSING_VALUES" and f.metrics.get("null_rate", 0.0) < 0.10:
        weight = min(weight, 3.0)
    return weight


def _readiness_weight(f: Finding) -> float:
    weight = READINESS_WEIGHTS.get(f.severity, 0.0)
    if f.engine == "outliers" and f.metrics.get("modeling_warning"):
        weight = min(weight, 5.0)
    if f.code in STRUCTURAL_MISSINGNESS_CODES:
        weight = max(weight, 3.0)
    if f.category == "data_integrity" and f.severity in (Severity.CRITICAL, Severity.HIGH):
        weight = max(weight, config.SEVERITY_WEIGHTS.get(f.severity, 0.0) * 0.6)
    return weight


def _verdict(integrity: float, readiness: float, overall: float, findings: list[Finding]) -> str:
    if any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in findings):
        return "Do not train until leakage is resolved"
    if integrity < 60:
        return "Fix data integrity before modeling"
    if overall >= 85 and readiness >= 75:
        return "Trainable with warnings" if readiness < 90 else "Ready for baseline modeling"
    if readiness < 70:
        return "Structurally usable, but modeling risk is high"
    return "Review before modeling"


def score_report(findings: list[Finding]) -> ScoreResult:
    integrity_by_engine: dict[str, float] = defaultdict(float)
    readiness_by_engine: dict[str, float] = defaultdict(float)
    severity_counts: dict[str, int] = {s.value: 0 for s in Severity}

    for f in findings:
        if f.engine == "outliers":
            f.category = "modeling_warning"

        integrity_cap = INTEGRITY_ENGINE_CAPS.get(f.engine, config.CATEGORY_CAP)
        readiness_key = f"{f.engine}:{f.code}" if f.code == "MESSY_NUMERIC_TEXT" else f.engine
        readiness_cap = READINESS_ENGINE_CAPS.get(readiness_key, READINESS_ENGINE_CAPS.get(f.engine, config.CATEGORY_CAP))

        iw = _integrity_weight(f)
        rw = _readiness_weight(f)

        i_room = integrity_cap - integrity_by_engine[f.engine]
        r_room = readiness_cap - readiness_by_engine[readiness_key]
        i_applied = max(0.0, min(iw, i_room))
        r_applied = max(0.0, min(rw, r_room))

        f.integrity_penalty = round(i_applied, 2)
        f.readiness_penalty = round(r_applied, 2)
        f.score_penalty = f.integrity_penalty

        integrity_by_engine[f.engine] += i_applied
        readiness_by_engine[readiness_key] += r_applied
        severity_counts[f.severity.value] += 1

    integrity_score = round(max(0.0, min(100.0, 100.0 - sum(integrity_by_engine.values()))), 1)
    readiness_score = round(max(0.0, min(100.0, 100.0 - sum(readiness_by_engine.values()))), 1)
    overall_score = round(0.6 * integrity_score + 0.4 * readiness_score)

    if any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in findings):
        overall_score = min(overall_score, 40)
    if any(f.code in CORRUPTION_CODES and f.severity in (Severity.HIGH, Severity.CRITICAL) for f in findings):
        overall_score = min(overall_score, 55)
    missing_high = [f for f in findings if f.code == "MISSING_VALUES" and f.severity in (Severity.HIGH, Severity.CRITICAL)]
    if len(missing_high) >= 3:
        overall_score = min(overall_score, 70)

    overall_score = float(overall_score)
    return ScoreResult(
        integrity_score=integrity_score,
        integrity_grade=_grade(integrity_score),
        readiness_score=readiness_score,
        readiness_grade=_grade(readiness_score),
        overall_score=overall_score,
        overall_grade=_overall_grade(overall_score),
        verdict=_verdict(integrity_score, readiness_score, overall_score, findings),
        severity_counts=severity_counts,
    )
