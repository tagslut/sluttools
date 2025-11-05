# AGENTS.md

# Contributor & Agent Guide for sluttools

## Overview
This project uses Poetry for dependency management and includes robust linting, testing, and automation. Please follow the guidelines below for contributing, automation, and agent-based workflows.

## Dev Environment Setup
- Use `poetry install` to set up your environment
- Run `poetry run pre-commit install` after cloning to enable pre-commit hooks
- All dependencies and tool configurations are in `pyproject.toml`

## Project Structure
- **Package**: `sluttools/` - main package directory (6 core modules)
- **Tests**: `tests/` - all test files
- **Docs**: `docs/` - project documentation
- **Config**: `pyproject.toml` (master config), `.pre-commit-config.yaml` (hooks only)

## Testing Instructions
- All tests are in the `tests/` directory
- Run tests: `poetry run pytest`
- With coverage: `poetry run pytest --cov=sluttools`
- Tests use ThreadPoolExecutor to avoid multiprocessing pickle issues

## Linting & Formatting
- **Black**: `poetry run black .` - code formatting
- **isort**: `poetry run isort .` - import sorting
- **flake8**: `poetry run flake8 .` - linting (using defaults)
- **mypy**: `poetry run mypy sluttools/` - type checking (relaxed settings)
- **Pre-commit**: `poetry run pre-commit run --all-files` - run all hooks

Or just run pre-commit hooks: `poetry run pre-commit run --all-files`

## Running the CLI
- Interactive: `poetry run slut` or `python -m sluttools`
- Commands: `poetry run slut --help`
- Main commands: `get library`, `match auto`, `match review`, `config edit`

## Contribution Guidelines
- See `CONTRIBUTING.md` for detailed contribution process
- Add or update tests for any code changes
- Run linters before committing (pre-commit hooks help with this)
- Follow existing code style and structure

---

# Agent Instructions
- Main code is in `sluttools/` directory (not `src/`)
- Use `pyproject.toml` for all dependency and tool configuration
- Run tests and linters before submitting changes
- Entry points: `slut` (Typer CLI), `fla` (argparse wrapper)
- Configuration: All in `pyproject.toml` - no separate config files needed
