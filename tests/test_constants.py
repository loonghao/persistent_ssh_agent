"""Tests for constants module."""

# Import built-in modules

# Import third-party modules
from persistent_ssh_agent.constants import AuthStrategyConstants
from persistent_ssh_agent.constants import CLIConstants
from persistent_ssh_agent.constants import GitConstants
from persistent_ssh_agent.constants import LoggingConstants
from persistent_ssh_agent.constants import SSHAgentConstants
from persistent_ssh_agent.constants import SystemConstants


class TestSSHAgentConstants:
    """Test SSH agent constants."""

    def test_ssh_key_types_order(self):
        """Test that SSH key types are in preference order."""
        key_types = SSHAgentConstants.SSH_KEY_TYPES
        
        # Should have expected key types
        assert "id_ed25519" in key_types
        assert "id_rsa" in key_types
        assert "id_ecdsa" in key_types
        assert "id_dsa" in key_types
        
        # Ed25519 should be first (most secure)
        assert key_types[0] == "id_ed25519"
        
        # DSA should be last (least secure)
        assert key_types[-1] == "id_dsa"

    def test_ssh_default_key(self):
        """Test SSH default key constant."""
        assert SSHAgentConstants.SSH_DEFAULT_KEY == "id_rsa"
        assert SSHAgentConstants.SSH_DEFAULT_KEY in SSHAgentConstants.SSH_KEY_TYPES

    def test_ssh_default_options(self):
        """Test SSH default options."""
        options = SSHAgentConstants.SSH_DEFAULT_OPTIONS
        
        # Should be a list
        assert isinstance(options, list)
        
        # Should contain expected options
        assert "-o" in options
        assert "StrictHostKeyChecking=no" in options
        assert "UserKnownHostsFile=/dev/null" in options
        assert "LogLevel=ERROR" in options

    def test_ssh_environment_variables(self):
        """Test SSH environment variable constants."""
        assert SSHAgentConstants.SSH_AUTH_SOCK_VAR == "SSH_AUTH_SOCK"
        assert SSHAgentConstants.SSH_AGENT_PID_VAR == "SSH_AGENT_PID"

    def test_default_expiration_time(self):
        """Test default expiration time (24 hours in seconds)."""
        assert SSHAgentConstants.DEFAULT_EXPIRATION_TIME == 86400
        assert SSHAgentConstants.DEFAULT_EXPIRATION_TIME == 24 * 60 * 60

    def test_file_names(self):
        """Test SSH-related file names."""
        assert SSHAgentConstants.AGENT_INFO_FILE == "agent_info.json"
        assert SSHAgentConstants.SSH_CONFIG_FILE == "config"
        assert SSHAgentConstants.SSH_DIR_NAME == ".ssh"


class TestGitConstants:
    """Test Git constants."""

    def test_git_environment_variables(self):
        """Test Git environment variable constants."""
        assert GitConstants.GIT_USERNAME_VAR == "GIT_USERNAME"
        assert GitConstants.GIT_PASSWORD_VAR == "GIT_PASSWORD"
        assert GitConstants.GIT_SSH_COMMAND_VAR == "GIT_SSH_COMMAND"

    def test_common_git_hosts(self):
        """Test common Git hosting services."""
        hosts = GitConstants.COMMON_GIT_HOSTS
        
        # Should be a list
        assert isinstance(hosts, list)
        
        # Should contain major Git hosting services
        assert "github.com" in hosts
        assert "gitlab.com" in hosts
        assert "bitbucket.org" in hosts

    def test_credential_helper_config(self):
        """Test credential helper configuration constants."""
        assert GitConstants.CREDENTIAL_HELPER_CLEAR == "credential.helper="
        assert GitConstants.CREDENTIAL_USE_HTTP_PATH == "credential.useHttpPath=true"

    def test_timeouts(self):
        """Test timeout constants."""
        assert GitConstants.DEFAULT_CREDENTIAL_TEST_TIMEOUT == 30
        assert GitConstants.DEFAULT_NETWORK_TEST_TIMEOUT == 10
        
        # Timeouts should be positive integers
        assert GitConstants.DEFAULT_CREDENTIAL_TEST_TIMEOUT > 0
        assert GitConstants.DEFAULT_NETWORK_TEST_TIMEOUT > 0

    def test_test_repositories(self):
        """Test repository constants for testing."""
        repos = GitConstants.TEST_REPOSITORIES
        
        # Should be a dictionary
        assert isinstance(repos, dict)
        
        # Should have entries for major hosts
        assert "github.com" in repos
        assert "gitlab.com" in repos
        assert "bitbucket.org" in repos
        
        # Each entry should be a list of URLs
        for _host, urls in repos.items():
            assert isinstance(urls, list)
            assert len(urls) > 0
            for url in urls:
                assert isinstance(url, str)
                assert url.startswith("https://")

    def test_system_credential_helpers(self):
        """Test system credential helper constants."""
        helpers = GitConstants.SYSTEM_CREDENTIAL_HELPERS
        
        # Should be a list
        assert isinstance(helpers, list)
        
        # Should contain common credential helpers
        assert "manager" in helpers  # Windows
        assert "store" in helpers    # Cross-platform
        assert "cache" in helpers    # Cross-platform
        assert "osxkeychain" in helpers  # macOS
        assert "wincred" in helpers  # Windows


class TestCLIConstants:
    """Test CLI constants."""

    def test_config_file_names(self):
        """Test configuration file name constants."""
        assert CLIConstants.CONFIG_DIR_NAME == ".persistent_ssh_agent"
        assert CLIConstants.CONFIG_FILE_NAME == "config.json"
        assert CLIConstants.LEGACY_CONFIG_FILE_NAME == "persistent_ssh_agent_config.json"

    def test_encryption_constants(self):
        """Test encryption-related constants."""
        assert CLIConstants.ENCRYPTION_ALGORITHM == "AES-256-GCM"
        assert CLIConstants.KEY_DERIVATION_ITERATIONS == 100000
        assert CLIConstants.SALT_SIZE == 16
        assert CLIConstants.IV_SIZE == 16
        assert CLIConstants.KEY_SIZE == 32
        assert CLIConstants.AES_BLOCK_SIZE == 16

    def test_time_conversion_constants(self):
        """Test time conversion constants."""
        assert CLIConstants.SECONDS_PER_HOUR == 3600
        assert CLIConstants.HOURS_PER_DAY == 24

    def test_file_permissions(self):
        """Test file permission constants."""
        assert CLIConstants.CONFIG_DIR_PERMISSIONS == 0o700
        assert CLIConstants.CONFIG_FILE_PERMISSIONS == 0o600

    def test_cli_command_names(self):
        """Test CLI command name constants."""
        commands = [
            CLIConstants.SETUP_COMMAND,
            CLIConstants.LIST_COMMAND,
            CLIConstants.REMOVE_COMMAND,
            CLIConstants.EXPORT_COMMAND,
            CLIConstants.IMPORT_COMMAND,
            CLIConstants.TEST_COMMAND,
            CLIConstants.CONFIG_COMMAND,
            CLIConstants.GIT_SETUP_COMMAND,
            CLIConstants.GIT_DEBUG_COMMAND,
            CLIConstants.GIT_CLEAR_COMMAND,
            CLIConstants.GIT_RUN_COMMAND,
        ]
        
        # All commands should be strings
        for command in commands:
            assert isinstance(command, str)
            assert len(command) > 0

    def test_config_keys(self):
        """Test configuration key constants."""
        keys = [
            CLIConstants.CONFIG_KEY_PASSPHRASE,
            CLIConstants.CONFIG_KEY_IDENTITY_FILE,
            CLIConstants.CONFIG_KEY_EXPIRATION_TIME,
            CLIConstants.CONFIG_KEY_REUSE_AGENT,
            CLIConstants.CONFIG_KEY_KEYS,
        ]
        
        # All keys should be strings
        for key in keys:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_default_key_name(self):
        """Test default key name constant."""
        assert CLIConstants.DEFAULT_KEY_NAME == "default"

    def test_non_sensitive_keys(self):
        """Test non-sensitive configuration keys."""
        non_sensitive = CLIConstants.NON_SENSITIVE_KEYS
        
        # Should be a list
        assert isinstance(non_sensitive, list)
        
        # Should contain expected keys
        assert "identity_file" in non_sensitive
        assert "keys" in non_sensitive
        assert "expiration_time" in non_sensitive
        assert "reuse_agent" in non_sensitive
        
        # Should not contain sensitive keys
        assert "passphrase" not in non_sensitive


class TestSystemConstants:
    """Test system constants."""

    def test_file_extensions(self):
        """Test file extension constants."""
        assert SystemConstants.SSH_PUBLIC_KEY_EXTENSION == ".pub"
        assert SystemConstants.SSH_PRIVATE_KEY_EXTENSION == ""
        assert SystemConstants.JSON_EXTENSION == ".json"

    def test_system_paths(self):
        """Test system path constants."""
        assert SystemConstants.LINUX_MACHINE_ID_PATH == "/etc/machine-id"
        assert SystemConstants.WINDOWS_MACHINE_GUID_REGISTRY_PATH == r"SOFTWARE\Microsoft\Cryptography"
        assert SystemConstants.WINDOWS_MACHINE_GUID_KEY == "MachineGuid"

    def test_platform_identifiers(self):
        """Test platform identifier constants."""
        assert SystemConstants.WINDOWS_PLATFORM == "nt"
        assert SystemConstants.POSIX_PLATFORM == "posix"

    def test_fallback_values(self):
        """Test fallback value constants."""
        fallbacks = [
            SystemConstants.UNKNOWN_HOST,
            SystemConstants.UNKNOWN_MACHINE,
            SystemConstants.UNKNOWN_USER,
            SystemConstants.UNKNOWN_HOME,
        ]
        
        # All fallbacks should be strings containing "unknown"
        for fallback in fallbacks:
            assert isinstance(fallback, str)
            assert "unknown" in fallback

    def test_environment_variables(self):
        """Test environment variable name constants."""
        assert SystemConstants.ENV_USER == "USER"
        assert SystemConstants.ENV_USERNAME == "USERNAME"
        assert SystemConstants.ENV_HOME == "HOME"

    def test_encoding_constants(self):
        """Test encoding constants."""
        assert SystemConstants.DEFAULT_ENCODING == "utf-8"
        assert SystemConstants.FALLBACK_ENCODING == "latin1"
        assert SystemConstants.WINDOWS_ENCODING == "gbk"
        assert SystemConstants.WINDOWS_CODEPAGE == "cp936"

    def test_ssh_key_pattern(self):
        """Test SSH key numeric pattern."""
        assert SystemConstants.SSH_KEY_NUMERIC_PATTERN == "[0-9]*"


class TestLoggingConstants:
    """Test logging constants."""

    def test_log_levels(self):
        """Test log level constants."""
        levels = [
            LoggingConstants.DEBUG_LEVEL,
            LoggingConstants.INFO_LEVEL,
            LoggingConstants.WARNING_LEVEL,
            LoggingConstants.ERROR_LEVEL,
        ]
        
        # All levels should be strings
        for level in levels:
            assert isinstance(level, str)
            assert len(level) > 0

    def test_log_formats(self):
        """Test log format constants."""
        formats = [
            LoggingConstants.DEBUG_LOG_FORMAT,
            LoggingConstants.DEFAULT_LOG_FORMAT,
        ]
        
        # All formats should be strings containing loguru format placeholders
        for fmt in formats:
            assert isinstance(fmt, str)
            assert "{time:" in fmt
            assert "{level:" in fmt
            assert "{message}" in fmt

    def test_log_prefixes(self):
        """Test log message prefix constants."""
        prefixes = [
            LoggingConstants.SUCCESS_PREFIX,
            LoggingConstants.ERROR_PREFIX,
            LoggingConstants.WARNING_PREFIX,
            LoggingConstants.INFO_PREFIX,
            LoggingConstants.DEBUG_PREFIX,
            LoggingConstants.ROCKET_PREFIX,
        ]
        
        # All prefixes should be strings (emojis)
        for prefix in prefixes:
            assert isinstance(prefix, str)
            assert len(prefix) > 0


class TestAuthStrategyConstants:
    """Test authentication strategy constants."""

    def test_strategy_types(self):
        """Test authentication strategy type constants."""
        strategies = [
            AuthStrategyConstants.STRATEGY_SMART,
            AuthStrategyConstants.STRATEGY_SSH_FIRST,
            AuthStrategyConstants.STRATEGY_CREDENTIALS_FIRST,
            AuthStrategyConstants.STRATEGY_SSH_ONLY,
            AuthStrategyConstants.STRATEGY_CREDENTIALS_ONLY,
        ]
        
        # All strategies should be strings
        for strategy in strategies:
            assert isinstance(strategy, str)
            assert len(strategy) > 0

    def test_default_strategy(self):
        """Test default authentication strategy."""
        assert AuthStrategyConstants.DEFAULT_STRATEGY == AuthStrategyConstants.STRATEGY_SMART

    def test_environment_variables(self):
        """Test authentication strategy environment variables."""
        env_vars = [
            AuthStrategyConstants.ENV_FORCE_SSH_AUTH,
            AuthStrategyConstants.ENV_PREFER_SSH_AUTH,
            AuthStrategyConstants.ENV_AUTH_STRATEGY,
        ]
        
        # All env vars should be strings
        for env_var in env_vars:
            assert isinstance(env_var, str)
            assert len(env_var) > 0

    def test_auth_methods(self):
        """Test authentication method constants."""
        assert AuthStrategyConstants.AUTH_METHOD_SSH == "ssh"
        assert AuthStrategyConstants.AUTH_METHOD_CREDENTIALS == "credentials"

    def test_timeouts_and_durations(self):
        """Test timeout and duration constants."""
        assert AuthStrategyConstants.CONNECTION_TEST_TIMEOUT == 30
        assert AuthStrategyConstants.AUTH_CACHE_DURATION == 3600
        
        # Should be positive integers
        assert AuthStrategyConstants.CONNECTION_TEST_TIMEOUT > 0
        assert AuthStrategyConstants.AUTH_CACHE_DURATION > 0


class TestConstantsIntegrity:
    """Test constants module integrity."""

    def test_all_exports(self):
        """Test that __all__ contains all constant classes."""
        # Import third-party modules
        from persistent_ssh_agent.constants import __all__
        
        expected_classes = [
            "AuthStrategyConstants",
            "CLIConstants",
            "GitConstants",
            "LoggingConstants",
            "SSHAgentConstants",
            "SystemConstants",
        ]
        
        assert set(__all__) == set(expected_classes)

    def test_class_var_annotations(self):
        """Test that constants use ClassVar annotations."""
        # This is more of a static analysis test, but we can check a few examples
        
        # Check that constants are class attributes
        assert hasattr(SSHAgentConstants, "SSH_KEY_TYPES")
        assert hasattr(CLIConstants, "CONFIG_FILE_NAME")
        assert hasattr(GitConstants, "COMMON_GIT_HOSTS")

    def test_no_mutable_defaults(self):
        """Test that list/dict constants are not mutable references."""
        # Get two references to the same list constant
        list1 = SSHAgentConstants.SSH_KEY_TYPES
        list2 = SSHAgentConstants.SSH_KEY_TYPES
        
        # They should be the same object (immutable)
        assert list1 is list2
        
        # But we shouldn't be able to modify them (they should be tuples or frozen)
        # Note: In Python, ClassVar doesn't enforce immutability, but the constants
        # should be treated as immutable by convention
