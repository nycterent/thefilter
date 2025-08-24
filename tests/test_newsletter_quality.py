import pytest
from src.quality_checks import (
    NewsletterQualityChecker, 
    validate_newsletter, 
    comprehensive_text_analysis
)

def test_validate_newsletter_banned_phrases():
    """Test detection of banned phrases in newsletter content."""
    test_content = """
    As we navigate the landscape of technology, we promise to empower our readers.
    This article raises questions about the paradigm of digital transformation.
    """
    
    report = validate_newsletter(test_content)
    
    assert report['total_issues'] > 0
    assert any('banned phrase' in issue.message for issue in report['critical_issues'])

def test_first_sentence_structure():
    """Validate first sentence structure requirements."""
    bad_content = "Technology exists."
    good_content = "Google invested $500 million in AI research, transforming the tech industry's approach to machine learning."
    
    bad_report = validate_newsletter(bad_content)
    good_report = validate_newsletter(good_content)
    
    assert len(bad_report['errors']) > 0
    assert len(good_report['errors']) == 0

def test_text_diagnostics():
    """Test comprehensive text analysis capabilities."""
    test_content = """
    The quick brown fox jumps over the lazy dog. 
    Synergistic ecosystem leverages innovative solutions to disrupt traditional paradigms.
    """
    
    diagnostics = comprehensive_text_analysis(test_content)
    
    assert diagnostics['detected_jargon']
    assert 'readability' in diagnostics
    assert 'semantic_density' in diagnostics