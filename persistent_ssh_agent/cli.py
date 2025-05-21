"""Command-line interface for persistent-ssh-agent."""

# Import built-in modules
import argparse
import getpass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict
from typing import Optional

# Import third-party modules
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages persistent configuration for SSH agent."""

    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".persistent_ssh_agent"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set proper permissions for config directory
        if os.name != "nt":  # Skip on Windows
            os.chmod(self.config_dir, 0o700)

    def load_config(self) -> Dict:
        """Load configuration from file.

        Returns:
            Dict: Configuration dictionary
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}

    def save_config(self, config: Dict) -> bool:
        """Save configuration to file.

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if successful
        """
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)

            # Set proper permissions for config file
            if os.name != "nt":  # Skip on Windows
                os.chmod(self.config_file, 0o600)

            return True
        except IOError as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def get_passphrase(self) -> Optional[str]:
        """Get stored passphrase.

        Returns:
            Optional[str]: Stored passphrase or None
        """
        config = self.load_config()
        return config.get("passphrase")

    def set_passphrase(self, passphrase: str) -> bool:
        """Set and store passphrase.

        Args:
            passphrase: SSH key passphrase

        Returns:
            bool: True if successful
        """
        config = self.load_config()
        # Simple obfuscation (not secure encryption)
        config["passphrase"] = self._obfuscate_passphrase(passphrase)
        return self.save_config(config)

    def get_identity_file(self) -> Optional[str]:
        """Get stored identity file path.

        Returns:
            Optional[str]: Stored identity file path or None
        """
        config = self.load_config()
        return config.get("identity_file")

    def set_identity_file(self, identity_file: str) -> bool:
        """Set and store identity file path.

        Args:
            identity_file: Path to SSH identity file

        Returns:
            bool: True if successful
        """
        config = self.load_config()
        config["identity_file"] = os.path.expanduser(identity_file)
        return self.save_config(config)

    @staticmethod
    def _obfuscate_passphrase(passphrase: str) -> str:
        """Simple obfuscation for passphrase (not secure encryption).

        Args:
            passphrase: Plain text passphrase

        Returns:
            str: Obfuscated passphrase
        """
        # Simple XOR with a fixed key (not secure, just obfuscation)
        key = b"persistent_ssh_agent_key"
        result = bytearray()

        for i, char in enumerate(passphrase.encode()):
            result.append(char ^ key[i % len(key)])

        return result.hex()

    @staticmethod
    def _deobfuscate_passphrase(obfuscated: str) -> str:
        """Simple deobfuscation for passphrase.

        Args:
            obfuscated: Obfuscated passphrase

        Returns:
            str: Plain text passphrase
        """
        # Reverse the XOR operation
        key = b"persistent_ssh_agent_key"
        result = bytearray()

        try:
            data = bytes.fromhex(obfuscated)
            for i, char in enumerate(data):
                result.append(char ^ key[i % len(key)])

            return result.decode()
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"Failed to deobfuscate passphrase: {e}")
            return ""


def setup_config(args):
    """Set up configuration.

    Args:
        args: Command line arguments
    """
    config_manager = ConfigManager()

    # Handle identity file
    if args.identity_file:
        identity_file = os.path.expanduser(args.identity_file)
        if not os.path.exists(identity_file):
            logger.error(f"Identity file not found: {identity_file}")
            sys.exit(1)

        if config_manager.set_identity_file(identity_file):
            logger.info(f"Identity file set to: {identity_file}")
        else:
            logger.error("Failed to set identity file")
            sys.exit(1)

    # Handle passphrase
    if args.passphrase:
        passphrase = args.passphrase
    elif args.prompt_passphrase:
        passphrase = getpass.getpass("Enter SSH key passphrase: ")
    else:
        passphrase = None

    if passphrase:
        if config_manager.set_passphrase(passphrase):
            logger.info("Passphrase set successfully")
        else:
            logger.error("Failed to set passphrase")
            sys.exit(1)


def run_ssh_connection_test(args):
    """Test SSH connection.

    Args:
        args: Command line arguments
    """
    config_manager = ConfigManager()

    # Get stored configuration
    identity_file = args.identity_file or config_manager.get_identity_file()
    if not identity_file:
        logger.error("No identity file specified or found in configuration")
        sys.exit(1)

    # Expand user directory in path
    identity_file = os.path.expanduser(identity_file)

    # Check if identity file exists
    if not os.path.exists(identity_file):
        logger.error(f"Identity file not found: {identity_file}")
        sys.exit(1)

    # Get passphrase
    stored_passphrase = config_manager.get_passphrase()
    if stored_passphrase:
        passphrase = config_manager._deobfuscate_passphrase(stored_passphrase)
    else:
        passphrase = None

    # Create SSH configuration
    ssh_config = SSHConfig(
        identity_file=identity_file,
        identity_passphrase=passphrase
    )

    # Initialize SSH agent
    ssh_agent = PersistentSSHAgent(config=ssh_config)

    # Test connection
    hostname = args.hostname
    if ssh_agent.setup_ssh(hostname):
        logger.info(f"✅ SSH connection to {hostname} successful")
    else:
        logger.error(f"❌ SSH connection to {hostname} failed")
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Persistent SSH Agent CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configure SSH agent")
    config_parser.add_argument("--identity-file", help="Path to SSH identity file")
    passphrase_group = config_parser.add_mutually_exclusive_group()
    passphrase_group.add_argument("--passphrase", help="SSH key passphrase (not recommended, use --prompt instead)")
    passphrase_group.add_argument("--prompt-passphrase", action="store_true", help="Prompt for SSH key passphrase")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test SSH connection")
    test_parser.add_argument("hostname", help="Hostname to test connection with")
    test_parser.add_argument("--identity-file", help="Path to SSH identity file (overrides config)")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "config":
        setup_config(args)
    elif args.command == "test":
        run_ssh_connection_test(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
