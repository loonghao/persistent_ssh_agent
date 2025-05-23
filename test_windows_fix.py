#!/usr/bin/env python3
"""Test script to verify Windows Git credential helper fix."""

import os
import sys
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from persistent_ssh_agent.git import GitIntegration


def test_windows_credential_helper():
    """Test Windows-specific credential helper generation."""
    # Mock SSH agent
    mock_ssh_agent = MagicMock()
    git_integration = GitIntegration(mock_ssh_agent)
    
    # Test Windows credential helper
    with patch('os.name', 'nt'):
        helper = git_integration._create_platform_credential_helper('testuser', 'testpass')
        print(f"Windows credential helper: {helper}")
        assert '&&' in helper  # Windows uses && to chain commands
        assert 'echo username=testuser' in helper
        assert 'echo password=testpass' in helper
    
    # Test Unix credential helper
    with patch('os.name', 'posix'):
        helper = git_integration._create_platform_credential_helper('testuser', 'testpass')
        print(f"Unix credential helper: {helper}")
        assert '{ echo username=testuser; echo password=testpass; }' in helper
    
    print("✅ All tests passed!")


def test_credential_escaping():
    """Test credential value escaping."""
    mock_ssh_agent = MagicMock()
    git_integration = GitIntegration(mock_ssh_agent)
    
    # Test Windows escaping
    with patch('os.name', 'nt'):
        escaped = git_integration._escape_credential_value('test"value%')
        print(f"Windows escaped: {escaped}")
        assert '""' in escaped  # Double quotes should be escaped
        assert '%%' in escaped  # Percent signs should be escaped
    
    # Test Unix escaping
    with patch('os.name', 'posix'):
        escaped = git_integration._escape_credential_value('test"value\'')
        print(f"Unix escaped: {escaped}")
        assert '\\"' in escaped  # Double quotes should be escaped
    
    print("✅ Escaping tests passed!")


if __name__ == "__main__":
    print("Testing Windows Git credential helper fix...")
    test_windows_credential_helper()
    test_credential_escaping()
    print("All tests completed successfully!")
