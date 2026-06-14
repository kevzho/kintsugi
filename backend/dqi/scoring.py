"""Deterministic two-score architecture.

External summary text and meta-classifiers do not assign scores. Findings from
rule engines are mapped into integrity and readiness penalties here.
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
    integrity_confidence: str
    integrity_confidence_reason: str
    readiness_confidence: str
    readiness_confidence_reason: str
    overall_confidence: str
    overall_confidence_reason: str
    dataset_purpose: str
    supervised_ml_readiness: str
    severity_counts: dict[str, int]


READINESS_WEIGHTS = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 12.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.0,
}

READINESS_ENGINE_CAPS = {
    "outliers": 12.0,
    "correlation": 8.0,
    "feature_quality": 7.0,
    "feature_quality:MESSY_NUMERIC_TEXT": 24.0,
    "imbalance": 18.0,
    "model_readiness": 60.0,
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
    if "readiness_penalty" in f.metrics:
        return float(f.metrics["readiness_penalty"])
    weight = READINESS_WEIGHTS.get(f.severity, 0.0)
    if f.engine == "outliers" and f.metrics.get("modeling_warning"):
        weight = min(weight, 5.0)
    if f.code in STRUCTURAL_MISSINGNESS_CODES:
        weight = max(weight, 3.0)
    if f.category == "data_integrity" and f.severity in (Severity.CRITICAL, Severity.HIGH):
        weight = max(weight, config.SEVERITY_WEIGHTS.get(f.severity, 0.0) * 0.6)
    return weight


def _dataset_purpose(findings: list[Finding], readiness: float, dataset_type: str = "unknown", target_provided: bool = True) -> str:
    if not target_provided:
        if dataset_type == "fixture_schedule":
            return "Simulation / forecasting / scheduling analysis"
        if dataset_type == "historical_archive":
            return "EDA / visualization / historical analysis"
        return "Data integrity and exploratory analysis"
    labels = [
        str(f.metrics.get("dataset_purpose"))
        for f in findings
        if f.metrics.get("dataset_purpose")
    ]
    caps = [
        str(f.metrics.get("dataset_purpose_cap"))
        for f in findings
        if f.metrics.get("dataset_purpose_cap")
    ]
    ordered = [
        "Not suitable for supervised ML",
        "EDA-only / visualization dataset",
        "Toy ML / demo only",
        "Trainable with caution",
        "Strong ML candidate",
    ]
    candidates = set(labels + caps)
    for label in ordered:
        if label in candidates:
            return label
    if readiness >= 85:
        return "Strong ML candidate"
    if readiness >= 70:
        return "Trainable with caution"
    if readiness >= 50:
        return "Toy ML / demo only"
    return "EDA-only / visualization dataset"


def _verdict(
    integrity: float,
    readiness: float,
    overall: float,
    findings: list[Finding],
    dataset_purpose: str,
    dataset_type: str = "unknown",
    target_provided: bool = True,
) -> str:
    if not target_provided:
        if dataset_type == "fixture_schedule":
            return "Suitable for simulation, scheduling analysis, and forecasting once outcome labels are added."
        if dataset_type == "historical_archive":
            if integrity >= 90:
                return "Excellent historical dataset, but not suitable for reliable supervised ML because it has too few rows."
            return "Best suited for EDA, visualization, and historical comparison."
        return "Supervised ML readiness requires a target column."
    if any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in findings):
        return "Do not train until leakage is resolved"
    if integrity < 60:
        return "Fix data integrity before modeling"
    if dataset_purpose == "Not suitable for supervised ML":
        if integrity >= 80:
            return "Clean dataset, but not suitable for reliable supervised ML. Best used for EDA, visualization, and historical analysis."
        return "Not suitable for supervised ML"
    if dataset_purpose == "EDA-only / visualization dataset":
        return "EDA-only / visualization dataset"
    if dataset_purpose == "Toy ML / demo only":
        return "Toy ML / demo only"
    if dataset_purpose == "Trainable with caution":
        return "Trainable with caution"
    if overall >= 85 and readiness >= 75:
        return "Trainable with warnings" if readiness < 90 else "Ready for baseline modeling"
    if readiness < 70:
        return "Structurally usable, but modeling risk is high"
    return "Review before modeling"


def _cap_confidence(level: str, cap: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return level if order[level] <= order[cap] else cap


def _confidence(
    *,
    score_kind: str,
    n_rows: int,
    sampled: bool,
    relevant: list[Finding],
    all_findings: list[Finding],
) -> tuple[str, str]:
    evidence = [f for f in relevant if f.severity != Severity.INFO]
    critical = [f for f in evidence if f.severity == Severity.CRITICAL]
    high = [f for f in evidence if f.severity == Severity.HIGH]

    if critical or high or len(evidence) >= 3:
        level = "high"
    elif n_rows >= 200 and len(all_findings) >= 1:
        level = "medium"
    else:
        level = "medium" if n_rows >= 100 else "low"

    if sampled:
        level = "medium" if level == "high" else level

    if score_kind in ("model-readiness", "overall"):
        if n_rows < 50:
            level = _cap_confidence(level, "low")
        elif n_rows < 200:
            level = _cap_confidence(level, "medium")
        if any(f.code == "WEAK_CLASSIFICATION_TARGET_SUPPORT" for f in all_findings):
            level = _cap_confidence(level, "low")
        if any(f.code == "POST_OUTCOME_LEAKAGE_RISK" for f in all_findings):
            level = _cap_confidence(level, "medium")

    if critical:
        reason = f"{len(critical)} critical finding{'s' if len(critical) != 1 else ''} with direct evidence."
    elif high:
        reason = f"{len(high)} high-severity finding{'s' if len(high) != 1 else ''} with measurable evidence."
    elif len(evidence) >= 3:
        reason = f"{len(evidence)} {score_kind} findings point in the same direction."
    elif n_rows < 100:
        reason = "Small sample size limits confidence in the score."
    elif sampled:
        reason = "Score is based on a deterministic sample of a larger file."
    elif evidence:
        reason = "A small number of measurable findings support the score."
    else:
        reason = "No major findings were detected, so confidence is based on schema and sample size."
    return level, reason


def score_report(
    findings: list[Finding],
    *,
    n_rows: int = 0,
    sampled: bool = False,
    dataset_type: str = "unknown",
    target_provided: bool = True,
) -> ScoreResult:
    integrity_by_engine: dict[str, float] = defaultdict(float)
    readiness_by_engine: dict[str, float] = defaultdict(float)
    severity_counts: dict[str, int] = {s.value: 0 for s in Severity}

    for f in findings:
        if f.engine == "outliers":
            f.category = "modeling_warning"
        if f.code == "HIGH_CARDINALITY_CATEGORICAL":
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
    readiness_caps = [
        float(f.metrics["readiness_cap"])
        for f in findings
        if "readiness_cap" in f.metrics
    ]
    if readiness_caps:
        readiness_score = round(min(readiness_score, min(readiness_caps)), 1)
    if target_provided and any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in findings):
        readiness_score = min(readiness_score, 40.0)
    if not target_provided:
        if dataset_type == "fixture_schedule":
            readiness_score = min(readiness_score, 60.0)
        elif dataset_type == "historical_archive":
            readiness_score = min(readiness_score, 30.0)
        else:
            readiness_score = min(readiness_score, 55.0)
    dataset_purpose = _dataset_purpose(findings, readiness_score, dataset_type, target_provided)
    overall_score = round(0.6 * integrity_score + 0.4 * readiness_score)

    if not target_provided:
        if dataset_type == "fixture_schedule":
            overall_score = round(0.8 * integrity_score + 0.2 * readiness_score)
            overall_score = min(max(overall_score, 70), 85)
        elif dataset_type == "historical_archive":
            overall_score = round(0.7 * integrity_score + 0.3 * readiness_score)
            overall_score = min(max(overall_score, 60), 75)
        else:
            overall_score = round(0.9 * integrity_score + 0.1 * readiness_score)

    if target_provided and any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in findings):
        overall_score = min(overall_score, 40)
    if any(f.code in CORRUPTION_CODES and f.severity in (Severity.HIGH, Severity.CRITICAL) for f in findings):
        overall_score = min(overall_score, 55)
    missing_high = [f for f in findings if f.code == "MISSING_VALUES" and f.severity in (Severity.HIGH, Severity.CRITICAL)]
    if len(missing_high) >= 3:
        overall_score = min(overall_score, 70)
    if target_provided and readiness_score < 40:
        overall_score = min(overall_score, 65)
    if target_provided and dataset_purpose == "EDA-only / visualization dataset":
        overall_score = min(overall_score, 70)
    if target_provided and dataset_purpose == "Not suitable for supervised ML":
        overall_score = min(overall_score, 60)
    overall_caps = [
        float(f.metrics["overall_cap"])
        for f in findings
        if "overall_cap" in f.metrics
    ]
    if target_provided and overall_caps:
        overall_score = min(overall_score, min(overall_caps))

    overall_score = float(overall_score)
    integrity_findings = [f for f in findings if f.category != "modeling_warning"]
    readiness_findings = [f for f in findings if f.category == "modeling_warning" or f.readiness_penalty > 0]
    integrity_confidence, integrity_reason = _confidence(
        score_kind="integrity",
        n_rows=n_rows,
        sampled=sampled,
        relevant=integrity_findings,
        all_findings=findings,
    )
    readiness_confidence, readiness_reason = _confidence(
        score_kind="model-readiness",
        n_rows=n_rows,
        sampled=sampled,
        relevant=readiness_findings,
        all_findings=findings,
    )
    supervised_ml_readiness = "scored" if target_provided else "N/A"
    if not target_provided:
        readiness_reason = (
            "Supervised ML readiness requires a target column. Since no target was selected, "
            "this report focuses on data integrity and likely dataset use cases."
        )
        readiness_confidence = "low"
    if integrity_confidence == readiness_confidence:
        overall_confidence = integrity_confidence
    elif "low" in (integrity_confidence, readiness_confidence):
        overall_confidence = "medium"
    else:
        overall_confidence = "medium"
    overall_confidence = _cap_confidence(overall_confidence, "low" if readiness_confidence == "low" else "medium" if readiness_confidence == "medium" else "high")
    overall_reason = (
        f"Integrity confidence is {integrity_confidence}; readiness confidence is {readiness_confidence}."
    )
    return ScoreResult(
        integrity_score=integrity_score,
        integrity_grade=_grade(integrity_score),
        readiness_score=readiness_score,
        readiness_grade=_grade(readiness_score),
        overall_score=overall_score,
        overall_grade=_overall_grade(overall_score),
        verdict=_verdict(
            integrity_score,
            readiness_score,
            overall_score,
            findings,
            dataset_purpose,
            dataset_type,
            target_provided,
        ),
        integrity_confidence=integrity_confidence,
        integrity_confidence_reason=integrity_reason,
        readiness_confidence=readiness_confidence,
        readiness_confidence_reason=readiness_reason,
        overall_confidence=overall_confidence,
        overall_confidence_reason=overall_reason,
        dataset_purpose=dataset_purpose,
        supervised_ml_readiness=supervised_ml_readiness,
        severity_counts=severity_counts,
    )
