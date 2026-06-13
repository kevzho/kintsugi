"""The hero engine: leaky.csv must yield a CRITICAL leakage finding."""
from __future__ import annotations

import dqi
from dqi.report import Severity


def test_leaky_dataset_has_critical_leakage(leaky_df):
    report = dqi.analyze(leaky_df, "leaky", target="defaulted")
    leakage = [f for f in report.findings if f.engine == "leakage"]
    assert leakage, "expected at least one leakage finding"
    criticals = [f for f in leakage if f.severity == Severity.CRITICAL]
    assert criticals, f"expected a CRITICAL leakage finding, got {[f.code for f in leakage]}"


def test_collections_flag_flagged_as_perfect_predictor(leaky_df):
    report = dqi.analyze(leaky_df, "leaky", target="defaulted")
    codes = {f.code for f in report.findings if f.engine == "leakage"}
    assert "TARGET_LEAKAGE_PERFECT_PREDICTOR" in codes or "TARGET_LEAKAGE_TARGET_COPY" in codes


def test_outcome_score_suspicious_name_or_predictor(leaky_df):
    report = dqi.analyze(leaky_df, "leaky", target="defaulted")
    leak_cols = {f.column for f in report.findings if f.engine == "leakage"}
    assert "outcome_score" in leak_cols


def test_clean_has_no_critical_leakage(clean_df):
    report = dqi.analyze(clean_df, "clean", target="churned")
    crit_leak = [
        f for f in report.findings
        if f.engine == "leakage" and f.severity == Severity.CRITICAL
    ]
    assert not crit_leak, f"clean data should not have critical leakage: {[f.code for f in crit_leak]}"
