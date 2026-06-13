"""Prompt templates for the LLM layer. The model only ever sees computed
diagnostics — never raw data rows.
"""
from __future__ import annotations

import json

SYSTEM = (
    "You are a senior machine-learning data-quality expert reviewing an automated "
    "diagnostic report. You are given ONLY computed diagnostics (no raw data rows). "
    "Never invent numbers — use only the metrics provided. For each issue, explain the "
    "concrete downstream consequence for model training/serving and give a precise fix. "
    "Be specific, technical, and concise; write for an ML engineer. "
    "Respond with STRICT JSON only — no markdown, no prose outside the JSON object."
)


def build_user_prompt(context_json: dict) -> str:
    ctx = json.dumps(context_json, indent=2, default=str)
    return (
        "Here is the deterministic data-quality report for a dataset:\n\n"
        f"{ctx}\n\n"
        "Produce a JSON object with EXACTLY these keys:\n"
        '  "exec_summary": a 3-4 sentence executive summary an engineer could paste into '
        "Slack. State the grade, the single most important risk, and calibrated model-readiness language.\n"
        '  "recommendations": an ordered list (max 5) of objects with keys '
        '"title", "why", and optional "fix". "fix" must be an object like '
        '{"type":"python","code":"df.drop(columns=[\'edition\'], inplace=True)"}. '
        "Do not put markdown backticks inside fix.code.\n\n"
        "Prioritize CRITICAL leakage and label issues first. Return STRICT JSON only:\n"
        '{"exec_summary": "...", "recommendations": [{"title":"...", "why":"...", "fix":{"type":"python", "code":"..."}}]}'
    )
