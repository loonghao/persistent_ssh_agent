"""SSH configuration file parser."""

# Import built-in modules
import glob
import logging
import os
from pathlib import Path
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


# Type definitions
SSHOptionValue = Union[str, List[str]]

# Set up logger
logger = logging.getLogger(__name__)


class SSHConfigParser:
    """Parser for SSH configuration files."""

    def __init__(self, ssh_dir: Path):
        """Initialize SSH config parser.

        Args:
            ssh_dir: Path to SSH directory
        """
        self.ssh_dir = ssh_dir
        self._config_cache: Dict[str, Dict[str, SSHOptionValue]] = {}

    def parse_ssh_config(self) -> Dict[str, Dict[str, SSHOptionValue]]:
        """Parse SSH config file to get host-specific configurations.

        Returns:
            Dict[str, Dict[str, SSHOptionValue]]: A dictionary containing host-specific SSH configurations.
            The outer dictionary maps host patterns to their configurations,
            while the inner dictionary maps configuration keys to their values.
            Values can be either strings or lists of strings for multi-value options.
        """
        config: Dict[str, Dict[str, SSHOptionValue]] = {}
        current_host: Optional[str] = None
        current_match: Optional[str] = None
        ssh_config_path = self.ssh_dir / "config"

        if not ssh_config_path.exists():
            logger.debug("SSH config file does not exist: %s", ssh_config_path)
            return config

        # Define valid keys and their validation functions
        valid_keys = self._get_valid_keys()

        def is_valid_host_pattern(pattern: str) -> bool:
            """Check if a host pattern is valid."""
            if not pattern:
                return False

            # Special cases
            if pattern == "*":
                return True

            # Split multiple patterns
            patterns = pattern.split()
            for p in patterns:
                # Skip empty patterns
                if not p:
                    continue

                # Allow negation prefix
                if p.startswith("!"):
                    p = p[1:]

                # Skip empty patterns after removing prefix
                if not p:
                    continue

                # Check for control characters
                if any(c in p for c in "\0\n\r\t"):
                    return False

                # Allow IPv6 addresses in square brackets
                if p.startswith("[") and p.endswith("]"):
                    # Basic IPv6 validation
                    p = p[1:-1]
                    if not all(c in "0123456789abcdefABCDEF:" for c in p):
                        return False
                    continue

            return True

        def get_validation_error(key: str, value: str) -> Optional[str]:
            """Get validation error message for a config key-value pair."""
            key = key.lower()
            if key not in valid_keys:
                logger.debug(f"Invalid configuration key: {key}")
                return f"Invalid configuration key: {key}"

            if not valid_keys[key](value):
                logger.debug(f"Invalid value for {key}: {value}")
                return f"Invalid value for {key}: {value}"

            return None

        def process_config_line(line: str) -> None:
            """Process a single line from SSH config file."""
            nonlocal current_host, current_match, config

            # Normalize line endings and remove BOM if present
            line = line.replace("\ufeff", "").strip()
            if not line or line.startswith("#"):
                return

            # Handle Include directives
            if line.lower().startswith("include "):
                self._process_include_directive(line, ssh_config_path, process_config_line)
                return

            # Handle Match blocks
            if line.lower().startswith("match "):
                parts = line.split(None, 2)
                if len(parts) >= 3 and parts[1].lower() == "host":
                    current_match = parts[2]
                    current_host = current_match
                    if current_host not in config:
                        config[current_host] = {}
                return

            # Handle Host blocks
            if line.lower().startswith("host "):
                current_host = line.split(None, 1)[1].strip()
                if is_valid_host_pattern(current_host):
                    if current_host not in config:
                        config[current_host] = {}
                    current_match = None
                else:
                    logger.debug(f"Invalid host pattern in {ssh_config_path}: {current_host}")
                return

            # Parse key-value pairs
            if current_host is not None:
                self._process_config_key_value(line, current_host, config, get_validation_error)

        try:
            with open(ssh_config_path, encoding="utf-8-sig") as f:
                # Reset config for each parse attempt
                config.clear()
                current_host = None
                current_match = None

                # Read the entire file content
                content = f.read()
                lines = content.split("\n")

                # Process each line
                for line in lines:
                    try:
                        process_config_line(line)
                    except Exception as e:
                        logger.debug(f"Error processing line: {line.strip()}, Error: {e}")

        except Exception as e:
            logger.error(f"Failed to parse SSH config: {e}")
            config.clear()

        if not config:
            logger.debug("No valid configuration found in SSH config file")

        return config

    def _get_valid_keys(self) -> Dict[str, Callable[[str], bool]]:
        """Get dictionary of valid SSH configuration keys and their validators."""
        return {
            # Connection settings
            "hostname": lambda _: True,  # Any hostname is valid
            "port": lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            "user": lambda _: True,  # Any username is valid
            "identityfile": lambda _: True,  # Any path is valid
            "identitiesonly": lambda x: x.lower() in ("yes", "no"),
            "batchmode": lambda x: x.lower() in ("yes", "no"),
            "bindaddress": lambda _: True,  # Any address is valid
            "connecttimeout": lambda x: x.isdigit() and int(x) >= 0,
            "connectionattempts": lambda x: x.isdigit() and int(x) >= 1,

            # Security settings
            "stricthostkeychecking": lambda x: x.lower() in ("yes", "no", "accept-new", "off", "ask"),
            "userknownhostsfile": lambda _: True,  # Any path is valid
            "passwordauthentication": lambda x: x.lower() in ("yes", "no"),
            "pubkeyauthentication": lambda x: x.lower() in ("yes", "no"),
            "kbdinteractiveauthentication": lambda x: x.lower() in ("yes", "no"),
            "hostbasedauthentication": lambda x: x.lower() in ("yes", "no"),
            "gssapiauthentication": lambda x: x.lower() in ("yes", "no"),
            "preferredauthentications": lambda x: all(
                auth in ["gssapi-with-mic", "hostbased", "publickey", "keyboard-interactive", "password"]
                for auth in x.split(",")),

            # Connection optimization
            "compression": lambda x: x.lower() in ("yes", "no"),
            "tcpkeepalive": lambda x: x.lower() in ("yes", "no"),
            "serveralivecountmax": lambda x: x.isdigit() and int(x) >= 0,
            "serveraliveinterval": lambda x: x.isdigit() and int(x) >= 0,

            # Proxy and forwarding
            "proxycommand": lambda _: True,  # Any command is valid
            "proxyhost": lambda _: True,  # Any host is valid
            "proxyport": lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            "proxyjump": lambda _: True,  # Any jump specification is valid
            "dynamicforward": lambda x: all(
                p.isdigit() and 1 <= int(p) <= 65535 for p in x.split(":") if p.isdigit()),
            "localforward": lambda _: True,  # Port forwarding specification
            "remoteforward": lambda _: True,  # Port forwarding specification
            "forwardagent": lambda x: x.lower() in ("yes", "no"),

            # Environment
            "sendenv": lambda _: True,  # Any environment variable pattern is valid
            "setenv": lambda _: True,  # Any environment variable setting is valid
            "requesttty": lambda x: x.lower() in ("yes", "no", "force", "auto"),
            "permittylocalcommand": lambda x: x.lower() in ("yes", "no"),
            "typylocalcommand": lambda _: True,  # Any command is valid

            # Multiplexing
            "controlmaster": lambda x: x.lower() in ("yes", "no", "ask", "auto", "autoask"),
            "controlpath": lambda _: True,  # Any path is valid
            "controlpersist": lambda _: True,  # Any time specification is valid

            # Misc
            "addkeystoagent": lambda x: x.lower() in ("yes", "no", "ask", "confirm"),
            "canonicaldomains": lambda _: True,  # Any domain list is valid
            "canonicalizefallbacklocal": lambda x: x.lower() in ("yes", "no"),
            "canonicalizehostname": lambda x: x.lower() in ("yes", "no", "always"),
            "canonicalizemaxdots": lambda x: x.isdigit() and int(x) >= 0,
            "canonicalizepermittedcnames": lambda _: True,  # Any CNAME specification is valid
        }

    def _process_include_directive(self, line: str, ssh_config_path: Path,
                                   process_config_line: Callable[[str], None]) -> None:
        """Process Include directive in SSH config."""
        include_path = line.split(None, 1)[1]
        include_path = os.path.expanduser(include_path)
        include_path = os.path.expandvars(include_path)

        # Support both absolute and relative paths
        if not os.path.isabs(include_path):
            include_path = os.path.join(os.path.dirname(str(ssh_config_path)), include_path)

        # Expand glob patterns
        include_files = glob.glob(include_path)
        for include_file in include_files:
            if os.path.isfile(include_file):
                try:
                    with open(include_file) as inc_f:
                        for inc_line in inc_f:
                            process_config_line(inc_line.strip())
                except Exception as e:
                    logger.debug(f"Failed to read include file {include_file}: {e}")

    def _process_config_key_value(self, line: str, current_host: str,
                                  config: Dict[str, Dict[str, SSHOptionValue]],
                                  get_validation_error: Callable[[str, str], Optional[str]]) -> None:
        """Process a key-value configuration line."""
        try:
            # Split line into key and value, supporting both space and = separators
            if "=" in line:
                key, value = [x.strip() for x in line.split("=", 1)]
            else:
                parts = line.split(None, 1)
                if len(parts) < 2:
                    return
                key, value = parts[0].strip(), parts[1].strip()

            key = key.lower()
            if not value:  # Skip empty values
                return

            # Validate key and value
            error_msg = get_validation_error(key, value)
            if error_msg:
                return

            # Handle array values
            if key in ["identityfile", "localforward", "remoteforward", "dynamicforward", "sendenv", "setenv"]:
                if key not in config[current_host]:
                    config[current_host][key] = [value]
                else:
                    current_value = config[current_host][key]
                    if isinstance(current_value, list):
                        if value not in current_value:  # Avoid duplicates
                            current_value.append(value)
                    else:
                        # Convert single value to list with new value
                        config[current_host][key] = [current_value, value]
            else:
                config[current_host][key] = value

        except Exception as e:
            logger.debug(f"Error processing line: {line.strip()}, Error: {e}")
