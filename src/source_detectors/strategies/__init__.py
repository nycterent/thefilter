"""Attribution strategies."""

from .attribution import (
    AttributionAnalyzer,
    AttributionStrategy,
    DomainExtractionStrategy,
    EmailFooterStrategy,
    FooterCopyrightStrategy,
    PoweredByLinkStrategy,
)

__all__ = [
    "AttributionStrategy",
    "AttributionAnalyzer",
    "FooterCopyrightStrategy",
    "PoweredByLinkStrategy",
    "EmailFooterStrategy",
    "DomainExtractionStrategy",
]
