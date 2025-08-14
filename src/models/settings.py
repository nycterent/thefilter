"""Settings and configuration management."""

import logging
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or Infisical."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Secrets Management
    use_infisical: bool = Field(False, description="Use Infisical for secrets")

    # Content Sources
    readwise_api_key: Optional[str] = Field(None, description="Readwise key")
    glasp_api_key: Optional[str] = Field(None, description="Glasp key")
    rss_feeds: Optional[str] = Field(None, description="RSS URLs")
    readwise_filter_tag: str = Field(
        default="twiar",
        description="Tag to filter Readwise content for editorial workflow",
    )

    # Newsletter Platform
    buttondown_api_key: Optional[str] = Field(None, description="Buttondown")

    # AI Processing
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter")

    # Image Search
    unsplash_api_key: Optional[str] = Field(None, description="Unsplash key")

    # Application Settings
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Log level")

    # API Timeout Settings (in seconds)
    openrouter_timeout: float = Field(
        30.0, ge=5.0, le=120.0, description="OpenRouter API request timeout in seconds"
    )
    readwise_timeout: float = Field(
        15.0, ge=5.0, le=60.0, description="Readwise API request timeout in seconds"
    )
    rss_feed_timeout: float = Field(
        30.0, ge=10.0, le=120.0, description="RSS feed fetch timeout in seconds"
    )
    rss_content_timeout: float = Field(
        15.0,
        ge=5.0,
        le=60.0,
        description="RSS article content fetch timeout in seconds",
    )
    unsplash_timeout: float = Field(
        10.0, ge=3.0, le=30.0, description="Unsplash API request timeout in seconds"
    )
    buttondown_timeout: float = Field(
        15.0, ge=5.0, le=60.0, description="Buttondown API request timeout in seconds"
    )

    # OpenRouter Rate Limiting Settings
    openrouter_min_request_interval: float = Field(
        3.2,
        ge=0.5,
        le=10.0,
        description="Minimum seconds between OpenRouter requests (free tier: 20 req/min)",
    )
    openrouter_max_backoff_multiplier: float = Field(
        8.0,
        ge=2.0,
        le=32.0,
        description="Maximum backoff multiplier for consecutive failures",
    )
    openrouter_max_consecutive_failures: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum consecutive failures before circuit breaking",
    )

    # General API Settings
    max_retries: int = Field(
        3, ge=0, le=10, description="Maximum number of API request retries"
    )
    default_user_agent: str = Field(
        "Newsletter-Bot/1.0",
        min_length=5,
        max_length=100,
        description="Default User-Agent for HTTP requests",
    )

    # Voice System Settings
    default_voice: str = Field(
        "saint", description="Default voice for newsletter commentary"
    )
    voice_languages: str = Field(
        "en", description="Comma-separated list of languages for voice generation"
    )
    voice_target_words: int = Field(
        700, ge=200, le=2000, description="Target word count for voice commentary"
    )

    @model_validator(mode="after")
    def load_secrets_from_infisical(self) -> "Settings":
        """Load secrets from Infisical if enabled."""
        if not self.use_infisical:
            return self

        try:
            from src.core.secrets import InfisicalConfig, InfisicalSecretManager

            # Initialize Infisical client
            infisical_config = InfisicalConfig()  # type: ignore
            secret_manager = InfisicalSecretManager(infisical_config)

            # Map of setting fields to secret names
            secret_mappings = {
                "readwise_api_key": "READWISE_API_KEY",
                "glasp_api_key": "GLASP_API_KEY",
                "rss_feeds": "RSS_FEEDS",
                "buttondown_api_key": "BUTTONDOWN_API_KEY",
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "unsplash_api_key": "UNSPLASH_API_KEY",
            }

            # Get secrets that aren't already set
            secrets_to_fetch = [
                secret_name
                for field_name, secret_name in secret_mappings.items()
                if getattr(self, field_name) is None
            ]

            if secrets_to_fetch:
                secrets = secret_manager.get_multiple_secrets(secrets_to_fetch)

                # Set the retrieved secrets
                for field_name, secret_name in secret_mappings.items():
                    if secret_name in secrets:
                        setattr(self, field_name, secrets[secret_name])
                        logger.debug(f"Loaded {field_name} from Infisical")

        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(
                "Infisical module not available - falling back to environment variables"
            )
            if self.debug:
                logger.debug(f"Infisical import error details: {e}")
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            logger.warning(
                "Infisical configuration error - check credentials and settings"
            )
            if self.debug:
                logger.debug(f"Infisical configuration error details: {e}")
        except Exception as e:
            logger.error(
                "Failed to load secrets from Infisical - falling back to environment variables"
            )
            if self.debug:
                logger.debug(f"Infisical error details: {e}")
                # In debug mode, re-raise exceptions for better debugging
                raise

        return self
