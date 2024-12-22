# persistent-ssh-agent

<div align="center">

[![PyPI version](https://badge.fury.io/py/persistent-ssh-agent.svg)](https://badge.fury.io/py/persistent-ssh-agent)
[![Python Support](https://img.shields.io/pypi/pyversions/persistent-ssh-agent.svg)](https://pypi.org/project/persistent-ssh-agent/)
[![License](https://img.shields.io/github/license/codeium/persistent-ssh-agent.svg)](https://github.com/codeium/persistent-ssh-agent/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

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

# Create an instance
ssh_agent = PersistentSSHAgent()

# Set up SSH for a specific host
if ssh_agent.setup_ssh('github.com'):
    print("✅ SSH authentication ready!")
```

### GitPython Integration

```python
from git import Repo
from persistent_ssh_agent import PersistentSSHAgent
import os

def clone_with_gitpython(repo_url: str, local_path: str, branch: str = None) -> Repo:
    """Clone a repository using GitPython with persistent SSH authentication."""
    ssh_agent = PersistentSSHAgent()

    # Extract hostname and set up SSH
    hostname = ssh_agent._extract_hostname(repo_url)
    if not hostname or not ssh_agent.setup_ssh(hostname):
        raise RuntimeError("Failed to set up SSH authentication")

    # Get SSH command and configure environment
    ssh_command = ssh_agent.get_git_ssh_command(hostname)
    if not ssh_command:
        raise RuntimeError("Failed to get SSH command")

    # Set up Git environment
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = ssh_command

    # Clone with GitPython
    return Repo.clone_from(
        repo_url,
        local_path,
        branch=branch,
        env=env
    )

# Example usage
try:
    repo = clone_with_gitpython(
        'git@github.com:username/repo.git',
        '/path/to/local/repo',
        branch='main'
    )
    print(f"✅ Repository cloned: {repo.working_dir}")

    # Perform Git operations
    repo.remotes.origin.pull()
    repo.remotes.origin.push()
except Exception as e:
    print(f"❌ Error: {e}")
```

### Advanced GitPython Operations

```python
def setup_git_operations():
    """Set up environment for Git operations."""
    ssh_agent = PersistentSSHAgent()
    hostname = "github.com"

    if not ssh_agent.setup_ssh(hostname):
        raise RuntimeError("SSH setup failed")

    ssh_command = ssh_agent.get_git_ssh_command(hostname)
    if not ssh_command:
        raise RuntimeError("Failed to get SSH command")

    os.environ['GIT_SSH_COMMAND'] = ssh_command
    return True

# Example: Complex Git operations
def manage_git_workflow(repo_path: str):
    if not setup_git_operations():
        return False

    repo = Repo(repo_path)

    # Create and checkout new branch
    new_branch = repo.create_head('feature/new-feature')
    new_branch.checkout()

    # Make changes
    with open(os.path.join(repo_path, 'new_file.txt'), 'w') as f:
        f.write('New content')

    # Stage and commit
    repo.index.add(['new_file.txt'])
    repo.index.commit('Add new file')

    # Push to remote
    repo.remotes.origin.push(new_branch)
```

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
