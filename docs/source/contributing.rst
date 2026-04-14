Contributing Guidelines
=======================

Thank you for your interest in contributing to **AxisPy Engine**! This document provides guidelines and instructions for contributing to the project.

Getting Started
---------------

Fork and Clone
^^^^^^^^^^^^^^

1. Fork the repository on GitHub
2. Clone your fork locally:

.. code-block:: bash

   git clone https://github.com/YOUR_USERNAME/axispy.git
   cd axispy

3. Add the upstream repository as a remote:

.. code-block:: bash

   git remote add upstream https://github.com/Bayaola/axispy.git

Development Environment
^^^^^^^^^^^^^^^^^^^^^^^

1. Create a virtual environment:

.. code-block:: bash

   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux

2. Install dependencies:

.. code-block:: bash

   pip install -r requirements.txt

3. Install the package in development mode:

.. code-block:: bash

   pip install -e .

4. Run tests to verify setup:

.. code-block:: bash

   pytest tests/

How to Contribute
-----------------

Reporting Bugs
^^^^^^^^^^^^^^

Before submitting a bug report:

- Check existing issues to avoid duplicates
- Use the bug report template
- Include:
  - AxisPy version
  - Python version
  - Operating system
  - Steps to reproduce
  - Expected vs actual behavior
  - Error messages and stack traces

Suggesting Features
^^^^^^^^^^^^^^^^^^^

- Open a GitHub Discussion or Feature Request issue
- Describe the feature and its use case
- Explain why it would be useful to most users

Submitting Pull Requests
^^^^^^^^^^^^^^^^^^^^^^^^

1. Create a new branch from ``main``:

.. code-block:: bash

   git checkout -b feature/your-feature-name

2. Make your changes
3. Write or update tests as needed
4. Run the full test suite:

.. code-block:: bash

   pytest tests/

5. Commit your changes (see `Commit Conventions`_)
6. Push to your fork:

.. code-block:: bash

   git push origin feature/your-feature-name

7. Open a Pull Request on GitHub

Code Standards
--------------

Style Guide
^^^^^^^^^^^

- Follow **PEP 8** for Python code style
- Use meaningful variable and function names
- Add docstrings to all public functions and classes (Google style)
- Maximum line length: 100 characters
- Use type hints where appropriate

Testing
^^^^^^^

- Write unit tests for all new functionality
- Maintain test coverage above 80%
- Tests should be placed in the ``tests/`` directory
- Use ``pytest`` for testing
- Run tests before submitting PR:

.. code-block:: bash

   pytest tests/ --cov=core --cov=editor --cov=plugins

Commit & Branch Conventions
---------------------------

Branch Naming
^^^^^^^^^^^^^

Use prefixes to categorize branches:

- ``feature/`` - New features (e.g., ``feature/physics-2d``)
- ``fix/`` - Bug fixes (e.g., ``fix/camera-crash``)
- ``docs/`` - Documentation changes (e.g., ``docs/api-reference``)
- ``refactor/`` - Code refactoring (e.g., ``refactor/input-system``)
- ``test/`` - Test additions or fixes (e.g., ``test/animation-coverage``)

Commit Messages
^^^^^^^^^^^^^^^

We follow **Conventional Commits**:

.. code-block:: text

   <type>(<scope>): <description>

   [optional body]

   [optional footer(s)]

Types:

- ``feat`` - New feature
- ``fix`` - Bug fix
- ``docs`` - Documentation changes
- ``style`` - Formatting (no code change)
- ``refactor`` - Code restructuring
- ``test`` - Adding or updating tests
- ``chore`` - Maintenance tasks

Examples:

.. code-block:: text

   feat(ai): add GPT-4o provider support
   fix(camera): resolve clipping issue at boundaries
   docs(tutorials): add multiplayer setup guide

Pull Request Process
--------------------

What Makes a Good PR
^^^^^^^^^^^^^^^^^^^^

- Clear description of changes
- Reference to related issue(s)
- Screenshots/GIFs for UI changes
- Updated documentation if needed
- Passing CI/CD checks
- Code review approval from at least one maintainer

Review Process
^^^^^^^^^^^^^^

1. Automated checks must pass (linting, tests)
2. Code review by maintainers
3. Address feedback promptly
4. Once approved, maintainers will merge

Issue Tracking
--------------

Labels
^^^^^^

We use labels to categorize issues:

- ``bug`` - Something isn't working
- ``enhancement`` - New feature requests
- ``documentation`` - Documentation improvements
- ``good first issue`` - Good for newcomers
- ``help wanted`` - Community assistance needed
- ``priority:high`` - Urgent issues

Claiming Issues
^^^^^^^^^^^^^^^

- Comment on an issue to express interest
- Wait for assignment before starting work
- If inactive for 2+ weeks, the issue may be reassigned

Code of Conduct
---------------

This project adheres to the `Code of Conduct <https://github.com/Bayaola/axispy/blob/main/CODE_OF_CONDUCT.md>`_. By participating, you are expected to uphold this code.

Community & Communication
-------------------------

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- Response time: Maintainers aim to respond within 48 hours

Legal
-----

License
^^^^^^^

By contributing, you agree that your contributions will be licensed under the same license as the project (see `LICENSE <https://github.com/Bayaola/axispy/blob/main/LICENSE>`_ file).

Developer Certificate of Origin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We require all contributors to agree to the Developer Certificate of Origin (DCO) for their contributions. By submitting a PR, you certify that:

- You have the right to submit the contribution
- The contribution is your original work
- You understand the contribution is public

Questions?
----------

If you have questions not covered by this guide, please:

1. Check existing documentation
2. Search closed issues on GitHub
3. Open a new GitHub Discussion

Thank you for contributing to AxisPy Engine!
