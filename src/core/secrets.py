"""Infisical secrets management integration."""

import logging
from typing import Dict, Optional

# The official Infisical SDK is optional. Import it lazily and provide a
# tiny fallback so that the rest of the code (and tests) can run without
# the package being installed.
try:  # pragma: no cover - behaviour is trivial
    from infisical_sdk import InfisicalSDKClient  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - only used in tests

    class InfisicalSDKClient:  # type: ignore
        """Fallback Infisical client used when the real SDK is unavailable.

        The test suite replaces this placeholder with a mock, allowing the
        rest of the module to be imported without the external dependency.
        """

        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
            pass


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class InfisicalConfig(BaseSettings):
    """Configuration for Infisical client."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Infisical instance configuration
    infisical_host: str = Field(
        "https://app.infisical.com", description="Infisical host URL"
    )
    infisical_project_id: Optional[str] = Field(
        None, description="Infisical project ID"
    )
    infisical_environment: str = Field("dev", description="Environment slug")
    infisical_secret_path: str = Field("/", description="Secret path")

    # Authentication
    infisical_client_id: Optional[str] = Field(None, description="Client ID")
    infisical_client_secret: Optional[str] = Field(None, description="Secret")
    infisical_token: Optional[str] = Field(None, description="Auth token")


class InfisicalSecretManager:
    """Manages secrets retrieval from Infisical."""

    def __init__(self, config: InfisicalConfig):
        """Initialize the Infisical secret manager.

        Args:
            config: Infisical configuration
        """
        self.config = config
        self._client: Optional[InfisicalSDKClient] = None
        self._secrets_cache: Dict[str, str] = {}

    @property
    def client(self) -> InfisicalSDKClient:
        """Get or create Infisical client."""
        if self._client is None:
            self._client = InfisicalSDKClient(host=self.config.infisical_host)
            self._authenticate()
        return self._client

    def _authenticate(self) -> None:
        """Authenticate with Infisical."""
        if self.config.infisical_token:
            # Token-based auth is handled during client initialization
            logger.debug("Using token-based authentication")
        elif self.config.infisical_client_id and self.config.infisical_client_secret:
            # Universal auth
            self.client.auth.universal_auth.login(
                self.config.infisical_client_id,
                self.config.infisical_client_secret,
            )
            logger.debug("Authenticated using universal auth")
        else:
            raise ValueError(
                "Must provide either infisical_token or both "
                "infisical_client_id and infisical_client_secret"
            )

    def get_secret(self, secret_name: str, use_cache: bool = True) -> str:
        """Get a secret from Infisical.

        Args:
            secret_name: Name of the secret to retrieve
            use_cache: Whether to use local cache

        Returns:
            Secret value

        Raises:
            ValueError: If secret not found
        """
        if use_cache and secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]

        try:
            if not self.config.infisical_project_id:
                raise ValueError("infisical_project_id is required")

            secret = self.client.secrets.get_secret_by_name(
                secret_name=secret_name,
                project_id=self.config.infisical_project_id,
                environment_slug=self.config.infisical_environment,
                secret_path=self.config.infisical_secret_path,
            )

            value: str = secret.secret_value
            if use_cache:
                self._secrets_cache[secret_name] = value

            logger.debug(f"Retrieved secret: {secret_name}")
            return value

        except (ImportError, ModuleNotFoundError) as e:
            logger.error(
                f"Infisical dependencies not available for secret {secret_name}: {e}"
            )
            raise ValueError(
                f"Secret '{secret_name}' not accessible - missing dependencies"
            ) from e
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Secret configuration error for {secret_name}: {e}")
            raise ValueError(f"Secret '{secret_name}' not found") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            raise ValueError(f"Secret '{secret_name}' not found") from e

    def get_multiple_secrets(
        self, secret_names: list[str], use_cache: bool = True
    ) -> Dict[str, str]:
        """Get multiple secrets from Infisical.

        Args:
            secret_names: List of secret names to retrieve
            use_cache: Whether to use local cache

        Returns:
            Dictionary mapping secret names to values
        """
        secrets = {}
        for name in secret_names:
            try:
                secrets[name] = self.get_secret(name, use_cache)
            except ValueError:
                logger.warning(f"Secret {name} not found, skipping")
                continue
        return secrets

    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._secrets_cache.clear()
        logger.debug("Secrets cache cleared")
