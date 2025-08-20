"""Quality assurance checks for newsletter content."""

import json
import re
import sys
from pathlib import Path
from typing import Dict


def run_checks(text: str) -> Dict[str, any]:
    """Run all QA checks on newsletter content.

    Args:
        text: Newsletter content (HTML or Markdown)

    Returns:
        Dictionary with check results and overall pass/fail status
    """
    results = []
    critical_results = []
    warning_results = []

    # Check 1: Prompt/meta leakage and guardrail refusals (CRITICAL)
    leakage_result = check_prompt_leakage(text)
    results.append(leakage_result)
    critical_results.append(leakage_result)

    # Check 2: Raw URLs in copy (WARNING - common in newsletters)
    url_result = check_raw_urls(text)
    url_result["severity"] = "warning"  # Mark as warning, not critical
    results.append(url_result)
    warning_results.append(url_result)

    # Check 3: Non-canonical links (WARNING - may be acceptable)
    canonical_result = check_canonical_links(text)
    canonical_result["severity"] = "warning"
    results.append(canonical_result)
    warning_results.append(canonical_result)

    # Check 4: Generic link labels (WARNING)
    link_result = check_generic_links(text)
    link_result["severity"] = "warning"
    results.append(link_result)
    warning_results.append(link_result)

    # Check 5: Truncated/unbalanced content (WARNING - markdown rules can trigger false positives)
    truncation_result = check_truncation(text)
    truncation_result["severity"] = "warning"  # Mark as warning, not critical
    results.append(truncation_result)

    # Check 6: Markdown formatting issues (WARNING)
    formatting_result = check_markdown_formatting(text)
    formatting_result["severity"] = "warning"
    results.append(formatting_result)
    warning_results.append(formatting_result)

    # Only fail if CRITICAL checks fail - warnings don't block publication
    critical_passed = all(result["passed"] for result in critical_results)

    # Count warnings for reporting
    warning_count = sum(1 for r in warning_results if not r["passed"])

    return {
        "passed": critical_passed,  # Only critical checks must pass
        "results": results,
        "summary": {
            "total_checks": len(results),
            "passed_checks": sum(1 for r in results if r["passed"]),
            "failed_checks": sum(1 for r in results if not r["passed"]),
            "critical_failed": sum(1 for r in critical_results if not r["passed"]),
            "warnings": warning_count,
        },
    }


def check_prompt_leakage(text: str) -> Dict[str, any]:
    """Check for AI prompt leakage or guardrail refusals."""
    patterns = [
        r"as an ai",
        r"i am an ai",
        r"i cannot fulfill",
        r"i cannot create content",
        r"ethical guidelines",
        r"i'm unable to",
        r"i cannot help",
        r"it is not within my programming",
        r"i am just an ai model",
        r"i can't provide assistance",
        r"i'm not able to",
        r"particularly when it involves",
        r"i'll never tire of hearing",
        r"i couldn't help but",
        r"it's a fascinating",
        r"what's interesting",
        r"what makes this",
        r"here's what",
        r"let me tell you",
        r"picture this",
        r"imagine if",
    ]

    issues = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            issues.append(
                {
                    "pattern": pattern,
                    "position": match.start(),
                    "context": text[max(0, match.start() - 20) : match.end() + 20],
                }
            )

    return {
        "name": "Prompt Leakage & Guardrail Refusals",
        "passed": len(issues) == 0,
        "issues": issues,
        "description": "Check for AI model artifacts and refusal patterns",
    }


def check_raw_urls(text: str) -> Dict[str, any]:
    """Check for raw URLs in content that should be properly linked."""
    # Look for URLs that aren't in HTML anchor tags or markdown links
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

    # Find all URLs
    all_urls = re.findall(url_pattern, text)

    # Find URLs in HTML links
    html_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', text)

    # Find URLs in image src attributes (these are valid, not "raw URLs")
    img_src_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', text)

    # Find URLs in markdown links - extract the URL part
    markdown_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    markdown_urls = [url for _, url in markdown_links]

    # Raw URLs are those not in proper link format (excluding image sources)
    linked_urls = set(html_links + markdown_urls + img_src_urls)
    raw_urls = []

    for url in all_urls:
        # Check if this URL is part of a markdown or HTML link
        is_linked = False
        for linked_url in linked_urls:
            if url in linked_url or linked_url in url:
                is_linked = True
                break

        if not is_linked:
            raw_urls.append(url)

    issues = []
    for url in raw_urls:
        # Find position of raw URL
        pos = text.find(url)
        issues.append(
            {
                "url": url,
                "position": pos,
                "context": text[max(0, pos - 20) : pos + len(url) + 20],
            }
        )

    return {
        "name": "Raw URLs in Content",
        "passed": len(raw_urls) == 0,
        "issues": issues,
        "description": "Check for URLs that should be properly linked",
    }


def check_canonical_links(text: str) -> Dict[str, any]:
    """Check for non-canonical link hosts."""
    forbidden_hosts = [
        "feedbinusercontent",
        "substackcdn",
        "cdn.substack",
        "list-manage",
        "cdn-images",
        "cdn.embed",
        "cdn.newsletter",
    ]

    issues = []
    for host in forbidden_hosts:
        pattern = rf'https?://[^/\s]+{re.escape(host)}[^\s<>"{{}}|\\^`\[\]]*'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            issues.append(
                {
                    "host": host,
                    "url": match.group(0),
                    "position": match.start(),
                    "context": text[max(0, match.start() - 20) : match.end() + 20],
                }
            )

    return {
        "name": "Non-Canonical Link Hosts",
        "passed": len(issues) == 0,
        "issues": issues,
        "description": "Check for CDN and non-canonical link hosts",
    }


def check_generic_links(text: str) -> Dict[str, any]:
    """Check for generic or placeholder link text."""
    generic_patterns = [
        r"^link$",
        r"^source$",
        r"^read more$",
        r"^article$",
        r"^newsletters$",
        r"^url$",
        r"^click here$",
        r"^url\d+$",
        r"^here$",
        r"^this$",
        r"^more$",
        r"^continue reading$",
    ]

    issues = []
    for pattern in generic_patterns:
        # Look for these patterns in link text - only exact matches
        # HTML links
        html_pattern = rf"<a[^>]+>([^<]*{pattern}[^<]*)</a>"
        html_matches = re.finditer(html_pattern, text, re.IGNORECASE)
        for match in html_matches:
            link_text = match.group(1).strip()
            # Only flag if the entire link text is generic
            if re.match(pattern, link_text, re.IGNORECASE):
                issues.append(
                    {
                        "pattern": pattern,
                        "link_text": link_text,
                        "position": match.start(),
                        "context": text[max(0, match.start() - 20) : match.end() + 20],
                    }
                )

        # Markdown links
        markdown_pattern = rf"\[([^]]*{pattern}[^]]*)\]\([^)]+\)"
        markdown_matches = re.finditer(markdown_pattern, text, re.IGNORECASE)
        for match in markdown_matches:
            link_text = match.group(1).strip()
            # Only flag if the entire link text is generic
            if re.match(pattern, link_text, re.IGNORECASE):
                issues.append(
                    {
                        "pattern": pattern,
                        "link_text": link_text,
                        "position": match.start(),
                        "context": text[max(0, match.start() - 20) : match.end() + 20],
                    }
                )

    return {
        "name": "Generic Link Labels",
        "passed": len(issues) == 0,
        "issues": issues,
        "description": "Check for generic or placeholder link text",
    }


def check_truncation(text: str) -> Dict[str, any]:
    """Check for truncated content and unbalanced quotes/parentheses."""
    issues = []

    # Check for unbalanced quotes - be more lenient with contractions
    # Count only quotes that are likely to be actual quotes, not contractions
    single_quotes = len(
        re.findall(r"(?<!\w)'", text)
    )  # Single quotes not preceded by word char
    double_quotes = len(
        re.findall(r'"(?=[^"]*[a-zA-Z])', text)
    )  # Double quotes followed by text

    if single_quotes % 2 != 0:
        issues.append(
            {
                "type": "unbalanced_single_quotes",
                "count": single_quotes,
                "description": f"Unbalanced single quotes: {single_quotes}",
            }
        )

    if double_quotes % 2 != 0:
        issues.append(
            {
                "type": "unbalanced_double_quotes",
                "count": double_quotes,
                "description": f"Unbalanced double quotes: {double_quotes}",
            }
        )

    # Check for unbalanced parentheses
    open_parens = text.count("(")
    close_parens = text.count(")")
    if open_parens != close_parens:
        issues.append(
            {
                "type": "unbalanced_parentheses",
                "open": open_parens,
                "close": close_parens,
                "description": f"Unbalanced parentheses: {open_parens} open, {close_parens} close",
            }
        )

    # Check for truncation indicators
    truncation_patterns = [r"\.\.\.$", r"…$", r"--$"]

    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped_line = line.strip()

        # Skip markdown horizontal rules (standalone --- lines)
        if re.match(r"^-{3,}$", stripped_line):
            continue

        for pattern in truncation_patterns:
            if re.search(pattern, stripped_line):
                issues.append(
                    {
                        "type": "truncated_line",
                        "line_number": i + 1,
                        "line": stripped_line,
                        "description": f"Line appears truncated: {stripped_line}",
                    }
                )

        # Check for lines ending with --- that aren't standalone horizontal rules
        if re.search(r"---$", stripped_line) and not re.match(
            r"^-{3,}$", stripped_line
        ):
            issues.append(
                {
                    "type": "truncated_line",
                    "line_number": i + 1,
                    "line": stripped_line,
                    "description": f"Line appears truncated: {stripped_line}",
                }
            )

    return {
        "name": "Content Truncation & Balance",
        "passed": len(issues) == 0,
        "issues": issues,
        "description": "Check for truncated content and unbalanced punctuation",
    }


def check_markdown_formatting(text: str) -> Dict[str, any]:
    """Check for markdown formatting issues."""
    issues = []

    # Check for double spaces in headers (markdown requires single space)
    header_pattern = r"^(#{1,6})\s{2,}(.+)$"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(header_pattern, line):
            issues.append(
                {
                    "type": "double_space_header",
                    "line_number": i + 1,
                    "line": line,
                    "description": f"Header with double spaces: {line}",
                }
            )

    # Check for inconsistent list formatting
    list_pattern = r"^(\s*)[*+-]\s{2,}(.+)$"
    for i, line in enumerate(lines):
        if re.match(list_pattern, line):
            issues.append(
                {
                    "type": "double_space_list",
                    "line_number": i + 1,
                    "line": line,
                    "description": f"List item with double spaces: {line}",
                }
            )

    return {
        "name": "Markdown Formatting",
        "passed": len(issues) == 0,
        "issues": issues,
        "description": "Check for markdown formatting issues",
    }


def main():
    """CLI interface for QA checks."""
    if len(sys.argv) < 2:
        print("Usage: python -m core.qacheck <file> [--json <output_file>]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} not found")
        sys.exit(1)

    # Read content
    try:
        content = input_file.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, PermissionError) as e:
        print(f"File access error: {e}")
        sys.exit(1)
    except (UnicodeDecodeError, ValueError) as e:
        print(f"File encoding/format error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error reading file: {e}")
        sys.exit(1)

    # Run checks
    results = run_checks(content)

    # Output results
    if "--json" in sys.argv:
        json_index = sys.argv.index("--json")
        if json_index + 1 < len(sys.argv):
            output_file = Path(sys.argv[json_index + 1])
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"Results written to {output_file}")
        else:
            print("Error: --json requires output file path")
            sys.exit(1)
    else:
        # Human readable output
        print(f"QA Check Results for {input_file}")
        print("=" * 50)
        print(f"Overall Status: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
        print(
            f"Checks: {results['summary']['passed_checks']}/{results['summary']['total_checks']} passed"
        )
        print()

        for result in results["results"]:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['name']}")
            if not result["passed"] and result["issues"]:
                for issue in result["issues"][:3]:  # Show first 3 issues
                    if "description" in issue:
                        print(f"   - {issue['description']}")
                    elif "line" in issue:
                        print(f"   - Line {issue['line_number']}: {issue['line']}")
                if len(result["issues"]) > 3:
                    print(f"   ... and {len(result['issues']) - 3} more issues")
            print()

    # Exit with appropriate code
    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
