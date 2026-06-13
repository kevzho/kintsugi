"""Central configuration: all thresholds, weights, and limits live here so the
engine's behavior is tunable in one place (no magic numbers scattered around).
"""
from __future__ import annotations

from .report import Severity

# ---------------------------------------------------------------------------
# Input limits (enforced before any processing — abuse/OOM prevention)
# ---------------------------------------------------------------------------
MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS_ANALYZED = 100_000          # sample beyond this
MAX_COLS = 200
SAMPLE_RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Schema inference
# ---------------------------------------------------------------------------
# A column is "id-like" if its distinct ratio exceeds this (near-unique).
ID_CARDINALITY_RATIO = 0.95
# A categorical is "high cardinality" above this many distinct values.
HIGH_CARDINALITY_ABS = 50
HIGH_CARDINALITY_RATIO = 0.5

# ---------------------------------------------------------------------------
# Missingness thresholds (null rate per column)
# ---------------------------------------------------------------------------
MISSING_CRITICAL = 0.60
MISSING_HIGH = 0.20
MISSING_MEDIUM = 0.05
COMISSING_CORR = 0.85   # correlation of null-masks indicating structural missingness

# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------
DUP_HIGH_RATE = 0.05    # >5% exact duplicate rows -> HIGH

# ---------------------------------------------------------------------------
# Imbalance (target must be selected + categorical-ish)
# ---------------------------------------------------------------------------
IMBALANCE_HIGH_RATIO = 10      # majority/minority
IMBALANCE_CRITICAL_RATIO = 100

# ---------------------------------------------------------------------------
# Outliers
# ---------------------------------------------------------------------------
OUTLIER_IQR_K = 1.5
OUTLIER_Z = 3.5                 # robust z (median/MAD)
OUTLIER_MEDIUM_RATE = 0.05
OUTLIER_HIGH_RATE = 0.15

# ---------------------------------------------------------------------------
# Leakage heuristics
# ---------------------------------------------------------------------------
LEAKAGE_MI_CRITICAL = 0.98      # near-perfect predictor of target
LEAKAGE_CORR_SUSPICIOUS = 0.70  # combined with suspicious name -> HIGH
LEAKAGE_NAME_PATTERN = (
    r"(target|label|outcome|result|score|prediction|predicted|"
    r"is_|_flag|flag_|future_|post_|_after|ground_truth|gt_|y_true)"
)
LEAKAGE_SAMPLE_ROWS = 20_000    # cap rows for mutual_info to keep it fast

# ---------------------------------------------------------------------------
# Feature quality
# ---------------------------------------------------------------------------
NEAR_ZERO_VARIANCE_RATIO = 0.99   # one value covers >=99% of rows -> quasi-constant
NEAR_DUPLICATE_CORR = 0.99        # two numeric columns essentially identical

# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------
STRONG_CORR = 0.90

# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------
SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 12.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.0,
}
CATEGORY_CAP = 40.0   # max total penalty any single engine can contribute

GRADE_BANDS = [(90, "A"), (75, "B"), (60, "C"), (45, "D"), (0, "F")]

# ---------------------------------------------------------------------------
# AI layer
# ---------------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.2
GROQ_MAX_TOKENS = 1200
TOP_FINDINGS_FOR_LLM = 15      # never send more than this to the LLM


def grade_for(score: float) -> str:
    for threshold, letter in GRADE_BANDS:
        if score >= threshold:
            return letter
    return "F"
