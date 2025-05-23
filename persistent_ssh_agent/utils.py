"""Utility functions for SSH agent management."""

# Import built-in modules
from contextlib import suppress
import logging
import os
import re
import socket
import subprocess
from subprocess import CompletedProcess
import tempfile
from typing import Dict
from typing import List
from typing import Optional
from typing import TypeVar
from typing import Union


# Type definitions
T = TypeVar("T")
SSHOptionValue = Union[str, List[str]]

# Set up logger
logger = logging.getLogger(__name__)


def run_command(command: List[str], shell: bool = False,
                check_output: bool = True, timeout: Optional[int] = None,
                env: Optional[Dict[str, str]] = None) -> Optional[CompletedProcess]:
    """Run a command and return its output.

    Args:
        command: Command and arguments to run
        shell: Whether to run command through shell
        check_output: Whether to capture command output
        timeout: Command timeout in seconds
        env: Environment variables for command

    Returns:
        CompletedProcess: CompletedProcess object if successful, None on error
    """
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=check_output,
            text=True,
            timeout=timeout,
            env=env,
            check=False
        )
        return result
    except subprocess.TimeoutExpired:
        logger.error("Command timed out: %s", command)
        return None
    except Exception as e:
        logger.error("Command failed: %s - %s", command, e)
        return None


def is_valid_hostname(hostname: str) -> bool:
    """Check if a hostname is valid according to RFC 1123 and supports IPv6.

    Args:
        hostname: The hostname to validate

    Returns:
        bool: True if the hostname is valid, False otherwise

    Notes:
        - Maximum length of 255 characters
        - Can contain letters (a-z), numbers (0-9), dots (.) and hyphens (-)
        - Cannot start or end with a dot or hyphen
        - Labels (parts between dots) cannot start or end with a hyphen
        - Labels cannot be longer than 63 characters
        - IPv6 addresses are supported (with or without brackets)
    """
    if not hostname:
        return False

    # Handle IPv6 addresses
    if ":" in hostname:
        # Remove brackets if present
        if hostname.startswith("[") and hostname.endswith("]"):
            hostname = hostname[1:-1]
        try:
            # Try to parse as IPv6 address
            socket.inet_pton(socket.AF_INET6, hostname)
            return True
        except (socket.error, ValueError):
            return False

    # Check length
    if len(hostname) > 255:
        return False

    # Check for valid characters and label lengths
    labels = hostname.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        if not all(c.isalnum() or c == "-" for c in label):
            return False

    return True


def extract_hostname(url: str) -> Optional[str]:
    """Extract hostname from SSH URL.

    This method extracts the hostname from an SSH URL using a regular expression.
    It validates both the URL format and the extracted hostname. The method
    supports standard SSH URL formats used by Git and other services.

    Args:
        url: SSH URL to extract hostname from (e.g., git@github.com:user/repo.git)

    Returns:
        str: Hostname if valid URL, None otherwise

    Note:
        Valid formats:
        - git@github.com:user/repo.git
        - git@host.example.com:user/repo.git
    """
    if not url or not isinstance(url, str):
        return None

    # Use regex to extract hostname from SSH URL
    # Pattern matches: username@hostname:path
    match = re.match(r"^([^@]+)@([a-zA-Z0-9][-a-zA-Z0-9._]*[a-zA-Z0-9]):(.+)$", url)
    if not match:
        return None

    # Extract hostname from match
    hostname = match.group(2)
    path = match.group(3)

    # Validate path and hostname
    if not path or not path.strip("/"):
        return None

    # Validate hostname
    if not is_valid_hostname(hostname):
        return None

    return hostname


def create_temp_key_file(key_content: str) -> Optional[str]:
    """Create a temporary file with SSH key content.

    Args:
        key_content: SSH key content

    Returns:
        str: Path to temporary key file if successful, None otherwise
    """
    if not key_content:
        return None

    # Convert line endings to LF
    key_content = key_content.replace("\r\n", "\n")
    temp_key = None

    try:
        # Create temp file with proper permissions
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_key = temp_file.name
            temp_file.write(key_content)
        # Set proper permissions for SSH key
        if os.name != "nt":  # Skip on Windows
            os.chmod(temp_key, 0o600)
        # Convert Windows path to Unix-style for consistency
        return temp_key.replace("\\", "/")

    except (PermissionError, OSError) as e:
        if temp_key and os.path.exists(temp_key):
            with suppress(OSError):
                os.unlink(temp_key)
        logger.error(f"Failed to write temporary key file: {e}")
        return None


def resolve_path(path: str) -> Optional[str]:
    """Resolve a path to an absolute path.

    Args:
        path: Path to resolve

    Returns:
        str: Absolute path if successful, None otherwise
    """
    try:
        # Expand user directory (e.g., ~/)
        expanded_path = os.path.expanduser(path)

        # Convert to absolute path
        abs_path = os.path.abspath(expanded_path)

        # Convert Windows path to Unix-style for consistency
        return abs_path.replace("\\", "/")

    except (TypeError, ValueError):
        return None


def ensure_home_env() -> None:
    """Ensure HOME environment variable is set correctly.

    This method ensures the HOME environment variable is set to the user's
    home directory, which is required for SSH operations.
    """
    if "HOME" not in os.environ:
        os.environ["HOME"] = os.path.expanduser("~")

    logger.debug("Set HOME environment variable: %s", os.environ.get("HOME"))
