Features
========

persistent_ssh_agent provides several key features to make SSH authentication easier and more secure:

Persistent SSH Agent
--------------------

* Automatically starts and manages an SSH agent process
* Keeps SSH keys loaded in the agent for the duration of your session
* Handles SSH agent forwarding for remote connections

Secure Key Management
---------------------

* Securely stores SSH key passphrases using AES-256 encryption
* Derives encryption keys from system-specific information
* Supports multiple SSH keys for different hosts or services

Command-Line Interface
----------------------

* Simple CLI for configuring and managing SSH keys
* Commands for testing SSH connections
* Export and import configuration for backup or sharing

Cross-Platform Support
----------------------

* Works on Linux, macOS, and Windows
* Consistent behavior across different operating systems
* Handles platform-specific SSH agent implementations
