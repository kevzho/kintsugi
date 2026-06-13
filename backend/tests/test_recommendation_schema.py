from __future__ import annotations

import dqi


def test_recommendations_use_structured_fix_schema(messy_df, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    report = dqi.analyze(messy_df, "messy.csv", target="converted")
    payload = report.to_dict()

    assert payload["recommendations"]
    with_fix = [rec for rec in payload["recommendations"] if rec.get("fix")]
    assert with_fix, "expected at least one recommendation with structured fix code"

    fix = with_fix[0]["fix"]
    assert set(fix) == {"type", "code"}
    assert fix["type"] in {"python", "pandas", "sklearn", "sql", "plaintext"}
    assert isinstance(fix["code"], str)
    assert fix["code"].strip()
    assert "`" not in fix["code"], "fix code should not rely on markdown backticks"
