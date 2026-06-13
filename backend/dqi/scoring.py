"""Health scoring: start at 100, subtract weighted penalties per finding,
cap each engine's total contribution, clamp, and grade.
"""
from __future__ import annotations

from collections import defaultdict

from . import config
from .report import Finding, Severity


def score_report(findings: list[Finding]) -> tuple[float, str, dict[str, int]]:
    per_engine: dict[str, float] = defaultdict(float)
    severity_counts: dict[str, int] = {s.value: 0 for s in Severity}

    for f in findings:
        weight = config.SEVERITY_WEIGHTS.get(f.severity, 0.0)
        room = config.CATEGORY_CAP - per_engine[f.engine]
        applied = max(0.0, min(weight, room))
        f.score_penalty = round(applied, 2)
        per_engine[f.engine] += applied
        severity_counts[f.severity.value] += 1

    total_penalty = sum(per_engine.values())
    score = max(0.0, min(100.0, 100.0 - total_penalty))
    score = round(score, 1)
    grade = config.grade_for(score)
    return score, grade, severity_counts
