"""Missingness + general engine behavior."""
from __future__ import annotations

import dqi
from dqi.report import Severity


def test_messy_reports_missingness(messy_df):
    report = dqi.analyze(messy_df, "messy", target="converted")
    miss = [f for f in report.findings if f.engine == "missingness"]
    assert miss, "expected missingness findings on messy data"
    # 'age' is ~22% missing -> HIGH band.
    age = [f for f in miss if f.column == "age"]
    assert age and age[0].severity == Severity.HIGH


def test_clean_has_little_missingness(clean_df):
    report = dqi.analyze(clean_df, "clean", target="churned")
    miss = [f for f in report.findings if f.engine == "missingness"]
    assert not miss, f"clean data should have no missingness findings, got {[f.column for f in miss]}"


def test_engines_never_raise_on_weird_input():
    import pandas as pd

    df = pd.DataFrame({"a": [None, None, None], "b": ["x", "x", "x"], "c": [1, 2, 3]})
    report = dqi.analyze(df, "weird", target="nonexistent")
    assert isinstance(report.health_score, float)
