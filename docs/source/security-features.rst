Security Features
=================

persistent_ssh_agent includes several security features to protect your SSH keys and passphrases:

AES-256 Encryption
------------------

* Passphrases are encrypted using AES-256 in CBC mode
* Encryption keys are derived from system-specific information
* PBKDF2 with SHA-256 is used for key derivation with 100,000 iterations

System-Bound Encryption
-----------------------

The encryption key is derived from:

* Machine ID (unique to each computer)
* Hostname
* Username
* Home directory path

This ensures that encrypted passphrases can only be decrypted on the same machine by the same user.

Secure Memory Handling
---------------------

* Sensitive data like passphrases are securely deleted from memory when no longer needed
* Best-effort approach to prevent passphrases from lingering in memory

File Permissions
----------------

* Configuration files are created with restricted permissions (0600)
* Configuration directory is created with restricted permissions (0700)
* These permissions ensure that only the owner can read or write the files

SSH Agent Security
-----------------

* Uses the system's SSH agent for key management
* Keys are never written to disk in unencrypted form
* SSH agent handles authentication without exposing the private key

Best Practices
--------------

For maximum security:

* Use the ``--prompt-passphrase`` option instead of providing the passphrase on the command line
* Regularly rotate your SSH keys
* Use different SSH keys for different services
* Consider using hardware security keys for critical systems
