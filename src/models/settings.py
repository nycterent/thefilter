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

    # Newsletter Platform
    buttondown_api_key: Optional[str] = Field(None, description="Buttondown")

    # AI Processing
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter")

    # Image Search
    unsplash_api_key: Optional[str] = Field(None, description="Unsplash key")

    # Application Settings
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Log level")

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

        except Exception as e:
            logger.warning(f"Failed to load secrets from Infisical: {e}")
            if self.debug:
                raise

        return self
