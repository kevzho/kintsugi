"""Shared fixtures: build the demo dataframes from the generator (no LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import make_demos  # noqa: E402


@pytest.fixture(scope="session")
def clean_df():
    return make_demos.make_clean()


@pytest.fixture(scope="session")
def messy_df():
    return make_demos.make_messy()


@pytest.fixture(scope="session")
def leaky_df():
    return make_demos.make_leaky()
