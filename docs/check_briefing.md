# Curated Briefing Checker

A small CLI tool to lint-check "Curated Briefing" newsletters before publishing.

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/check_briefing.py --golden GOLDEN_URL_OR_FILE newsletter.html
```

## Rules

1. **prompt_leakage** – prompts or role tags like `user:` or `assistant:`.
2. **guardrail_refusals** – boilerplate refusals such as "I'm sorry, but I can't...".
3. **raw_urls_in_copy** – bare URLs or links whose text is a URL.
4. **non_canonical_links** – links to `feedbinusercontent.com`, `substackcdn.com`, `cdn.substack.com`.
5. **generic_or_placeholder_link_text** – anchors with text like `click here` or `source`.
6. **headline_style_inconsistencies** – lowercase or overly short headings.
7. **separators_and_spacing** – repeated separators (`***`) or headings with double spaces.
8. **image_alt_captions** – missing, short, or generic image alt text.
9. **truncated_or_unbalanced_sentences** – long sentences without terminal punctuation or unbalanced quotes/parentheses.
10. **section_parity_with_golden** – h2/h3 differences compared to a golden briefing.

## Example

```bash
python scripts/check_briefing.py --golden https://buttondown.com/filter/archive/curated-briefing-001 \
    https://buttondown.com/filter/archive/curated-briefing-026/ \
    --json report.json
```

## CI Tip

Add a job to your GitHub Actions workflow:

```yaml
- name: Lint Curated Briefing
  run: |
    pip install -r requirements.txt
    python scripts/check_briefing.py --golden $GOLDEN_URL path/to/briefing.html
```
