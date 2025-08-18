# Project Improvement Tasks Checklist

Use this checklist to track improvements. Each task line begins with an unchecked box [ ] and items are ordered from foundational hygiene to architecture, features, performance, quality, and docs.

## 1. Repository hygiene and layout
1. [ ] Remove or relocate loose root-level scripts (e.g., `tidal2qobuz.py`) into `scripts/` or package entry points; ensure none remain in the project root.
2. [ ] Explicitly deprecate and remove the root-level `tidal2qobuz.py`; keep only `scripts/tidal2qobuz.py` (or a CLI subcommand) and update docs.
3. [ ] Ensure `library.db` and other runtime artifacts are git-ignored and moved to an OS-appropriate app data location (e.g., `~/.config/sluttools` by default).
4. [ ] Consolidate duplicate/legacy code in `scripts/archive/` and `music_automation/` by either deleting deprecated modules or moving maintained functionality into `sluttools/` with a deprecation notice.
5. [ ] Remove or archive `main.py` at root in favor of `sluttools/__main__.py` and Typer CLI entry points.
6. [ ] Add a clear scripts layout policy in `docs/PROJECT_STRUCTURE.md` (bin/ scripts vs library code vs archived experiments).

## 2. Packaging and distribution
1. [ ] Define `console_scripts` entry points in `pyproject.toml` (e.g., `sluttools=sluttools.cli:app`).
2. [ ] Remove `requirements.txt` or make it generated from `pyproject.toml`; avoid duplication of dependency definitions.
3. [ ] Add project classifiers, supported Python versions, and minimal pinned dependency bounds.
4. [ ] Verify `__version__` strategy (e.g., single source via `sluttools/__init__.py` or dynamic via git tags) and expose it in CLI `--version`.

## 3. Configuration management
1. [ ] Decouple interactive config creation from module import. Avoid prompting at import time (e.g., lazy-init in CLI command paths only).
2. [ ] Introduce a JSON schema (or Pydantic model) for config validation with clear error messages and defaults.
3. [ ] Support XDG base directory on Linux/macOS and appropriate Windows equivalent; allow env overrides and CLI flags.
4. [ ] Add a `sluttools config validate` command and a non-interactive `config init --defaults` mode for CI/containers.

## 4. Architecture and module boundaries
1. [ ] Split `sluttools/cli.py` into subcommands/modules (e.g., `cli/match.py`, `cli/config.py`, `cli/list.py`) to keep files small and testable.
2. [ ] Break down `sluttools/matching.py` into smaller units (I/O parsing, normalization, scoring, review UI) with clear interfaces.
3. [ ] Introduce a service layer for matching that is UI-agnostic, so matching logic can be reused by CLI and future APIs.
4. [ ] Encapsulate DB access behind a repository layer or use lightweight ORM patterns for maintainability.

## 5. Data and database layer
1. [ ] Add migrations or a versioning approach for the SQLite schema; include an auto-upgrade path.
2. [ ] Create appropriate indexes (artist, title, album, path) and verify query plans for `get_flac_lookup` and matching queries.
3. [ ] Ensure safe concurrent access (thread/process) using write locks or a job queue; document supported concurrency.
4. [ ] Add backup/restore utilities (`sluttools db backup`, `db vacuum`, `db stats`).

## 6. Matching and normalization
1. [ ] Replace `fuzzywuzzy` with `rapidfuzz` for faster, license-friendly fuzzy matching.
2. [ ] Centralize normalization: case-folding, Unicode NFC/NFKD, punctuation removal, common feature removal (feat., remaster), and whitespace rules.
3. [ ] Add configurable thresholds per source (auto/review), with sensible defaults and clear CLI flags.
4. [ ] Implement and test alternative scorers (token set/ratio, partial ratio, weighted combos) with benchmarks.
5. [ ] Provide deterministic tie-breaking (e.g., by path stability or album match) and expose rationale in verbose mode.

## 7. CLI and UX
1. [ ] Provide a `--plain` mode to disable animation/colors reliably via a single flag and env var.
2. [ ] Add consistent non-interactive modes for all commands (no prompts), with exit codes for automation.
3. [ ] Standardize output paths using templates with `{playlist_name}` and safe filename sanitization.
4. [ ] Improve error handling: friendly messages, `--verbose`/`--debug` flags, and stack traces gated behind debug.
5. [ ] Provide progress bars with opt-out and TTY detection.

## 8. I/O and playlist handling
1. [ ] Expand playlist input support and auto-detection (M3U/M3U8/JSON), with clear schema for JSON.
2. [ ] Add encoding and path normalization (Windows/macOS/Linux) and robust BOM handling.
3. [ ] Validate and sanitize file writes; prevent overwriting without `--force`.

## 9. Performance and scalability
1. [ ] Profile matching on large libraries; add batching and optional precomputed search indexes.
2. [ ] Use multiprocessing/threading pools where appropriate; make pool size configurable.
3. [ ] Cache normalized library tokens to reduce per-run CPU.

## 10. Code quality and maintainability
1. [ ] Enforce type hints and run `mypy` with a strict-enough configuration; address key typing gaps.
2. [ ] Adopt `ruff` for linting/formatting (or `black` + `isort`) and add a `pre-commit` config.
3. [ ] Add logging using the standard library `logging` with module-level loggers; remove ad-hoc prints.
4. [ ] Reduce overly long functions; aim for small, testable units.

## 11. Testing and CI
1. [ ] Increase test coverage for matching edge cases (unicode, punctuation, featuring artists, remasters, live versions).
2. [ ] Add tests for config loading (env overrides, schema validation) and DB migrations.
3. [ ] Add end-to-end tests for typical workflows (scan library, match playlist, export outputs).
4. [ ] Set up CI (GitHub Actions) to run lint, type-check, tests on supported Python versions.

## 12. Documentation
1. [ ] Update README with install, quickstart, and examples using the new CLI entry point.
2. [ ] Expand `USAGE-CONFIG.md` with schema, env vars, and examples; add a troubleshooting section.
3. [ ] Document architecture in `docs/PROJECT_STRUCTURE.md` reflecting refactoring (modules, boundaries, data flow).
4. [ ] Add a CHANGELOG policy (Keep a Changelog, SemVer) and release instructions.

## 13. Security and compliance
1. [ ] Review third-party deps; replace deprecated or unmaintained ones; pin minimal secure versions.
2. [ ] Ensure paths and filenames are sanitized to prevent traversal and injection issues in outputs.
3. [ ] Add a basic security policy note in SECURITY.md regarding reporting vulnerabilities.

## 14. Developer experience
1. [ ] Provide `make`/`tox`/`nox` tasks for setup, test, lint, type-check, package, and release.
2. [ ] Add example config and sample inputs under `examples/` with small fixtures for testing.
3. [ ] Provide a `contrib/` guideline and PR template updates in `CONTRIBUTING.md`.

## 15. Migration and cleanup plan
1. [ ] Create a deprecation plan for `music_automation` and `scripts/archive` with a target removal version.
2. [ ] Provide a migration guide for users of legacy scripts to the CLI.
3. [ ] Run a repository-wide dead code and reference check; remove unused modules and imports.
