# Makefile for music-automation-toolkit

.PHONY: install lint test check

install:
	pip install -e .

lint:
	black . && isort . && flake8 . && mypy src/

test:
	pytest

match:
\tpoetry run slut-match match "$(PLAYLIST)" --m3u Minimal_Focus.m3u --export-unmatched Minimal_Focus_unmatched.json


check: lint test
