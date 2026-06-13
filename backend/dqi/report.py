"""Core data contracts for Data Quality IQ.

These dataclasses are the spine of the entire system. Every engine returns
List[Finding]; the pipeline aggregates them into a Report. The frontend and
the AI layer both consume the JSON form of these objects.

IMPORTANT: nothing in this module (or anywhere in `dqi/`) may import a web
framework. The engine is a pure library so it can be served by FastAPI today
and reused as a CLI / GitHub Action / library later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    CRITICAL = "critical"  # will break or invalidate ML results
    HIGH = "high"          # materially hurts model quality
    MEDIUM = "medium"      # worth fixing
    LOW = "low"            # minor
    INFO = "info"          # informational only

    @property
    def rank(self) -> int:
        order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        return order[self]


@dataclass
class Finding:
    """A single data-quality issue discovered by an engine."""
    engine: str                          # e.g. "leakage"
    code: str                            # stable machine code, e.g. "TARGET_LEAKAGE_PERFECT_PREDICTOR"
    severity: Severity
    title: str                           # human-readable headline
    detail: str                          # deterministic technical explanation
    impact: str                          # downstream ML consequence
    column: Optional[str] = None         # column the finding relates to (if any)
    fix_snippet: Optional[str] = None    # copy-pasteable pandas fix
    metrics: dict[str, Any] = field(default_factory=dict)  # numbers for charts / LLM
    score_penalty: float = 0.0           # filled by scoring layer
    integrity_penalty: float = 0.0       # filled by scoring layer
    readiness_penalty: float = 0.0       # filled by scoring layer
    category: str = "data_integrity"     # or "modeling_warning"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class Report:
    """The complete analysis result for one dataset."""
    dataset_name: str
    n_rows: int
    n_cols: int
    n_rows_analyzed: int                 # may be < n_rows if sampled
    sampled: bool
    target_column: Optional[str]
    health_score: float                  # 0-100
    grade: str                           # A-F
    integrity_score: float
    integrity_grade: str
    readiness_score: float
    readiness_grade: str
    overall_score: float
    overall_grade: str
    verdict: str
    dataset_type: str
    findings: list[Finding]
    schema: dict[str, Any]               # column profiles
    fingerprint: str                     # cache key
    severity_counts: dict[str, int] = field(default_factory=dict)
    modeling_warnings: list[Finding] = field(default_factory=list)
    exec_summary: str = ""               # filled by AI layer
    recommendations: list[str] = field(default_factory=list)  # AI-enriched, ordered
    ai_available: bool = True            # False if Groq was unavailable (graceful degradation)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        d["modeling_warnings"] = [f.to_dict() for f in self.modeling_warnings]
        return d
