"""Analytics engines. Each subclasses Engine and returns List[Finding]."""
from __future__ import annotations

from .correlation import CorrelationEngine
from .duplicates import DuplicatesEngine
from .feature_quality import FeatureQualityEngine
from .imbalance import ImbalanceEngine
from .leakage import LeakageEngine
from .missingness import MissingnessEngine
from .model_readiness import ModelReadinessEngine
from .outliers import OutliersEngine

ALL_ENGINES = [
    MissingnessEngine(),
    DuplicatesEngine(),
    ImbalanceEngine(),
    ModelReadinessEngine(),
    OutliersEngine(),
    LeakageEngine(),
    FeatureQualityEngine(),
    CorrelationEngine(),
]

__all__ = [
    "ALL_ENGINES",
    "MissingnessEngine",
    "DuplicatesEngine",
    "ImbalanceEngine",
    "ModelReadinessEngine",
    "OutliersEngine",
    "LeakageEngine",
    "FeatureQualityEngine",
    "CorrelationEngine",
]
