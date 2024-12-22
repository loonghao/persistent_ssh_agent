## v0.3.0 (2024-12-22)

### Feat

- **persistent_ssh_agent**: Add expiration time for SSH agent info and improve error handling
- **persistent_ssh_agent**: Add expiration time for SSH agent info and improve error handling

## v0.2.1 (2024-12-22)

### Refactor

- **workflows**: Update Python publishing workflow configuration

## v0.2.0 (2024-12-22)

### Feat

- **persistent_ssh_agent**: Improve SSH config parsing and add tests for invalid syntax

### Refactor

- Update tests and core module to use pathlib for path handling - Replace os.path with pathlib for better readability and cross-platform compatibility - Add new SSHError exception class for SSH-related errors - Update _run_command method to handle command output and exceptions more gracefully

## v0.1.0 (2024-12-22)

### Feat

- **persistent_ssh_agent**: Add persistent SSH agent management library
- Add persistent SSH agent management library
- Add persistent SSH agent management library

### Refactor

- **tests**: Enhance SSH setup and agent startup tests
