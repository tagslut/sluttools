# Changelog

## Unreleased
- Docs: Updated README with `slut-match` usage and new flags; updated docs/PROJECT_STRUCTURE.md to reflect removed archives; added docs/REFACTOR_PROPOSAL.md.
- Cleanup: Removed archived prototypes and redundant wrappers/backups (scripts/archive/*, scripts/__init__.py, scripts/tidal2qobuz.py, tidal2qobuz.py.bak, root main.py, musictools). No impact to public CLI entry points.
- Matcher UX: Improved `slut-match` output views (compact/unmatched/full), truncation, plain-text fallback with `--no-color`, and relative path display.

## 2.1.0 - 2025-08-09
- Branding: Keep package name `sluttools`, CLI command `slut`, tagline “Get. Match. Tag. Out.”
- CLI: Structured subcommands (get/match/out/list/config); retained animated header with Arabic line; `--plain`/`SLUT_PLAIN` to disable animation.
- Config: Unified schema and precedence (env > file > defaults). Added SLUT_* env vars. First-run wizard prompts for LIBRARY_ROOTS.
- Docs: README updates (pipx quickstart, commands), added USAGE-CONFIG.md, docs/PROJECT_STRUCTURE.md.
- Build: Pinned Click/Rich/Typer to resolve `--help` issue. Bumped version to 2.1.0.
- Tests: Legacy shims preserved; all tests passing.
