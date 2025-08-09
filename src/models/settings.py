"""Settings and configuration management."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Content Sources
    readwise_api_key: Optional[str] = Field(None, description="Readwise key")
    glasp_api_key: Optional[str] = Field(None, description="Glasp key")
    feedbin_username: Optional[str] = Field(None, description="Feedbin user")
    feedbin_password: Optional[str] = Field(None, description="Feedbin pass")
    snipd_api_key: Optional[str] = Field(None, description="Snipd key")

    # Newsletter Platform
    buttondown_api_key: Optional[str] = Field(None, description="Buttondown")

    # AI Processing
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter")

    # Image Search
    unsplash_api_key: Optional[str] = Field(None, description="Unsplash key")

    # Application Settings
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Log level")
