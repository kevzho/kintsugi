"""Kintsugi — pure analytics library (no web framework imports)."""
from __future__ import annotations

from .pipeline import analyze, analyze_csv_bytes
from .report import Finding, Report, Severity

__all__ = ["analyze", "analyze_csv_bytes", "Report", "Finding", "Severity"]
