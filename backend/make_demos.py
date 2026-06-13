"""Generate the three demo CSVs used by the app and tests.

  clean.csv  ~2000 rows, well-behaved             -> ~A/B
  messy.csv  ~3000 rows, many issues              -> ~C/D
  leaky.csv  ~2000 rows, obvious target leakage   -> F (CRITICAL leakage)

Deterministic (fixed seed) so tests and demos are reproducible.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
OUT = Path(__file__).resolve().parent / "data" / "demos"


def make_clean(n: int = 2000) -> pd.DataFrame:
    age = RNG.integers(18, 80, n)
    tenure = RNG.integers(0, 120, n)
    monthly = np.round(RNG.normal(70, 20, n).clip(10, 200), 2)
    plan = RNG.choice(["basic", "standard", "premium"], n, p=[0.5, 0.3, 0.2])
    region = RNG.choice(["north", "south", "east", "west"], n)
    support_calls = RNG.poisson(1.5, n)
    # A balanced-ish target with mild dependence on real features.
    logit = -1.0 + 0.02 * (tenure < 6) * 30 + 0.3 * support_calls - 0.01 * tenure
    prob = 1 / (1 + np.exp(-logit))
    churned = (RNG.random(n) < prob).astype(int)
    return pd.DataFrame(
        {
            "customer_age": age,
            "tenure_months": tenure,
            "monthly_charge": monthly,
            "plan": plan,
            "region": region,
            "support_calls": support_calls,
            "churned": churned,
        }
    )


def make_messy(n: int = 3000) -> pd.DataFrame:
    income = RNG.normal(60000, 20000, n)
    # Inject heavy outliers into ~10% of incomes.
    out_idx = RNG.choice(n, size=int(n * 0.10), replace=False)
    income[out_idx] = income[out_idx] * RNG.uniform(10, 30, len(out_idx))

    age = RNG.integers(18, 90, n).astype(float)
    # Missingness: age ~22% (HIGH), notes ~12% (MEDIUM).
    age[RNG.random(n) < 0.22] = np.nan
    notes = pd.Series(RNG.choice(["short", "long"], n), dtype=object)
    notes[RNG.random(n) < 0.12] = np.nan

    constant_col = np.ones(n)  # constant column
    region = RNG.choice(["north", "south", "east", "west"], n)

    visits = RNG.poisson(3, n)
    # Moderately imbalanced target (~12:1 -> HIGH, not CRITICAL).
    converted = (RNG.random(n) < 0.075).astype(int)

    df = pd.DataFrame(
        {
            "annual_income": np.round(income, 2),
            "age": age,
            "visits": visits,
            "region": region,
            "constant_flag": constant_col,
            "notes": notes,
            "converted": converted,
        }
    )
    # Inject exact duplicate rows (~3% -> MEDIUM band).
    dup = df.sample(int(n * 0.03), random_state=7)
    df = pd.concat([df, dup], ignore_index=True)
    return df


def make_leaky(n: int = 2000) -> pd.DataFrame:
    credit_score = RNG.integers(300, 850, n)
    loan_amount = np.round(RNG.normal(15000, 6000, n).clip(1000, 50000), 2)
    income = np.round(RNG.normal(55000, 18000, n).clip(8000, 200000), 2)
    employment_years = RNG.integers(0, 40, n)

    # The real (modest) signal.
    logit = -0.5 + (credit_score < 600) * 1.5 + (loan_amount > 20000) * 0.8 - employment_years * 0.02
    prob = 1 / (1 + np.exp(-logit))
    defaulted = (RNG.random(n) < prob).astype(int)

    # LEAKAGE 1: a near-perfect predictor (essentially the label, recorded post-outcome).
    collections_flag = defaulted.copy()
    flip = RNG.random(n) < 0.003  # 0.3% noise -> effectively the label
    collections_flag[flip] = 1 - collections_flag[flip]

    # LEAKAGE 2: a suspiciously-named score strongly correlated with the target.
    outcome_score = defaulted * 0.9 + RNG.normal(0, 0.05, n)

    # Secondary real-world issues a leaky export tends to ship with:
    # heavy missingness in a column, and exact duplicate rows.
    debt_to_income = RNG.normal(0.35, 0.1, n)
    debt_to_income[RNG.random(n) < 0.65] = np.nan  # ~65% missing -> CRITICAL missingness

    df = pd.DataFrame(
        {
            "credit_score": credit_score,
            "loan_amount": loan_amount,
            "annual_income": income,
            "employment_years": employment_years,
            "debt_to_income": np.round(debt_to_income, 4),
            "collections_flag": collections_flag,   # perfect-predictor leakage
            "outcome_score": np.round(outcome_score, 4),  # suspicious-name leakage
            "defaulted": defaulted,
        }
    )
    # Inject exact duplicate rows (~7%) -> duplicates engine + split-leak warning.
    dup = df.sample(int(n * 0.07), random_state=11)
    df = pd.concat([df, dup], ignore_index=True)
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_clean().to_csv(OUT / "clean.csv", index=False)
    make_messy().to_csv(OUT / "messy.csv", index=False)
    make_leaky().to_csv(OUT / "leaky.csv", index=False)
    print(f"Wrote demo CSVs to {OUT}")
    for f in ("clean.csv", "messy.csv", "leaky.csv"):
        p = OUT / f
        print(f"  {f}: {p.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
