# AGENTS.md

# Contributor & Agent Guide for music-automation-toolkit

## Overview
This project uses a modern Python src/ layout, Poetry for dependency management, and includes robust linting, testing, and automation. Please follow the guidelines below for contributing, automation, and agent-based workflows.

## Dev Environment Tips
- Use `pip install -e .` or `poetry install` to set up your environment.
- Run `pre-commit install` after cloning to enable pre-commit hooks.
- Use `pytest` to run tests. Coverage is enabled via `pytest-cov`.
- Lint and format code with `black`, `flake8`, `isort`, and `mypy`.

## Testing Instructions
- All tests are in the `tests/` directory.
- Run `pytest` for the full suite.
- Coverage reports: `pytest --cov=music_automation`.

## Linting & Type Checking
- Run all checks: `black . && isort . && flake8 . && mypy src/`.
- Or use the provided Makefile or scripts (if present).

## Automation
- Use `setup_script.sh` to install the package in editable mode.
- For agent workflows, this file provides context and instructions.

## Contribution
- See `CONTRIBUTING.md` for more details.
- Please add or update tests for any code you change.

---

# Agent Instructions
- Explore the `src/` directory for main code.
- Use `pyproject.toml` for dependency and tool configuration.
- Run tests and linters before submitting changes.
- See this file for project-specific automation and CI tips.
