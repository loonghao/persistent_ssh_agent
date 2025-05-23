# CI Environment Integration Example

## Simplified Git Credential Helper Usage

### 1. CI Environment Pre-setup

Pre-configure Git credentials on CI machines:

```bash
# Method 1: Set credentials directly
uvx persistent_ssh_agent git-setup --username myuser --password mytoken

# Method 2: Interactive setup (suitable for local testing)
uvx persistent_ssh_agent git-setup --prompt

# Method 3: Setup via environment variables
export GIT_USERNAME=myuser
export GIT_PASSWORD=mytoken
uvx persistent_ssh_agent git-setup
```

### 2. Usage in Build Scripts

```python
from persistent_ssh_agent import PersistentSSHAgent
import subprocess
import os

def custom_build():
    """Custom build function with Git operations support"""

    # Use context manager to ensure SSH agent is properly configured
    with PersistentSSHAgent() as agent:
        # Setup SSH authentication (if needed)
        if agent.setup_ssh('github.com'):
            print("✅ SSH authentication configured successfully")

        # Execute Git commands - Git credential helper will handle authentication automatically
        git_commands = [
            ["git", "config", "--global", "user.name", "CI Bot"],
            ["git", "config", "--global", "user.email", "ci@example.com"],
            ["git", "submodule", "update", "--init", "--recursive"],
            ["git", "fetch", "--all"],
            ["git", "pull", "origin", "main"]
        ]

        for cmd in git_commands:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"❌ Command failed: {' '.join(cmd)}")
                print(f"Error output: {result.stderr}")
                return False
            else:
                print(f"✅ Command succeeded: {' '.join(cmd)}")

        return True

# Call in build script
if __name__ == "__main__":
    if custom_build():
        print("✅ Build completed")
    else:
        print("❌ Build failed")
        exit(1)
```

### 3. Environment Variable Approach (Recommended for CI)

If you prefer to manage credentials through environment variables:

```python
from persistent_ssh_agent import PersistentSSHAgent
import os

def setup_git_in_ci():
    """Setup Git credentials in CI environment"""

    # Get credentials from environment variables
    username = os.environ.get('GIT_USERNAME')
    password = os.environ.get('GIT_PASSWORD')

    if not username or not password:
        print("❌ GIT_USERNAME or GIT_PASSWORD environment variables not set")
        return False

    # Create SSH agent and setup Git credentials
    agent = PersistentSSHAgent()

    # Setup Git credential helper
    if agent.git.setup_git_credentials(username, password):
        print("✅ Git credentials configured successfully")
        return True
    else:
        print("❌ Failed to configure Git credentials")
        return False

def main():
    """Main function"""
    with PersistentSSHAgent() as agent:
        # Setup Git credentials (if not already configured)
        if not setup_git_in_ci():
            exit(1)

        # Setup SSH authentication
        if agent.setup_ssh('github.com'):
            print("✅ SSH authentication ready")

        # Now you can execute any Git operations
        # Git will automatically use the configured credential helper

if __name__ == "__main__":
    main()
```

### 4. Comparison with Existing CI Workflows

**Previous Complex Workflow:**
```python
# Manual script file creation and configuration required
cmds = [
    ["git", "config", "--global", "credential.helper", "/path/to/credential-helper.sh"],
    ["git", "submodule", "update", "--remote"]
]

for cmd in cmds:
    subprocess.call(cmd, shell=True, cwd=source_path)
```

**Current Simplified Workflow:**
```python
# One-line credential setup
with PersistentSSHAgent() as agent:
    # Git credentials pre-configured via CLI, ready to use
    subprocess.call(["git", "submodule", "update", "--remote"], cwd=source_path)
```

### 5. Advantages Summary

1. **Simplified Setup**: Reduced from multi-step to single command
2. **Environment Isolation**: Credential setup separated from code
3. **Enhanced Security**: No need to hardcode credentials in code
4. **Better Maintainability**: Unified credential management approach
5. **Backward Compatibility**: Does not affect existing SSH key functionality

### 6. Troubleshooting

If you encounter issues, you can check:

```bash
# Check Git credential helper configuration
git config --global --get credential.helper

# Test Git credentials
git ls-remote https://github.com/your-repo/test.git

# Check SSH agent status
uvx persistent_ssh_agent test github.com
```
