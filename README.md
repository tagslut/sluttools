# sluttools

`sluttools` is a command-line utility for managing and matching local music libraries against playlists. It features an interactive matching process, fuzzy search, and automatic generation of M3U and SongShift-compatible JSON files.

## Features

- **Interactive First-Run Setup**: Automatically prompts you to configure your music library on the first run. No manual config file editing required to get started.
- **Persistent User Configuration**: Saves your settings in a dedicated user configuration file (`~/.config/sluttools/config.json`).
- **Music Library Database**: Scans your music directories and creates a searchable SQLite database of your tracks.
- **Interactive Track Matching**:
  - **Transparent Auto-Matching**: Automatically matches tracks with a high confidence score while showing you the scoring process, match criteria, and exact reason for match selection.
  - **Match Visualization**: See detailed match scores and comparison metrics between your tracks and potential matches in the library.
  - **Uncertainty Review**: Guides you through an interactive review for tracks with ambiguous matches.
  - **Manual Override**: Provides options to manually search for or enter paths for unmatched tracks.
- **Flexible Input**: Accepts playlist files (JSON, M3U/M3U8, or TXT) as inputs for matching and export.
- **Export Formats**: Generates both M3U playlists and SongShift JSON files for easy importing.

## Requirements

- Python 3.11+
- [pipx](https://pipx.pypa.io/stable/) recommended for CLI install, or Poetry for development.

## Installation & Setup

Quickstart with pipx (recommended):

```bash
pipx install sluttools
slut --help
```

Development install with Poetry:

```bash
git clone https://github.com/georgeskhawam/sluttools.git
cd sluttools
poetry install
```

## First Run & Configuration

The first time you run any `sluttools` command, it will automatically launch a setup wizard to configure your music library.

```bash
poetry run slut get library
```

- You will be prompted to enter the absolute path(s) to your music library folders.
- Your settings will be saved to `~/.config/sluttools/config.json`.
- The tool will use these saved settings for all future runs, so you only need to do this once.

## Workflow

A typical workflow involves refreshing the library and matching a playlist.

1. **Refresh Your Library**: Scan your music collection to create or update the local database. On the first run this launches the setup wizard so you can pick your library paths.

   ```bash
   poetry run slut get library
   ```
2. **Match a Playlist**: Once the database is up-to-date, you can match a playlist.

   ```bash
   poetry run slut match auto "path/to/your/playlist.txt"
   poetry run slut out m3u "path/to/your/playlist.txt"
   ```

   The tool will guide you through the interactive matching process and write outputs to the configured locations (see the Out section and USAGE-CONFIG.md).

## Project Layout

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for a full overview. In short:

- Core app code is in the `sluttools/` package.
- Generated files (e.g., playlists, local databases) are ignored by Git.

### Repository cleanup and deprecations

We have simplified the repository to reduce duplication and archived code. See docs/REFACTOR_PROPOSAL.md for the background. In brief:
- `slut match` provides both non-interactive (`auto`) and interactive (`review`) matching modes.
- `sluttools/matching.py` contains the core matching logic with integrated scoring algorithm.
- Standalone utilities (qobuz_auth.py, tidal2qobuz.py) and archived prototypes have been removed. Use the packaged CLI entry points instead.

## Command Reference

### `get library`

Scans the directories listed in your configuration and updates the track database.

## Command Reference

### `slut-match` (fast non-interactive matcher)

Match a playlist file or a directory of audio files against your local FLAC library using a cached SQLite index.

- Basic usage:
  - poetry run slut-match match "/path/playlist.json"
  - poetry run slut-match match "/path/playlist.m3u"
  - poetry run slut-match match "/path/to/dir/of/audio"

- Common options:
  - --refresh [auto|yes|no]  Refresh the index (auto = only if stale; default)
  - --library DIR            Override FLAC library root (defaults to SLUTTOOLS_FLAC_DIR or /Volumes/sad/MUSIC)
  - --db FILE                Override SQLite DB path (defaults to SLUTTOOLS_FLAC_DB or ~/flibrary.db)
  - --threshold INT          Override fuzzy accept threshold (else uses env AUTO_MATCH_THRESHOLD)

- Views and output formatting:
  - --view [compact|unmatched|full]
    - compact: one-line table per input (default)
    - unmatched: show only unmatched entries (prints “No unmatched tracks.” if none)
    - full: verbose per-entry line including method, score, and key; can show top-K
  - --topk INT              With --view full, show top K candidate scores (0 = off, default 5)
  - --truncate INT          Max column width (default 80; 0 = no truncation)
  - --path-col [basename|relative|full]  How to display matched path (default basename)
  - --relative-root DIR     Base when using --path-col=relative
  - --no-color              Disable rich colors (falls back to plain text)
  - --print-paths           Print only matched paths to stdout (useful for piping)

Examples:
- poetry run slut-match match "/path/playlist.json" --refresh no --no-color --view compact
- poetry run slut-match match "/path/playlist.json" --view unmatched --path-col relative --relative-root /Volumes/sad/MUSIC
- poetry run slut-match match "/path/playlist.json" --view full --topk 5 --truncate 100

### `get library`

Scans the directories listed in your configuration and updates the track database.

**Usage:** `poetry run slut get library`

### `match`

Match tracks from a given input against your music library.

- Auto (non-interactive): `poetry run slut match auto <PLAYLIST_INPUT>`
- Review (interactive): `poetry run slut match review <PLAYLIST_INPUT> [--plain]`

What is <PLAYLIST_INPUT>?

- A file path to one of the following formats:
  - JSON: SongShift export or a simple JSON with tracks.
    - Supported shapes:
      - SongShift list with an object containing a "tracks" array.
      - { "tracks": [ {"artist": "...", "track" or "title": "...", "album": "..."}, ... ] }
      - [ "Artist Title", "Artist Album Title", ... ]
  - M3U/M3U8: Lines of text (paths or titles). Lines starting with # are ignored.
  - TXT: Plain text, one entry per line.
- Tips:
  - Quote paths that contain spaces or special characters.
  - iCloud paths like /Users/you/Library/Mobile Documents/... work fine.

Examples:

- poetry run slut match auto "/path/playlist.m3u8"
- poetry run slut match auto "/path/playlist.txt"
- poetry run slut match auto "/path/playlist.json"

### `out`

Export matched/unmatched results from a playlist input.

What is <PLAYLIST_INPUT>?

- A file path to one of: JSON (SongShift or simple), M3U/M3U8, or TXT. See the match section above for shapes.

What each subcommand writes:

- m3u: an .m3u playlist containing only successfully matched local FLAC file paths.
- json: a JSON mapping of input tracks to matched paths (or null) including scoring details.
- songshift: a SongShift-compatible JSON playlist containing only the unmatched tracks, so you can continue on a streaming service.

Output location rules:

- If you pass --output PATH, the file is written exactly there.
- If you omit --output:
  - m3u: uses config MATCH_OUTPUT_PATH_M3U, which may include {playlist_name} (derived from the input filename).
  - json: uses config MATCH_OUTPUT_PATH_JSON, which may include {playlist_name}.
  - songshift: defaults to "{playlist_name}_songshift.json" in the current working directory.

Examples:

- poetry run slut out m3u "/path/playlist.txt"
- poetry run slut out json "/path/playlist.json" --output "/tmp/matches.json"
- poetry run slut out songshift "/path/playlist.m3u8"

### `config`

- Edit: `poetry run slut config edit`
- Show: `poetry run slut config show`

### `list`

Inspect library contents and cached metadata:

- Albums: `poetry run slut list albums`
- Artists: `poetry run slut list artists`
- Tracks: `poetry run slut list tracks --limit 20`

## Advanced Configuration

Your personalized settings are stored in `~/.config/sluttools/config.json`. The effective configuration is computed with precedence: environment variables > user config file > built-in defaults.

Environment variable overrides (examples):

- SLUT_LIBRARY_ROOTS="/Volumes/MUSIC1,/Volumes/MUSIC2"
- SLUT_DB_PATH="/path/to/flibrary.db"
- SLUT_MATCH_OUTPUT_PATH_M3U="/playlists/{playlist_name}.m3u"
- SLUT_MATCH_OUTPUT_PATH_JSON="/json/{playlist_name}.json"
- SLUT_THRESHOLD_AUTO_MATCH=90
- SLUT_THRESHOLD_REVIEW_MIN=75

See USAGE-CONFIG.md for the full schema and examples.

## Interactive Wizard

The CLI includes interactive prompts built with Rich that provide a guided experience for both initial configuration and playlist matching.

What it does:
- Configuration wizard: step-by-step setup of library paths, DB path, output locations, and thresholds. Saves to ~/.config/sluttools/config.json.
- Matching wizard: prompts for interactive review of matches, offers manual search/override, and exports M3U and JSON using your configured templates (MATCH_OUTPUT_PATH_M3U and MATCH_OUTPUT_PATH_JSON, which may include {playlist_name}).

How to run it:
- Configuration: `poetry run slut config edit`
- Interactive matching: `poetry run slut match review <PLAYLIST_INPUT>`

Notes:
- Press Ctrl+C at any time to abort the wizard.
- The wizard uses your existing configuration (see USAGE-CONFIG.md) and respects thresholds THRESHOLD_AUTO_MATCH and THRESHOLD_REVIEW_MIN.

## Development

Set up a local development environment with Poetry:

```bash
poetry install
poetry shell
```

Useful commands:

- Run the test suite: `poetry run pytest`
- Check types and lint: `poetry run mypy`, `poetry run flake8`, and `poetry run bandit -r sluttools`
- Format code: `poetry run black .` and `poetry run isort .`

The repository includes a [tasks checklist](docs/tasks.md) that outlines ongoing refactors and cleanup plans. See [docs/REFACTOR_PROPOSAL.md](docs/REFACTOR_PROPOSAL.md) for additional context on historical changes.
