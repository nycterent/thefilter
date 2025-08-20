"""Configuration management for source detection system."""

import os
from typing import Any, Dict


class DetectionConfig:
    """Configuration manager for source detection settings."""

    def __init__(self):
        """Initialize configuration with default values."""
        self._config = {
            # Mailchimp settings
            "mailchimp.timeout": 30,
            "mailchimp.max_retries": 3,
            "mailchimp.retry_delay": 1.0,
            # General settings
            "detection.max_content_size": 10 * 1024 * 1024,  # 10MB
            "detection.user_agent": "Mozilla/5.0 (compatible; Newsletter-Bot/1.0)",
            # Attribution settings
            "attribution.min_confidence": 0.3,
            "attribution.max_strategies": 10,
        }

        # Override with environment variables if available
        self._load_from_environment()

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "MAILCHIMP_TIMEOUT": "mailchimp.timeout",
            "MAILCHIMP_MAX_RETRIES": "mailchimp.max_retries",
            "DETECTION_MAX_CONTENT_SIZE": "detection.max_content_size",
            "ATTRIBUTION_MIN_CONFIDENCE": "attribution.min_confidence",
        }

        for env_var, config_key in env_mappings.items():
            if env_var in os.environ:
                try:
                    # Try to convert to appropriate type
                    value = os.environ[env_var]
                    if config_key.endswith(
                        (".timeout", ".max_retries", ".max_content_size")
                    ):
                        value = int(value)
                    elif config_key.endswith(".min_confidence"):
                        value = float(value)

                    self._config[config_key] = value
                except (ValueError, TypeError) as e:
                    # If conversion fails, keep default value
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key (e.g., 'mailchimp.timeout')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dictionary of all configuration values
        """
        return self._config.copy()


# Global configuration instance
_config = DetectionConfig()


def get_config(key: str, default: Any = None) -> Any:
    """
    Get configuration value using global config instance.

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    return _config.get(key, default)


def set_config(key: str, value: Any):
    """
    Set configuration value using global config instance.

    Args:
        key: Configuration key
        value: Value to set
    """
    _config.set(key, value)
