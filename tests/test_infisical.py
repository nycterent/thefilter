"""Tests for Infisical secrets management integration."""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from src.core.secrets import InfisicalConfig, InfisicalSecretManager
from src.models.settings import Settings


class TestInfisicalConfig:
    """Tests for Infisical configuration."""
    
    def test_infisical_config_defaults(self):
        """Test InfisicalConfig default values."""
        config = InfisicalConfig(infisical_project_id="test-project")
        
        assert config.infisical_host == "https://app.infisical.com"
        assert config.infisical_project_id == "test-project"
        assert config.infisical_environment == "dev"
        assert config.infisical_secret_path == "/"
        assert config.infisical_client_id is None
        assert config.infisical_client_secret is None
        assert config.infisical_token is None
    
    def test_infisical_config_from_env(self, monkeypatch):
        """Test InfisicalConfig loads from environment variables."""
        monkeypatch.setenv("INFISICAL_HOST", "https://my-infisical.com")
        monkeypatch.setenv("INFISICAL_PROJECT_ID", "my-project")
        monkeypatch.setenv("INFISICAL_ENVIRONMENT", "prod")
        monkeypatch.setenv("INFISICAL_CLIENT_ID", "my-client-id")
        monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "my-client-secret")
        
        config = InfisicalConfig()
        
        assert config.infisical_host == "https://my-infisical.com"
        assert config.infisical_project_id == "my-project"
        assert config.infisical_environment == "prod"
        assert config.infisical_client_id == "my-client-id"
        assert config.infisical_client_secret == "my-client-secret"


class TestInfisicalSecretManager:
    """Tests for Infisical secret manager."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Infisical configuration."""
        return InfisicalConfig(
            infisical_host="https://test-infisical.com",
            infisical_project_id="test-project",
            infisical_environment="test",
            infisical_client_id="test-client-id",
            infisical_client_secret="test-client-secret"
        )
    
    @pytest.fixture
    def mock_client(self):
        """Mock Infisical SDK client."""
        client = Mock()
        client.auth.universal_auth.login = Mock()
        client.secrets.get_secret_by_name = Mock()
        return client
    
    def test_secret_manager_initialization(self, mock_config):
        """Test secret manager initialization."""
        manager = InfisicalSecretManager(mock_config)
        
        assert manager.config == mock_config
        assert manager._client is None
        assert manager._secrets_cache == {}
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_client_property_creates_client(self, mock_client_class, mock_config):
        """Test that client property creates and authenticates client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        manager = InfisicalSecretManager(mock_config)
        client = manager.client
        
        mock_client_class.assert_called_once_with(
            host="https://test-infisical.com"
        )
        mock_client.auth.universal_auth.login.assert_called_once_with(
            "test-client-id", "test-client-secret"
        )
        assert client == mock_client
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_authentication_with_token(self, mock_client_class, mock_config):
        """Test authentication with token."""
        mock_config.infisical_token = "test-token"
        mock_config.infisical_client_id = None
        mock_config.infisical_client_secret = None
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        manager = InfisicalSecretManager(mock_config)
        client = manager.client
        
        # Token auth should not call login
        mock_client.auth.universal_auth.login.assert_not_called()
    
    def test_authentication_missing_credentials(self, mock_config):
        """Test authentication fails with missing credentials."""
        mock_config.infisical_client_id = None
        mock_config.infisical_client_secret = None
        mock_config.infisical_token = None
        
        manager = InfisicalSecretManager(mock_config)
        
        with pytest.raises(ValueError, match="Must provide either"):
            manager.client
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_get_secret_success(self, mock_client_class, mock_config):
        """Test successful secret retrieval."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.secret_value = "test-secret-value"
        mock_client.secrets.get_secret_by_name.return_value = mock_secret
        
        manager = InfisicalSecretManager(mock_config)
        result = manager.get_secret("TEST_SECRET")
        
        assert result == "test-secret-value"
        mock_client.secrets.get_secret_by_name.assert_called_once_with(
            secret_name="TEST_SECRET",
            project_id="test-project",
            environment_slug="test",
            secret_path="/"
        )
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_get_secret_with_cache(self, mock_client_class, mock_config):
        """Test secret retrieval uses cache."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        manager = InfisicalSecretManager(mock_config)
        manager._secrets_cache["CACHED_SECRET"] = "cached-value"
        
        result = manager.get_secret("CACHED_SECRET")
        
        assert result == "cached-value"
        # Should not call the API
        mock_client.secrets.get_secret_by_name.assert_not_called()
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_get_secret_not_found(self, mock_client_class, mock_config):
        """Test secret retrieval when secret not found."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.secrets.get_secret_by_name.side_effect = Exception(
            "Secret not found"
        )
        
        manager = InfisicalSecretManager(mock_config)
        
        with pytest.raises(ValueError, match="Secret 'MISSING_SECRET' not found"):
            manager.get_secret("MISSING_SECRET")
    
    @patch('src.core.secrets.InfisicalSDKClient')
    def test_get_multiple_secrets(self, mock_client_class, mock_config):
        """Test retrieving multiple secrets."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        def mock_get_secret(secret_name, **kwargs):
            mock_secret = Mock()
            if secret_name == "SECRET1":
                mock_secret.secret_value = "value1"
            elif secret_name == "SECRET2":
                mock_secret.secret_value = "value2"
            else:
                raise Exception("Not found")
            return mock_secret
        
        mock_client.secrets.get_secret_by_name.side_effect = mock_get_secret
        
        manager = InfisicalSecretManager(mock_config)
        result = manager.get_multiple_secrets(["SECRET1", "SECRET2", "SECRET3"])
        
        # Should return found secrets, skip missing ones
        assert result == {"SECRET1": "value1", "SECRET2": "value2"}
    
    def test_clear_cache(self, mock_config):
        """Test cache clearing."""
        manager = InfisicalSecretManager(mock_config)
        manager._secrets_cache = {"key": "value"}
        
        manager.clear_cache()
        
        assert manager._secrets_cache == {}


class TestSettingsWithInfisical:
    """Tests for Settings integration with Infisical."""
    
    def test_settings_without_infisical(self):
        """Test settings work normally without Infisical."""
        settings = Settings(
            use_infisical=False,
            readwise_api_key="env-key"
        )
        
        assert settings.use_infisical is False
        assert settings.readwise_api_key == "env-key"
    
    @patch('src.core.secrets.InfisicalConfig')
    @patch('src.core.secrets.InfisicalSecretManager')
    def test_settings_with_infisical_success(
        self, mock_manager_class, mock_config_class
    ):
        """Test settings load secrets from Infisical successfully."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.get_multiple_secrets.return_value = {
            "READWISE_API_KEY": "infisical-readwise-key",
            "GLASP_API_KEY": "infisical-glasp-key"
        }
        
        settings = Settings(use_infisical=True)
        
        assert settings.readwise_api_key == "infisical-readwise-key"
        assert settings.glasp_api_key == "infisical-glasp-key"
        mock_manager.get_multiple_secrets.assert_called_once()
    
    @patch('src.core.secrets.InfisicalConfig')
    @patch('src.core.secrets.InfisicalSecretManager')
    def test_settings_infisical_partial_override(
        self, mock_manager_class, mock_config_class
    ):
        """Test that Infisical only overrides unset values."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.get_multiple_secrets.return_value = {
            "GLASP_API_KEY": "infisical-glasp-key"
        }
        
        settings = Settings(
            use_infisical=True,
            readwise_api_key="env-readwise-key"  # Already set
        )
        
        # Should keep env value, load missing from Infisical
        assert settings.readwise_api_key == "env-readwise-key"
        assert settings.glasp_api_key == "infisical-glasp-key"
    
    @patch('src.core.secrets.InfisicalConfig')
    @patch('src.core.secrets.InfisicalSecretManager')
    def test_settings_infisical_failure_non_debug(
        self, mock_manager_class, mock_config_class
    ):
        """Test Infisical failure is handled gracefully in non-debug mode."""
        # Setup mocks to fail
        mock_config_class.side_effect = Exception("Infisical error")
        
        settings = Settings(use_infisical=True, debug=False)
        
        # Should not raise exception, just log warning
        assert settings.use_infisical is True
    
    @patch('src.core.secrets.InfisicalConfig')
    @patch('src.core.secrets.InfisicalSecretManager')
    def test_settings_infisical_failure_debug_mode(
        self, mock_manager_class, mock_config_class
    ):
        """Test Infisical failure raises in debug mode."""
        # Setup mocks to fail
        mock_config_class.side_effect = Exception("Infisical error")
        
        with pytest.raises(Exception, match="Infisical error"):
            Settings(use_infisical=True, debug=True)