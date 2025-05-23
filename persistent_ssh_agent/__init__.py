"""Persistent SSH Agent for managing SSH keys and connections."""

# Import version
# Import third-party modules
from persistent_ssh_agent.__version__ import __version__

# Import core components
from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.constants import SSHAgentConstants
from persistent_ssh_agent.core import PersistentSSHAgent


# Import CLI components
# Avoid circular imports by importing ConfigManager only when needed
__all__ = ["PersistentSSHAgent", "SSHAgentConstants", "SSHConfig", "__version__"]
