# persistent-ssh-agent

[![Python Version](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)
[![Nox](https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg)](https://github.com/wntrblm/nox)
[![PyPI Version](https://img.shields.io/pypi/v/persistent_ssh_agent?color=green)](https://pypi.org/project/persistent_ssh_agent/)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/month)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/week)](https://pepy.tech/project/persistent_ssh_agent)
[![License](https://img.shields.io/pypi/l/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![PyPI Format](https://img.shields.io/pypi/format/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/loonghao/persistent_ssh_agent/graphs/commit-activity)
[![Codecov](https://img.shields.io/codecov/c/github/loonghao/persistent_ssh_agent)](https://codecov.io/gh/loonghao/persistent_ssh_agent)

[English](./README.md) | [中文](./README_zh.md)

🔐 A modern Python library for persistent SSH agent management across sessions.

## 📚 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Security Features](#security-features)
- [Contributing](#contributing)

## ✨ Features

- 🔄 Persistent SSH agent management across sessions
- 🔑 Automatic SSH key loading and caching
- 🪟 Windows-optimized implementation
- 🔗 Seamless Git integration
- 🌐 Cross-platform compatibility (Windows, Linux, macOS)
- 📦 No external dependencies beyond standard SSH tools
- 🔒 Secure key management and session control with AES-256 encryption
- ⚡ Asynchronous operation support
- 🧪 Complete unit test coverage with performance benchmarks
- 📝 Comprehensive type hints support
- 🔐 Support for multiple SSH key types (Ed25519, ECDSA, RSA)
- 🌍 IPv6 support
- 📚 Multi-language documentation support
- 🔍 Enhanced SSH configuration validation
- 🛠️ Modern development toolchain (Poetry, Commitizen, Black)
- 🔑 Git credential helper integration for seamless Git operations
- 💻 Command-line interface with comprehensive configuration options

## 🚀 Installation

```bash
pip install persistent-ssh-agent
```

## 📋 Requirements

- Python 3.8-3.13
- OpenSSH (ssh-agent, ssh-add) installed and available in PATH
- Git (optional, for Git operations)

## 📖 Usage

### Basic Usage

```python
from persistent_ssh_agent import PersistentSSHAgent

# Create an instance with custom expiration time (default is 24 hours)
ssh_agent = PersistentSSHAgent(expiration_time=86400)

# Set up SSH for a specific host
if ssh_agent.setup_ssh('github.com'):
    print("✅ SSH authentication ready!")
```

### Advanced Configuration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create custom SSH configuration
config = SSHConfig(
    identity_file='~/.ssh/github_key',  # Optional specific identity file
    identity_passphrase='your-passphrase',  # Optional passphrase
    ssh_options={  # Optional SSH options
        'StrictHostKeyChecking': 'yes',
        'PasswordAuthentication': 'no',
        'PubkeyAuthentication': 'yes'
    }
)

# Initialize with custom config and agent reuse settings
ssh_agent = PersistentSSHAgent(
    config=config,
    expiration_time=86400,  # Optional: Set agent expiration time (default 24 hours)
    reuse_agent=True  # Optional: Control agent reuse behavior (default True)
)

# Set up SSH authentication
if ssh_agent.setup_ssh('github.com'):
    # Get Git SSH command for the host
    ssh_command = ssh_agent.get_git_ssh_command('github.com')
    if ssh_command:
        print("✅ Git SSH command ready!")
```

### Agent Reuse Behavior

The `reuse_agent` parameter controls how the SSH agent handles existing sessions:

- When `reuse_agent=True` (default):
  - Attempts to reuse an existing SSH agent if available
  - Reduces the number of agent startups and key additions
  - Improves performance by avoiding unnecessary agent operations

- When `reuse_agent=False`:
  - Always starts a new SSH agent session
  - Useful when you need a fresh agent state
  - May be preferred in certain security-sensitive environments

Example with agent reuse disabled:

```python
# Always start a new agent session
ssh_agent = PersistentSSHAgent(reuse_agent=False)
```

### Multiple Host Configuration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create configuration with common options
config = SSHConfig(
    ssh_options={
        'BatchMode': 'yes',
        'StrictHostKeyChecking': 'yes',
        'ServerAliveInterval': '60'
    }
)

# Initialize agent
agent = PersistentSSHAgent(config=config)

# Set up SSH for multiple hosts
hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
for host in hosts:
    if agent.setup_ssh(host):
        print(f"✅ SSH configured for {host}")
    else:
        print(f"❌ Failed to configure SSH for {host}")
```

### Global SSH Configuration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create configuration with global options
config = SSHConfig(
    # Set identity file (optional)
    identity_file='~/.ssh/id_ed25519',

    # Set global SSH options
    ssh_options={
        'StrictHostKeyChecking': 'yes',
        'PasswordAuthentication': 'no',
        'PubkeyAuthentication': 'yes',
        'BatchMode': 'yes',
        'ConnectTimeout': '30'
    }
)

# Initialize agent with global configuration
agent = PersistentSSHAgent(config=config)
```

### Asynchronous Support

```python
import asyncio
from persistent_ssh_agent import PersistentSSHAgent

async def setup_multiple_hosts(hosts: list[str]) -> dict[str, bool]:
    """Set up SSH for multiple hosts concurrently."""
    ssh_agent = PersistentSSHAgent()
    results = {}

    async def setup_host(host: str):
        results[host] = await ssh_agent.async_setup_ssh(host)

    await asyncio.gather(*[setup_host(host) for host in hosts])
    return results

# Usage example
async def main():
    hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
    results = await setup_multiple_hosts(hosts)
    for host, success in results.items():
        print(f"{host}: {'✅' if success else '❌'}")

asyncio.run(main())
```

### Security Best Practices

1. **Key Management**:
   - Store SSH keys in standard locations (`~/.ssh/`)
   - Use Ed25519 keys for better security
   - Keep private keys protected (600 permissions)

2. **Error Handling**:

   ```python
   try:
       ssh_agent = PersistentSSHAgent()
       success = ssh_agent.setup_ssh('github.com')
       if not success:
           print("⚠️ SSH setup failed")
   except Exception as e:
       print(f"❌ Error: {e}")
   ```

3. **Session Management**:
   - Agent information persists across sessions
   - Automatic cleanup of expired sessions
   - Configurable expiration time
   - Multi-session concurrent management

4. **Security Features**:
   - Automatic key unloading after expiration
   - Secure temporary file handling
   - Platform-specific security measures
   - Key usage tracking

## 🔧 Common Use Cases

### Command Line Interface (CLI)

The library provides a command-line interface for easy configuration and testing:

```bash
# Configure SSH agent with a specific identity file
uvx persistent_ssh_agent config --identity-file ~/.ssh/id_ed25519 --prompt-passphrase

# Test SSH connection to a host
uvx persistent_ssh_agent test github.com

# List configured SSH keys
uvx persistent_ssh_agent list

# Remove a specific SSH key
uvx persistent_ssh_agent remove --name github

# Export configuration to a file
uvx persistent_ssh_agent export --output ~/.ssh/config.json

# Import configuration from a file
uvx persistent_ssh_agent import config.json

# Set up Git credentials (new feature)
uvx persistent_ssh_agent git-setup --username your-username --prompt
```

Available commands:

- `config`: Configure SSH agent settings
  - `--identity-file`: Path to SSH identity file
  - `--passphrase`: SSH key passphrase (not recommended, use --prompt-passphrase instead)
  - `--prompt-passphrase`: Prompt for SSH key passphrase
  - `--expiration`: Expiration time in hours
  - `--reuse-agent`: Whether to reuse existing SSH agent

- `test`: Test SSH connection to a host
  - `hostname`: Hostname to test connection with
  - `--identity-file`: Path to SSH identity file (overrides config)
  - `--expiration`: Expiration time in hours (overrides config)
  - `--reuse-agent`: Whether to reuse existing SSH agent (overrides config)
  - `--verbose`: Enable verbose output

- `list`: List configured SSH keys

- `remove`: Remove configured SSH keys
  - `--name`: Name of the key to remove
  - `--all`: Remove all keys

- `export`: Export configuration
  - `--output`: Output file path
  - `--include-sensitive`: Include sensitive information in export

- `import`: Import configuration
  - `input_file`: Input file path

- `git-setup`: Configure Git credentials
  - `--username`: Git username
  - `--password`: Git password (not recommended, use --prompt instead)
  - `--prompt`: Prompt for Git credentials interactively

### CI/CD Pipeline Integration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

def setup_ci_ssh():
    """Set up SSH for CI environment."""
    # Create configuration with key content
    config = SSHConfig(
        identity_content=os.environ.get('SSH_PRIVATE_KEY'),
        ssh_options={'BatchMode': 'yes'}
    )

    ssh_agent = PersistentSSHAgent(config=config)

    if ssh_agent.setup_ssh('github.com'):
        print("✅ SSH agent started successfully")
        return True

    raise RuntimeError("Failed to start SSH agent")
```

### Git Integration

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_repo(repo_url: str, local_path: str) -> Repo:
    """Clone a repository using persistent SSH authentication."""
    ssh_agent = PersistentSSHAgent()

    # Extract hostname and set up SSH
    hostname = ssh_agent.extract_hostname(repo_url)
    if not hostname or not ssh_agent.setup_ssh(hostname):
        raise RuntimeError("Failed to set up SSH authentication")

    # Get SSH command and configure environment
    ssh_command = ssh_agent.get_git_ssh_command(hostname)
    if not ssh_command:
        raise RuntimeError("Failed to get SSH command")

    # Clone with GitPython
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = ssh_command

    return Repo.clone_from(
        repo_url,
        local_path,
        env=env
    )
```

### Git Credential Helper Support (Simplified)

You can now set up Git credentials in a simplified way without manual script creation:

```python
from persistent_ssh_agent import PersistentSSHAgent

# Method 1: Set credentials directly
ssh_agent = PersistentSSHAgent()
ssh_agent.git.setup_git_credentials('your-username', 'your-password')

# Method 2: Use environment variables
import os
os.environ['GIT_USERNAME'] = 'your-username'
os.environ['GIT_PASSWORD'] = 'your-password'
ssh_agent.git.setup_git_credentials()  # Automatically reads from env vars

# Now Git commands will use these credentials
```

**CLI Setup:**

```bash
# Set credentials directly
uvx persistent_ssh_agent git-setup --username your-username --password your-password

# Interactive setup
uvx persistent_ssh_agent git-setup --prompt

# Using environment variables
export GIT_USERNAME=your-username
export GIT_PASSWORD=your-password
uvx persistent_ssh_agent git-setup
```

**CI Environment Usage:**

```python
# In build scripts
from persistent_ssh_agent import PersistentSSHAgent

# Use context manager
with PersistentSSHAgent() as agent:
    # SSH and Git credentials are configured, ready for Git operations
    agent.setup_ssh('github.com')
    # Execute any Git commands...
```

## 🌟 Advanced Features

### Custom Configuration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create config instance
config = SSHConfig()

# Add global configuration
config.add_global_config({
    'AddKeysToAgent': 'yes',
    'UseKeychain': 'yes'
})

# Add host-specific configuration
config.add_host_config('*.github.com', {
    'User': 'git',
    'IdentityFile': '~/.ssh/github_ed25519',
    'PreferredAuthentications': 'publickey'
})

# Initialize agent with config
agent = PersistentSSHAgent(config=config)
```

### Key Management

The library automatically manages SSH keys based on your SSH configuration:

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Use specific key
config = SSHConfig(identity_file='~/.ssh/id_ed25519')
agent = PersistentSSHAgent(config=config)

# Or let the library automatically detect and use available keys
agent = PersistentSSHAgent()
if agent.setup_ssh('github.com'):
    print("✅ SSH key loaded and ready!")
```

The library supports the following key types in order of preference:

- Ed25519 (recommended, most secure)
- ECDSA
- ECDSA with security key
- Ed25519 with security key
- RSA
- DSA (legacy, not recommended)

### SSH Configuration Validation

The library provides comprehensive SSH configuration validation with support for:

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create custom SSH configuration with validation
config = SSHConfig()

# Add host configuration with various options
config.add_host_config('github.com', {
    # Connection Settings
    'IdentityFile': '~/.ssh/github_key',
    'User': 'git',
    'Port': '22',

    # Security Settings
    'StrictHostKeyChecking': 'yes',
    'PasswordAuthentication': 'no',
    'PubkeyAuthentication': 'yes',

    # Connection Optimization
    'Compression': 'yes',
    'ConnectTimeout': '60',
    'ServerAliveInterval': '60',
    'ServerAliveCountMax': '3',

    # Proxy and Forwarding
    'ProxyCommand': 'ssh -W %h:%p bastion',
    'ForwardAgent': 'yes'
})

# Initialize with validated config
ssh_agent = PersistentSSHAgent(config=config)
```

Supported configuration categories:

- **Connection Settings**: Port, Hostname, User, IdentityFile
- **Security Settings**: StrictHostKeyChecking, BatchMode, PasswordAuthentication
- **Connection Optimization**: Compression, ConnectTimeout, ServerAliveInterval
- **Proxy and Forwarding**: ProxyCommand, ForwardAgent, ForwardX11
- **Environment Settings**: RequestTTY, SendEnv
- **Multiplexing Options**: ControlMaster, ControlPath, ControlPersist

For detailed validation rules and supported options, see [SSH Configuration Validation](#ssh-configuration-validation)

### SSH Key Types Support

The library supports multiple SSH key types:

- Ed25519 (recommended, most secure)
- ECDSA
- ECDSA with security key
- Ed25519 with security key
- RSA
- DSA (legacy, not recommended)

### Security Features

1. **SSH Key Management**:

   - Automatic detection and loading of SSH keys (Ed25519, ECDSA, RSA)
   - Support for key content injection (useful in CI/CD)
   - Secure key file permissions handling
   - Optional passphrase support

2. **Configuration Security**:

   - Strict hostname validation
   - Secure default settings
   - Support for security-focused SSH options

3. **Session Management**:

   - Secure storage of agent information
   - Platform-specific security measures
   - Automatic cleanup of expired sessions
   - Cross-platform compatibility

### Type Hints Support

The library provides comprehensive type hints for all public interfaces:

```python
from typing import Optional
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

def setup_ssh(hostname: str, key_file: Optional[str] = None) -> bool:
    config = SSHConfig(identity_file=key_file)
    agent = PersistentSSHAgent(config=config)
    return agent.setup_ssh(hostname)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](#license) file for details.
