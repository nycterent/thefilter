from src.core.sanitizer import ContentSanitizer


def test_sanitizer_removes_ai_refusal_phrase():
    sanitizer = ContentSanitizer()
    text, issues = sanitizer.sanitize_text(
        "I can't provide assistance with creating content that contains or promotes harmful, illegal, or adult material."
    )
    assert text == ""
    assert any("AI refusal" in issue for issue in issues)
