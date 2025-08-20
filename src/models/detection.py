"""Data models for source detection using Pydantic for validation."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class DetectionStatus(str, Enum):
    """Status of the source detection process."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class AttributionInfo(BaseModel):
    """Information about content attribution."""

    publisher: Optional[str] = Field(None, description="Name of the publisher")
    original_url: Optional[str] = Field(None, description="Original URL of the content")
    confidence_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence in attribution (0.0 to 1.0)"
    )
    extraction_method: Optional[str] = Field(
        None, description="Method used to extract attribution"
    )


class SourceDetectionResult(BaseModel):
    """Result of source detection process."""

    provider: str = Field(..., description="Name of the source detector provider")
    url: str = Field(..., description="URL that was analyzed")
    status: DetectionStatus = Field(..., description="Status of the detection process")
    content_extracted: bool = Field(
        False, description="Whether content was successfully extracted"
    )
    attribution_found: bool = Field(False, description="Whether attribution was found")
    raw_content: Optional[str] = Field(None, description="Raw extracted content")
    attribution: Optional[AttributionInfo] = Field(
        None, description="Attribution information"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if detection failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    processing_time: Optional[float] = Field(
        None, description="Time taken to process in seconds"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
