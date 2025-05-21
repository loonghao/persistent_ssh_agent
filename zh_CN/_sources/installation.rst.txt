Installation
============

You can install persistent_ssh_agent using pip:

.. code-block:: bash

    pip install persistent_ssh_agent

From Source
----------

To install from source:

.. code-block:: bash

    git clone https://github.com/loonghao/persistent_ssh_agent.git
    cd persistent_ssh_agent
    pip install -e .

Requirements
-----------

persistent_ssh_agent requires:

* Python 3.7 or higher
* OpenSSH client installed on your system
* cryptography library for encryption operations
* click library for CLI functionality

Development Installation
-----------------------

For development, you can install with additional dependencies:

.. code-block:: bash

    pip install -e ".[dev]"

This will install additional packages needed for development, such as:

* pytest for testing
* ruff for linting
* isort for import sorting
* sphinx for documentation
