# Makefile for music-automation-toolkit

.PHONY: install lint test check

install:
	pip install -e .

lint:
	black . && isort . && flake8 . && mypy src/

test:
	pytest

check: lint test
