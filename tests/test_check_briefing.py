import pytest

from check_briefing import (
    BriefingChecker,
    ParsedDocument,
    parse_html,
    parse_md,
)


def test_prompt_leakage():
    html = "<main>System prompt: do not include</main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_prompt_leakage(doc)
    assert not result.passed
    assert result.count >= 1


def test_guardrail_refusals():
    html = "<main>I'm sorry, but I can't help with that.</main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_guardrail_refusals(doc)
    assert not result.passed
    assert result.count == 1


def test_raw_urls_in_copy():
    html = "<main>Visit http://example.com for info</main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_raw_urls_in_copy(doc)
    assert not result.passed
    assert result.count == 1


def test_non_canonical_links():
    html = "<main><a href='https://feedbinusercontent.com/x'>bad</a></main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_non_canonical_links(doc)
    assert not result.passed
    assert result.count == 1


def test_generic_or_placeholder_link_text():
    html = "<main><a href='https://example.com'>Click here</a></main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_generic_or_placeholder_link_text(doc)
    assert not result.passed
    assert result.count == 1


def test_headline_style_inconsistencies_markdown():
    md = "## all lowercase heading\n## short"
    doc = parse_md(md, "src")
    checker = BriefingChecker()
    result = checker.rule_headline_style_inconsistencies(doc)
    assert not result.passed
    assert result.count == 2


def test_separators_and_spacing():
    html = "<main>***<h2>Bad  heading</h2></main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_separators_and_spacing(doc)
    assert not result.passed
    assert result.count == 2


def test_image_alt_captions():
    html = "<main><img src='x.jpg' alt='image'></main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_image_alt_captions(doc)
    assert not result.passed
    assert result.count == 1


def test_truncated_or_unbalanced_sentences():
    html = "<main>This is a very long sentence that goes on and on without proper ending and should be flagged \"quote</main>"
    doc = parse_html(html, "src")
    checker = BriefingChecker()
    result = checker.rule_truncated_or_unbalanced_sentences(doc)
    assert not result.passed
    assert result.count >= 1


def test_section_parity_with_golden():
    golden_html = "<main><h2>Alpha</h2><h3>Beta</h3></main>"
    doc_html = "<main><h2>Alpha</h2><h3>Gamma</h3></main>"
    golden = parse_html(golden_html, "golden")
    doc = parse_html(doc_html, "doc")
    checker = BriefingChecker(golden)
    result = checker.rule_section_parity_with_golden(doc)
    assert not result.passed
    assert result.count == 2
