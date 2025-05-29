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
- 🧠 Smart authentication strategies with automatic fallback mechanisms
- 🔍 Comprehensive health check and diagnostic capabilities
- 🧹 Automatic cleanup of invalid credential configurations

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

# Set up Git credentials
uvx persistent_ssh_agent git-setup --username your-username --prompt

# Test Git credentials validity
uvx persistent_ssh_agent test-credentials github.com

# Perform comprehensive health check
uvx persistent_ssh_agent health-check

# Smart authentication setup with automatic fallback
uvx persistent_ssh_agent smart-setup github.com --strategy auto

# Run Git commands with automatic passwordless authentication
uvx persistent_ssh_agent git-run clone git@github.com:user/repo.git
uvx persistent_ssh_agent git-run --prefer-credentials push origin main
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

- `test-credentials`: Test Git credentials validity
  - `hostname`: Git host to test (optional, tests all common hosts if not specified)
  - `--username`: Git username for testing
  - `--password`: Git password for testing
  - `--timeout`: Timeout in seconds for each test

- `health-check`: Perform comprehensive authentication health check
  - `--format`: Output format (text or json)
  - `--verbose`: Show detailed diagnostic information

- `smart-setup`: Intelligent authentication setup with automatic fallback
  - `hostname`: Target Git host
  - `--strategy`: Authentication strategy (auto, ssh_first, credentials_first, ssh_only)
  - `--username`: Git username (for credential-based authentication)
  - `--password`: Git password (for credential-based authentication)

- `git-run`: Run Git commands with automatic passwordless authentication
  - `git_args`: Git command arguments (e.g., clone, pull, push, etc.)
  - `--username`: Git username (overrides GIT_USERNAME env var)
  - `--password`: Git password/token (overrides GIT_PASSWORD env var)
  - `--prefer-credentials`: Prefer credential helper over SSH authentication
  - `--prompt`: Prompt for credentials if not provided



### CI/CD Pipeline Integration

The library provides specialized support for CI/CD environments with automatic credential setup and submodule management.

#### Python API for CI

```python
from persistent_ssh_agent import PersistentSSHAgent
import os

# Set up credentials from environment variables
os.environ['GIT_USERNAME'] = 'your-username'
os.environ['GIT_PASSWORD'] = 'your-token'

agent = PersistentSSHAgent()

# Set up Git credentials (automatically uses forced credential helper)
agent.git.setup_git_credentials()

# Run Git commands with automatic passwordless authentication
# This will use forced credential helper that clears existing helpers
result = agent.run_git_command_passwordless([
    'git', 'submodule', 'update', '--init', '--recursive'
], prefer_ssh=False)  # Prefer credentials in CI

# Or use git-run CLI command
# uvx persistent_ssh_agent git-run submodule update --init --recursive
```

#### CLI for CI Environments

```bash
# Set up credentials using environment variables
export GIT_USERNAME=your-username
export GIT_PASSWORD=your-token

# Set up Git credentials (uses forced credential helper)
uvx persistent_ssh_agent git-setup

# Run Git commands with automatic passwordless authentication
uvx persistent_ssh_agent git-run submodule update --init --recursive
uvx persistent_ssh_agent git-run --prefer-credentials pull origin main
uvx persistent_ssh_agent git-run clone https://github.com/user/repo.git

# All git-run commands automatically use forced credential helper:
# git -c "credential.helper=" -c "credential.helper=script" -c "credential.useHttpPath=true" ...
```

#### GitHub Actions Integration

```yaml
name: Update Submodules
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC

jobs:
  update-submodules:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          submodules: false

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install persistent-ssh-agent
        run: pip install persistent-ssh-agent

      - name: Configure Git
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Set up Git credentials and update submodules
        env:
          GIT_USERNAME: ${{ github.actor }}
          GIT_PASSWORD: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Set up Git credentials
          uvx persistent_ssh_agent git-setup

          # Update submodules using forced credential helper
          uvx persistent_ssh_agent git-run submodule update --init --recursive --prefer-credentials

      - name: Create PR if changes
        # Add your PR creation logic here
```

#### Features for CI/CD

- **Environment Variable Support**: Automatic detection of `GIT_USERNAME` and `GIT_PASSWORD`
- **Credential Verification**: Optional verification of credentials before operations
- **Submodule Management**: Multiple strategies for updating submodules
- **Quiet Mode**: Reduced output for cleaner CI logs
- **Status Reporting**: Comprehensive environment status and recommendations
- **Error Handling**: Proper exit codes and error messages for CI systems
- **Forced Credential Helper**: Automatically clears existing credential helpers and uses our own
- **Path-Specific Credentials**: Enables `credential.useHttpPath=true` for better credential isolation

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

### Passwordless Git Operations

The library provides intelligent passwordless Git command execution that automatically chooses between SSH and credential helper authentication:

```python
from persistent_ssh_agent import PersistentSSHAgent

# Create agent instance
agent = PersistentSSHAgent()

# Run any Git command with automatic authentication
# Prefers SSH if available, falls back to credentials
result = agent.run_git_command_passwordless(['git', 'clone', 'git@github.com:user/repo.git'])

# Force credential helper authentication
result = agent.run_git_command_passwordless(
    ['git', 'pull', 'origin', 'main'],
    username='your-username',
    password='your-token',
    prefer_ssh=False
)

# Run with environment variables
import os
os.environ['GIT_USERNAME'] = 'your-username'
os.environ['GIT_PASSWORD'] = 'your-token'
result = agent.run_git_command_passwordless(['git', 'push', 'origin', 'main'])
```

**CLI Usage:**

```bash
# Run Git commands with automatic authentication
uvx persistent_ssh_agent git-run clone git@github.com:user/repo.git
uvx persistent_ssh_agent git-run pull origin main
uvx persistent_ssh_agent git-run push origin main

# Force credential helper over SSH
uvx persistent_ssh_agent git-run --prefer-credentials push origin main

# Interactive credential input
uvx persistent_ssh_agent git-run --prompt submodule update --init --recursive

# With explicit credentials
uvx persistent_ssh_agent git-run --username user --password token clone https://github.com/user/repo.git
```

**Authentication Strategy:**

1. **SSH Preferred (default)**: Try SSH first, fall back to credentials if SSH fails
2. **Credentials Preferred**: Try credentials first, fall back to SSH if credentials fail
3. **Automatic Detection**: Intelligently detect available authentication methods
4. **Fallback Support**: Seamless fallback between authentication methods

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

### Smart Authentication Strategies

The library now includes intelligent authentication strategies that automatically select the best authentication method:

```python
from persistent_ssh_agent import PersistentSSHAgent

# Create agent instance
agent = PersistentSSHAgent()

# Smart authentication with automatic fallback
# Tries Git credentials first, falls back to SSH if needed
success = agent.git.setup_smart_credentials('github.com', strategy='auto')

# Force SSH-only authentication
success = agent.git.setup_smart_credentials('github.com', strategy='ssh_only')

# Prefer SSH, fallback to credentials
success = agent.git.setup_smart_credentials('github.com', strategy='ssh_first')
```

**Available Authentication Strategies:**

- `auto` (default): Intelligent selection based on environment and cached preferences
- `ssh_first`: Try SSH authentication first, fallback to credentials
- `credentials_first`: Try Git credentials first, fallback to SSH
- `ssh_only`: Use only SSH key authentication
- `credentials_only`: Use only Git credential authentication

**Environment Variable Control:**

```bash
# Force SSH authentication for all operations
export FORCE_SSH_AUTH=true

# Prefer SSH authentication (with fallback)
export PREFER_SSH_AUTH=true

# Set specific authentication strategy
export AUTH_STRATEGY=ssh_first
```

### Health Check and Diagnostics

Comprehensive health checking capabilities for authentication systems:

```python
from persistent_ssh_agent import PersistentSSHAgent

agent = PersistentSSHAgent()

# Perform comprehensive health check
health_status = agent.git.health_check()

print(f"Overall status: {health_status['overall']}")  # healthy, warning, or error
print(f"Git credentials: {health_status['git_credentials']['status']}")
print(f"SSH keys: {health_status['ssh_keys']['status']}")
print(f"Network connectivity: {health_status['network']['status']}")

# Get recommendations for improvement
for recommendation in health_status['recommendations']:
    print(f"💡 {recommendation}")
```

**Health Check Features:**

- Git credential validation and testing
- SSH key availability and functionality testing
- Network connectivity verification to Git hosts
- Automatic recommendation generation
- Detailed diagnostic information

### Credential Management

Advanced credential management with automatic cleanup:

```python
from persistent_ssh_agent import PersistentSSHAgent

agent = PersistentSSHAgent()

# Test credential validity for specific hosts
results = agent.git.test_credentials('github.com', username='user', password='token')
print(f"GitHub credentials valid: {results['github.com']}")

# Test all common Git hosts
all_results = agent.git.test_credentials()
for host, valid in all_results.items():
    print(f"{host}: {'✅' if valid else '❌'}")

# Clean up invalid credential helpers
cleanup_success = agent.git.clear_invalid_credentials()
if cleanup_success:
    print("✅ Invalid credentials cleaned up successfully")
```

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
