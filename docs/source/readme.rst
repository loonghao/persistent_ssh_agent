.. include:: ../../README.md
   :parser: myst_parser.sphinx_

persistent_ssh_agent is a Python package that helps manage SSH agent persistence across sessions.

Features
--------

- Automatic SSH agent management
- Session persistence
- Cross-platform support
- Easy configuration

Installation
------------

You can install persistent_ssh_agent using pip:

.. code-block:: bash

   pip install persistent_ssh_agent

Usage
-----

Basic usage:

.. code-block:: python

   from persistent_ssh_agent import SSHAgent

   # Initialize the agent
   agent = SSHAgent()

   # Start the agent
   agent.start()

   # Add your SSH key
   agent.add_key('path/to/your/key')

   # The agent will persist across sessions

Configuration
------------

You can configure the agent behavior through:

1. Environment variables
2. Configuration file
3. Direct parameters

See the documentation for detailed configuration options.
