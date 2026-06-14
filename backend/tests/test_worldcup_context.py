from __future__ import annotations

import numpy as np
import pandas as pd

import dqi
from dqi import Severity


def _wc_2026_fixtures_like() -> pd.DataFrame:
    rows = []
    for i in range(96):
        unresolved = i >= 72
        rows.append(
            {
                "match_id": i + 1,
                "date": pd.Timestamp("2026-06-11") + pd.Timedelta(days=i // 4),
                "round": "Group stage" if i < 72 else "Round of 32",
                "group": f"Group {chr(65 + (i % 12))}" if not unresolved else None,
                "venue": f"Stadium {i % 10}",
                "team1": f"Team {i % 48}" if not unresolved else None,
                "team2": f"Team {(i + 1) % 48}" if not unresolved else None,
                "team1_confederation": ["UEFA", "CONMEBOL", "AFC", "CAF"][i % 4] if not unresolved else None,
                "team1_fifa_rank": 1 + (i % 80) if not unresolved else np.nan,
                "team1_coach": f"Coach {i % 48}" if not unresolved else None,
                "team2_confederation": ["UEFA", "CONMEBOL", "AFC", "CAF"][(i + 1) % 4] if not unresolved else None,
                "team2_fifa_rank": 1 + ((i + 1) % 80) if not unresolved else np.nan,
                "team2_coach": f"Coach {(i + 1) % 48}" if not unresolved else None,
            }
        )
    return pd.DataFrame(rows)


def _wc_all_editions_like() -> pd.DataFrame:
    rows = []
    for i, year in enumerate(range(1930, 2026, 4)):
        if year in {1942, 1946}:
            continue
        rows.append(
            {
                "edition": i + 1,
                "year": year,
                "host": f"Host {i}",
                "winner": f"Winner {i % 18}",
                "runner_up": f"Runner {i % 20}",
                "third_place": f"Third {i % 20}",
                "fourth_place": f"Fourth {i % 20}",
                "top_scorer": f"Scorer {i}",
                "final_city": f"City {i}",
                "attendance": 500_000 + i * 120_000,
                "goals": 70 + i * 9,
                "matches": 18 + i * 2,
                "format": ["knockout", "groups", "expanded"][i % 3],
            }
        )
    return pd.DataFrame(rows[:22])


def _large_clean_ml_df(n: int = 5000) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    data = {f"x{i:02d}": rng.normal(size=n) for i in range(12)}
    data["segment"] = rng.choice(["A", "B", "C"], size=n)
    data["region"] = rng.choice(["NA", "EU", "APAC"], size=n)
    data["plan"] = rng.choice(["basic", "pro"], size=n)
    data["churn"] = (data["x00"] + data["x01"] * 0.5 + rng.normal(size=n) > 0).astype(int)
    return pd.DataFrame(data)


def test_wc_2026_fixtures_no_target_is_schedule_analysis(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_wc_2026_fixtures_like(), "wc_2026_fixtures.csv")

    assert report.dataset_type == "fixture_schedule"
    assert report.target_column is None
    assert report.supervised_ml_readiness == "N/A"
    assert not any(f.engine == "leakage" and f.severity == Severity.CRITICAL for f in report.findings)
    assert any(f.code == "STRUCTURAL_MISSINGNESS_CLUSTER" for f in report.findings)
    assert not any(".median()" in (f.fix_snippet or "") and f.column == "group" for f in report.findings)
    assert report.overall_score > 70
    assert "simulation" in report.dataset_purpose.lower() or "scheduling" in report.dataset_purpose.lower()


def test_wc_all_editions_no_target_is_historical_archive(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_wc_all_editions_like(), "wc_all_editions.csv")

    assert report.dataset_type == "historical_archive"
    assert report.target_column is None
    assert report.supervised_ml_readiness == "N/A"
    assert report.integrity_score > 90
    assert 20 <= report.readiness_score <= 35
    assert 60 <= report.overall_score <= 80
    assert not any(f.engine == "imbalance" and f.category == "data_integrity" for f in report.findings)
    assert any(f.code == "NEAR_UNIQUE_FEATURE_CLUSTER" for f in report.findings)
    assert "historical" in report.dataset_purpose.lower()
    assert "not suitable for reliable supervised ml" in report.verdict.lower()


def test_true_leakage_still_scores_as_critical(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    rng = np.random.default_rng(25)
    n = 1000
    churn = rng.integers(0, 2, size=n)
    df = pd.DataFrame(
        {
            "tenure": rng.integers(1, 72, size=n),
            "monthly_charge": rng.normal(70, 10, size=n),
            "churn_date": np.where(churn == 1, "2025-01-01", ""),
            "final_status": np.where(churn == 1, "cancelled", "active"),
            "revenue_after_churn": np.where(churn == 1, 0, rng.normal(700, 50, size=n)),
            "churn": churn,
        }
    )

    report = dqi.analyze(df, "true_leaky.csv", target="churn")

    assert any(f.code.startswith("TARGET_LEAKAGE") and f.severity == Severity.CRITICAL for f in report.findings)
    assert report.readiness_score <= 40
    assert report.overall_score <= 60


def test_large_clean_explicit_target_is_supervised_ml(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(_large_clean_ml_df(), "large_clean.csv", target="churn")

    assert report.dataset_type == "supervised_tabular_ml"
    assert report.target_column == "churn"
    assert report.readiness_score > 75
    assert report.overall_score > 75
