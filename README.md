# persistent-ssh-agent

<div align="center">

[![Python Version](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)](https://img.shields.io/pypi/pyversions/persistent_ssh_agent)
[![Nox](https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg)](https://github.com/wntrblm/nox)
[![PyPI Version](https://img.shields.io/pypi/v/persistent_ssh_agent?color=green)](https://pypi.org/project/persistent_ssh_agent/)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/month)](https://pepy.tech/project/persistent_ssh_agent)
[![Downloads](https://static.pepy.tech/badge/persistent_ssh_agent/week)](https://pepy.tech/project/persistent_ssh_agent)
[![License](https://img.shields.io/pypi/l/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![PyPI Format](https://img.shields.io/pypi/format/persistent_ssh_agent)](https://pypi.org/project/persistent_ssh_agent/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/loonghao/persistent_ssh_agent/graphs/commit-activity)
![Codecov](https://img.shields.io/codecov/c/github/loonghao/persistent_ssh_agent)

[English](README.md) | [中文](README_zh.md)

</div>

🔐 A modern Python library for persistent SSH agent management across sessions.

[Key Features](#key-features) •
[Installation](#installation) •
[Documentation](#usage) •
[Examples](#examples) •
[Contributing](#contributing)

## ✨ Key Features

- 🔄 Persistent SSH agent management across sessions
- 🔑 Automatic SSH key loading and caching
- 🪟 Windows-optimized implementation
- 🔗 Seamless Git integration
- 🌐 Cross-platform compatibility (Windows, Linux, macOS)
- 📦 No external dependencies beyond standard SSH tools
- 🔒 Secure key management and session control
- ⚡ Asynchronous operation support
- 🧪 Complete unit test coverage
- 📝 Type hints support

## 🚀 Installation

```bash
pip install persistent-ssh-agent
```

## 📋 Requirements

- Python 3.8+
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
config = SSHConfig()
config.add_host_config('github.com', {
    'IdentityFile': '~/.ssh/github_key',
    'User': 'git',
    'Port': '22'
})

# Initialize with custom config
ssh_agent = PersistentSSHAgent(config=config)

# Set up SSH authentication
if ssh_agent.setup_ssh('github.com'):
    # Get Git SSH command for the host
    ssh_command = ssh_agent.get_git_ssh_command('github.com')
    if ssh_command:
        print("✅ Git SSH command ready!")
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

### CI/CD Pipeline Integration

```python
import os
from persistent_ssh_agent import PersistentSSHAgent

def setup_ci_ssh():
    """Set up SSH for CI environment."""
    ssh_agent = PersistentSSHAgent()

    # Set up SSH key from environment
    key_path = os.environ.get('SSH_PRIVATE_KEY_PATH')
    if not key_path:
        raise ValueError("SSH key path not provided")

    if ssh_agent.start_ssh_agent(key_path):
        print("✅ SSH agent started successfully")
        return True

    raise RuntimeError("Failed to start SSH agent")
```

### Git Integration

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_repo(repo_url: str, local_path: str, branch: str = None) -> Repo:
    """Clone a repository using persistent SSH authentication."""
    ssh_agent = PersistentSSHAgent()

    # Extract hostname from URL and set up SSH
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
        branch=branch,
        env=env
    )

# Usage example
try:
    repo = clone_repo(
        'git@github.com:username/repo.git',
        '/path/to/local/repo',
        branch='main'
    )
    print("✅ Repository cloned successfully")
except Exception as e:
    print(f"❌ Error: {e}")
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

```python
from persistent_ssh_agent import PersistentSSHAgent

agent = PersistentSSHAgent()

# Add a key
agent.add_key('~/.ssh/id_ed25519')

# List loaded keys
keys = agent.list_keys()
for key in keys:
    print(f"Loaded key: {key}")

# Remove a specific key
agent.remove_key('~/.ssh/id_ed25519')

# Clear all keys
agent.clear_keys()
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
