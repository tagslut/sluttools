# Unified lint and check script for music-automation-toolkit

# Run all code quality checks and tests
black .
isort .
flake8 .
mypy src/
pytest
