"""Tests for data models."""

import pytest
from datetime import datetime
from src.models.content import ContentItem, NewsletterDraft


def test_content_item_creation():
    """Test creating a ContentItem with required fields."""
    item = ContentItem(
        id="test-123",
        title="Test Article",
        content="This is test content",
        source="readwise",
    )

    assert item.id == "test-123"
    assert item.title == "Test Article"
    assert item.content == "This is test content"
    assert item.source == "readwise"
    assert item.tags == []
    assert item.is_paywalled is False
    assert isinstance(item.created_at, datetime)


def test_content_item_with_optional_fields():
    """Test ContentItem with all optional fields."""
    item = ContentItem(
        id="test-456",
        title="Premium Article",
        url="https://example.com/article",
        content="Premium content behind paywall",
        source="glasp",
        tags=["tech", "ai"],
        is_paywalled=True,
    )

    assert str(item.url) == "https://example.com/article"
    assert item.tags == ["tech", "ai"]
    assert item.is_paywalled is True


def test_newsletter_draft_creation():
    """Test creating a NewsletterDraft."""
    items = [
        ContentItem(id="1", title="Article 1", content="Content 1", source="readwise"),
        ContentItem(id="2", title="Article 2", content="Content 2", source="glasp"),
    ]

    draft = NewsletterDraft(
        title="Weekly Digest", content="Generated newsletter content here", items=items
    )

    assert draft.title == "Weekly Digest"
    assert draft.content == "Generated newsletter content here"
    assert len(draft.items) == 2
    assert isinstance(draft.created_at, datetime)
    assert draft.draft_id is None


def test_newsletter_draft_with_image():
    """Test NewsletterDraft with featured image."""
    draft = NewsletterDraft(
        title="Image Newsletter",
        content="Content with image",
        items=[],
        image_url="https://images.unsplash.com/photo-123",
        draft_id="buttondown-456",
    )

    assert str(draft.image_url) == "https://images.unsplash.com/photo-123"
    assert draft.draft_id == "buttondown-456"


def test_content_item_validation():
    """Test that ContentItem validates required fields."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContentItem()  # Missing required fields

    # Test that empty strings are still valid for title (Pydantic allows empty strings by default)
    item = ContentItem(
        id="test",
        title="",  # Empty title is actually valid in Pydantic
        content="content",
        source="test",
    )
    assert item.title == ""
