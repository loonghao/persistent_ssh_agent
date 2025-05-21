Contributing
============

We welcome contributions to persistent_ssh_agent! Here's how you can help:

Setting Up Development Environment
----------------------------------

1. Clone the repository:

   .. code-block:: bash

       git clone https://github.com/loonghao/persistent_ssh_agent.git
       cd persistent_ssh_agent

2. Create a virtual environment and install development dependencies:

   .. code-block:: bash

       python -m venv venv
       source venv/bin/activate  # On Windows: venv\Scripts\activate
       pip install -e ".[dev]"

3. Install pre-commit hooks:

   .. code-block:: bash

       pre-commit install

Development Workflow
--------------------

1. Create a new branch for your feature or bugfix:

   .. code-block:: bash

       git checkout -b feature/your-feature-name

2. Make your changes and write tests for them.

3. Run the tests to ensure everything works:

   .. code-block:: bash

       uvx nox -s pytest

4. Check code style:

   .. code-block:: bash

       uvx nox -s lint

5. Build and check the documentation:

   .. code-block:: bash

       uvx nox -s docs-build

6. Commit your changes with a descriptive message:

   .. code-block:: bash

       git commit -m "Add feature: your feature description"

7. Push your branch and create a pull request:

   .. code-block:: bash

       git push origin feature/your-feature-name

Pull Request Guidelines
-----------------------

* Include tests for any new features or bug fixes
* Update documentation if necessary
* Follow the code style of the project
* Make sure all tests pass before submitting
* Keep pull requests focused on a single topic
* Reference any relevant issues in your PR description

Code Style
----------

This project uses:

* isort for import sorting
* ruff for linting and formatting
* Type hints for all function signatures

Testing
-------

* Write unit tests for all new functionality
* Run the test suite with ``uvx nox -s pytest``
* Aim for high test coverage for all new code

Documentation
-------------

* Update documentation for any new features or changes
* Build and check documentation with ``uvx nox -s docs-build``
* Use clear, concise language in docstrings and documentation
