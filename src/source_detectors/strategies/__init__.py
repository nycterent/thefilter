"""Attribution strategies."""

from .attribution import (
    AttributionStrategy,
    AttributionAnalyzer,
    FooterCopyrightStrategy,
    PoweredByLinkStrategy,
    EmailFooterStrategy,
    DomainExtractionStrategy,
)

__all__ = [
    "AttributionStrategy",
    "AttributionAnalyzer", 
    "FooterCopyrightStrategy",
    "PoweredByLinkStrategy",
    "EmailFooterStrategy",
    "DomainExtractionStrategy",
]