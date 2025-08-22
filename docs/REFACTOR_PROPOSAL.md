Refactor proposal: simplify scripts and consolidate entry points

Date: 2025-08-23
Owner: repo maintainers (authored by Junie, autonomous programmer)

Context
- Overlapping matcher implementations and CLIs exist (sluttools/matcher_fast.py, sluttools/matching.py, sluttools/matcher.py, music_automation/core/matcher.py, scripts/archive/matcher.py).
- Multiple top-level scripts and wrappers (root main.py, scripts/main.py, root tidal2qobuz.py, scripts/tidal2qobuz.py, tidal2qobuz.py.bak, qobuz_auth.py).
- Historical/archived code under scripts/archive and a stale launcher (musictools) that references a non-existent music_automation CLI.
- Current Poetry console scripts point to sluttools.cli and sluttools.matcher_fast, which work and are covered by tests.

Goals
1) Reduce duplication and dead code.
2) Keep backwards compatibility for tests and common user entry points.
3) Clarify a single recommended CLI surface.
4) Prepare for future packaging (lean sdist/wheel).

Summary of recommendations

A. Keep (actively used/maintained)
- sluttools/matcher_fast.py — primary fast matcher; exposed as `slut-match` in pyproject.
- sluttools/cli.py — Typer-based CLI; exposed as `slut` and `fla`.
- sluttools/database.py, sluttools/metadata.py, sluttools/playlist.py, etc. (core libs).
- music_automation/core/{database.py, matcher.py} — thin shims used by tests; keep as compatibility layer.
- tests/ — unchanged.

B. Deprecate (soft, warn in docs; optional DeprecationWarning later)
- sluttools/matcher.py — low-level helpers (calculate_match_score, formatting). Recommendation: leave as a small helper module, mark deprecated in docs. In a subsequent release, add a DeprecationWarning pointing users to sluttools/matching.py or matcher_fast.
- sluttools/matching.py — retains richer/interactive logic; keep but document that `slut-match` (matcher_fast) is the default non-interactive engine. Consider merging `calculate_match_score` here and turning sluttools/matcher.py into a shim.
- qobuz_auth.py — keep functionally but plan to move under package namespace (sluttools/qobuz_auth.py) and add a Poetry entry point `qobuz-auth = "sluttools.qobuz_auth:main"` in a later release.

C. Remove (dead/duplicate/archived) — Phase 2 after a short deprecation window
- scripts/archive/ (entire directory): contains prototypes (gg.py, matcher.py, database.py, processor.py, copier.py) that are not imported by the package and have archived comments. Replace with a link in README to the commit history if needed.
- scripts/__init__.py: exposes archive modules that are not intended for import; remove alongside archive.
- scripts/tidal2qobuz.py: a wrapper that only invokes the legacy root script; redundant if we keep the root script.
- tidal2qobuz.py.bak: backup file; delete.
- main.py (root): empty file; delete.
- musictools: launcher referencing non-existent music_automation.cli.main; delete.

D. Optional consolidation (future minor release)
- Decide on the canonical location for the TIDAL→Qobuz tool. Two options:
  1) Keep root-level tidal2qobuz.py as the single source and add a Poetry script entry (e.g., `t2q = "tidal2qobuz:main"`). Remove scripts/tidal2qobuz.py wrapper.
  2) Move logic into `sluttools/tools/tidal2qobuz.py` and expose as `t2q = "sluttools.tools.tidal2qobuz:main"`. Remove root/script duplicates.
  Recommendation: 1) short-term; 2) longer-term.

Compatibility notes
- The tests import music_automation.core.matcher and database; those shims must remain.
- User-facing commands remain:
  - `slut` (Typer CLI), `fla` alias.
  - `slut-match` (fast matcher CLI).
- No behavior changes required for matcher_fast beyond minor UX improvements already merged.

Proposed deprecation/removal plan
- Version N (current): Publish this proposal; no file deletions. Optionally add DeprecationWarning in sluttools/matcher.py guarded by an env var (SLUTTOOLS_SHOW_DEPRECATIONS) to keep tests quiet by default.
- Version N+1: Remove scripts/archive, scripts/__init__.py, scripts/tidal2qobuz.py, tidal2qobuz.py.bak, main.py, musictools. Add a CHANGELOG entry and README migration notes.
- Version N+2: Move qobuz_auth into package namespace and add a console script.

Detailed file list and actions

1) scripts/archive/* — REMOVE
   - Rationale: Clearly marked as archived/prototypes; duplicative of packaged functionality; not used by tests nor package imports.

2) scripts/__init__.py — REMOVE
   - Rationale: Misleading exports of archive fragments.

3) scripts/tidal2qobuz.py — REMOVE
   - Rationale: Thin wrapper to root tidal2qobuz.py; keep single source of truth (root file) in short term.

4) tidal2qobuz.py.bak — REMOVE
   - Rationale: Backup; not executable; source control is the backup.

5) main.py (root) — REMOVE
   - Rationale: Empty file.

6) musictools — REMOVE
   - Rationale: Launcher points to missing music_automation.cli.main; dead file.

7) sluttools/matcher.py — DEPRECATE (keep)
   - Rationale: Helper-only; calculate_match_score used by matching.py; not required by matcher_fast nor tests. Plan to merge into matching.py later.

8) sluttools/matching.py — KEEP, mark as “interactive/advanced” in README. Consider extracting common scoring into shared helpers to reduce overlap with matcher_fast over time.

9) qobuz_auth.py — KEEP (future move under package + console script).

10) music_automation/core/* — KEEP
   - Rationale: Required by tests. Keep as thin shims.

Action items in this commit (non-breaking)
- Add this refactor proposal document.
- No deletions or moves to avoid breaking consumers without prior notice.
- Optionally, in a follow-up commit, add an opt-in DeprecationWarning in sluttools/matcher.py (guarded by env SLUTTOOLS_SHOW_DEPRECATIONS).

Appendix: Suggested pyproject additions (future)

[tool.poetry.scripts]
# Existing
fla = "sluttools.cli:main"
slut = "sluttools.cli:app"
slut-match = "sluttools.matcher_fast:main"
# Future additions
# t2q = "tidal2qobuz:main"          # if keeping root-level script
# qobuz-auth = "sluttools.qobuz_auth:main"  # after moving under package

