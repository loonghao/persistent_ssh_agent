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


def _decode_subprocess_output(data: bytes, encoding_hint: Optional[str] = None) -> str:
    """Decode subprocess output with intelligent encoding detection.

    Args:
        data: Raw bytes from subprocess
        encoding_hint: Optional encoding hint to try first

    Returns:
        str: Decoded string
    """
    if not data:
        return ""

    # List of encodings to try in order
    encodings_to_try = []

    # Add encoding hint if provided
    if encoding_hint:
        encodings_to_try.append(encoding_hint)

    # Add common encodings based on platform
    if os.name == "nt":
        # Windows: try UTF-8 first, then system default (usually GBK for Chinese), then fallbacks
        encodings_to_try.extend(["utf-8", "gbk", "cp936", "latin1"])
    else:
        # Unix/Linux: try UTF-8 first, then fallbacks
        encodings_to_try.extend(["utf-8", "latin1"])

    # Try each encoding
    for encoding in encodings_to_try:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # If all encodings fail, use UTF-8 with error replacement
    try:
        result = data.decode("utf-8", errors="replace")
        logger.warning(
            "Failed to decode subprocess output with standard encodings, "
            "using UTF-8 with replacement characters"
        )
        return result
    except Exception as e:
        logger.error("Critical encoding error: %s", e)
        # Last resort: return a safe representation
        return repr(data)[2:-1]  # Remove b' and ' from repr


def run_command(
    command: List[str],
    shell: bool = False,
    check_output: bool = True,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    encoding: Optional[str] = None,
    input_data: Optional[str] = None,
) -> Optional[CompletedProcess]:
    """Run a command and return its output with robust encoding handling.

    Args:
        command: Command and arguments to run
        shell: Whether to run command through shell
        check_output: Whether to capture command output
        timeout: Command timeout in seconds (default: 30 seconds for Git commands)
        env: Environment variables for command
        encoding: Optional encoding hint for output decoding
        input_data: Optional input data to send to the process

    Returns:
        CompletedProcess: CompletedProcess object if successful, None on error

    Note:
        This function handles encoding issues by:
        1. Capturing raw bytes output
        2. Intelligently detecting and converting encoding
        3. Providing fallback mechanisms for encoding errors
        4. Automatic timeout for Git commands to prevent hanging
    """
    try:
        # Set default timeout for Git commands to prevent hanging
        if timeout is None and command and command[0] == "git":
            timeout = 30  # 30 seconds default for Git commands

        # Prepare input data if provided
        input_bytes = None
        if input_data:
            input_bytes = input_data.encode("utf-8")

        # Add non-interactive flags for Git commands to prevent hanging
        enhanced_command = command.copy()
        if command and command[0] == "git":
            # Add batch mode and non-interactive flags
            git_flags = []


            # Insert flags after 'git' but before subcommand
            if git_flags:
                enhanced_command = [command[0]] + git_flags + command[1:]

        logger.debug("Running command with timeout %s: %s", timeout, enhanced_command)

        # Capture raw bytes to handle encoding ourselves
        result = subprocess.run(
            enhanced_command,
            shell=shell,
            capture_output=check_output,
            text=False,  # Get raw bytes
            timeout=timeout,
            env=env,
            check=False,
            input=input_bytes
        )

        # If we captured output, decode it properly
        if check_output and result.stdout is not None and isinstance(result.stdout, bytes):
            result.stdout = _decode_subprocess_output(result.stdout, encoding)  # type: ignore
        if check_output and result.stderr is not None and isinstance(result.stderr, bytes):
            result.stderr = _decode_subprocess_output(result.stderr, encoding)  # type: ignore

        return result

    except subprocess.TimeoutExpired as e:
        logger.error("Command timed out after %s seconds: %s", timeout, command)
        # Try to kill the process if it's still running
        try:
            if hasattr(e, "process") and e.process:
                e.process.kill()
                e.process.wait(timeout=5)
        except Exception:
            pass  # Best effort cleanup
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
