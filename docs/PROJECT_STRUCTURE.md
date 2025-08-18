# Project Structure

A quick guide to where things live and how to navigate the codebase.

- README.md — Top-level overview and quickstart.
- pyproject.toml — Project metadata and dependencies (Poetry).
- sluttools/ — The Python package with the application code.
  - __main__.py — Enables `python -m sluttools`.
  - cli.py — Typer CLI application (commands: get, match, out, list, config).
  - config.py — First-run config wizard defaults and dynamic loading.
  - database.py — Library indexing and SQLite interaction for the app.
  - matching.py — Canonical playlist parsing and matching logic (use this).
  - matcher.py — Deprecated low-level helpers (e.g., calculate_match_score) kept for compatibility.
  - metadata.py — Normalization and metadata extraction helpers.
  - wizard.py — Rich/interactive setup and matching workflows.
- scripts/ — Invokable helper scripts (prefer using these over root files).
  - main.py — Thin wrapper to run the CLI; equivalent to `python -m sluttools`.
  - tidal2qobuz.py — Wrapper that forwards to the legacy root script.
- tests/ — Pytest suite.
- docs/ — Additional documentation like this structure guide.

Legacy or archived materials:
- scripts/archive — Old prototypes kept for reference (e.g., g.py and gg.py). Not part of the active CLI.

Ignored/ephemeral files:
- json/ — Local outputs (ignored).
- library.db — Example/temporary DB file (ignored).

# Conventions
- Use `pipx run slut` or `poetry run slut` to invoke the CLI.
- Do not add new standalone Python scripts to the repository root. Place them under `scripts/` or implement as `sluttools` subcommands.
- Keep user data and generated files out of version control; add patterns to .gitignore.
