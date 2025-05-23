Fix Windows compatibility for Git credential helper functionality.

The Git credential helper now uses platform-specific shell syntax:
- Windows: Uses `cmd.exe` compatible syntax with `&&` to chain commands
- Unix/Linux: Uses `bash` compatible syntax with function definitions

This resolves the issue where Git credential helper setup would fail on Windows
due to incompatible bash syntax being used in a Windows environment.

Additionally, added proper credential value escaping for both platforms to handle
special characters in usernames and passwords safely.

Also added global `--debug` flag to CLI for enhanced debugging capabilities.
