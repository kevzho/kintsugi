from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fix_code_block_renders_pre_code_and_copy_button():
    source = (ROOT / "frontend" / "components" / "FixCodeBlock.tsx").read_text()

    assert "<pre" in source
    assert "<code" in source
    assert "navigator.clipboard.writeText(code)" in source
    assert 'data-testid="fix-code-block"' in source
    assert "dangerouslySetInnerHTML" in source


def test_results_and_findings_do_not_render_fix_code_as_plain_paragraphs():
    results = (ROOT / "frontend" / "components" / "Results.tsx").read_text()
    finding = (ROOT / "frontend" / "components" / "FindingCard.tsx").read_text()

    assert "<FixCodeBlock fix={rec.fix}" in results
    assert '<FixCodeBlock fix={{ type: "python", code: finding.fix_snippet }}' in finding
    assert "{rec}</span>" not in results
    assert "Copy fix" not in finding


def test_smoke_code_examples_are_supported_by_structured_schema():
    types = (ROOT / "frontend" / "lib" / "types.ts").read_text()
    markdown = (ROOT / "frontend" / "lib" / "markdown.ts").read_text()

    assert "export interface FixCode" in types
    assert "code: string" in types
    assert "fix: FixCode | null" in types
    assert "rec.fix.code" in markdown
    assert "```" in markdown
