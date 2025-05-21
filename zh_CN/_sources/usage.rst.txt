Usage
=====

Basic Usage
----------

persistent_ssh_agent can be used both as a Python library and as a command-line tool.

Python Library
-------------

To use persistent_ssh_agent in your Python code:

.. code-block:: python

    from persistent_ssh_agent import PersistentSSHAgent
    from persistent_ssh_agent.config import SSHConfig

    # Create an SSH configuration
    ssh_config = SSHConfig(
        identity_file="~/.ssh/id_rsa",
        identity_passphrase="your_passphrase"  # Optional
    )

    # Initialize the SSH agent
    ssh_agent = PersistentSSHAgent(config=ssh_config)

    # Test a connection
    success = ssh_agent.setup_ssh("github.com")
    if success:
        print("SSH connection successful!")
    else:
        print("SSH connection failed.")

Command-Line Interface
---------------------

persistent_ssh_agent provides a command-line interface for common operations:

Configure SSH Agent
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Set identity file
    persistent_ssh_agent config --identity-file ~/.ssh/id_rsa

    # Set passphrase (not recommended for security reasons)
    persistent_ssh_agent config --passphrase "your_passphrase"

    # Prompt for passphrase (more secure)
    persistent_ssh_agent config --prompt-passphrase

Test SSH Connection
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Test connection to a host
    persistent_ssh_agent test github.com

    # Test with a specific identity file
    persistent_ssh_agent test github.com --identity-file ~/.ssh/github_key

Manage SSH Keys
~~~~~~~~~~~~~~

.. code-block:: bash

    # List configured SSH keys
    persistent_ssh_agent list

    # Remove a specific key
    persistent_ssh_agent remove --name github

    # Remove all keys
    persistent_ssh_agent remove --all

Export and Import Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Export configuration
    persistent_ssh_agent export --output config.json

    # Import configuration
    persistent_ssh_agent import config.json
