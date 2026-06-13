"""Engine abstract base class. Every analytics engine subclasses this and
returns a list of Findings. Engines are pure functions of (df, schema, target)
and must never raise — wrap risky logic in try/except and degrade gracefully so
one bad column can't crash the whole analysis.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from ..report import Finding


class Engine(ABC):
    name: str = "base"

    @abstractmethod
    def run(
        self,
        df: pd.DataFrame,
        schema: dict,
        target: Optional[str] = None,
    ) -> list[Finding]:
        ...

    def safe_run(
        self,
        df: pd.DataFrame,
        schema: dict,
        target: Optional[str] = None,
    ) -> list[Finding]:
        """Never-raise wrapper used by the pipeline."""
        try:
            return self.run(df, schema, target)
        except Exception as exc:  # pragma: no cover - defensive
            import logging

            logging.getLogger("dqi").warning(
                "engine %s failed: %s", self.name, exc, exc_info=False
            )
            return []
