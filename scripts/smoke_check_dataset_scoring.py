"""Smoke-check deterministic scoring calibration.

Run from the repository root:
    python scripts/smoke_check_dataset_scoring.py

Or through pytest:
    pytest tests/smoke_check_dataset_scoring.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import dqi  # noqa: E402


def make_tiny_clean_dataset() -> pd.DataFrame:
    rows = []
    results = [
        "Winner",
        "Runner-up",
        "Third place",
        "Fourth place",
        "Quarter-final",
        "Round of 16",
        "Group stage",
    ]
    for i in range(22):
        rows.append(
            {
                "player": f"Player {i:02d}",
                "team": f"Team {i % 16:02d}",
                "rank": i + 1,
                "goals": 9 - min(i // 3, 8),
                "assists": i % 6,
                "matches_played": 3 + (i % 5),
                "minutes": 160 + i * 19,
                "age": 19 + (i % 15),
                "position": ["Forward", "Midfielder", "Winger", "Striker"][i % 4],
                "final_score": f"{i % 5}-{(i + 2) % 4}",
                "team_result": results[i % len(results)],
            }
        )
    return pd.DataFrame(rows)


def make_large_clean_dataset(n: int = 5_000) -> pd.DataFrame:
    rng = np.random.default_rng(101)
    data = {
        f"feature_{i:02d}": rng.normal(loc=i * 0.1, scale=1.0, size=n)
        for i in range(12)
    }
    data.update(
        {
            "segment": rng.choice(["A", "B", "C", "D"], size=n),
            "region": rng.choice(["NE", "SE", "MW", "W", "SW"], size=n),
            "plan": rng.choice(["basic", "pro", "enterprise"], size=n),
        }
    )
    signal = data["feature_00"] + 0.7 * data["feature_01"] - 0.4 * data["feature_02"]
    data["target"] = (signal + rng.normal(0, 1.2, size=n) > 0).astype(int)
    return pd.DataFrame(data)


def make_dirty_but_learnable_dataset(n: int = 2_000) -> pd.DataFrame:
    rng = np.random.default_rng(202)
    data = {
        f"measure_{i:02d}": rng.normal(loc=0, scale=1, size=n)
        for i in range(17)
    }
    data.update(
        {
            "category_a": rng.choice(["low", "medium", "high"], size=n),
            "category_b": rng.choice(["north", "south", "east", "west"], size=n),
            "category_c": rng.choice(["new", "returning"], size=n),
        }
    )
    df = pd.DataFrame(data)

    for col in ["measure_00", "measure_03", "measure_06", "measure_09", "category_b"]:
        missing_idx = rng.choice(n, size=int(n * 0.10), replace=False)
        df.loc[missing_idx, col] = np.nan

    outlier_idx = rng.choice(n, size=140, replace=False)
    df.loc[outlier_idx, "measure_12"] = rng.normal(35, 4, size=len(outlier_idx))
    df["target"] = rng.choice([0, 1], size=n, p=[0.70, 0.30])
    return df


def make_leakage_dataset(n: int = 1_000) -> pd.DataFrame:
    rng = np.random.default_rng(303)
    churn = rng.choice([0, 1], size=n, p=[0.55, 0.45])
    return pd.DataFrame(
        {
            "monthly_fee": rng.normal(80, 18, size=n),
            "tenure_months": rng.integers(1, 84, size=n),
            "support_tickets": rng.poisson(1.4, size=n),
            "usage_score": rng.normal(0, 1, size=n),
            "churn_probability": churn,
            "final_status": np.where(churn == 1, "cancelled", "active"),
            "cancellation_date": np.where(churn == 1, "2025-12-31", ""),
            "revenue_after_churn": np.where(churn == 1, 0, rng.normal(900, 110, size=n)),
            "churn": churn,
        }
    )


def make_weak_target_support_dataset(n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(404)
    classes = [f"class_{i:02d}" for i in range(40)]
    target = classes * 2 + classes[:30] + list(rng.choice(classes[:10], size=n - 110))
    rng.shuffle(target)
    return pd.DataFrame(
        {
            "feature_00": rng.normal(size=n),
            "feature_01": rng.normal(size=n),
            "feature_02": rng.normal(size=n),
            "feature_03": rng.normal(size=n),
            "segment": rng.choice(["A", "B", "C"], size=n),
            "target_class": target,
        }
    )


def run_evaluation(df: pd.DataFrame, target: str | None):
    os.environ.pop("GROQ_API_KEY", None)
    return dqi.analyze(df, "smoke_check_dataset.csv", target=target)


def assert_score_range(name: str, actual: float, low: float, high: float) -> None:
    assert low <= actual <= high, f"{name}: expected {low}-{high}, got {actual}"


def _finding_text(findings) -> str:
    parts = []
    for f in findings:
        parts.extend([f.code, f.title, f.detail, f.impact, str(f.column or "")])
    return " ".join(parts).lower()


def assert_finding_contains(findings, required_terms: Iterable[str]) -> None:
    text = _finding_text(findings)
    missing = [term for term in required_terms if term.lower() not in text]
    assert not missing, f"Missing finding terms {missing}. Findings text was: {text[:1200]}"


def _print_report(name: str, report) -> None:
    print(f"\n=== {name} ===")
    print(f"Integrity: {report.integrity_score} ({report.integrity_grade}, {report.integrity_confidence})")
    print(f"Readiness: {report.readiness_score} ({report.readiness_grade}, {report.readiness_confidence})")
    print(f"Overall: {report.overall_score} ({report.overall_grade}, {report.overall_confidence})")
    print(f"Purpose: {report.dataset_purpose}")
    print(f"Verdict: {report.verdict}")
    print("Top findings:")
    for f in sorted(report.findings, key=lambda item: item.severity.rank)[:8]:
        col = f" [{f.column}]" if f.column else ""
        print(f"  - {f.severity.value.upper()} {f.code}{col}: {f.title}")


def check_tiny_clean_dataset() -> None:
    report = run_evaluation(make_tiny_clean_dataset(), "team_result")
    _print_report("Tiny clean dataset", report)
    assert_score_range("tiny integrity", report.integrity_score, 80, 100)
    assert_score_range("tiny readiness", report.readiness_score, 20, 50)
    assert_score_range("tiny overall", report.overall_score, 45, 70)
    assert report.readiness_score <= 55, "Old failure mode: tiny dataset readiness is inflated above 55"
    assert report.overall_score <= 70, "Old failure mode: tiny dataset overall score is inflated above 70"
    verdict = f"{report.verdict} {report.dataset_purpose}".lower()
    assert any(term in verdict for term in ("eda-only", "toy", "not suitable", "not suitable for reliable supervised ml"))
    assert report.readiness_confidence != "high"
    assert report.overall_confidence != "high"
    assert_finding_contains(report.findings, ["sample", "row", "unique", "target", "class", "leak"])


def check_large_clean_dataset() -> None:
    report = run_evaluation(make_large_clean_dataset(), "target")
    _print_report("Large clean classification dataset", report)
    assert_score_range("large integrity", report.integrity_score, 85, 100)
    assert_score_range("large readiness", report.readiness_score, 75, 100)
    assert_score_range("large overall", report.overall_score, 75, 100)
    verdict = f"{report.verdict} {report.dataset_purpose}".lower()
    assert any(term in verdict for term in ("trainable", "strong ml candidate", "ready for baseline"))
    assert "SMALL_SAMPLE_SIZE" not in {f.code for f in report.findings}
    assert "LOW_ROWS_PER_FEATURE" not in {f.code for f in report.findings}


def check_dirty_but_learnable_dataset() -> None:
    report = run_evaluation(make_dirty_but_learnable_dataset(), "target")
    _print_report("Dirty but learnable dataset", report)
    assert_score_range("dirty integrity", report.integrity_score, 55, 80)
    assert_score_range("dirty readiness", report.readiness_score, 65, 90)
    assert_score_range("dirty overall", report.overall_score, 60, 85)
    verdict = f"{report.verdict} {report.dataset_purpose}".lower()
    assert "eda-only" not in verdict
    assert "not suitable" not in verdict
    assert_finding_contains(report.findings, ["missing", "outlier"])
    assert "SMALL_SAMPLE_SIZE" not in {f.code for f in report.findings}


def check_leakage_dataset() -> None:
    report = run_evaluation(make_leakage_dataset(), "churn")
    _print_report("High leakage dataset", report)
    assert_finding_contains(report.findings, ["leak"])
    assert report.readiness_score <= 60
    assert report.readiness_confidence in {"low", "medium"}
    combined = f"{report.exec_summary} {_finding_text(report.findings)}".lower()
    assert "after" in combined or "outcome" in combined


def check_weak_target_support_dataset() -> None:
    report = run_evaluation(make_weak_target_support_dataset(), "target_class")
    _print_report("Many weak target classes dataset", report)
    assert_finding_contains(report.findings, ["target", "class"])
    assert report.readiness_score <= 60
    assert report.readiness_confidence in {"low", "medium"}
    verdict = f"{report.verdict} {report.dataset_purpose} {report.exec_summary}".lower()
    assert any(term in verdict for term in ("unreliable", "not suitable", "eda", "toy", "caution"))


def run_smoke_check() -> None:
    check_tiny_clean_dataset()
    check_large_clean_dataset()
    check_dirty_but_learnable_dataset()
    check_leakage_dataset()
    check_weak_target_support_dataset()
    print("\nSmoke check passed: scoring separates data cleanliness from ML learnability.")


def test_smoke_check_dataset_scoring() -> None:
    run_smoke_check()


if __name__ == "__main__":
    run_smoke_check()
