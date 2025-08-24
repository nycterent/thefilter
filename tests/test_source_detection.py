"""
Comprehensive test suite for source detection system.
"""

import asyncio
import sys
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

sys.path.append("src")

from src.models.detection import AttributionInfo, DetectionStatus, SourceDetectionResult
from src.source_detectors.orchestrator import (
    SourceDetectionOrchestrator,
    get_orchestrator,
)
from src.source_detectors.providers.mailchimp import MailchimpDetector
from src.source_detectors.strategies.attribution import (
    AttributionAnalyzer,
    EmailFooterStrategy,
    PoweredByLinkStrategy,
)


class TestSourceDetectionOrchestrator:
    """Test the main orchestrator functionality."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes with correct detectors."""
        orchestrator = SourceDetectionOrchestrator()
        stats = orchestrator.get_detector_stats()

        assert stats["total_detectors"] >= 1
        assert "mailchimp" in stats["providers"]

    def test_get_global_orchestrator(self):
        """Test global orchestrator singleton pattern."""
        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()

        assert orchestrator1 is orchestrator2
        assert isinstance(orchestrator1, SourceDetectionOrchestrator)

    @pytest.mark.asyncio
    async def test_detect_source_with_applicable_detector(self):
        """Test detection with applicable URL."""
        orchestrator = SourceDetectionOrchestrator()

        # Mock the detector response
        mock_result = SourceDetectionResult(
            provider="mailchimp",
            url="https://us7.campaign-archive.com/test",
            status=DetectionStatus.SUCCESS,
            content_extracted=True,
            attribution_found=True,
        )

        with patch.object(
            orchestrator.detectors[0], "run_detection", return_value=mock_result
        ):
            result = await orchestrator.detect_source(
                "https://us7.campaign-archive.com/test"
            )

            assert result is not None
            assert result.provider == "mailchimp"
            assert result.status == DetectionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_detect_source_no_applicable_detector(self):
        """Test detection with non-applicable URL."""
        orchestrator = SourceDetectionOrchestrator()

        result = await orchestrator.detect_source("https://example.com/article")

        assert result is None


class TestMailchimpDetector:
    """Test the Mailchimp detector implementation."""

    def test_mailchimp_detector_initialization(self):
        """Test detector initializes correctly."""
        detector = MailchimpDetector()

        assert detector.provider_name == "mailchimp"
        assert detector.get_priority() == 10

    def test_is_applicable_mailchimp_url(self):
        """Test URL applicability checking."""
        detector = MailchimpDetector()

        # Test positive cases
        assert detector.is_applicable("https://us7.campaign-archive.com/test")
        assert detector.is_applicable("https://campaign-archive.com/test")
        assert detector.is_applicable("HTTPS://CAMPAIGN-ARCHIVE.COM/TEST")

        # Test negative cases
        assert not detector.is_applicable("https://example.com/article")
        assert not detector.is_applicable("https://substack.com/test")
        assert not detector.is_applicable("")

    @pytest.mark.asyncio
    async def test_run_detection_success(self):
        """Test successful detection run."""
        detector = MailchimpDetector()

        mock_content = """
        <html>
        <body>
        <div>
        You are receiving this email because you signed up to receive updates from ClearerThinking.org.
        </div>
        </body>
        </html>
        """

        with patch.object(
            detector, "_extract_content_with_retry", return_value=mock_content
        ):
            result = await detector.run_detection(
                "https://us7.campaign-archive.com/test"
            )

            assert result is not None
            assert result.provider == "mailchimp"
            assert result.status == DetectionStatus.SUCCESS
            assert result.content_extracted is True
            assert result.attribution_found is True
            assert result.attribution is not None
            assert "ClearerThinking.org" in result.attribution.publisher

    @pytest.mark.asyncio
    async def test_run_detection_content_extraction_failure(self):
        """Test detection when content extraction fails."""
        detector = MailchimpDetector()

        with patch.object(
            detector,
            "_extract_content_with_retry",
            side_effect=Exception("Network error"),
        ):
            result = await detector.run_detection(
                "https://us7.campaign-archive.com/test"
            )

            assert result is not None
            assert result.provider == "mailchimp"
            assert result.status == DetectionStatus.FAILURE
            assert result.content_extracted is False
            assert result.attribution_found is False
            assert "Network error" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_content_with_retry_success(self):
        """Test content extraction with retry mechanism."""
        detector = MailchimpDetector()
        mock_content = "<html><body>Test content</body></html>"

        # Mock the get_http_session function to return a mock session
        with patch("src.source_detectors.providers.mailchimp.get_http_session") as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value = mock_session
            
            # Create proper async context manager mock for session.get()
            mock_response = AsyncMock()
            mock_response.text.return_value = mock_content
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None
            
            # Create a proper async context manager
            mock_get_context_manager = Mock()
            mock_get_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            # Mock the session.get method
            mock_session.get = Mock(return_value=mock_get_context_manager)

            content = await detector._extract_content_with_retry("https://test.com")

            assert content == mock_content
            mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_content_with_retry_max_attempts(self):
        """Test retry mechanism reaches maximum attempts."""
        detector = MailchimpDetector()

        # Mock the get_http_session function to return a mock session  
        with patch("src.source_detectors.providers.mailchimp.get_http_session") as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value = mock_session

            # Mock response that always fails - raise_for_status must be a regular method
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock(side_effect=aiohttp.ClientError("HTTP 500"))
            
            # Create a proper async context manager that raises on raise_for_status()
            mock_get_context_manager = Mock()
            mock_get_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            # Mock the session.get method
            mock_session.get = Mock(return_value=mock_get_context_manager)

            # Should return None after max retries
            content = await detector._extract_content_with_retry("https://test.com")

            assert content is None
            # Should have tried max_retries times (default is 3)
            assert mock_session.get.call_count == 3


class TestAttributionStrategies:
    """Test attribution extraction strategies."""

    def test_email_footer_strategy_success(self):
        """Test email footer attribution extraction."""
        strategy = EmailFooterStrategy()

        content = """
        <html>
        <body>
        <div>Some content here</div>
        <div>You are receiving this email because you signed up to receive updates from ClearerThinking.org.</div>
        </body>
        </html>
        """

        result = strategy.extract(content)

        assert result is not None
        assert "ClearerThinking.org" in result.publisher
        assert result.confidence_score > 0.8
        assert result.extraction_method == "email_footer"

    def test_email_footer_strategy_no_match(self):
        """Test email footer strategy with no matching content."""
        strategy = EmailFooterStrategy()

        content = "<html><body><div>Just some random content</div></body></html>"

        result = strategy.extract(content)

        assert result is None

    def test_powered_by_link_strategy_success(self):
        """Test powered by link attribution extraction."""
        strategy = PoweredByLinkStrategy()

        content = """
        <html>
        <body>
        <div>Content here</div>
        Powered by <a href="https://beehiiv.com">beehiiv</a>
        </body>
        </html>
        """

        result = strategy.extract(content)

        assert result is not None
        assert "beehiiv" in result.publisher.lower()
        assert result.confidence_score > 0.7
        assert result.extraction_method == "powered_by_link"

    def test_attribution_analyzer_best_strategy_selection(self):
        """Test analyzer selects best strategy result."""
        strategies = [EmailFooterStrategy(), PoweredByLinkStrategy()]
        analyzer = AttributionAnalyzer(strategies)

        content = """
        <html>
        <body>
        <div>You are receiving this email because you signed up to receive updates from HighConfidenceSource.org.</div>
        Powered by <a href="https://lowconfidence.com">LowConfidence</a>
        </body>
        </html>
        """

        result = analyzer.analyze(content)

        assert result is not None
        assert "HighConfidenceSource.org" in result.publisher
        # Should select email footer (higher confidence) over powered by link
        assert result.extraction_method == "email_footer"


class TestDetectionModels:
    """Test Pydantic data models."""

    def test_source_detection_result_creation(self):
        """Test creating SourceDetectionResult with valid data."""
        result = SourceDetectionResult(
            provider="test",
            url="https://example.com",
            status=DetectionStatus.SUCCESS,
            content_extracted=True,
            attribution_found=True,
        )

        assert result.provider == "test"
        assert result.url == "https://example.com"
        assert result.status == DetectionStatus.SUCCESS
        assert result.content_extracted is True
        assert result.attribution_found is True

    def test_attribution_info_validation(self):
        """Test AttributionInfo model validation."""
        attribution = AttributionInfo(
            publisher="Test Publisher",
            original_url="https://example.com",
            confidence_score=0.95,
            extraction_method="test",
        )

        assert attribution.publisher == "Test Publisher"
        assert attribution.confidence_score == 0.95
        assert 0.0 <= attribution.confidence_score <= 1.0

    def test_attribution_info_confidence_score_validation(self):
        """Test confidence score validation bounds."""
        # Valid scores
        AttributionInfo(publisher="Test", confidence_score=0.0)
        AttributionInfo(publisher="Test", confidence_score=1.0)
        AttributionInfo(publisher="Test", confidence_score=0.5)

        # Invalid scores should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            AttributionInfo(publisher="Test", confidence_score=-0.1)

        with pytest.raises(Exception):  # Pydantic validation error
            AttributionInfo(publisher="Test", confidence_score=1.1)


class TestIntegration:
    """Integration tests for the complete detection pipeline."""

    @pytest.mark.asyncio
    async def test_full_detection_pipeline(self):
        """Test complete detection pipeline from URL to result."""
        from src.source_detectors import detect_source

        mock_content = """
        <html>
        <body>
        <div>Newsletter content</div>
        <div>You are receiving this email because you signed up to receive updates from TechCrunch.</div>
        </body>
        </html>
        """

        with patch("src.source_detectors.providers.mailchimp.get_http_session") as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value = mock_session
            
            # Create proper async context manager mock
            mock_response = AsyncMock()
            mock_response.text.return_value = mock_content
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None
            
            # Create a proper async context manager
            mock_get_context_manager = Mock()
            mock_get_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            # Mock the session.get method
            mock_session.get = Mock(return_value=mock_get_context_manager)

            result = await detect_source("https://us7.campaign-archive.com/test")

            assert result is not None
            assert result.provider == "mailchimp"
            assert result.status in [
                DetectionStatus.SUCCESS,
                DetectionStatus.PARTIAL_SUCCESS,
            ]
            # Note: Attribution may be partial due to content formatting
            if result.attribution_found and result.attribution:
                assert "TechCrunch" in result.attribution.publisher

    @pytest.mark.asyncio
    async def test_detection_with_non_applicable_url(self):
        """Test detection pipeline with URL that no detector handles."""
        from src.source_detectors import detect_source

        result = await detect_source("https://random-blog.com/article")

        assert result is None

    @pytest.mark.asyncio
    async def test_detection_error_handling(self):
        """Test detection pipeline error handling."""
        from src.source_detectors import detect_source

        with patch("src.source_detectors.providers.mailchimp.get_http_session") as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value = mock_session
            mock_session.get.side_effect = Exception("Network failure")
            
            result = await detect_source("https://us7.campaign-archive.com/test")

            # When all detectors fail, orchestrator returns None
            assert result is None


# Test fixtures and utilities
@pytest.fixture
def sample_mailchimp_content():
    """Sample Mailchimp newsletter content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Newsletter</title>
    </head>
    <body>
        <div class="newsletter-content">
            <h1>Weekly Update</h1>
            <p>This is the newsletter content.</p>
        </div>
        <div class="footer">
            <p>You are receiving this email because you signed up to receive updates from ClearerThinking.org.</p>
            <p>Our mailing address is: ClearerThinking.org, 123 Main St, City, State 12345</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_attribution_info():
    """Sample attribution info for testing."""
    return AttributionInfo(
        publisher="Test Publisher",
        original_url="https://example.com",
        confidence_score=0.9,
        extraction_method="test_method",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
