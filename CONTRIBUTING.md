# Contributing to FaultPack

Thank you for helping improve FaultPack. The project values small, reviewable changes that preserve deterministic behavior and keep the security boundary explicit.

Before opening a pull request, install the development dependencies with `pip install -e '.[dev]'`, run `ruff check .`, `mypy src`, and `pytest`, and explain the user-facing behavior and test coverage. Changes to the manifest contract require a format-version discussion, migration notes, and fixtures for both valid and invalid inputs.

Please do not include real secrets, private logs, customer data, or undisclosed vulnerabilities in issues or pull requests. Use synthetic fixtures and redact captured output. New functionality should be implemented in a pure service first and exposed through the CLI only after the service has unit coverage.
