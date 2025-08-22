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

1. **Refresh Your Library**: First, scan your music collection to create or update the local database. If it's your first time, this will trigger the setup wizard.

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

See docs/PROJECT_STRUCTURE.md for a full overview. In short:

- Core app code is in the `sluttools/` package.
- Helper scripts live in `scripts/`.
- Legacy/prototype materials are under `scripts/archive/`.
- Generated files (e.g., playlists, local databases) are ignored by Git.

### Repository cleanup and deprecations

We are simplifying the repository to reduce duplication and archived code. Please see docs/REFACTOR_PROPOSAL.md for the full plan. In brief:
- `slut-match` (sluttools/matcher_fast.py) is the recommended non-interactive matcher CLI.
- `sluttools/matching.py` remains for interactive/advanced flows.
- The `scripts/archive/` directory and a few wrappers/backups are slated for removal in an upcoming release. Avoid relying on archived scripts.

## Command Reference

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

## Interactive Wizard (wizard.py)

The project includes an optional full-screen interactive wizard, built with Rich, that provides a guided experience for both initial configuration and playlist matching.

What it does:
- Configuration wizard: step-by-step setup of library paths, DB path, output locations, and thresholds. Saves to ~/.config/sluttools/config.json.
- Matching wizard: prompts for a playlist file, optionally refreshes the FLAC library index, performs matching with interactive review, and offers to export M3U and JSON using your configured templates (MATCH_OUTPUT_PATH_M3U and MATCH_OUTPUT_PATH_JSON, which may include {playlist_name}).

How to run it:
- Via CLI (preferred):
  - Configuration: poetry run slut config edit
  - Interactive matching: poetry run slut match review <PLAYLIST_INPUT>
- Direct module (useful for development/testing):
  - poetry run python -m sluttools.wizard --mode config
  - poetry run python -m sluttools.wizard --mode match

Notes:
- Press Ctrl+C at any time to abort while using the wizard.
- The wizard uses your existing configuration (see USAGE-CONFIG.md) and respects thresholds THRESHOLD_AUTO_MATCH and THRESHOLD_REVIEW_MIN.

## Standalone Utilities

### `tidal2qobuz.py`

This project also includes a powerful standalone script for mapping Tidal URLs to their Qobuz equivalents.

**Features:**

- Converts Tidal track, album, or playlist URLs.
- Uses intelligent parsing and fuzzy matching to find the best Qobuz match.
- Securely stores credentials in your system's Keychain for authenticated API requests.

**Setup:**

This script requires the `keyring` library and your Qobuz credentials.

1. **Install the dependency:**
   ```bash
   pip install keyring
   ```
2. **Store your credentials:**
   Run the following commands in your terminal. You will be prompted to enter each credential. This only needs to be done once.
   ```bash
   # Store your Qobuz App ID
   keyring set sluttools.tidal2qobuz qobuz_app_id

   # Store your Qobuz User Auth Token
   keyring set sluttools.tidal2qobuz qobuz_user_auth_token
   ```

**Usage:**

```bash
python tidal2qobuz.py "https://tidal.com/track/..."
```
