# Changelog

## Unreleased
- Docs: Added docs/REFACTOR_PROPOSAL.md detailing repository cleanup (archives removal, duplicates consolidation) and updated README with a “Repository cleanup and deprecations” section.
- Matcher UX: Recent improvements to slut-match output views (compact/unmatched/full), truncation, no-color mode, and relative path display.
- Note: No breaking changes in this release; actual removals will occur in a subsequent minor version per the proposal.

## 2.1.0 - 2025-08-09
- Branding: Keep package name `sluttools`, CLI command `slut`, tagline “Get. Match. Tag. Out.”
- CLI: Structured subcommands (get/match/out/list/config); retained animated header with Arabic line; `--plain`/`SLUT_PLAIN` to disable animation.
- Config: Unified schema and precedence (env > file > defaults). Added SLUT_* env vars. First-run wizard prompts for LIBRARY_ROOTS.
- Docs: README updates (pipx quickstart, commands), added USAGE-CONFIG.md, docs/PROJECT_STRUCTURE.md.
- Build: Pinned Click/Rich/Typer to resolve `--help` issue. Bumped version to 2.1.0.
- Tests: Legacy shims preserved; all tests passing.
