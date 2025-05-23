#!/usr/bin/env python3
"""Test script to verify the core Windows Git credential helper fix."""

import os
import sys
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the dependencies
sys.modules['persistent_ssh_agent.constants'] = MagicMock()
sys.modules['persistent_ssh_agent.utils'] = MagicMock()

# Create mock functions
def mock_extract_hostname(url):
    return "github.com"

def mock_is_valid_hostname(hostname):
    return True

def mock_run_command(cmd):
    result = MagicMock()
    result.returncode = 0
    result.stderr = b""
    return result

# Apply mocks
sys.modules['persistent_ssh_agent.utils'].extract_hostname = mock_extract_hostname
sys.modules['persistent_ssh_agent.utils'].is_valid_hostname = mock_is_valid_hostname
sys.modules['persistent_ssh_agent.utils'].run_command = mock_run_command

# Mock constants
mock_constants = MagicMock()
mock_constants.SSH_DEFAULT_OPTIONS = ["-o", "StrictHostKeyChecking=no"]
sys.modules['persistent_ssh_agent.constants'].SSHAgentConstants = mock_constants

try:
    from persistent_ssh_agent.git import GitIntegration
    
    print("Testing Windows Git credential helper fix...")
    
    # Create a mock SSH agent
    mock_ssh_agent = MagicMock()
    git_integration = GitIntegration(mock_ssh_agent)
    
    # Test 1: Windows credential helper generation
    print("\n1. Testing Windows credential helper generation:")
    with patch('os.name', 'nt'):
        helper = git_integration._create_platform_credential_helper('testuser', 'testpass')
        print(f"   Windows helper: {helper}")
        assert '&&' in helper, "Windows helper should use && to chain commands"
        assert 'echo username=testuser' in helper, "Should contain username"
        assert 'echo password=testpass' in helper, "Should contain password"
        print("   ✅ Windows credential helper generation works")
    
    # Test 2: Unix credential helper generation
    print("\n2. Testing Unix credential helper generation:")
    with patch('os.name', 'posix'):
        helper = git_integration._create_platform_credential_helper('testuser', 'testpass')
        print(f"   Unix helper: {helper}")
        assert '{ echo username=testuser; echo password=testpass; }' in helper, "Unix helper should use bash syntax"
        print("   ✅ Unix credential helper generation works")
    
    # Test 3: Credential escaping for Windows
    print("\n3. Testing Windows credential escaping:")
    with patch('os.name', 'nt'):
        escaped = git_integration._escape_credential_value('test"value%special')
        print(f"   Original: test\"value%special")
        print(f"   Escaped:  {escaped}")
        assert '""' in escaped, "Double quotes should be escaped"
        assert '%%' in escaped, "Percent signs should be escaped"
        print("   ✅ Windows credential escaping works")
    
    # Test 4: Credential escaping for Unix
    print("\n4. Testing Unix credential escaping:")
    with patch('os.name', 'posix'):
        escaped = git_integration._escape_credential_value('test"value\'special')
        print(f"   Original: test\"value'special")
        print(f"   Escaped:  {escaped}")
        assert '\\"' in escaped, "Double quotes should be escaped"
        print("   ✅ Unix credential escaping works")
    
    # Test 5: Full setup_git_credentials method
    print("\n5. Testing full setup_git_credentials method:")
    with patch('os.name', 'nt'):
        with patch.dict(os.environ, {'GIT_USERNAME': 'envuser', 'GIT_PASSWORD': 'envpass'}):
            result = git_integration.setup_git_credentials()
            print(f"   Setup result: {result}")
            assert result == True, "Setup should succeed"
            print("   ✅ Full setup_git_credentials method works")
    
    print("\n🎉 All tests passed! The Windows Git credential helper fix is working correctly.")
    
except Exception as e:
    print(f"❌ Error testing core fix: {e}")
    import traceback
    traceback.print_exc()
