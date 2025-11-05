# Project Structure

A quick guide to where things live and how to navigate the codebase.

- README.md — Top-level overview and quickstart.
- pyproject.toml — Project metadata and dependencies (Poetry).
- sluttools/ — The Python package with the application code.
  - __main__.py — Enables `python -m sluttools`.
  - cli.py — Typer CLI application (commands: get, match, out, list, config).
  - config.py — First-run config wizard defaults and dynamic loading.
  - database.py — Library indexing and SQLite interaction for the app.
  - matching.py — Interactive/advanced matching workflows.
  - matcher.py — Deprecated low-level helpers (kept for compatibility; may emit deprecation in future).
  - matcher_fast.py — Fast non-interactive matcher; exposed as `slut-match`.
  - metadata.py — Normalization and metadata extraction helpers.
  - wizard.py — Rich/interactive setup and matching workflows.
- scripts/ — Invokable helper scripts kept minimal (prefer CLI entry points via Poetry).
  - main.py — Thin wrapper to run the CLI; equivalent to `python -m sluttools`.
- tests/ — Pytest suite.
- docs/ — Additional documentation like this structure guide, configuration notes, and refactor proposals.

Removed legacy/archived materials (previously under scripts/archive):
- Historical prototypes were removed to simplify the repo. See docs/REFACTOR_PROPOSAL.md for context.

Ignored/ephemeral files:
- json/ — Local outputs (ignored).
- library.db — Example/temporary DB file (ignored).

# Conventions
- Use `pipx run slut` or `poetry run slut` to invoke the CLI; `poetry run slut-match` for the fast matcher.
- Do not add new standalone Python scripts to the repository root. Prefer CLI subcommands or add a Poetry script entry.
- Keep user data and generated files out of version control; add patterns to .gitignore.
- Tests live under `tests/` and use pytest. Add fixtures alongside the tests that exercise them.
- Documentation updates should accompany behavior changes. Cross-link new guides from `README.md` where appropriate.
