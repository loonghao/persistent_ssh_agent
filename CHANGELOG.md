## v0.8.2 (2025-05-26)

### Fix

- handle both string and bytes stderr in Git credential setup

## v0.8.1 (2025-05-23)

### Fix

- correct Unix credential escaping order to prevent double escaping
- Windows compatibility for Git credential helper and add CLI debug support

## v0.8.0 (2025-05-23)

### Feat

- add comprehensive SSH configuration and Git credential helper support

## v0.7.7 (2025-05-21)

### Fix

- use client_payload.version as tag in release workflow

## v0.7.6 (2025-05-21)

### Fix

- Update PyPI publishing config

## v0.7.5 (2025-05-21)

### Fix

- update commitizen workflow configuration to fix tag format issue
- update release workflow with proper permissions and configuration

## v0.7.4 (2025-05-21)

### Fix

- improve tag detection in release workflow using olegtarasov/get-tag output

### Refactor

- clean up debug steps in release workflow

## v0.7.3 (2025-05-21)

### Fix

- resolve CLI executable name and release action tag issues

## v0.7.2 (2025-05-21)

### Fix

- ensure release-action has valid tag input

## v0.7.1 (2025-05-21)

### Fix

- ensure tag push triggers python-publish workflow
- ensure tag push triggers python-publish workflow

## v0.7.0 (2025-05-21)

### Feat

- add CLI command for adding SSH keys

### Fix

- update tests to use deobfuscate_passphrase instead of _deobfuscate_passphrase

## v0.6.0 (2025-05-21)

### Feat

- enhance CLI with security and additional commands
- add CLI interface for persistent_ssh_agent

### Fix

- update all GitHub Actions workflows to use github.token instead of PERSONAL_ACCESS_TOKEN
- update GitHub Actions workflow to use github.token with proper permissions
- improve test coverage to 79%
- fix lint issues in test files
- make tests compatible with non-Windows platforms
- improve test coverage and fix docs lint issues
- resolve CI test failures and improve test coverage
- improve CI compatibility for encryption tests

### Refactor

- migrate CLI from argparse to Click

## v0.5.1 (2024-12-28)

### Refactor

- **persistent_ssh_agent/core.py**: Refactor and clean up PersistentSSHAgent class

## v0.5.0 (2024-12-28)

### Feat

- **persistent_ssh_agent/core.py**: Add reuse_agent parameter to PersistentSSHAgent constructor
- **README.md**: Document reuse_agent parameter and behavior

## v0.4.0 (2024-12-28)

### Feat

- **README.md**: Enhance documentation with multiple host configuration and global SSH options
- **tests/test_core_coverage.py**: Enhance SSH agent tests with various scenarios Add tests for missing fields, expired timestamp, invalid JSON, non-running agent, and advanced SSH config parsing scenarios. Also, update tests for invalid file content and file read errors.
- **README.md**: Add Chinese translation and update installation requirements
- **persistent_ssh_agent**: Enhance SSH agent functionality with improved key handling and configuration options
- **persistent_ssh_agent**: Enhance SSH agent functionality and add tests - Added pytest-timeout to test requirements - Improved SSH config parsing and added tests for invalid syntax - Refactored _run_command method for better readability and error handling - Added new SSHError exception class for SSH-related errors - Updated tests and core module to use pathlib for path handling
- Add support for SSH key passphrase

### Fix

- Fix SSH key passphrase handling and path issues

### Refactor

- **persistent_ssh_agent/core.py**: Improve SSH config parsing and error handling Remove unused `config_file` parameter from `process_config_line` function. Normalize line endings and handle BOM if present. Update tests for array values in configuration.
- **persistent_ssh_agent/core.py**: Improve SSH config parsing and error handling Add debug logs for missing SSH config file and invalid configuration keys/values. Normalize line endings and handle BOM if present. Update tests for array values in configuration.
- **persistent_ssh_agent/core.py**: Improve SSH config parsing and add type definitions
- **core.py**: Improve SSH config parsing and error handling
- **persistent_ssh_agent/core.py**: Improve SSH config parsing and error handling
- **persistent_ssh_agent/core.py**: Improve SSH config parsing and handling of include files and match blocks

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
