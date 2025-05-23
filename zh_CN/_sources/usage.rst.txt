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
    uvx persistent_ssh_agent config --identity-file ~/.ssh/id_rsa

    # Set passphrase (not recommended for security reasons)
    uvx persistent_ssh_agent config --passphrase "your_passphrase"

    # Prompt for passphrase (more secure)
    uvx persistent_ssh_agent config --prompt-passphrase

Test SSH Connection
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Test connection to a host
    uvx persistent_ssh_agent test github.com

    # Test with a specific identity file
    uvx persistent_ssh_agent test github.com --identity-file ~/.ssh/github_key

Manage SSH Keys
~~~~~~~~~~~~~~

.. code-block:: bash

    # List configured SSH keys
    uvx persistent_ssh_agent list

    # Remove a specific key
    uvx persistent_ssh_agent remove --name github

    # Remove all keys
    uvx persistent_ssh_agent remove --all

Export and Import Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Export configuration
    uvx persistent_ssh_agent export --output config.json

    # Import configuration
    uvx persistent_ssh_agent import config.json

Git Credential Setup
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Set up Git credentials interactively
    uvx persistent_ssh_agent git-setup --prompt

    # Set up Git credentials with username
    uvx persistent_ssh_agent git-setup --username your-username --prompt

    # Set up Git credentials using environment variables
    export GIT_USERNAME=your-username
    export GIT_PASSWORD=your-password
    uvx persistent_ssh_agent git-setup
