from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.smoke_check_dataset_scoring import run_smoke_check


def test_smoke_check_dataset_scoring() -> None:
    run_smoke_check()
