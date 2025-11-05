# Changelog

## Unreleased
- **Breaking**: Removed `music_automation/` compatibility shim directory. Tests now import directly from `sluttools` modules.
- **Breaking**: Removed deprecated `sluttools/matcher.py` module. Scoring logic merged into `sluttools/matching.py`.
- **Breaking**: Removed standalone utility scripts `qobuz_auth.py` and `tidal2qobuz.py`. These were separate tools not integrated with the main CLI.
- **Breaking**: Removed `slut-match` standalone command. Use `slut match auto` for non-interactive matching or `slut match review` for interactive matching instead.
- **Breaking**: Removed `sluttools/wizard.py` module. Configuration wizard functionality is now inline in `slut config edit`, and matching wizard functionality is provided by `slut match review`.
- **Refactor**: Merged `sluttools/metadata.py` into `sluttools/database.py`. All metadata extraction utilities (normalize_string, gather_metadata, parse_filename_structure) are now in the database module where they logically belong as part of the data layer.
- **Cleanup**: Removed redundant scripts:
  - `sluttools/example_usage.py` → moved to `examples/`
  - `sluttools/match_visualizer.py` → functionality integrated into `sluttools/matching.py`
  - `sluttools/transparent_matching.py` → replaced by `sluttools/matching.py`
  - `sluttools/playlist.py` → unused mock database interface
  - `sluttools/package_manager_setup.sh` → trivial wrapper around `poetry install`
  - `scripts/main.py` → equivalent to `python -m sluttools`
  - `sluttools/matcher.py` → scoring logic merged into `matching.py`
  - `sluttools/matcher_fast.py` → duplicate functionality, use `slut match auto/review` instead
  - `sluttools/wizard.py` → duplicate functionality, use `slut config edit` and `slut match review` instead
  - `sluttools/metadata.py` → merged into `database.py`
  - `qobuz_auth.py` → standalone Qobuz auth helper (not part of core functionality)
  - `tidal2qobuz.py` → standalone Tidal-to-Qobuz mapper (not part of core functionality)
  - `scripts/` directory → now empty, removed
- **Migration Guide**: Added `examples/README.md` with migration path from deprecated APIs to current CLI commands.
- **Tests**: Updated `test_matcher.py` and `test_database.py` to import directly from `sluttools.*` instead of `music_automation.core.*`.
- **Tests**: Fixed multiprocessing pickle issues in tests by using ThreadPoolExecutor for test execution.
- **Refactor**: Consolidated match scoring algorithm into `matching.py` - removed module boundary overhead and deprecation warnings.
- Docs: Updated README with `slut-match` usage and new flags; updated docs/PROJECT_STRUCTURE.md to reflect removed archives; added docs/REFACTOR_PROPOSAL.md.
- Matcher UX: Improved `slut-match` output views (compact/unmatched/full), truncation, plain-text fallback with `--no-color`, and relative path display.
- Bugfix: Fixed PosixPath.format() AttributeError in M3U export by converting path to string before formatting.

## 2.1.0 - 2025-08-09
- Branding: Keep package name `sluttools`, CLI command `slut`, tagline “Get. Match. Tag. Out.”
- CLI: Structured subcommands (get/match/out/list/config); retained animated header with Arabic line; `--plain`/`SLUT_PLAIN` to disable animation.
- Config: Unified schema and precedence (env > file > defaults). Added SLUT_* env vars. First-run wizard prompts for LIBRARY_ROOTS.
- Docs: README updates (pipx quickstart, commands), added USAGE-CONFIG.md, docs/PROJECT_STRUCTURE.md.
- Build: Pinned Click/Rich/Typer to resolve `--help` issue. Bumped version to 2.1.0.
- Tests: Legacy shims preserved; all tests passing.
