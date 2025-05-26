"""Authentication strategy implementations for persistent SSH agent.

This module provides a strategy pattern implementation for handling different
authentication methods (SSH keys and Git credentials) with intelligent
fallback mechanisms and authentication result caching.
"""

# Import built-in modules
from abc import ABC
from abc import abstractmethod
import os
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Import third-party modules
from loguru import logger
from persistent_ssh_agent.constants import AuthStrategyConstants


class AuthenticationStrategy(ABC):
    """Abstract base class for authentication strategies.

    This class defines the interface that all authentication strategies must implement.
    It provides a common contract for different authentication approaches while
    allowing for flexible implementation of specific authentication logic.
    """

    @abstractmethod
    def authenticate(self, host: str, **kwargs) -> bool:
        """Execute authentication for the specified host.

        Args:
            host: Target hostname for authentication
            **kwargs: Additional authentication parameters

        Returns:
            bool: True if authentication successful, False otherwise
        """

    @abstractmethod
    def test_connection(self, host: str) -> bool:
        """Test connection to the specified host.

        Args:
            host: Target hostname to test

        Returns:
            bool: True if connection test successful, False otherwise
        """

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current authentication status and statistics.

        Returns:
            Dict containing authentication status information
        """


class SmartAuthenticationStrategy(AuthenticationStrategy):
    """Smart authentication strategy with automatic fallback and caching.

    This strategy implements intelligent authentication selection by:
    1. Checking environment variables for forced authentication modes
    2. Using cached successful authentication methods when available
    3. Testing Git credentials first (faster and more common)
    4. Falling back to SSH authentication if credentials fail
    5. Caching successful authentication methods for future use
    """

    def __init__(self, ssh_agent, preferences: Optional[Dict[str, Any]] = None):
        """Initialize smart authentication strategy.

        Args:
            ssh_agent: PersistentSSHAgent instance
            preferences: Optional preferences dictionary for strategy configuration
        """
        self._ssh_agent = ssh_agent
        self._preferences = preferences or {}
        self._last_successful_method: Dict[str, str] = {}
        self._auth_cache: Dict[str, Dict[str, Any]] = {}

    def authenticate(self, host: str, **kwargs) -> bool:
        """Execute smart authentication with automatic fallback.

        Authentication flow:
        1. Check environment variables for forced authentication modes
        2. Check cache for last successful method
        3. Try Git credentials first (if not forced to SSH)
        4. Fall back to SSH authentication if credentials fail
        5. Cache successful authentication method

        Args:
            host: Target hostname for authentication
            **kwargs: Additional parameters (username, password, etc.)

        Returns:
            bool: True if authentication successful, False otherwise
        """
        logger.debug(f"Starting smart authentication for host: {host}")

        # Check environment variables for forced authentication modes
        force_ssh = self._get_env_bool(AuthStrategyConstants.ENV_FORCE_SSH_AUTH)
        prefer_ssh = self._get_env_bool(AuthStrategyConstants.ENV_PREFER_SSH_AUTH)
        auth_strategy = os.environ.get(AuthStrategyConstants.ENV_AUTH_STRATEGY, "").lower()

        # Determine authentication order based on environment and preferences
        if force_ssh or auth_strategy == AuthStrategyConstants.STRATEGY_SSH_ONLY:
            logger.debug("Forced SSH authentication mode")
            return self._try_ssh_auth(host)
        elif auth_strategy == AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY:
            logger.debug("Forced credentials authentication mode")
            return self._try_credentials_auth(host, **kwargs)

        # Smart authentication: try based on last successful method or preferences
        last_method = self._last_successful_method.get(host)

        if (
            prefer_ssh
            or auth_strategy == AuthStrategyConstants.STRATEGY_SSH_FIRST
            or last_method == AuthStrategyConstants.AUTH_METHOD_SSH
        ):
            # Try SSH first, then credentials
            logger.debug("Trying SSH authentication first")
            if self._try_ssh_auth(host):
                self._cache_successful_method(host, AuthStrategyConstants.AUTH_METHOD_SSH)
                return True

            logger.debug("SSH authentication failed, trying credentials")
            if self._try_credentials_auth(host, **kwargs):
                self._cache_successful_method(host, AuthStrategyConstants.AUTH_METHOD_CREDENTIALS)
                return True
        else:
            # Try credentials first, then SSH (default behavior)
            logger.debug("Trying credentials authentication first")
            if self._try_credentials_auth(host, **kwargs):
                self._cache_successful_method(host, AuthStrategyConstants.AUTH_METHOD_CREDENTIALS)
                return True

            logger.debug("Credentials authentication failed, trying SSH")
            if self._try_ssh_auth(host):
                self._cache_successful_method(host, AuthStrategyConstants.AUTH_METHOD_SSH)
                return True

        logger.error(f"All authentication methods failed for host: {host}")
        return False

    def test_connection(self, host: str) -> bool:
        """Test connection to the specified host using available methods.

        Args:
            host: Target hostname to test

        Returns:
            bool: True if any connection method succeeds
        """
        logger.debug(f"Testing connection to host: {host}")

        # Try both SSH and credentials testing
        ssh_test = self._test_ssh_connection(host)
        credentials_test = self._test_credentials_connection(host)

        result = ssh_test or credentials_test
        logger.debug(f"Connection test result for {host}: SSH={ssh_test}, Credentials={credentials_test}")

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive authentication status.

        Returns:
            Dict containing authentication status, cache info, and statistics
        """
        return {
            "strategy_type": "smart",
            "last_successful_methods": self._last_successful_method.copy(),
            "cache_entries": len(self._auth_cache),
            "preferences": self._preferences.copy(),
            "environment_overrides": {
                "force_ssh": self._get_env_bool(AuthStrategyConstants.ENV_FORCE_SSH_AUTH),
                "prefer_ssh": self._get_env_bool(AuthStrategyConstants.ENV_PREFER_SSH_AUTH),
                "auth_strategy": os.environ.get(AuthStrategyConstants.ENV_AUTH_STRATEGY, ""),
            },
        }

    def _try_ssh_auth(self, host: str) -> bool:
        """Try SSH authentication for the specified host.

        Args:
            host: Target hostname

        Returns:
            bool: True if SSH authentication successful
        """
        try:
            return self._ssh_agent.setup_ssh(host)
        except Exception as e:
            logger.error(f"SSH authentication failed for {host}: {e}")
            return False

    def _try_credentials_auth(self, host: str, **kwargs) -> bool:
        """Try Git credentials authentication for the specified host.

        Args:
            host: Target hostname
            **kwargs: Credentials (username, password)

        Returns:
            bool: True if credentials authentication successful
        """
        try:
            # Test if credentials are available and valid
            test_result = self._ssh_agent.git.test_credentials(
                host=host, username=kwargs.get("username"), password=kwargs.get("password")
            )
            return test_result.get(host, False) if isinstance(test_result, dict) else test_result
        except Exception as e:
            logger.error(f"Credentials authentication failed for {host}: {e}")
            return False

    def _test_ssh_connection(self, host: str) -> bool:
        """Test SSH connection to host.

        Args:
            host: Target hostname

        Returns:
            bool: True if SSH connection successful
        """
        try:
            return self._ssh_agent._test_ssh_connection(host)
        except Exception as e:
            logger.debug(f"SSH connection test failed for {host}: {e}")
            return False

    def _test_credentials_connection(self, host: str) -> bool:
        """Test credentials connection to host.

        Args:
            host: Target hostname

        Returns:
            bool: True if credentials connection successful
        """
        try:
            test_result = self._ssh_agent.git.test_credentials(host=host)
            return test_result.get(host, False) if isinstance(test_result, dict) else test_result
        except Exception as e:
            logger.debug(f"Credentials connection test failed for {host}: {e}")
            return False

    def _cache_successful_method(self, host: str, method: str) -> None:
        """Cache successful authentication method for future use.

        Args:
            host: Target hostname
            method: Successful authentication method
        """
        self._last_successful_method[host] = method
        self._auth_cache[host] = {"method": method, "timestamp": time.time(), "success": True}
        logger.debug(f"Cached successful authentication method for {host}: {method}")

    def _get_env_bool(self, env_var: str) -> bool:
        """Get boolean value from environment variable.

        Args:
            env_var: Environment variable name

        Returns:
            bool: True if environment variable is set to a truthy value
        """
        value = os.environ.get(env_var, "").lower()
        return value in ("true", "1", "yes", "on")


class SSHOnlyAuthenticationStrategy(AuthenticationStrategy):
    """Authentication strategy that only uses SSH keys.

    This strategy forces the use of SSH key authentication and will not
    attempt to use Git credentials. Useful for environments where only
    SSH authentication is desired or allowed.
    """

    def __init__(self, ssh_agent):
        """Initialize SSH-only authentication strategy.

        Args:
            ssh_agent: PersistentSSHAgent instance
        """
        self._ssh_agent = ssh_agent

    def authenticate(self, host: str, **kwargs) -> bool:
        """Execute SSH-only authentication.

        Args:
            host: Target hostname for authentication
            **kwargs: Additional parameters (ignored for SSH-only)

        Returns:
            bool: True if SSH authentication successful, False otherwise
        """
        # Explicitly ignore kwargs for SSH-only authentication
        _ = kwargs
        logger.debug(f"SSH-only authentication for host: {host}")
        try:
            return self._ssh_agent.setup_ssh(host)
        except Exception as e:
            logger.error(f"SSH authentication failed for {host}: {e}")
            return False

    def test_connection(self, host: str) -> bool:
        """Test SSH connection to the specified host.

        Args:
            host: Target hostname to test

        Returns:
            bool: True if SSH connection successful
        """
        try:
            return self._ssh_agent._test_ssh_connection(host)
        except Exception as e:
            logger.debug(f"SSH connection test failed for {host}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get SSH-only authentication status.

        Returns:
            Dict containing authentication status information
        """
        return {
            "strategy_type": "ssh_only",
            "ssh_agent_active": self._ssh_agent._ssh_agent_started,
            "supported_methods": [AuthStrategyConstants.AUTH_METHOD_SSH],
        }


class CredentialsOnlyAuthenticationStrategy(AuthenticationStrategy):
    """Authentication strategy that only uses Git credentials.

    This strategy forces the use of Git credential authentication and will not
    attempt to use SSH keys. Useful for environments where only credential-based
    authentication is desired or SSH is not available.
    """

    def __init__(self, ssh_agent):
        """Initialize credentials-only authentication strategy.

        Args:
            ssh_agent: PersistentSSHAgent instance (for Git integration)
        """
        self._ssh_agent = ssh_agent

    def authenticate(self, host: str, **kwargs) -> bool:
        """Execute credentials-only authentication.

        Args:
            host: Target hostname for authentication
            **kwargs: Credentials (username, password)

        Returns:
            bool: True if credentials authentication successful, False otherwise
        """
        logger.debug(f"Credentials-only authentication for host: {host}")
        try:
            test_result = self._ssh_agent.git.test_credentials(
                host=host, username=kwargs.get("username"), password=kwargs.get("password")
            )
            return test_result.get(host, False) if isinstance(test_result, dict) else test_result
        except Exception as e:
            logger.error(f"Credentials authentication failed for {host}: {e}")
            return False

    def test_connection(self, host: str) -> bool:
        """Test credentials connection to the specified host.

        Args:
            host: Target hostname to test

        Returns:
            bool: True if credentials connection successful
        """
        try:
            test_result = self._ssh_agent.git.test_credentials(host=host)
            return test_result.get(host, False) if isinstance(test_result, dict) else test_result
        except Exception as e:
            logger.debug(f"Credentials connection test failed for {host}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get credentials-only authentication status.

        Returns:
            Dict containing authentication status information
        """
        return {
            "strategy_type": "credentials_only",
            "git_integration_available": hasattr(self._ssh_agent, "git"),
            "supported_methods": [AuthStrategyConstants.AUTH_METHOD_CREDENTIALS],
        }


class AuthenticationStrategyFactory:
    """Factory class for creating authentication strategy instances.

    This factory provides a centralized way to create authentication strategy
    instances based on strategy type and configuration.
    """

    @staticmethod
    def create_strategy(strategy_type: str, ssh_agent, **kwargs) -> AuthenticationStrategy:
        """Create an authentication strategy instance.

        Args:
            strategy_type: Type of strategy to create
            ssh_agent: PersistentSSHAgent instance
            **kwargs: Additional configuration parameters

        Returns:
            AuthenticationStrategy instance

        Raises:
            ValueError: If strategy_type is not supported
        """
        strategy_type = strategy_type.lower()

        if strategy_type == AuthStrategyConstants.STRATEGY_SMART:
            return SmartAuthenticationStrategy(ssh_agent, kwargs.get("preferences"))
        if strategy_type == AuthStrategyConstants.STRATEGY_SSH_ONLY:
            return SSHOnlyAuthenticationStrategy(ssh_agent)
        if strategy_type == AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY:
            return CredentialsOnlyAuthenticationStrategy(ssh_agent)

        raise ValueError(f"Unsupported authentication strategy: {strategy_type}")

    @staticmethod
    def get_available_strategies() -> List[str]:
        """Get list of available authentication strategies.

        Returns:
            List of available strategy names
        """
        return [
            AuthStrategyConstants.STRATEGY_SMART,
            AuthStrategyConstants.STRATEGY_SSH_ONLY,
            AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY,
        ]

    @staticmethod
    def get_default_strategy() -> str:
        """Get the default authentication strategy.

        Returns:
            Default strategy name
        """
        return AuthStrategyConstants.DEFAULT_STRATEGY


# Export all classes for easy access
__all__ = [
    "AuthenticationStrategy",
    "AuthenticationStrategyFactory",
    "CredentialsOnlyAuthenticationStrategy",
    "SSHOnlyAuthenticationStrategy",
    "SmartAuthenticationStrategy",
]
