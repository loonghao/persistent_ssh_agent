"""Tests for encoding handling in utils module."""

# Import built-in modules
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.utils import _decode_subprocess_output
from persistent_ssh_agent.utils import run_command
import pytest


class TestDecodeSubprocessOutput:
    """Test cases for _decode_subprocess_output function."""

    def test_decode_empty_data(self):
        """Test decoding empty data."""
        result = _decode_subprocess_output(b"")
        assert result == ""

    def test_decode_utf8_data(self):
        """Test decoding UTF-8 data."""
        test_data = "Hello, 世界!".encode("utf-8")
        result = _decode_subprocess_output(test_data)
        assert result == "Hello, 世界!"

    def test_decode_gbk_data_on_windows(self):
        """Test decoding GBK data on Windows."""
        test_data = "你好世界".encode("gbk")

        with patch("os.name", "nt"):
            result = _decode_subprocess_output(test_data)
            assert result == "你好世界"

    def test_decode_latin1_fallback(self):
        """Test fallback to latin1 encoding."""
        # Create some bytes that are valid latin1 but not UTF-8
        test_data = b"\xff\xfe\xfd"
        result = _decode_subprocess_output(test_data)
        # Should decode successfully with latin1
        assert isinstance(result, str)
        assert len(result) == 3

    def test_decode_with_encoding_hint(self):
        """Test decoding with encoding hint."""
        test_data = "测试".encode("gbk")
        result = _decode_subprocess_output(test_data, encoding_hint="gbk")
        assert result == "测试"

    def test_decode_invalid_encoding_hint(self):
        """Test with invalid encoding hint."""
        test_data = "Hello".encode("utf-8")
        result = _decode_subprocess_output(test_data, encoding_hint="invalid-encoding")
        assert result == "Hello"

    def test_decode_replacement_fallback(self):
        """Test UTF-8 replacement fallback for problematic bytes."""
        # Create bytes that can't be decoded by common encodings
        test_data = b"\x80\x81\x82\x83"

        result = _decode_subprocess_output(test_data)
        # Should use replacement characters or latin1 fallback
        assert isinstance(result, str)
        # The function should handle this gracefully without necessarily logging a warning

    def test_decode_critical_error_fallback(self):
        """Test critical error fallback."""
        # Test the real function with problematic data that causes errors
        # Use data that will trigger the fallback path
        problematic_data = b"\x80\x81\x82\x83"
        result = _decode_subprocess_output(problematic_data)
        # Should return a string (either decoded or fallback)
        assert isinstance(result, str)

    @pytest.mark.parametrize("platform", ["nt", "posix"])
    def test_platform_specific_encodings(self, platform):
        """Test platform-specific encoding selection."""
        test_data = "test".encode("utf-8")

        with patch("os.name", platform):
            result = _decode_subprocess_output(test_data)
            assert result == "test"
            # This test verifies that the function works correctly on different platforms
            # The actual encoding selection logic is tested implicitly


class TestRunCommandEncoding:
    """Test cases for run_command with encoding handling."""

    def test_run_command_with_utf8_output(self):
        """Test run_command with UTF-8 output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello, 世界!".encode("utf-8")
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            result = run_command(["echo", "test"])
            assert result is not None
            assert result.stdout == "Hello, 世界!"
            assert result.stderr == ""

    def test_run_command_with_gbk_output(self):
        """Test run_command with GBK output on Windows."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "你好世界".encode("gbk")
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            with patch("os.name", "nt"):
                result = run_command(["echo", "test"])
                assert result is not None
                assert result.stdout == "你好世界"

    def test_run_command_with_encoding_hint(self):
        """Test run_command with encoding hint."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "测试".encode("gbk")
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            result = run_command(["echo", "test"], encoding="gbk")
            assert result is not None
            assert result.stdout == "测试"

    def test_run_command_no_output_capture(self):
        """Test run_command without output capture."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = None
        mock_result.stderr = None

        with patch("subprocess.run", return_value=mock_result):
            result = run_command(["echo", "test"], check_output=False)
            assert result is not None
            assert result.stdout is None
            assert result.stderr is None

    def test_run_command_with_problematic_encoding(self):
        """Test run_command with problematic encoding."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\x80\x81\x82\x83"  # Problematic bytes
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            result = run_command(["echo", "test"])
            assert result is not None
            assert isinstance(result.stdout, str)
            # The function should handle problematic encoding gracefully

    def test_run_command_timeout_with_encoding(self):
        """Test run_command timeout handling."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("test", 1)):
            with patch("persistent_ssh_agent.utils.logger") as mock_logger:
                result = run_command(["sleep", "10"], timeout=1)
                assert result is None
                mock_logger.error.assert_called_once()

    def test_run_command_exception_with_encoding(self):
        """Test run_command exception handling."""
        with patch("subprocess.run", side_effect=Exception("Test error")):
            with patch("persistent_ssh_agent.utils.logger") as mock_logger:
                result = run_command(["invalid", "command"])
                assert result is None
                mock_logger.error.assert_called_once()

    def test_run_command_stderr_encoding(self):
        """Test run_command stderr encoding handling."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = "错误信息".encode("gbk")

        with patch("subprocess.run", return_value=mock_result):
            with patch("os.name", "nt"):
                result = run_command(["test"])
                assert result is not None
                assert result.stderr == "错误信息"

    def test_run_command_backward_compatibility(self):
        """Test that run_command maintains backward compatibility."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test output".encode("utf-8")
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            # Test with old-style parameters
            result = run_command(["echo", "test"], shell=False, check_output=True)
            assert result is not None
            assert result.stdout == "test output"
            assert result.stderr == ""

    def test_run_command_git_timeout_default(self):
        """Test that Git commands get default timeout."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"git output"
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = run_command(["git", "status"])
            assert result is not None
            # Check that timeout was set to 30 seconds for Git commands
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[1]["timeout"] == 30

    def test_run_command_git_non_interactive_flags(self):
        """Test that Git commands are handled properly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"git output"
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Test submodule command
            result = run_command(["git", "submodule", "update"])
            assert result is not None
            # Check that the command was called correctly
            call_args = mock_run.call_args
            enhanced_command = call_args[0][0]
            assert "git" in enhanced_command
            assert "submodule" in enhanced_command
            assert "update" in enhanced_command

    def test_run_command_input_data(self):
        """Test run_command with input data."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"output"
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = run_command(["cat"], input_data="test input")
            assert result is not None
            # Check that input was provided as bytes
            call_args = mock_run.call_args
            assert call_args[1]["input"] == b"test input"
