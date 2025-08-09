"""Content models for newsletter automation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ContentItem(BaseModel):
    """Represents a single piece of content from any source."""

    id: str = Field(..., description="Unique identifier")
    title: str = Field(..., description="Content title")
    url: Optional[HttpUrl] = Field(None, description="Original URL")
    content: str = Field(..., description="Content text/summary")
    source: str = Field(..., description="Source platform")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation time"
    )
    tags: List[str] = Field(default_factory=list, description="Tags")
    is_paywalled: bool = Field(False, description="Behind paywall")


class NewsletterDraft(BaseModel):
    """Represents a generated newsletter draft."""

    title: str = Field(..., description="Newsletter title")
    content: str = Field(..., description="Generated newsletter content")
    items: List[ContentItem] = Field(..., description="Source items")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Generation time"
    )
    image_url: Optional[HttpUrl] = Field(None, description="Featured image")
    draft_id: Optional[str] = Field(None, description="External draft ID")
