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
        "Slack. State the grade, the single most important risk, and whether the data is "
        "fit to train on yet.\n"
        '  "recommendations": an ordered list (max 5) of the highest-impact actions. Each '
        "item is a single string formatted as \"<what to do> — <why it matters for the model> "
        "— `<one-line pandas snippet>`\".\n\n"
        "Prioritize CRITICAL leakage and label issues first. Return STRICT JSON only:\n"
        '{"exec_summary": "...", "recommendations": ["...", "..."]}'
    )
