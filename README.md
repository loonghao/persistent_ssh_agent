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
</div>
🔐 A modern Python library for persistent SSH agent management across sessions.

[Key Features](#key-features) •
[Installation](#installation) •
[Documentation](#usage) •
[Examples](#examples) •
[Contributing](#contributing)

</div>

## ✨ Key Features

- 🔄 Persistent SSH agent management across sessions
- 🔑 Automatic SSH key loading and caching
- 🪟 Windows-optimized implementation
- 🔗 Seamless Git integration
- 🌐 Cross-platform compatibility (Windows, Linux, macOS)
- 📦 No external dependencies beyond standard SSH tools

## 🚀 Installation

```bash
pip install persistent-ssh-agent
```

## 📋 Requirements

- Python 3.x
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

### Advanced Usage with Custom Configuration

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create custom SSH configuration
config = SSHConfig()
config.add_host_config('github.com', {
    'IdentityFile': '~/.ssh/github_key',
    'User': 'git'
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

### GitPython Integration

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_repo(repo_url: str, local_path: str, branch: str = None) -> Repo:
    """Clone a repository using GitPython with persistent SSH authentication."""
    ssh_agent = PersistentSSHAgent()

    # Extract hostname from URL and set up SSH
    hostname = ssh_agent._extract_hostname(repo_url)
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

# Example usage
try:
    repo = clone_repo(
        'git@github.com:username/repo.git',
        '/path/to/local/repo',
        branch='main'
    )
    print(f"✅ Repository cloned successfully")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Cross-Platform Support

The library is designed to work seamlessly across Windows, Linux, and macOS:

- Windows: Automatically manages `ssh-agent.exe` lifecycle
- Linux/macOS: Integrates with system SSH agent
- All platforms: Maintains persistent SSH sessions

### Best Practices

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

4. **Security**:
   - Automatic key unloading after expiration
   - Secure temporary file handling
   - Platform-specific security measures

## 🔧 Common Use Cases

### CI/CD Pipelines

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

    if ssh_agent._start_ssh_agent(key_path):
        print("✅ SSH agent started successfully")
        return True

    raise RuntimeError("Failed to start SSH agent")
```

### Multi-Host Management

```python
async def setup_multiple_hosts(hosts: list[str]) -> dict[str, bool]:
    """Set up SSH for multiple hosts concurrently."""
    ssh_agent = PersistentSSHAgent()
    results = {}

    for host in hosts:
        results[host] = ssh_agent.setup_ssh(host)

    return results

# Usage
hosts = ['github.com', 'gitlab.com', 'bitbucket.org']
status = await setup_multiple_hosts(hosts)
```

## 🔗 Using Password Authentication

### Using Password Authentication

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create configuration with passphrase
config = SSHConfig(
    identity_file='~/.ssh/id_rsa',  # Path to your private key
    identity_passphrase='your-key-passphrase',  # Your key's passphrase
    ssh_options={
        'PreferredAuthentications': 'publickey,password',
        'PasswordAuthentication': 'yes'
    }
)

# Initialize SSH agent with config
ssh_agent = PersistentSSHAgent(config=config)

# Set up SSH for a host
if ssh_agent.setup_ssh('github.com'):
    print("✅ SSH authentication with passphrase ready!")
```

### Using Key Content Directly (CI/CD Environment)

```python
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig

# Create configuration with key content
config = SSHConfig(
    identity_content="""-----BEGIN OPENSSH PRIVATE KEY-----
your_private_key_content_here
-----END OPENSSH PRIVATE KEY-----""",
    identity_passphrase='your-key-passphrase',  # Optional if key is encrypted
    ssh_options={
        'BatchMode': 'yes',  # Prevents interactive prompts
        'StrictHostKeyChecking': 'no'  # For CI environments
    }
)

# Initialize SSH agent with config
ssh_agent = PersistentSSHAgent(config=config)

# Set up SSH for CI operations
if ssh_agent.setup_ssh('github.com'):
    print("✅ CI/CD SSH authentication ready!")
```

### Security Best Practices for Password Authentication

1. **Key Storage**:
   - Store private keys in secure locations
   - Use environment variables for passphrases in production
   - Regularly rotate SSH keys and passphrases

2. **Environment Variables**:
   ```python
   import os

   config = SSHConfig(
       identity_file='~/.ssh/id_rsa',
       identity_passphrase=os.environ.get('SSH_KEY_PASS'),
       ssh_options={'PasswordAuthentication': 'yes'}
   )
   ```

3. **Temporary Keys**:
   ```python
   # For ephemeral environments
   config = SSHConfig(
       identity_content=os.environ.get('SSH_PRIVATE_KEY'),
       identity_passphrase=os.environ.get('SSH_KEY_PASS')
   )
   ```

## 💡 Best Practices

### Key Management

- 🔑 Store SSH keys in standard locations (`~/.ssh/`)
- 🔒 Use Ed25519 keys for better security
- 📝 Maintain organized SSH config files

### Error Handling

```python
from typing import Optional
from pathlib import Path

def safe_git_operation(repo_url: str, local_path: Path) -> Optional[Repo]:
    """Safely perform Git operations with proper error handling."""
    ssh_agent = PersistentSSHAgent()
    try:
        hostname = ssh_agent._extract_hostname(repo_url)
        if not hostname:
            raise ValueError("Invalid repository URL")

        if not ssh_agent.setup_ssh(hostname):
            raise RuntimeError("SSH setup failed")

        return Repo.clone_from(repo_url, local_path)
    except Exception as e:
        logger.error(f"Git operation failed: {e}")
        return None
```

## 🔍 Troubleshooting

### Common Issues

1. **SSH Agent Issues**
   ```bash
   # Check SSH agent status
   ssh-add -l

   # Start SSH agent manually
   eval $(ssh-agent -s)
   ```

2. **Key Problems**
   ```bash
   # Fix key permissions
   chmod 600 ~/.ssh/id_ed25519

   # Test SSH connection
   ssh -T git@github.com
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
