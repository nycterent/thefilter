#!/usr/bin/env python3
"""
Anti-LLM Validation System

Detects and prevents generic LLM content patterns in newsletter drafts.
Enforces specific editorial standards and structure requirements.
"""

import re
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    ERROR = "error"      # Blocks publication
    WARNING = "warning"  # Logged but allows publication
    INFO = "info"       # Informational only


@dataclass
class ValidationIssue:
    level: ValidationLevel
    category: str
    message: str
    line_number: int = 0
    suggestion: str = ""


class AntiLLMValidator:
    """
    Validates newsletter content against LLM contamination patterns.
    Enforces editorial standards from The Filter style guide.
    """
    
    # Banned LLM phrases that must be flagged as errors
    BANNED_PHRASES = {
        # Generic LLM openings
        "as we navigate": "Use specific actor + consequence instead",
        "in a world where": "Start with concrete facts",
        "welcome to": "Cut the greeting, lead with news", 
        "imagine a world": "Report what happened, not hypotheticals",
        "picture this": "Lead with facts, not scene-setting",
        
        # LLM hedging language
        "promises to": "Use 'claims' or 'targets' or state the specific commitment",
        "raises questions": "Say what questions specifically, or cut",
        "underscores": "Use 'shows' or 'demonstrates'",
        "reminds us": "State the fact directly",
        "invites debate": "Say what the disagreement is about",
        
        # LLM filler words
        "landscape": "Use specific field/market/sector",
        "paradigm": "Use model/approach/method",
        "realm": "Use field/area/domain",
        "fabric of reality": "Be specific about what changed",
        "complexities": "Name the specific complexity",
        "implications": "State the specific consequence",
        
        # Generic conclusions
        "only time will tell": "State what metric will determine outcome",
        "remains to be seen": "Say what evidence would confirm/deny",
        "the jury is still out": "Specify what evidence is missing",
        
        # Philosophical padding
        "what does it mean": "State the specific impact/consequence",
        "forces us to reconsider": "Say what specifically changed",
        "challenges our understanding": "Name what understanding and how"
    }
    
    # Required structural elements
    REQUIRED_SECTIONS = {
        "## HEADLINES AT A GLANCE": "Must have 4-column headlines table",
        "## LEAD STORIES": "Must have 2-column table with images", 
        "## TECHNOLOGY DESK": "Tech section required",
        "## SOCIETY & POLITICS": "Society section required",
        "---": "Section dividers required"
    }
    
    # Patterns that indicate LLM writing
    LLM_PATTERNS = [
        (r"Why it matters:", "Cut 'Why it matters' boxes - bake stakes into sentence 2"),
        (r"Here's what (?:you|we) need to know", "Lead with the facts directly"),
        (r"The (?:bottom line|key takeaway) is", "State the conclusion directly"),
        (r"At the end of the day", "Cut filler, state the consequence"),
        (r"\b(?:However|Moreover|Furthermore|Nevertheless),", "Use shorter connectors or new sentences"),
        (r"It's worth noting that", "If it's worth noting, just state it"),
        (r"This (?:development|advancement|breakthrough)", "Name the specific thing, don't use 'this'"),
        (r"The (?:implications|ramifications) are", "State specific consequences"),
        (r"represents? a (?:significant|major|important)", "Quantify the significance or cut the modifier"),
    ]
    
    # Image validation patterns
    IMAGE_REQUIREMENTS = [
        (r'<img[^>]*>', "Use markdown image format ![alt](url), not HTML"),
        (r'!\[([^\]]*)\]\([^)]*\?[^)]*\?[^)]*\)', "Fix malformed Unsplash URLs with double ? parameters"),
        (r'!\[[^\]]*professional illustration[^\]]*\]', "Alt text should describe what's in the image, not vibes"),
        (r'!\[[^\]]*in (?:technology|business|society) context[^\]]*\]', "Alt text should be literal, not conceptual"),
    ]
    
    # Table structure validation
    TABLE_PATTERNS = [
        (r'\| \*\*Technology\*\* \| \*\*Society & Politics\*\* \| \*\*Arts & Culture\*\* \| \*\*Business & Economy\*\* \|', 
         "4-column headlines table found"),
        (r'\|\s*\*\*[^*]+\*\*\s*\|\s*\*\*[^*]+\*\*\s*\|',
         "2-column lead stories table structure"),
    ]
    
    def validate_newsletter(self, content: str) -> List[ValidationIssue]:
        """
        Validate newsletter content against anti-LLM standards.
        
        Returns:
            List of validation issues sorted by severity
        """
        issues = []
        lines = content.split('\n')
        
        # Check for banned phrases
        issues.extend(self._check_banned_phrases(content, lines))
        
        # Check for LLM patterns
        issues.extend(self._check_llm_patterns(content, lines))
        
        # Check required structure
        issues.extend(self._check_structure_requirements(content))
        
        # Check image formats
        issues.extend(self._check_image_requirements(content, lines))
        
        # Check table structure
        issues.extend(self._check_table_structure(content))
        
        # Sort by severity: ERROR, WARNING, INFO
        return sorted(issues, key=lambda x: (x.level.value, x.line_number))
    
    def _check_banned_phrases(self, content: str, lines: List[str]) -> List[ValidationIssue]:
        """Check for explicitly banned LLM phrases."""
        issues = []
        content_lower = content.lower()
        
        for phrase, suggestion in self.BANNED_PHRASES.items():
            if phrase.lower() in content_lower:
                # Find line number
                line_num = self._find_line_number(phrase, lines)
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="banned_phrase",
                    message=f"Banned LLM phrase: '{phrase}'",
                    line_number=line_num,
                    suggestion=suggestion
                ))
        
        return issues
    
    def _check_llm_patterns(self, content: str, lines: List[str]) -> List[ValidationIssue]:
        """Check for LLM writing patterns."""
        issues = []
        
        for pattern, message in self.LLM_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = self._find_line_number_by_position(match.start(), content)
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category="llm_pattern",
                    message=f"LLM pattern detected: {match.group()}",
                    line_number=line_num,
                    suggestion=message
                ))
        
        return issues
    
    def _check_structure_requirements(self, content: str) -> List[ValidationIssue]:
        """Check for required structural elements."""
        issues = []
        
        for section, description in self.REQUIRED_SECTIONS.items():
            if section not in content:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="structure",
                    message=f"Missing required section: {section}",
                    suggestion=description
                ))
        
        # Check for proper table structure in headlines
        if "## HEADLINES AT A GLANCE" in content:
            headlines_section = self._extract_section(content, "## HEADLINES AT A GLANCE", "---")
            if "|" not in headlines_section or "Technology" not in headlines_section:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="structure",
                    message="HEADLINES AT A GLANCE must be a 4-column table",
                    suggestion="Use: | **Technology** | **Society & Politics** | **Arts & Culture** | **Business & Economy** |"
                ))
        
        return issues
    
    def _check_image_requirements(self, content: str, lines: List[str]) -> List[ValidationIssue]:
        """Check image format and alt text quality."""
        issues = []
        
        for pattern, message in self.IMAGE_REQUIREMENTS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = self._find_line_number_by_position(match.start(), content)
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="image_format",
                    message=message,
                    line_number=line_num,
                    suggestion="Use proper markdown: ![specific alt text](url?w=500&h=200&fit=crop)"
                ))
        
        return issues
    
    def _check_table_structure(self, content: str) -> List[ValidationIssue]:
        """Check for proper table formatting."""
        issues = []
        
        # Look for headline table structure
        if "HEADLINES AT A GLANCE" in content:
            section = self._extract_section(content, "## HEADLINES AT A GLANCE", "---")
            has_4_col = bool(re.search(r'\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|', section))
            
            if not has_4_col:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="table_structure", 
                    message="Headlines table must have 4 columns",
                    suggestion="Format: | **Technology** | **Society & Politics** | **Arts & Culture** | **Business & Economy** |"
                ))
        
        # Look for lead stories table
        if "LEAD STORIES" in content:
            section = self._extract_section(content, "## LEAD STORIES", "---")
            has_2_col = bool(re.search(r'\|\s*[^|]+\s*\|\s*[^|]+\s*\|', section))
            
            if not has_2_col:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="table_structure",
                    message="Lead stories must be in 2-column table format",
                    suggestion="Use side-by-side table with images"
                ))
        
        return issues
    
    def _find_line_number(self, phrase: str, lines: List[str]) -> int:
        """Find line number containing phrase."""
        phrase_lower = phrase.lower()
        for i, line in enumerate(lines):
            if phrase_lower in line.lower():
                return i + 1
        return 0
    
    def _find_line_number_by_position(self, position: int, content: str) -> int:
        """Find line number by character position."""
        return content[:position].count('\n') + 1
    
    def _extract_section(self, content: str, start_marker: str, end_marker: str) -> str:
        """Extract content between two markers."""
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return ""
        
        end_idx = content.find(end_marker, start_idx + len(start_marker))
        if end_idx == -1:
            return content[start_idx:]
        
        return content[start_idx:end_idx]
    
    def generate_validation_report(self, issues: List[ValidationIssue]) -> str:
        """Generate human-readable validation report."""
        if not issues:
            return "✅ NEWSLETTER PASSES ANTI-LLM VALIDATION"
        
        errors = [i for i in issues if i.level == ValidationLevel.ERROR]
        warnings = [i for i in issues if i.level == ValidationLevel.WARNING]
        
        report = []
        
        if errors:
            report.append("🚨 ERRORS (BLOCKS PUBLICATION):")
            for error in errors:
                report.append(f"  Line {error.line_number}: {error.message}")
                if error.suggestion:
                    report.append(f"    → {error.suggestion}")
            report.append("")
        
        if warnings:
            report.append("⚠️  WARNINGS:")
            for warning in warnings:
                report.append(f"  Line {warning.line_number}: {warning.message}")
                if warning.suggestion:
                    report.append(f"    → {warning.suggestion}")
        
        report.append(f"\nSUMMARY: {len(errors)} errors, {len(warnings)} warnings")
        
        return "\n".join(report)
    
    def should_block_publication(self, issues: List[ValidationIssue]) -> bool:
        """Determine if issues should block publication."""
        return any(issue.level == ValidationLevel.ERROR for issue in issues)


# Integration helper functions
def validate_newsletter_content(content: str) -> Tuple[bool, str]:
    """
    Validate newsletter content and return publication decision.
    
    Returns:
        (should_publish, validation_report)
    """
    validator = AntiLLMValidator()
    issues = validator.validate_newsletter(content)
    report = validator.generate_validation_report(issues)
    should_publish = not validator.should_block_publication(issues)
    
    return should_publish, report


# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python anti_llm_validator.py <newsletter_file.md>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
        
        should_publish, report = validate_newsletter_content(content)
        
        print("ANTI-LLM VALIDATION REPORT")
        print("=" * 50)
        print(report)
        print("=" * 50)
        print(f"PUBLICATION STATUS: {'✅ APPROVED' if should_publish else '🚫 BLOCKED'}")
        
        sys.exit(0 if should_publish else 1)
        
    except Exception as e:
        print(f"Error validating newsletter: {e}")
        sys.exit(1)