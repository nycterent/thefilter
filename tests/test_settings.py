"""Tests for settings and configuration."""

import pytest
import os
from src.models.settings import Settings


def test_settings_defaults(monkeypatch):
    """Test that settings have proper default values."""
    # Clear all API key environment variables
    monkeypatch.delenv("READWISE_API_KEY", raising=False)
    monkeypatch.delenv("GLASP_API_KEY", raising=False)
    monkeypatch.delenv("BUTTONDOWN_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("UNSPLASH_API_KEY", raising=False)
    monkeypatch.delenv("RSS_FEEDS", raising=False)
    
    settings = Settings()
    assert settings.debug is False
    assert settings.log_level == "INFO"
    assert settings.readwise_api_key is None
    assert settings.buttondown_api_key is None


def test_settings_from_env(monkeypatch):
    """Test that settings are loaded from environment variables."""
    monkeypatch.setenv("READWISE_API_KEY", "test_readwise_key")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    settings = Settings()
    assert settings.readwise_api_key == "test_readwise_key"
    assert settings.debug is True
    assert settings.log_level == "DEBUG"


def test_settings_validation():
    """Test that settings validation works properly."""
    # Should not raise any exceptions with valid data
    settings = Settings(
        readwise_api_key="valid_key",
        debug=True,
        log_level="ERROR"
    )
    assert settings.readwise_api_key == "valid_key"
    assert settings.debug is True
    assert settings.log_level == "ERROR"


def test_settings_case_insensitive(monkeypatch):
    """Test that environment variable names are case insensitive."""
    monkeypatch.setenv("readwise_api_key", "lowercase_key")
    monkeypatch.setenv("GLASP_API_KEY", "uppercase_key")
    
    settings = Settings()
    assert settings.readwise_api_key == "lowercase_key"
    assert settings.glasp_api_key == "uppercase_key"