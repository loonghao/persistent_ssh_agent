"""Command-line interface for persistent-ssh-agent."""

# Import built-in modules
import argparse
import base64
import ctypes
import getpass
import hashlib
import json
import os
import platform
import secrets
import socket
import sys
import uuid
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

# Import third-party modules
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig


# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Constants for encryption
SALT_SIZE = 16
IV_SIZE = 16
KEY_SIZE = 32  # 256 bits
ITERATIONS = 100000


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
            with open(self.config_file, "r", encoding="utf-8") as f:
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
            with open(self.config_file, "w", encoding="utf-8") as f:
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
        encrypted_data = config.get("passphrase")
        if not encrypted_data:
            return None
        return encrypted_data

    def set_passphrase(self, passphrase: str) -> bool:
        """Set and store passphrase.

        Args:
            passphrase: SSH key passphrase

        Returns:
            bool: True if successful
        """
        config = self.load_config()
        # Use AES-256 encryption
        config["passphrase"] = self._encrypt_passphrase(passphrase)
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

    def get_expiration_time(self) -> Optional[int]:
        """Get stored expiration time.

        Returns:
            Optional[int]: Expiration time in seconds or None
        """
        config = self.load_config()
        return config.get("expiration_time")

    def set_expiration_time(self, hours: int) -> bool:
        """Set and store expiration time.

        Args:
            hours: Expiration time in hours

        Returns:
            bool: True if successful
        """
        config = self.load_config()
        config["expiration_time"] = hours * 3600  # Convert to seconds
        return self.save_config(config)

    def get_reuse_agent(self) -> Optional[bool]:
        """Get stored reuse agent setting.

        Returns:
            Optional[bool]: Reuse agent setting or None
        """
        config = self.load_config()
        return config.get("reuse_agent")

    def set_reuse_agent(self, reuse: bool) -> bool:
        """Set and store reuse agent setting.

        Args:
            reuse: Whether to reuse existing SSH agent

        Returns:
            bool: True if successful
        """
        config = self.load_config()
        config["reuse_agent"] = reuse
        return self.save_config(config)

    def list_keys(self) -> Dict:
        """List all configured SSH keys.

        Returns:
            Dict: Dictionary of configured keys
        """
        config = self.load_config()
        result = {}

        if "identity_file" in config:
            result["default"] = config["identity_file"]

        if "keys" in config and isinstance(config["keys"], dict):
            result.update(config["keys"])

        return result

    def add_key(self, name: str, identity_file: str) -> bool:
        """Add a named SSH key.

        Args:
            name: Name of the key
            identity_file: Path to SSH identity file

        Returns:
            bool: True if successful
        """
        config = self.load_config()

        if "keys" not in config:
            config["keys"] = {}

        config["keys"][name] = os.path.expanduser(identity_file)
        return self.save_config(config)

    def remove_key(self, name: str) -> bool:
        """Remove a named SSH key.

        Args:
            name: Name of the key

        Returns:
            bool: True if successful
        """
        config = self.load_config()

        if name == "default" and "identity_file" in config:
            config.pop("identity_file")
            return self.save_config(config)

        if "keys" in config and name in config["keys"]:
            config["keys"].pop(name)
            return self.save_config(config)

        return False

    def clear_config(self) -> bool:
        """Clear all configuration.

        Returns:
            bool: True if successful
        """
        return self.save_config({})

    def export_config(self, include_sensitive: bool = False) -> Dict:
        """Export configuration.

        Args:
            include_sensitive: Whether to include sensitive information

        Returns:
            Dict: Exported configuration
        """
        config = self.load_config()
        export = {}

        # Always include non-sensitive information
        if "identity_file" in config:
            export["identity_file"] = config["identity_file"]

        if "keys" in config:
            export["keys"] = config["keys"]

        if "expiration_time" in config:
            export["expiration_time"] = config["expiration_time"]

        if "reuse_agent" in config:
            export["reuse_agent"] = config["reuse_agent"]

        # Include sensitive information if requested
        if include_sensitive and "passphrase" in config:
            export["passphrase"] = config["passphrase"]

        return export

    def import_config(self, config_data: Dict) -> bool:
        """Import configuration.

        Args:
            config_data: Configuration data to import

        Returns:
            bool: True if successful
        """
        current_config = self.load_config()

        # Update current configuration with imported data
        for key, value in config_data.items():
            current_config[key] = value

        return self.save_config(current_config)

    def _derive_key_from_system(self) -> Tuple[bytes, bytes]:
        """Derive encryption key from system-specific information.

        Returns:
            Tuple[bytes, bytes]: (key, salt)
        """
        # Get system-specific information
        system_info = {
            "hostname": socket.gethostname(),
            "machine_id": self._get_machine_id(),
            "username": os.getlogin() if hasattr(os, "getlogin") else getpass.getuser(),
            "home": str(Path.home())
        }

        # Create a deterministic salt from system info
        salt_base = f"{system_info['hostname']}:{system_info['machine_id']}:{system_info['username']}"
        salt = hashlib.sha256(salt_base.encode()).digest()[:SALT_SIZE]

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=ITERATIONS,
            backend=default_backend()
        )

        # Use a combination of system info as the password
        password = f"{system_info['hostname']}:{system_info['machine_id']}:{system_info['home']}"
        key = kdf.derive(password.encode())

        return key, salt

    def _get_machine_id(self) -> str:
        """Get a unique machine identifier.

        Returns:
            str: Machine ID
        """
        # Try to get machine ID from common locations
        machine_id = ""

        # Linux
        if os.path.exists("/etc/machine-id"):
            try:
                with open("/etc/machine-id", "r", encoding="utf-8") as f:
                    machine_id = f.read().strip()
            except (IOError, OSError):
                pass

        # Windows
        elif os.name == "nt":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"SOFTWARE\Microsoft\Cryptography") as key:
                    machine_id = winreg.QueryValueEx(key, "MachineGuid")[0]
            except (ImportError, OSError):
                pass

        # macOS
        elif os.path.exists("/Library/Preferences/SystemConfiguration/com.apple.computer.plist"):
            try:
                import plistlib
                with open("/Library/Preferences/SystemConfiguration/com.apple.computer.plist", "rb") as f:
                    plist = plistlib.load(f)
                    machine_id = plist.get("LocalHostName", "")
            except (ImportError, OSError):
                pass

        # Fallback to a hash of the hostname if we couldn't get a machine ID
        if not machine_id:
            machine_id = hashlib.sha256(socket.gethostname().encode()).hexdigest()

        return machine_id

    def _encrypt_passphrase(self, passphrase: str) -> str:
        """Encrypt passphrase using AES-256.

        Args:
            passphrase: Plain text passphrase

        Returns:
            str: Encrypted passphrase
        """
        try:
            # Get key and salt
            key, salt = self._derive_key_from_system()

            # Generate a random IV
            iv = os.urandom(IV_SIZE)

            # Create an encryptor
            cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()

            # Pad the plaintext to a multiple of 16 bytes (AES block size)
            plaintext = passphrase.encode()
            padding_length = 16 - (len(plaintext) % 16)
            plaintext += bytes([padding_length]) * padding_length

            # Encrypt the padded plaintext
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()

            # Combine salt, IV, and ciphertext
            encrypted_data = salt + iv + ciphertext

            # Encode as base64 for storage
            return base64.b64encode(encrypted_data).decode()

        except Exception as e:
            logger.error(f"Failed to encrypt passphrase: {e}")
            # Fall back to simple obfuscation if encryption fails
            return self._legacy_obfuscate_passphrase(passphrase)

    def _deobfuscate_passphrase(self, encrypted_data: str) -> str:
        """Decrypt or deobfuscate passphrase.

        Args:
            encrypted_data: Encrypted or obfuscated passphrase

        Returns:
            str: Plain text passphrase
        """
        # Try to decrypt using AES-256
        try:
            # Check if this is a base64-encoded string (AES encryption)
            data = base64.b64decode(encrypted_data)

            # Extract salt, IV, and ciphertext
            salt = data[:SALT_SIZE]
            iv = data[SALT_SIZE:SALT_SIZE+IV_SIZE]
            ciphertext = data[SALT_SIZE+IV_SIZE:]

            # Derive key using the extracted salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=KEY_SIZE,
                salt=salt,
                iterations=ITERATIONS,
                backend=default_backend()
            )

            # Use system info as the password
            system_info = {
                "hostname": socket.gethostname(),
                "machine_id": self._get_machine_id(),
                "username": os.getlogin() if hasattr(os, "getlogin") else getpass.getuser(),
                "home": str(Path.home())
            }
            password = f"{system_info['hostname']}:{system_info['machine_id']}:{system_info['home']}"
            key = kdf.derive(password.encode())

            # Create a decryptor
            cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            # Decrypt the ciphertext
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove padding
            padding_length = padded_plaintext[-1]
            plaintext = padded_plaintext[:-padding_length]

            return plaintext.decode()

        except Exception as e:
            # If AES decryption fails, try legacy XOR deobfuscation
            logger.debug(f"AES decryption failed, trying legacy deobfuscation: {e}")
            return self._legacy_deobfuscate_passphrase(encrypted_data)

    @staticmethod
    def _legacy_obfuscate_passphrase(passphrase: str) -> str:
        """Legacy obfuscation for passphrase (not secure encryption).

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
    def _legacy_deobfuscate_passphrase(obfuscated: str) -> str:
        """Legacy deobfuscation for passphrase.

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

    @staticmethod
    def secure_delete_from_memory(data: Union[str, bytes, bytearray]) -> None:
        """Securely delete sensitive data from memory.

        Args:
            data: Data to delete
        """
        if isinstance(data, str):
            # For strings, we can't modify the bytes directly
            # This is a best-effort approach
            data = "0" * len(data)
            return

        if isinstance(data, bytearray):
            # For bytearrays, we can modify in place
            for i in range(len(data)):
                data[i] = 0
            return

        # For bytes, we can't modify (immutable), but we can try to
        # encourage garbage collection by removing references
        if isinstance(data, bytes):
            del data


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
            # Securely delete passphrase from memory
            config_manager.secure_delete_from_memory(passphrase)
        else:
            logger.error("Failed to set passphrase")
            # Securely delete passphrase from memory
            config_manager.secure_delete_from_memory(passphrase)
            sys.exit(1)

    # Handle expiration time
    if hasattr(args, "expiration") and args.expiration is not None:
        if args.expiration < 0:
            logger.error("Expiration time must be a positive number")
            sys.exit(1)

        if config_manager.set_expiration_time(args.expiration):
            logger.info(f"Expiration time set to: {args.expiration} hours")
        else:
            logger.error("Failed to set expiration time")
            sys.exit(1)

    # Handle reuse agent
    if hasattr(args, "reuse_agent") and args.reuse_agent is not None:
        if config_manager.set_reuse_agent(args.reuse_agent):
            logger.info(f"Reuse agent set to: {args.reuse_agent}")
        else:
            logger.error("Failed to set reuse agent")
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

    # Get expiration time and add to SSH config if available
    if hasattr(args, "expiration") and args.expiration is not None:
        # Use command line argument
        logger.debug(f"Using expiration time from command line: {args.expiration} hours")
        # We don't need to set it in ssh_config as it's not used there
    else:
        # Check stored configuration
        stored_expiration = config_manager.get_expiration_time()
        if stored_expiration:
            logger.debug(f"Using expiration time from config: {stored_expiration/3600} hours")
            # We don't need to set it in ssh_config as it's not used there

    # Get reuse agent setting and add to SSH config if available
    if hasattr(args, "reuse_agent") and args.reuse_agent is not None:
        # Use command line argument
        logger.debug(f"Using reuse agent setting from command line: {args.reuse_agent}")
        # We don't need to set it in ssh_config as it's not used there
    else:
        # Check stored configuration
        stored_reuse = config_manager.get_reuse_agent()
        if stored_reuse is not None:
            logger.debug(f"Using reuse agent setting from config: {stored_reuse}")
            # We don't need to set it in ssh_config as it's not used there

    # Create SSH configuration
    ssh_config = SSHConfig(
        identity_file=identity_file,
        identity_passphrase=passphrase
    )

    # Initialize SSH agent
    ssh_agent = PersistentSSHAgent(config=ssh_config)

    # Set verbosity level
    if hasattr(args, "verbose") and args.verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )

    # Test connection
    hostname = args.hostname
    if ssh_agent.setup_ssh(hostname):
        logger.info(f"✅ SSH connection to {hostname} successful")

        # Clean up sensitive data
        if passphrase:
            config_manager.secure_delete_from_memory(passphrase)
    else:
        logger.error(f"❌ SSH connection to {hostname} failed")

        # Clean up sensitive data
        if passphrase:
            config_manager.secure_delete_from_memory(passphrase)

        sys.exit(1)


def list_keys(_):
    """List all configured SSH keys.

    Args:
        _: Command line arguments (unused)
    """
    config_manager = ConfigManager()
    keys = config_manager.list_keys()

    if not keys:
        logger.info("No SSH keys configured")
        return

    logger.info("Configured SSH keys:")
    for name, path in keys.items():
        logger.info(f"  {name}: {path}")


def remove_key(args):
    """Remove a configured SSH key.

    Args:
        args: Command line arguments
    """
    config_manager = ConfigManager()

    if args.all:
        # Remove all keys
        if config_manager.clear_config():
            logger.info("All SSH keys removed")
        else:
            logger.error("Failed to remove SSH keys")
            sys.exit(1)
    elif args.name:
        # Remove specific key
        if config_manager.remove_key(args.name):
            logger.info(f"SSH key '{args.name}' removed")
        else:
            logger.error(f"Failed to remove SSH key '{args.name}' (not found)")
            sys.exit(1)
    else:
        logger.error("No key specified to remove")
        sys.exit(1)


def export_config(args):
    """Export configuration.

    Args:
        args: Command line arguments
    """
    config_manager = ConfigManager()

    # Export configuration
    config = config_manager.export_config(include_sensitive=args.include_sensitive)

    # Print configuration
    if args.output:
        # Write to file
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration exported to {args.output}")
        except IOError as e:
            logger.error(f"Failed to export configuration: {e}")
            sys.exit(1)
    else:
        # Print to console
        print(json.dumps(config, indent=2))


def import_config(args):
    """Import configuration.

    Args:
        args: Command line arguments
    """
    config_manager = ConfigManager()

    # Read configuration
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to import configuration: {e}")
        sys.exit(1)

    # Import configuration
    if config_manager.import_config(config):
        logger.info("Configuration imported successfully")
    else:
        logger.error("Failed to import configuration")
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
    passphrase_group.add_argument(
        "--passphrase",
        help="SSH key passphrase (not recommended, use --prompt instead)"
    )
    passphrase_group.add_argument(
        "--prompt-passphrase",
        action="store_true",
        help="Prompt for SSH key passphrase"
    )
    config_parser.add_argument(
        "--expiration",
        type=int,
        help="Expiration time in hours"
    )
    config_parser.add_argument(
        "--reuse-agent",
        type=bool,
        help="Whether to reuse existing SSH agent"
    )

    # Test command
    test_parser = subparsers.add_parser("test", help="Test SSH connection")
    test_parser.add_argument("hostname", help="Hostname to test connection with")
    test_parser.add_argument("--identity-file", help="Path to SSH identity file (overrides config)")
    test_parser.add_argument(
        "--expiration",
        type=int,
        help="Expiration time in hours (overrides config)"
    )
    test_parser.add_argument(
        "--reuse-agent",
        type=bool,
        help="Whether to reuse existing SSH agent (overrides config)"
    )
    test_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    # List command
    subparsers.add_parser("list", help="List configured SSH keys")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove configured SSH keys")
    remove_group = remove_parser.add_mutually_exclusive_group(required=True)
    remove_group.add_argument("--name", help="Name of the key to remove")
    remove_group.add_argument("--all", action="store_true", help="Remove all keys")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export configuration")
    export_parser.add_argument("--output", help="Output file path")
    export_parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Include sensitive information in export"
    )

    # Import command
    import_parser = subparsers.add_parser("import", help="Import configuration")
    import_parser.add_argument("input", help="Input file path")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "config":
        setup_config(args)
    elif args.command == "test":
        run_ssh_connection_test(args)
    elif args.command == "list":
        list_keys(args)
    elif args.command == "remove":
        remove_key(args)
    elif args.command == "export":
        export_config(args)
    elif args.command == "import":
        import_config(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
