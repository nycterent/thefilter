import re
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ValidationIssue:
    """Represents a specific issue found during newsletter validation."""
    line_number: int
    message: str
    severity: str  # 'warning', 'error', 'critical'
    fix_suggestion: Optional[str] = None

class NewsletterQualityChecker:
    """Comprehensive newsletter quality validation system."""

    BANNED_PHRASES = [
        "as we navigate", 
        "raises questions", 
        "promises", 
        "landscape", 
        "paradigm",
        "in the realm of",
        "it's important to note"
    ]

    LLM_PATTERN_INDICATORS = [
        r"\b(unlock|revolutionize|transform|empower)\b",  # Vibe verbs
        r"Why it matters:",  # Explicit template marker
        r"^In an era where",  # Sweeping contextual opener
    ]

    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')
        self.issues: List[ValidationIssue] = []

    def check_structure(self) -> List[ValidationIssue]:
        """Check overall newsletter structural integrity."""
        structural_checks = [
            self._check_headline_structure,
            self._check_source_hierarchy,
            self._detect_llm_patterns
        ]
        
        for check in structural_checks:
            self.issues.extend(check())
        
        return self.issues

    def _check_headline_structure(self) -> List[ValidationIssue]:
        """Validate headline formatting and first-sentence rules."""
        issues = []
        first_sentences = [line.split('.')[0] for line in self.lines if line.strip()]
        
        for i, sentence in enumerate(first_sentences):
            # Actor + Number + Verb + Consequence check
            if not re.search(r'\b\d+\b', sentence) or \
               len(sentence.split()) < 5:
                issues.append(ValidationIssue(
                    line_number=i+1, 
                    message="First sentence lacks quantitative precision",
                    severity="error",
                    fix_suggestion="Revise to include specific numbers, actors, and direct consequences"
                ))
        
        return issues

    def _check_source_hierarchy(self) -> List[ValidationIssue]:
        """Validate source types and their appropriate placement."""
        issues = []
        # TODO: Implement advanced source type detection
        return issues

    def _detect_llm_patterns(self) -> List[ValidationIssue]:
        """Detect potential LLM-generated content patterns."""
        issues = []
        
        # Check for banned phrases
        for i, line in enumerate(self.lines):
            for banned in self.BANNED_PHRASES:
                if banned.lower() in line.lower():
                    issues.append(ValidationIssue(
                        line_number=i+1,
                        message=f"Contains banned phrase: '{banned}'",
                        severity="critical",
                        fix_suggestion=f"Remove or rephrase the sentence to avoid '{banned}'"
                    ))
            
            # Check for LLM pattern indicators
            for pattern in self.LLM_PATTERN_INDICATORS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(ValidationIssue(
                        line_number=i+1,
                        message=f"Potential LLM pattern detected: '{pattern}'",
                        severity="warning",
                        fix_suggestion="Rewrite to sound more journalistic and specific"
                    ))
        
        return issues

    def generate_report(self) -> Dict:
        """Generate a comprehensive validation report."""
        return {
            "total_issues": len(self.issues),
            "critical_issues": [i for i in self.issues if i.severity == "critical"],
            "warnings": [i for i in self.issues if i.severity == "warning"],
            "errors": [i for i in self.issues if i.severity == "error"]
        }

def validate_newsletter(content: str) -> Dict:
    """Main entry point for newsletter validation."""
    checker = NewsletterQualityChecker(content)
    checker.check_structure()
    return checker.generate_report()