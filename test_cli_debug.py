#!/usr/bin/env python3
"""Test script to verify CLI debug functionality."""

import os
import sys
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the dependencies that might not be installed
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.hazmat'] = MagicMock()
sys.modules['cryptography.hazmat.backends'] = MagicMock()
sys.modules['cryptography.hazmat.primitives'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers.algorithms'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers.modes'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf.pbkdf2'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.hashes'] = MagicMock()
sys.modules['loguru'] = MagicMock()
sys.modules['click'] = MagicMock()

# Mock click decorators
def mock_group(**kwargs):
    def decorator(func):
        return func
    return decorator

def mock_command(name, **kwargs):
    def decorator(func):
        return func
    return decorator

def mock_option(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

def mock_argument(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

def mock_pass_context(func):
    return func

# Apply mocks
sys.modules['click'].group = mock_group
sys.modules['click'].command = mock_command
sys.modules['click'].option = mock_option
sys.modules['click'].argument = mock_argument
sys.modules['click'].pass_context = mock_pass_context
sys.modules['click'].prompt = lambda x, **kwargs: "test_input"
sys.modules['click'].echo = print

# Mock loguru logger
mock_logger = MagicMock()
mock_logger.remove = MagicMock()
mock_logger.add = MagicMock()
mock_logger.debug = lambda msg, *args: print(f"DEBUG: {msg % args if args else msg}")
mock_logger.info = lambda msg, *args: print(f"INFO: {msg % args if args else msg}")
mock_logger.error = lambda msg, *args: print(f"ERROR: {msg % args if args else msg}")
mock_logger.exception = lambda msg, *args: print(f"EXCEPTION: {msg % args if args else msg}")
sys.modules['loguru'].logger = mock_logger

try:
    from persistent_ssh_agent.cli import _configure_debug_logging, _configure_default_logging
    
    print("Testing CLI debug configuration...")
    
    # Test debug logging configuration
    print("\n1. Testing debug logging configuration:")
    _configure_debug_logging()
    print("✅ Debug logging configured successfully")
    
    # Test default logging configuration
    print("\n2. Testing default logging configuration:")
    _configure_default_logging()
    print("✅ Default logging configured successfully")
    
    print("\n✅ All CLI debug tests passed!")
    
except Exception as e:
    print(f"❌ Error testing CLI debug functionality: {e}")
    import traceback
    traceback.print_exc()
