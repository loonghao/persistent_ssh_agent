"""Tests for authentication strategy implementations."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from persistent_ssh_agent.auth_strategy import (
    AuthenticationStrategy,
    AuthenticationStrategyFactory,
    CredentialsOnlyAuthenticationStrategy,
    SmartAuthenticationStrategy,
    SSHOnlyAuthenticationStrategy,
)
from persistent_ssh_agent.constants import AuthStrategyConstants


class TestAuthenticationStrategy:
    """Test the abstract AuthenticationStrategy base class."""

    def test_abstract_methods(self):
        """Test that AuthenticationStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AuthenticationStrategy()


class TestSmartAuthenticationStrategy:
    """Test the SmartAuthenticationStrategy implementation."""

    @pytest.fixture
    def mock_ssh_agent(self):
        """Create a mock SSH agent for testing."""
        agent = MagicMock()
        agent.setup_ssh.return_value = True
        agent._test_ssh_connection.return_value = True
        agent.git.test_credentials.return_value = {"github.com": True}
        return agent

    @pytest.fixture
    def strategy(self, mock_ssh_agent):
        """Create a SmartAuthenticationStrategy instance for testing."""
        return SmartAuthenticationStrategy(mock_ssh_agent)

    def test_init(self, mock_ssh_agent):
        """Test SmartAuthenticationStrategy initialization."""
        preferences = {"test": "value"}
        strategy = SmartAuthenticationStrategy(mock_ssh_agent, preferences)
        
        assert strategy._ssh_agent == mock_ssh_agent
        assert strategy._preferences == preferences
        assert strategy._last_successful_method == {}
        assert strategy._auth_cache == {}

    def test_init_without_preferences(self, mock_ssh_agent):
        """Test SmartAuthenticationStrategy initialization without preferences."""
        strategy = SmartAuthenticationStrategy(mock_ssh_agent)
        
        assert strategy._preferences == {}

    @patch.dict(os.environ, {}, clear=True)
    def test_authenticate_credentials_first_success(self, strategy, mock_ssh_agent):
        """Test authentication with credentials first (default behavior)."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        assert strategy._last_successful_method["github.com"] == AuthStrategyConstants.AUTH_METHOD_CREDENTIALS
        mock_ssh_agent.git.test_credentials.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_authenticate_ssh_fallback_success(self, strategy, mock_ssh_agent):
        """Test authentication with SSH fallback when credentials fail."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": False}
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        assert strategy._last_successful_method["github.com"] == AuthStrategyConstants.AUTH_METHOD_SSH
        mock_ssh_agent.git.test_credentials.assert_called_once()
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")

    @patch.dict(os.environ, {"FORCE_SSH_AUTH": "true"}, clear=True)
    def test_authenticate_force_ssh(self, strategy, mock_ssh_agent):
        """Test authentication with forced SSH mode."""
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")
        mock_ssh_agent.git.test_credentials.assert_not_called()

    @patch.dict(os.environ, {"AUTH_STRATEGY": "ssh_only"}, clear=True)
    def test_authenticate_ssh_only_strategy(self, strategy, mock_ssh_agent):
        """Test authentication with SSH only strategy."""
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")
        mock_ssh_agent.git.test_credentials.assert_not_called()

    @patch.dict(os.environ, {"AUTH_STRATEGY": "credentials_only"}, clear=True)
    def test_authenticate_credentials_only_strategy(self, strategy, mock_ssh_agent):
        """Test authentication with credentials only strategy."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        mock_ssh_agent.git.test_credentials.assert_called_once()
        mock_ssh_agent.setup_ssh.assert_not_called()

    @patch.dict(os.environ, {"PREFER_SSH_AUTH": "true"}, clear=True)
    def test_authenticate_prefer_ssh(self, strategy, mock_ssh_agent):
        """Test authentication with SSH preference."""
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")

    def test_authenticate_all_methods_fail(self, strategy, mock_ssh_agent):
        """Test authentication when all methods fail."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": False}
        mock_ssh_agent.setup_ssh.return_value = False
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is False

    def test_authenticate_with_cached_method(self, strategy, mock_ssh_agent):
        """Test authentication using cached successful method."""
        # Set up cache
        strategy._last_successful_method["github.com"] = AuthStrategyConstants.AUTH_METHOD_SSH
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")

    def test_test_connection(self, strategy, mock_ssh_agent):
        """Test connection testing functionality."""
        mock_ssh_agent._test_ssh_connection.return_value = True
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.test_connection("github.com")
        
        assert result is True

    def test_test_connection_partial_success(self, strategy, mock_ssh_agent):
        """Test connection testing with partial success."""
        mock_ssh_agent._test_ssh_connection.return_value = False
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.test_connection("github.com")
        
        assert result is True

    def test_test_connection_all_fail(self, strategy, mock_ssh_agent):
        """Test connection testing when all methods fail."""
        mock_ssh_agent._test_ssh_connection.return_value = False
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": False}
        
        result = strategy.test_connection("github.com")
        
        assert result is False

    @patch.dict(os.environ, {"FORCE_SSH_AUTH": "true", "AUTH_STRATEGY": "smart"}, clear=True)
    def test_get_status(self, strategy):
        """Test status reporting functionality."""
        strategy._last_successful_method["github.com"] = AuthStrategyConstants.AUTH_METHOD_SSH
        strategy._preferences = {"test": "value"}
        
        status = strategy.get_status()
        
        assert status["strategy_type"] == "smart"
        assert status["last_successful_methods"]["github.com"] == AuthStrategyConstants.AUTH_METHOD_SSH
        assert status["preferences"]["test"] == "value"
        assert status["environment_overrides"]["force_ssh"] is True
        assert status["environment_overrides"]["auth_strategy"] == "smart"

    def test_get_env_bool_true_values(self, strategy):
        """Test environment boolean parsing for true values."""
        with patch.dict(os.environ, {"TEST_VAR": "true"}):
            assert strategy._get_env_bool("TEST_VAR") is True
        
        with patch.dict(os.environ, {"TEST_VAR": "1"}):
            assert strategy._get_env_bool("TEST_VAR") is True
        
        with patch.dict(os.environ, {"TEST_VAR": "yes"}):
            assert strategy._get_env_bool("TEST_VAR") is True
        
        with patch.dict(os.environ, {"TEST_VAR": "on"}):
            assert strategy._get_env_bool("TEST_VAR") is True

    def test_get_env_bool_false_values(self, strategy):
        """Test environment boolean parsing for false values."""
        with patch.dict(os.environ, {"TEST_VAR": "false"}):
            assert strategy._get_env_bool("TEST_VAR") is False
        
        with patch.dict(os.environ, {"TEST_VAR": "0"}):
            assert strategy._get_env_bool("TEST_VAR") is False
        
        with patch.dict(os.environ, {}, clear=True):
            assert strategy._get_env_bool("TEST_VAR") is False

    def test_cache_successful_method(self, strategy):
        """Test caching of successful authentication methods."""
        strategy._cache_successful_method("github.com", AuthStrategyConstants.AUTH_METHOD_SSH)
        
        assert strategy._last_successful_method["github.com"] == AuthStrategyConstants.AUTH_METHOD_SSH
        assert strategy._auth_cache["github.com"]["method"] == AuthStrategyConstants.AUTH_METHOD_SSH
        assert strategy._auth_cache["github.com"]["success"] is True
        assert "timestamp" in strategy._auth_cache["github.com"]

    def test_try_ssh_auth_success(self, strategy, mock_ssh_agent):
        """Test SSH authentication attempt success."""
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy._try_ssh_auth("github.com")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")

    def test_try_ssh_auth_failure(self, strategy, mock_ssh_agent):
        """Test SSH authentication attempt failure."""
        mock_ssh_agent.setup_ssh.side_effect = Exception("SSH failed")
        
        result = strategy._try_ssh_auth("github.com")
        
        assert result is False

    def test_try_credentials_auth_success(self, strategy, mock_ssh_agent):
        """Test credentials authentication attempt success."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy._try_credentials_auth("github.com", username="user", password="pass")
        
        assert result is True

    def test_try_credentials_auth_dict_response(self, strategy, mock_ssh_agent):
        """Test credentials authentication with dictionary response."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": False}
        
        result = strategy._try_credentials_auth("github.com", username="user", password="pass")
        
        assert result is False

    def test_try_credentials_auth_boolean_response(self, strategy, mock_ssh_agent):
        """Test credentials authentication with boolean response."""
        mock_ssh_agent.git.test_credentials.return_value = True
        
        result = strategy._try_credentials_auth("github.com", username="user", password="pass")
        
        assert result is True

    def test_try_credentials_auth_failure(self, strategy, mock_ssh_agent):
        """Test credentials authentication attempt failure."""
        mock_ssh_agent.git.test_credentials.side_effect = Exception("Credentials failed")
        
        result = strategy._try_credentials_auth("github.com", username="user", password="pass")
        
        assert result is False


class TestSSHOnlyAuthenticationStrategy:
    """Test the SSHOnlyAuthenticationStrategy implementation."""

    @pytest.fixture
    def mock_ssh_agent(self):
        """Create a mock SSH agent for testing."""
        agent = MagicMock()
        agent.setup_ssh.return_value = True
        agent._test_ssh_connection.return_value = True
        agent._ssh_agent_started = True
        return agent

    @pytest.fixture
    def strategy(self, mock_ssh_agent):
        """Create an SSHOnlyAuthenticationStrategy instance for testing."""
        return SSHOnlyAuthenticationStrategy(mock_ssh_agent)

    def test_init(self, mock_ssh_agent):
        """Test SSHOnlyAuthenticationStrategy initialization."""
        strategy = SSHOnlyAuthenticationStrategy(mock_ssh_agent)
        assert strategy._ssh_agent == mock_ssh_agent

    def test_authenticate_success(self, strategy, mock_ssh_agent):
        """Test successful SSH authentication."""
        mock_ssh_agent.setup_ssh.return_value = True
        
        result = strategy.authenticate("github.com", username="ignored", password="ignored")
        
        assert result is True
        mock_ssh_agent.setup_ssh.assert_called_once_with("github.com")

    def test_authenticate_failure(self, strategy, mock_ssh_agent):
        """Test failed SSH authentication."""
        mock_ssh_agent.setup_ssh.side_effect = Exception("SSH failed")
        
        result = strategy.authenticate("github.com")
        
        assert result is False

    def test_test_connection_success(self, strategy, mock_ssh_agent):
        """Test successful SSH connection test."""
        mock_ssh_agent._test_ssh_connection.return_value = True
        
        result = strategy.test_connection("github.com")
        
        assert result is True
        mock_ssh_agent._test_ssh_connection.assert_called_once_with("github.com")

    def test_test_connection_failure(self, strategy, mock_ssh_agent):
        """Test failed SSH connection test."""
        mock_ssh_agent._test_ssh_connection.side_effect = Exception("Connection failed")
        
        result = strategy.test_connection("github.com")
        
        assert result is False

    def test_get_status(self, strategy, mock_ssh_agent):
        """Test status reporting for SSH-only strategy."""
        status = strategy.get_status()
        
        assert status["strategy_type"] == "ssh_only"
        assert status["ssh_agent_active"] is True
        assert status["supported_methods"] == [AuthStrategyConstants.AUTH_METHOD_SSH]


class TestCredentialsOnlyAuthenticationStrategy:
    """Test the CredentialsOnlyAuthenticationStrategy implementation."""

    @pytest.fixture
    def mock_ssh_agent(self):
        """Create a mock SSH agent for testing."""
        agent = MagicMock()
        agent.git.test_credentials.return_value = {"github.com": True}
        return agent

    @pytest.fixture
    def strategy(self, mock_ssh_agent):
        """Create a CredentialsOnlyAuthenticationStrategy instance for testing."""
        return CredentialsOnlyAuthenticationStrategy(mock_ssh_agent)

    def test_init(self, mock_ssh_agent):
        """Test CredentialsOnlyAuthenticationStrategy initialization."""
        strategy = CredentialsOnlyAuthenticationStrategy(mock_ssh_agent)
        assert strategy._ssh_agent == mock_ssh_agent

    def test_authenticate_success(self, strategy, mock_ssh_agent):
        """Test successful credentials authentication."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True
        mock_ssh_agent.git.test_credentials.assert_called_once()

    def test_authenticate_dict_false(self, strategy, mock_ssh_agent):
        """Test credentials authentication with dict false response."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": False}
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is False

    def test_authenticate_boolean_response(self, strategy, mock_ssh_agent):
        """Test credentials authentication with boolean response."""
        mock_ssh_agent.git.test_credentials.return_value = True
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is True

    def test_authenticate_failure(self, strategy, mock_ssh_agent):
        """Test failed credentials authentication."""
        mock_ssh_agent.git.test_credentials.side_effect = Exception("Credentials failed")
        
        result = strategy.authenticate("github.com", username="user", password="pass")
        
        assert result is False

    def test_test_connection_success(self, strategy, mock_ssh_agent):
        """Test successful credentials connection test."""
        mock_ssh_agent.git.test_credentials.return_value = {"github.com": True}
        
        result = strategy.test_connection("github.com")
        
        assert result is True

    def test_test_connection_failure(self, strategy, mock_ssh_agent):
        """Test failed credentials connection test."""
        mock_ssh_agent.git.test_credentials.side_effect = Exception("Connection failed")
        
        result = strategy.test_connection("github.com")
        
        assert result is False

    def test_get_status(self, strategy, mock_ssh_agent):
        """Test status reporting for credentials-only strategy."""
        status = strategy.get_status()
        
        assert status["strategy_type"] == "credentials_only"
        assert status["git_integration_available"] is True
        assert status["supported_methods"] == [AuthStrategyConstants.AUTH_METHOD_CREDENTIALS]


class TestAuthenticationStrategyFactory:
    """Test the AuthenticationStrategyFactory."""

    @pytest.fixture
    def mock_ssh_agent(self):
        """Create a mock SSH agent for testing."""
        return MagicMock()

    def test_create_smart_strategy(self, mock_ssh_agent):
        """Test creating SmartAuthenticationStrategy."""
        strategy = AuthenticationStrategyFactory.create_strategy(
            AuthStrategyConstants.STRATEGY_SMART, mock_ssh_agent
        )
        
        assert isinstance(strategy, SmartAuthenticationStrategy)
        assert strategy._ssh_agent == mock_ssh_agent

    def test_create_ssh_only_strategy(self, mock_ssh_agent):
        """Test creating SSHOnlyAuthenticationStrategy."""
        strategy = AuthenticationStrategyFactory.create_strategy(
            AuthStrategyConstants.STRATEGY_SSH_ONLY, mock_ssh_agent
        )
        
        assert isinstance(strategy, SSHOnlyAuthenticationStrategy)
        assert strategy._ssh_agent == mock_ssh_agent

    def test_create_credentials_only_strategy(self, mock_ssh_agent):
        """Test creating CredentialsOnlyAuthenticationStrategy."""
        strategy = AuthenticationStrategyFactory.create_strategy(
            AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY, mock_ssh_agent
        )
        
        assert isinstance(strategy, CredentialsOnlyAuthenticationStrategy)
        assert strategy._ssh_agent == mock_ssh_agent

    def test_create_strategy_with_preferences(self, mock_ssh_agent):
        """Test creating strategy with preferences."""
        preferences = {"test": "value"}
        strategy = AuthenticationStrategyFactory.create_strategy(
            AuthStrategyConstants.STRATEGY_SMART, mock_ssh_agent, preferences=preferences
        )
        
        assert isinstance(strategy, SmartAuthenticationStrategy)
        assert strategy._preferences == preferences

    def test_create_strategy_case_insensitive(self, mock_ssh_agent):
        """Test creating strategy with case insensitive type."""
        strategy = AuthenticationStrategyFactory.create_strategy(
            "SMART", mock_ssh_agent
        )
        
        assert isinstance(strategy, SmartAuthenticationStrategy)

    def test_create_strategy_invalid_type(self, mock_ssh_agent):
        """Test creating strategy with invalid type."""
        with pytest.raises(ValueError, match="Unsupported authentication strategy"):
            AuthenticationStrategyFactory.create_strategy("invalid", mock_ssh_agent)

    def test_get_available_strategies(self):
        """Test getting available strategies."""
        strategies = AuthenticationStrategyFactory.get_available_strategies()
        
        expected = [
            AuthStrategyConstants.STRATEGY_SMART,
            AuthStrategyConstants.STRATEGY_SSH_ONLY,
            AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY,
        ]
        assert strategies == expected

    def test_get_default_strategy(self):
        """Test getting default strategy."""
        default = AuthenticationStrategyFactory.get_default_strategy()
        assert default == AuthStrategyConstants.DEFAULT_STRATEGY
