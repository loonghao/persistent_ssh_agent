"""Constants for SSH agent operations."""

# Import built-in modules
from typing import ClassVar
from typing import List


class SSHAgentConstants:
    """Constants for SSH agent operations."""

    # SSH key types in order of preference (most secure first)
    SSH_KEY_TYPES: ClassVar[List[str]] = [
        "id_ed25519",     # Ed25519 (recommended, most secure)
        "id_ecdsa",       # ECDSA
        "id_ecdsa_sk",    # ECDSA with security key
        "id_ed25519_sk",  # Ed25519 with security key
        "id_rsa",         # RSA
        "id_dsa"          # DSA (legacy, not recommended)
    ]

    # Default SSH key type for fallback
    SSH_DEFAULT_KEY: ClassVar[str] = "id_rsa"  # Fallback default key

    # SSH command constants
    SSH_DEFAULT_OPTIONS: ClassVar[List[str]] = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR"
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
    COMMON_GIT_HOSTS: ClassVar[List[str]] = [
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "git.sr.ht",
        "codeberg.org"
    ]


class CLIConstants:
    """Constants for CLI operations."""

    # Configuration file names
    CONFIG_FILE_NAME: ClassVar[str] = "persistent_ssh_agent_config.json"

    # Encryption constants
    ENCRYPTION_ALGORITHM: ClassVar[str] = "AES-256-GCM"
    KEY_DERIVATION_ITERATIONS: ClassVar[int] = 100000

    # CLI command names
    SETUP_COMMAND: ClassVar[str] = "setup"
    LIST_COMMAND: ClassVar[str] = "list"
    REMOVE_COMMAND: ClassVar[str] = "remove"
    EXPORT_COMMAND: ClassVar[str] = "export"
    IMPORT_COMMAND: ClassVar[str] = "import"
    TEST_COMMAND: ClassVar[str] = "test"


# Export all constants for easy access
__all__ = [
    "CLIConstants",
    "GitConstants",
    "SSHAgentConstants"
]
