"""Configuration management for SSH agent."""
# Import built-in modules
from dataclasses import dataclass
from typing import Dict
from typing import Optional


@dataclass
class SSHConfig:
    """SSH configuration class."""
    # Path to identity file
    identity_file: Optional[str] = None
    # Identity file content (for CI environments)
    identity_content: Optional[str] = None
    # Identity file passphrase
    identity_passphrase: Optional[str] = None
    # Additional SSH options
    ssh_options: Dict[str, str] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.ssh_options is None:
            self.ssh_options = {}
