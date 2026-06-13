"""Row sampling to keep analysis fast on large datasets."""
from __future__ import annotations

import pandas as pd

from .. import config


def maybe_sample(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Return (df, sampled). Down-samples to MAX_ROWS_ANALYZED deterministically."""
    if len(df) > config.MAX_ROWS_ANALYZED:
        sampled = df.sample(
            config.MAX_ROWS_ANALYZED, random_state=config.SAMPLE_RANDOM_STATE
        ).reset_index(drop=True)
        return sampled, True
    return df, False
