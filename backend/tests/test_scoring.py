"""Scoring ordering + degradation guarantees: clean > messy > leaky."""
from __future__ import annotations

import numpy as np
import pandas as pd

import dqi
from dqi import Severity
from dqi.schema import infer_schema


def _cyber_heavy_tail_df(n: int = 5000) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "src_bytes": rng.lognormal(mean=7.0, sigma=2.0, size=n).round().astype(int),
            "dst_bytes": rng.lognormal(mean=6.7, sigma=1.9, size=n).round().astype(int),
            "packet_count": rng.negative_binomial(n=2, p=0.08, size=n),
            "failed_logins": rng.poisson(lam=0.15, size=n) + rng.binomial(1, 0.02, size=n) * rng.integers(5, 40, size=n),
            "duration": rng.lognormal(mean=2.0, sigma=1.4, size=n),
            "protocol": rng.choice(["tcp", "udp", "icmp"], size=n, p=[0.7, 0.25, 0.05]),
            "attack": rng.integers(0, 2, size=n),
        }
    )


def _state_crime_income_df() -> pd.DataFrame:
    rows = []
    states = [f"State_{i:02d}" for i in range(30)]
    rng = np.random.default_rng(12)
    for year in range(1978, 1986):
        for state_idx, state in enumerate(states):
            population = 500_000 + state_idx * 83_000 + (year - 1978) * 11_000
            violent = 900 + state_idx * 17 + (year - 1978) * 13 + rng.integers(-20, 20)
            property_crime = 4_000 + state_idx * 31 + (year - 1978) * 19 + rng.integers(-50, 50)
            rows.append(
                {
                    "State": state,
                    "Year": year,
                    "Crime Count_aggravated_assault": violent + rng.integers(0, 30),
                    "Crime Count_burglary": property_crime + rng.integers(0, 60),
                    "Population": population,
                    "Violent Crime": violent,
                    "Property Crime": property_crime,
                    "Median Income": np.nan if year == 1978 and state_idx < 20 else 45_000 + state_idx * 900 + (year - 1978) * 700,
                    "High Crime": int(rng.random() > 0.5),
                }
            )
    return pd.DataFrame(rows)


def _telco_df(n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(21)
    total = (rng.uniform(20, 8000, size=n)).round(2).astype(str)
    blank_idx = rng.choice(n, size=12, replace=False)
    for i in blank_idx:
        total[i] = " "
    return pd.DataFrame(
        {
            "customerID": [f"cust-{i:05d}" for i in range(n)],
            "tenure": rng.integers(0, 72, size=n),
            "MonthlyCharges": rng.uniform(20, 120, size=n).round(2),
            "TotalCharges": total,
            "Contract": rng.choice(["Month-to-month", "One year", "Two year"], size=n),
            "Churn": rng.choice(["Yes", "No"], size=n),
        }
    )


def _quikr_df() -> pd.DataFrame:
    rows = []
    for i in range(120):
        price = "Ask For Price" if i % 5 == 0 else f"{1 + i % 8},{50 + i:02d},000"
        kms = "not available" if i % 7 == 0 else f"{20_000 + i * 750:,} kms"
        rows.append(
            {
                "name": f"Car {i % 20}",
                "company": ["Maruti", "Hyundai", "Honda"][i % 3],
                "year": 2000 + (i % 23),
                "Price": price,
                "kms_driven": kms,
                "fuel_type": None if i % 11 == 0 else ["Petrol", "Diesel", "CNG"][i % 3],
            }
        )
    return pd.concat([pd.DataFrame(rows), pd.DataFrame(rows[:20])], ignore_index=True)


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
    assert report.grade in {"A", "A-", "B+", "B", "B-", "C", "D", "F"}
    assert 0.0 <= report.integrity_score <= 100.0
    assert 0.0 <= report.readiness_score <= 100.0
    assert report.overall_score == report.health_score
    assert report.integrity_confidence in {"low", "medium", "high"}
    assert report.readiness_confidence in {"low", "medium", "high"}
    assert report.overall_confidence in {"low", "medium", "high"}
    assert report.integrity_confidence_reason


def test_works_with_groq_off(messy_df, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(messy_df, "messy", target="converted")
    assert report.ai_available is False
    assert report.exec_summary, "deterministic exec_summary must be populated with LLM off"
    assert report.recommendations, "deterministic recommendations must be populated with LLM off"


def test_cyber_heavy_tails_are_modeling_warnings_not_integrity_failures(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_cyber_heavy_tail_df(), "cyber_attack_dataset_100000.csv", target="attack")
    outliers = [f for f in report.findings if f.engine == "outliers"]

    assert report.dataset_type == "network_logs"
    assert report.integrity_score >= 90
    assert 80 <= report.readiness_score <= 90
    assert 89 <= report.overall_score <= 94
    assert outliers, "heavy-tailed numeric columns should still be visible"
    assert all(f in report.modeling_warnings for f in outliers)
    assert all(f.category == "modeling_warning" for f in outliers)
    assert all(f.severity in {Severity.MEDIUM, Severity.LOW} for f in outliers)
    assert sum(f.integrity_penalty for f in outliers) <= 3.0
    assert any("heavy-tailed" in f.title for f in outliers)
    assert any("Do not blindly remove" in (f.fix_snippet or "") for f in outliers)
    for col in ("src_bytes", "dst_bytes", "packet_count", "failed_logins", "duration"):
        assert report.schema["columns"][col]["column_role"] == "measurement"


def test_true_integrity_failures_still_score_low(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    n = 140
    base = pd.DataFrame(
        {
            "customer_id": np.arange(n),
            "age": [None if i % 3 == 0 else 30 + (i % 20) for i in range(n)],
            "amount": ["unknown" if i % 4 == 0 else str(100 + i) for i in range(n)],
            "target": [i % 2 for i in range(n)],
        }
    )
    base["target_copy"] = base["target"]
    base = pd.concat([base, base.iloc[:60]], ignore_index=True)

    report = dqi.analyze(base, "integrity_failures.csv", target="target")

    assert report.health_score < 75
    assert any(f.engine == "leakage" and f.severity == Severity.CRITICAL for f in report.findings)
    assert any(f.engine == "missingness" for f in report.findings)
    assert any(f.engine == "duplicates" for f in report.findings)
    assert any(f.code == "MIXED_TYPE_COLUMN" for f in report.findings)


def test_numeric_score_is_independent_of_groq_response(monkeypatch, messy_df):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    no_groq = dqi.analyze(messy_df, "messy", target="converted")

    from dqi.ai import groq_client

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        groq_client,
        "chat",
        lambda system, user: '{"exec_summary":"Groq text only.","recommendations":["Narrative only."]}',
    )
    with_groq = dqi.analyze(messy_df, "messy", target="converted")

    assert with_groq.ai_available is True
    assert with_groq.exec_summary == "Groq text only."
    assert with_groq.health_score == no_groq.health_score
    assert with_groq.grade == no_groq.grade
    assert with_groq.integrity_score == no_groq.integrity_score
    assert with_groq.readiness_score == no_groq.readiness_score
    assert with_groq.integrity_confidence == no_groq.integrity_confidence
    assert with_groq.readiness_confidence == no_groq.readiness_confidence


def test_outlier_penalty_cap_even_with_many_heavy_tailed_columns(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_cyber_heavy_tail_df(), "many_outliers.csv", target="attack")
    outlier_penalty = sum(f.integrity_penalty for f in report.findings if f.engine == "outliers")

    assert outlier_penalty <= 3.0
    assert report.integrity_score >= 95.0


def test_state_crime_measurements_are_not_identifiers(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _state_crime_income_df()
    schema = infer_schema(df)
    measurement_cols = [
        "Crime Count_aggravated_assault",
        "Crime Count_burglary",
        "Population",
        "Violent Crime",
        "Property Crime",
    ]

    for col in measurement_cols:
        prof = schema["columns"][col]
        assert prof["dtype_inferred"] == "numeric"
        assert prof["name_kind"] == "measurement"
        assert prof["is_id_like"] is False

    report = dqi.analyze(df, "state_crime_income_merged.csv", target="High Crime")
    critical_id_findings = [
        f for f in report.findings
        if f.severity == Severity.CRITICAL
        and f.column in measurement_cols
        and f.code in {"DUPLICATE_ID_LABEL_NOISE", "ID_USED_AS_FEATURE"}
    ]
    id_memorization = [
        f for f in report.findings
        if f.code == "ID_USED_AS_FEATURE" and f.column in measurement_cols
    ]

    assert not critical_id_findings
    assert not id_memorization
    assert report.dataset_type == "panel_data"
    assert 85 <= report.integrity_score <= 95
    assert 75 <= report.readiness_score <= 85
    assert 83 <= report.overall_score <= 91
    assert any(f.code == "STRUCTURAL_MISSINGNESS_TIME_REGIME" for f in report.findings)


def test_confirmed_identifier_still_runs_entity_consistency(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", "c2", "c3", "c3"],
            "amount": [10, 10, 20, 20, 30, 30],
            "target": [0, 1, 0, 0, 1, 1],
        }
    )

    report = dqi.analyze(df, "confirmed_ids.csv", target="target")
    schema = infer_schema(df)

    assert schema["columns"]["customer_id"]["is_id_like"] is True
    assert any(f.code == "DUPLICATE_ID_LABEL_NOISE" for f in report.findings)


def test_telco_totalcharges_blanks_are_not_catastrophic(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_telco_df(), "WA_Fn-UseC_-Telco-Customer-Churn.csv")

    assert report.dataset_type == "business_tabular"
    assert report.target_column == "Churn"
    assert report.schema["columns"]["customerID"]["column_role"] == "identifier"
    assert report.schema["columns"]["Churn"]["column_role"] == "target"
    assert any(f.column == "TotalCharges" for f in report.findings)
    assert report.integrity_score >= 85
    assert report.overall_score >= 86


def test_quikr_messy_numeric_columns_stay_low(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_quikr_df(), "quikr_car.csv")

    assert report.dataset_type == "ecommerce"
    assert any(f.code == "MESSY_NUMERIC_TEXT" and f.column == "Price" for f in report.findings)
    assert any(f.code == "MESSY_NUMERIC_TEXT" and f.column == "kms_driven" for f in report.findings)
    assert any(f.engine == "duplicates" for f in report.findings)
    assert 30 <= report.integrity_score <= 55
    assert 35 <= report.overall_score <= 60
    assert report.integrity_confidence == "high"
    assert "finding" in report.integrity_confidence_reason
