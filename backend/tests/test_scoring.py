"""Scoring ordering + degradation guarantees: clean > messy > leaky."""
from __future__ import annotations

import dqi


def test_score_ordering(clean_df, messy_df, leaky_df):
    clean = dqi.analyze(clean_df, "clean", target="churned")
    messy = dqi.analyze(messy_df, "messy", target="converted")
    leaky = dqi.analyze(leaky_df, "leaky", target="defaulted")
    assert clean.health_score > messy.health_score, (
        f"clean ({clean.health_score}) should beat messy ({messy.health_score})"
    )
    assert messy.health_score > leaky.health_score, (
        f"messy ({messy.health_score}) should beat leaky ({leaky.health_score})"
    )


def test_leaky_scores_low(leaky_df):
    leaky = dqi.analyze(leaky_df, "leaky", target="defaulted")
    assert leaky.health_score <= 45, f"leaky should be ~F, got {leaky.health_score}"
    assert leaky.grade == "F"


def test_score_bounds_and_grade(clean_df):
    report = dqi.analyze(clean_df, "clean", target="churned")
    assert 0.0 <= report.health_score <= 100.0
    assert report.grade in {"A", "B", "C", "D", "F"}


def test_works_with_groq_off(messy_df, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(messy_df, "messy", target="converted")
    assert report.ai_available is False
    assert report.exec_summary, "deterministic exec_summary must be populated with LLM off"
    assert report.recommendations, "deterministic recommendations must be populated with LLM off"
