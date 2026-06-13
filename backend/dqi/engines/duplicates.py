"""Duplicates engine: exact duplicate rows + duplicate IDs with label noise."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import config
from ..report import Finding, Severity
from .base import Engine


class DuplicatesEngine(Engine):
    name = "duplicates"

    def run(self, df: pd.DataFrame, schema: dict, target: Optional[str] = None) -> list[Finding]:
        findings: list[Finding] = []
        n = len(df)
        if n == 0:
            return findings

        dup_mask = df.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        dup_rate = dup_count / n if n else 0.0

        if dup_count > 0:
            sev = Severity.HIGH if dup_rate >= config.DUP_HIGH_RATE else Severity.MEDIUM
            pct = round(dup_rate * 100, 1)
            findings.append(
                Finding(
                    engine=self.name,
                    code="EXACT_DUPLICATE_ROWS",
                    severity=sev,
                    title=f"{dup_count} exact duplicate rows ({pct}%)",
                    detail=f"{dup_count} of {n} rows are byte-for-byte duplicates of an earlier row.",
                    impact=(
                        "Duplicate rows inflate apparent sample size and leak between "
                        "train/test on a random split, producing optimistic metrics that "
                        "won't hold in production."
                    ),
                    column=None,
                    fix_snippet="df = df.drop_duplicates().reset_index(drop=True)",
                    metrics={"dup_count": dup_count, "dup_rate": round(dup_rate, 4)},
                )
            )

        # Duplicate IDs with differing target -> label noise (CRITICAL).
        cols = schema.get("columns", {})
        id_cols = [c for c, p in cols.items() if p.get("is_id_like") and c != target]
        if target and target in df.columns:
            for idc in id_cols:
                try:
                    grp = df[[idc, target]].dropna()
                    if grp.empty:
                        continue
                    nunique_targets = grp.groupby(idc)[target].nunique()
                    conflicting = int((nunique_targets > 1).sum())
                    if conflicting > 0:
                        findings.append(
                            Finding(
                                engine=self.name,
                                code="DUPLICATE_ID_LABEL_NOISE",
                                severity=Severity.CRITICAL,
                                title=f"{conflicting} IDs in '{idc}' map to multiple '{target}' values",
                                detail=(
                                    f"{conflicting} distinct values of the id-like column '{idc}' "
                                    f"appear with more than one '{target}' label."
                                ),
                                impact=(
                                    "The same entity has contradictory labels — this is label "
                                    "noise that caps achievable accuracy and confuses any model "
                                    "keyed on this identifier."
                                ),
                                column=idc,
                                fix_snippet=(
                                    f"# Inspect conflicting ids, then resolve (dedupe/majority vote)\n"
                                    f"conf = df.groupby({idc!r})[{target!r}].nunique()\n"
                                    f"print(conf[conf > 1])"
                                ),
                                metrics={"conflicting_ids": conflicting},
                            )
                        )
                except Exception:
                    continue

        return findings
