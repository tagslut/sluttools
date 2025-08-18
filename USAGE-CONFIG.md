# Configuration and Environment Overrides

This document describes the configuration schema used by sluttools and how to override values with environment variables.

Effective configuration precedence:
- Environment variables (SLUT_*)
- User config file: ~/.config/sluttools/config.json
- Built-in defaults

## Schema (config.json)

- LIBRARY_ROOTS: list of strings
  - Absolute paths to your music library roots.
  - Example: ["/Volumes/MUSIC", "/Volumes/ARCHIVE/MUSIC"]
- DB_PATH: string
  - Path to the SQLite database file.
  - Example: "/Users/you/.config/sluttools/flibrary.db"
- MATCH_OUTPUT_PATH_M3U: string
  - Output path or template for M3U playlists. Can include {playlist_name}.
  - Example: "/Users/you/Music/Playlists/{playlist_name}.m3u"
- MATCH_OUTPUT_PATH_JSON: string
  - Output path or template for JSON match data. Can include {playlist_name}.
  - Example: "/Users/you/Music/Playlists/json/{playlist_name}.json"
- SONGSHIFT_DEFAULT_FILENAME: implicit
  - If not overridden by --output, songshift exports default to "{playlist_name}_songshift.json" in the current working directory.
- THRESHOLD_AUTO_MATCH: integer (0-100)
  - Fuzzy score for auto-accepting matches.
  - Default: 90
- THRESHOLD_REVIEW_MIN: integer (0-100)
  - Minimum score to send a candidate to review instead of auto-unmatched.
  - Default: 75

## Environment variables

- SLUT_LIBRARY_ROOTS
  - Comma-separated list of library paths.
  - Example: `SLUT_LIBRARY_ROOTS="/Vol/MUSIC1,/Vol/MUSIC2"`
- SLUT_DB_PATH
  - Example: `SLUT_DB_PATH="/path/to/flibrary.db"`
- SLUT_MATCH_OUTPUT_PATH_M3U
  - Example: `SLUT_MATCH_OUTPUT_PATH_M3U="/playlists/{playlist_name}.m3u"`
- SLUT_MATCH_OUTPUT_PATH_JSON
  - Example: `SLUT_MATCH_OUTPUT_PATH_JSON="/json/{playlist_name}.json"`
- SLUT_THRESHOLD_AUTO_MATCH
  - Example: `SLUT_THRESHOLD_AUTO_MATCH=88`
- SLUT_THRESHOLD_REVIEW_MIN
  - Example: `SLUT_THRESHOLD_REVIEW_MIN=70`

## Notes

- On first run, the tool prompts for LIBRARY_ROOTS and creates `~/.config/sluttools/config.json`.
- Paths in the effective configuration are expanded to absolute paths where applicable.
- You can disable the animated UI with either `--plain` flag on interactive commands or by setting `SLUT_PLAIN=1`.
