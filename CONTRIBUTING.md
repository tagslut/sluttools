# Contributing to music-automation-toolkit

Thank you for considering contributing!

## Development Setup

- Install dependencies: `pip install -e .` or `poetry install`
- Install pre-commit hooks: `pre-commit install`

## Code Style

- Format: `black .`
- Lint: `flake8 .`
- Sort imports: `isort .`
- Type check: `mypy src/`

## Testing

- Run tests: `pytest`
- Coverage: `pytest --cov=music_automation`

## Submitting Changes

- Fork the repo and create a feature branch
- Add/modify tests for your changes
- Run all checks before submitting a PR
- Use clear commit messages

## Reporting Issues

- Use GitHub Issues and provide as much detail as possible
