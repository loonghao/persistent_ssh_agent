"""Constants for SSH agent operations."""

# Import built-in modules
from typing import ClassVar
from typing import List


class SSHAgentConstants:
    """Constants for SSH agent operations."""

    # SSH key types in order of preference (most secure first)
    SSH_KEY_TYPES: ClassVar[List[str]] = [
        "id_ed25519",  # Ed25519 (recommended, most secure)
        "id_ecdsa",  # ECDSA
        "id_ecdsa_sk",  # ECDSA with security key
        "id_ed25519_sk",  # Ed25519 with security key
        "id_rsa",  # RSA
        "id_dsa",  # DSA (legacy, not recommended)
    ]

    # Default SSH key type for fallback
    SSH_DEFAULT_KEY: ClassVar[str] = "id_rsa"  # Fallback default key

    # SSH command constants
    SSH_DEFAULT_OPTIONS: ClassVar[List[str]] = [
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
    ]

    # SSH agent environment variables
    SSH_AUTH_SOCK_VAR: ClassVar[str] = "SSH_AUTH_SOCK"
    SSH_AGENT_PID_VAR: ClassVar[str] = "SSH_AGENT_PID"

    # Default expiration time (24 hours in seconds)
    DEFAULT_EXPIRATION_TIME: ClassVar[int] = 86400

    # SSH agent info file name
    AGENT_INFO_FILE: ClassVar[str] = "agent_info.json"

    # SSH config file name
    SSH_CONFIG_FILE: ClassVar[str] = "config"

    # Default SSH directory name
    SSH_DIR_NAME: ClassVar[str] = ".ssh"


class GitConstants:
    """Constants for Git integration."""

    # Git environment variables
    GIT_USERNAME_VAR: ClassVar[str] = "GIT_USERNAME"
    GIT_PASSWORD_VAR: ClassVar[str] = "GIT_PASSWORD"
    GIT_SSH_COMMAND_VAR: ClassVar[str] = "GIT_SSH_COMMAND"

    # Common Git hosts
    COMMON_GIT_HOSTS: ClassVar[List[str]] = ["github.com", "gitlab.com", "bitbucket.org", "git.sr.ht", "codeberg.org"]

    # Credential helper configuration
    CREDENTIAL_HELPER_CLEAR: ClassVar[str] = "credential.helper="
    CREDENTIAL_USE_HTTP_PATH: ClassVar[str] = "credential.useHttpPath=true"

    # Default timeouts and limits
    DEFAULT_CREDENTIAL_TEST_TIMEOUT: ClassVar[int] = 30
    DEFAULT_NETWORK_TEST_TIMEOUT: ClassVar[int] = 10

    # Test repositories for credential validation
    TEST_REPOSITORIES: ClassVar[dict] = {
        "github.com": ["https://github.com/octocat/Hello-World.git"],
        "gitlab.com": ["https://gitlab.com/gitlab-org/gitlab.git"],
        "bitbucket.org": ["https://bitbucket.org/atlassian/atlassian-frontend.git"],
    }

    # System credential helpers (built into Git or OS)
    SYSTEM_CREDENTIAL_HELPERS: ClassVar[List[str]] = [
        "manager", "store", "cache", "osxkeychain", "wincred"
    ]


class CLIConstants:
    """Constants for CLI operations."""

    # Configuration directory and file names
    CONFIG_DIR_NAME: ClassVar[str] = ".persistent_ssh_agent"
    CONFIG_FILE_NAME: ClassVar[str] = "config.json"
    LEGACY_CONFIG_FILE_NAME: ClassVar[str] = "persistent_ssh_agent_config.json"

    # Encryption constants
    ENCRYPTION_ALGORITHM: ClassVar[str] = "AES-256-GCM"
    KEY_DERIVATION_ITERATIONS: ClassVar[int] = 100000
    SALT_SIZE: ClassVar[int] = 16
    IV_SIZE: ClassVar[int] = 16
    KEY_SIZE: ClassVar[int] = 32  # 256 bits
    AES_BLOCK_SIZE: ClassVar[int] = 16

    # Time conversion constants
    SECONDS_PER_HOUR: ClassVar[int] = 3600
    HOURS_PER_DAY: ClassVar[int] = 24

    # File permissions (Unix/Linux)
    CONFIG_DIR_PERMISSIONS: ClassVar[int] = 0o700
    CONFIG_FILE_PERMISSIONS: ClassVar[int] = 0o600

    # CLI command names
    SETUP_COMMAND: ClassVar[str] = "setup"
    LIST_COMMAND: ClassVar[str] = "list"
    REMOVE_COMMAND: ClassVar[str] = "remove"
    EXPORT_COMMAND: ClassVar[str] = "export"
    IMPORT_COMMAND: ClassVar[str] = "import"
    TEST_COMMAND: ClassVar[str] = "test"
    CONFIG_COMMAND: ClassVar[str] = "config"
    GIT_SETUP_COMMAND: ClassVar[str] = "git-setup"
    GIT_DEBUG_COMMAND: ClassVar[str] = "git-debug"
    GIT_CLEAR_COMMAND: ClassVar[str] = "git-clear"
    GIT_RUN_COMMAND: ClassVar[str] = "git-run"

    # Configuration keys
    CONFIG_KEY_PASSPHRASE: ClassVar[str] = "passphrase"
    CONFIG_KEY_IDENTITY_FILE: ClassVar[str] = "identity_file"
    CONFIG_KEY_EXPIRATION_TIME: ClassVar[str] = "expiration_time"
    CONFIG_KEY_REUSE_AGENT: ClassVar[str] = "reuse_agent"
    CONFIG_KEY_KEYS: ClassVar[str] = "keys"

    # Default key name
    DEFAULT_KEY_NAME: ClassVar[str] = "default"

    # Non-sensitive configuration keys for export
    NON_SENSITIVE_KEYS: ClassVar[List[str]] = [
        "identity_file", "keys", "expiration_time", "reuse_agent"
    ]


class SystemConstants:
    """Constants for system-specific operations."""

    # File extensions
    SSH_PUBLIC_KEY_EXTENSION: ClassVar[str] = ".pub"
    SSH_PRIVATE_KEY_EXTENSION: ClassVar[str] = ""
    JSON_EXTENSION: ClassVar[str] = ".json"

    # System paths
    LINUX_MACHINE_ID_PATH: ClassVar[str] = "/etc/machine-id"
    WINDOWS_MACHINE_GUID_REGISTRY_PATH: ClassVar[str] = r"SOFTWARE\Microsoft\Cryptography"
    WINDOWS_MACHINE_GUID_KEY: ClassVar[str] = "MachineGuid"

    # Platform identifiers
    WINDOWS_PLATFORM: ClassVar[str] = "nt"
    POSIX_PLATFORM: ClassVar[str] = "posix"

    # Default fallback values
    UNKNOWN_HOST: ClassVar[str] = "unknown_host"
    UNKNOWN_MACHINE: ClassVar[str] = "unknown_machine"
    UNKNOWN_USER: ClassVar[str] = "unknown_user"
    UNKNOWN_HOME: ClassVar[str] = "/unknown_home"

    # Environment variable names
    ENV_USER: ClassVar[str] = "USER"
    ENV_USERNAME: ClassVar[str] = "USERNAME"
    ENV_HOME: ClassVar[str] = "HOME"

    # Encoding constants
    DEFAULT_ENCODING: ClassVar[str] = "utf-8"
    FALLBACK_ENCODING: ClassVar[str] = "latin1"
    WINDOWS_ENCODING: ClassVar[str] = "gbk"
    WINDOWS_CODEPAGE: ClassVar[str] = "cp936"

    # Numeric patterns for SSH keys
    SSH_KEY_NUMERIC_PATTERN: ClassVar[str] = "[0-9]*"


class LoggingConstants:
    """Constants for logging configuration."""

    # Log levels
    DEBUG_LEVEL: ClassVar[str] = "DEBUG"
    INFO_LEVEL: ClassVar[str] = "INFO"
    WARNING_LEVEL: ClassVar[str] = "WARNING"
    ERROR_LEVEL: ClassVar[str] = "ERROR"

    # Log format templates
    DEBUG_LOG_FORMAT: ClassVar[str] = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    DEFAULT_LOG_FORMAT: ClassVar[str] = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Log message prefixes
    SUCCESS_PREFIX: ClassVar[str] = "✅"
    ERROR_PREFIX: ClassVar[str] = "❌"
    WARNING_PREFIX: ClassVar[str] = "⚠️"
    INFO_PREFIX: ClassVar[str] = "💡"
    DEBUG_PREFIX: ClassVar[str] = "🔍"
    ROCKET_PREFIX: ClassVar[str] = "🚀"


class AuthStrategyConstants:
    """Constants for authentication strategy operations."""

    # Authentication strategy types
    STRATEGY_SMART: ClassVar[str] = "smart"
    STRATEGY_SSH_FIRST: ClassVar[str] = "ssh_first"
    STRATEGY_CREDENTIALS_FIRST: ClassVar[str] = "credentials_first"
    STRATEGY_SSH_ONLY: ClassVar[str] = "ssh_only"
    STRATEGY_CREDENTIALS_ONLY: ClassVar[str] = "credentials_only"

    # Default strategy
    DEFAULT_STRATEGY: ClassVar[str] = STRATEGY_SMART

    # Environment variables for strategy control
    ENV_FORCE_SSH_AUTH: ClassVar[str] = "FORCE_SSH_AUTH"
    ENV_PREFER_SSH_AUTH: ClassVar[str] = "PREFER_SSH_AUTH"
    ENV_AUTH_STRATEGY: ClassVar[str] = "AUTH_STRATEGY"

    # Authentication method names
    AUTH_METHOD_SSH: ClassVar[str] = "ssh"
    AUTH_METHOD_CREDENTIALS: ClassVar[str] = "credentials"

    # Connection test timeout (seconds)
    CONNECTION_TEST_TIMEOUT: ClassVar[int] = 30

    # Authentication cache duration (seconds)
    AUTH_CACHE_DURATION: ClassVar[int] = 3600


# Export all constants for easy access
__all__ = [
    "AuthStrategyConstants",
    "CLIConstants",
    "GitConstants",
    "LoggingConstants",
    "SSHAgentConstants",
    "SystemConstants",
]
