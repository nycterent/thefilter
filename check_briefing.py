from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class ParsedDocument:
    source: str
    text: str
    headings: List[Tuple[int, str]]
    raw_headings: List[str]
    anchors: List[Tuple[str, str]]
    images: List[Tuple[str, Optional[str]]]


@dataclass
class RuleResult:
    name: str
    passed: bool
    count: int
    examples: List[str]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_html(content: str, source: str) -> ParsedDocument:
    soup = BeautifulSoup(content, "lxml")
    container = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = normalize_whitespace(container.get_text(" "))

    headings: List[Tuple[int, str]] = []
    raw_headings: List[str] = []
    for level in range(1, 7):
        for tag in container.find_all(f"h{level}"):
            raw = tag.get_text(" ")
            raw_headings.append(raw)
            headings.append((level, normalize_whitespace(raw)))

    anchors: List[Tuple[str, str]] = []
    for a in container.find_all("a"):
        href = a.get("href", "")
        anchors.append((href, normalize_whitespace(a.get_text(" "))))

    images: List[Tuple[str, Optional[str]]] = []
    for img in container.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt")
        images.append((src, normalize_whitespace(alt) if alt is not None else None))

    return ParsedDocument(
        source=source,
        text=text,
        headings=headings,
        raw_headings=raw_headings,
        anchors=anchors,
        images=images,
    )


def parse_md(content: str, source: str) -> ParsedDocument:
    headings: List[Tuple[int, str]] = []
    raw_headings: List[str] = []
    anchors: List[Tuple[str, str]] = []
    images: List[Tuple[str, Optional[str]]] = []
    text_lines: List[str] = []

    for line in content.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            raw = heading_match.group(2)
            heading_text = normalize_whitespace(raw)
            headings.append((level, heading_text))
            raw_headings.append(raw)
            text_lines.append(heading_text)
            continue

        def replace_image(match: re.Match) -> str:
            alt, src = match.group(1), match.group(2)
            images.append((src, normalize_whitespace(alt)))
            return alt

        line = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, line)

        def replace_link(match: re.Match) -> str:
            text, href = match.group(1), match.group(2)
            anchors.append((href, normalize_whitespace(text)))
            return text

        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, line)
        text_lines.append(line)

    text = normalize_whitespace(" ".join(text_lines))
    return ParsedDocument(
        source=source,
        text=text,
        headings=headings,
        raw_headings=raw_headings,
        anchors=anchors,
        images=images,
    )


class BriefingChecker:
    def __init__(self, golden: Optional[ParsedDocument] = None) -> None:
        self.golden = golden
        self.rules: List[Callable[[ParsedDocument], RuleResult]] = [
            self.rule_prompt_leakage,
            self.rule_guardrail_refusals,
            self.rule_raw_urls_in_copy,
            self.rule_non_canonical_links,
            self.rule_generic_or_placeholder_link_text,
            self.rule_headline_style_inconsistencies,
            self.rule_separators_and_spacing,
            self.rule_image_alt_captions,
            self.rule_truncated_or_unbalanced_sentences,
        ]
        if golden is not None:
            self.rules.append(self.rule_section_parity_with_golden)

    # Rule implementations
    def rule_prompt_leakage(self, doc: ParsedDocument) -> RuleResult:
        patterns = [
            r"hint to ai",
            r"system prompt",
            r"\buser:\b",
            r"\bassistant:\b",
            r"as an ai language model",
            r"do not (?:include|output|mention)",
        ]
        matches: List[str] = []
        for pat in patterns:
            for m in re.finditer(pat, doc.text, re.IGNORECASE):
                snippet = doc.text[max(0, m.start() - 20) : m.end() + 20]
                matches.append(snippet.strip())
        return RuleResult("prompt_leakage", not matches, len(matches), matches[:5])

    def rule_guardrail_refusals(self, doc: ParsedDocument) -> RuleResult:
        patterns = [
            r"i['’]m sorry, but i can[’']t",
            r"i cannot comply",
            r"i can['’]t provide[^.]*?(illegal|harmful|dangerous|weapons|self-harm|malware|adult)",
            r"i am just an ai model",
            r"not within my programming",
            r"particularly when it involves minors",
        ]
        matches: List[str] = []
        for pat in patterns:
            for m in re.finditer(pat, doc.text, re.IGNORECASE):
                snippet = doc.text[max(0, m.start() - 20) : m.end() + 20]
                matches.append(snippet.strip())
        return RuleResult("guardrail_refusals", not matches, len(matches), matches[:5])

    def rule_raw_urls_in_copy(self, doc: ParsedDocument) -> RuleResult:
        scheme_pattern = re.compile(r"https?://\S+", re.IGNORECASE)
        domain_pattern = re.compile(r"\b[a-zA-Z0-9.-]+\.[a-z]{2,}/?\S*", re.IGNORECASE)
        scheme_matches = [m.group(0) for m in scheme_pattern.finditer(doc.text)]
        matches: List[str] = list(scheme_matches)
        for m in domain_pattern.finditer(doc.text):
            url = m.group(0)
            if (
                not url.startswith("http://")
                and not url.startswith("https://")
                and not url.startswith("www.")
                and all(url not in s for s in scheme_matches)
            ):
                matches.append(url)
        for _, text in doc.anchors:
            if scheme_pattern.fullmatch(text) or (
                domain_pattern.fullmatch(text)
                and not text.startswith("http://")
                and not text.startswith("https://")
                and not text.startswith("www.")
            ):
                if text not in matches:
                    matches.append(text)
        return RuleResult("raw_urls_in_copy", not matches, len(matches), matches[:5])

    def rule_non_canonical_links(self, doc: ParsedDocument) -> RuleResult:
        bad_hosts = {
            "feedbinusercontent.com",
            "substackcdn.com",
            "cdn.substack.com",
            "list-manage.com",
        }
        matches: List[str] = []
        for href, _ in doc.anchors:
            host = urlparse(href).hostname or ""
            if any(host.endswith(bad) for bad in bad_hosts):
                matches.append(href)
        return RuleResult("non_canonical_links", not matches, len(matches), matches[:5])

    def rule_generic_or_placeholder_link_text(self, doc: ParsedDocument) -> RuleResult:
        generic = {
            "link",
            "source",
            "read more",
            "article",
            "newsletters",
            "url",
            "url1",
            "url2",
            "url3",
            "visit",
            "here",
            "click here",
        }
        matches: List[str] = []
        for _, text in doc.anchors:
            t = text.strip().lower()
            if t in generic or re.fullmatch(r"url\d+", t):
                matches.append(text)
        return RuleResult(
            "generic_or_placeholder_link_text", not matches, len(matches), matches[:5]
        )

    def rule_headline_style_inconsistencies(self, doc: ParsedDocument) -> RuleResult:
        matches: List[str] = []
        for _, text in doc.headings:
            letters = "".join(ch for ch in text if ch.isalpha())
            if letters and letters.islower():
                matches.append(text)
                continue
            if len(text.split()) <= 2 and len(text.replace(" ", "")) < 10:
                matches.append(text)
            if re.search(
                r"\bfuck\b|\bshit\b|\bbitch\b|\bdamn\b|\bass\b", text, re.IGNORECASE
            ):
                matches.append(text)
        return RuleResult(
            "headline_style_inconsistencies", not matches, len(matches), matches[:5]
        )

    def rule_separators_and_spacing(self, doc: ParsedDocument) -> RuleResult:
        matches: List[str] = []
        for m in re.finditer(r"(\*\s*){3,}", doc.text):
            matches.append(m.group(0))
        for raw in doc.raw_headings:
            if "  " in raw:
                matches.append(raw)
        return RuleResult(
            "separators_and_spacing", not matches, len(matches), matches[:5]
        )

    def rule_image_alt_captions(self, doc: ParsedDocument) -> RuleResult:
        generic = {"image", "photo", "picture", "graphic"}
        matches: List[str] = []
        sources: List[str] = []
        for src, alt in doc.images:
            sources.append(src)
            if (
                not alt
                or len(alt) < 5
                or alt.lower() in generic
                or alt.lower().startswith("image: professional illustration depicting")
            ):
                matches.append(src or alt or "<missing>")
        # Duplicate image sources
        from collections import Counter

        dupes = [url for url, count in Counter(sources).items() if count > 1]
        matches.extend(dupes)
        return RuleResult("image_alt_captions", not matches, len(matches), matches[:5])

    def rule_truncated_or_unbalanced_sentences(self, doc: ParsedDocument) -> RuleResult:
        sentences = re.split(r"(?<=[.!?])\s+", doc.text)
        matches: List[str] = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 60 and not re.search(r"""[.!?]['")\]]?$""", s):
                matches.append(s[:80])
            if (
                re.search(r":\s*$", s)
                or re.search(r"\([^\)]*$", s)
                or re.search(r"\b\w{1,2}$", s)
            ):
                matches.append(s[:80])
        if doc.text.count("(") != doc.text.count(")"):
            matches.append("unbalanced parentheses")
        if doc.text.count("“") != doc.text.count("”"):
            matches.append("unbalanced quotes")
        if doc.text.count('"') % 2 != 0:
            matches.append("unbalanced quotes")
        return RuleResult(
            "truncated_or_unbalanced_sentences", not matches, len(matches), matches[:5]
        )

    def rule_section_parity_with_golden(self, doc: ParsedDocument) -> RuleResult:
        if not self.golden:
            return RuleResult("section_parity_with_golden", True, 0, [])
        golden_set = {
            text.lower() for level, text in self.golden.headings if level in (2, 3)
        }
        doc_set = {text.lower() for level, text in doc.headings if level in (2, 3)}
        missing = sorted(golden_set - doc_set)
        extra = sorted(doc_set - golden_set)
        examples: List[str] = []
        for m in missing:
            examples.append(f"missing: {m}")
        for e in extra:
            examples.append(f"extra: {e}")
        count = len(missing) + len(extra)
        return RuleResult("section_parity_with_golden", count == 0, count, examples[:5])

    def check(self, doc: ParsedDocument) -> Tuple[bool, List[RuleResult]]:
        results = [rule(doc) for rule in self.rules]
        passed = all(r.passed for r in results)
        return passed, results


def load_source(source: str) -> ParsedDocument:
    if re.match(r"https?://", source):
        if "null" in source.lower() or source.endswith("/null"):
            raise ValueError(f"Invalid URL - contains 'null': {source}")
        resp = requests.get(source, timeout=30)
        resp.raise_for_status()
        return parse_html(resp.text, source)

    path = Path(source)
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".md", ".markdown"}:
        return parse_md(content, source)
    return parse_html(content, source)


def print_report(source: str, passed: bool, results: List[RuleResult]) -> None:
    print(f"Source: {source}")
    print(f"Overall: {'PASS' if passed else 'FAIL'}")
    header = f"{'Rule':40} {'Result':7} {'Count':5}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r.name:40} {'OK' if r.passed else 'FAIL':7} {r.count:5}")
    for r in results:
        if not r.passed and r.examples:
            print(f"\nExamples for {r.name}:")
            for ex in r.examples[:5]:
                print(f"- {ex}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lint-check Curated Briefing newsletters"
    )
    parser.add_argument("inputs", nargs="+", help="URLs or local HTML/MD files")
    parser.add_argument("--golden", help="URL or file of known good briefing")
    parser.add_argument("--json", dest="json_path", help="Path to save JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    golden_doc: Optional[ParsedDocument] = None
    if args.golden:
        try:
            golden_doc = load_source(args.golden)
        except Exception as e:  # noqa: BLE001
            parser.error(f"Failed to load golden source: {e}")

    checker = BriefingChecker(golden_doc)
    reports = []
    for src in args.inputs:
        try:
            if args.verbose:
                print(f"📥 Loading source: {src}")
            doc = load_source(src)
            if args.verbose:
                print(f"📄 Document loaded: {len(doc.text)} characters")
            passed, results = checker.check(doc)
            print_report(src, passed, results)
            if args.verbose:
                print(f"✅ Validation {'passed' if passed else 'failed'} for {src}")
                for result in results:
                    if not result.passed and result.examples:
                        print(f"  ⚠️  {result.name}: {result.examples[:3]}")  # Show first 3 examples
            reports.append(
                {
                    "source": src,
                    "passed": passed,
                    "results": [r.__dict__ for r in results],
                    "summary": {
                        r.name: {"pass": r.passed, "count": r.count} for r in results
                    },
                }
            )
        except Exception as e:  # noqa: BLE001
            print(f"Error processing {src}: {e}")

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump({"reports": reports}, f, indent=2)

    if not all(r["passed"] for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
