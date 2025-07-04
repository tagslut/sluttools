# Music Tools - Unified CLI for Music Library Automation

A comprehensive command-line toolkit for managing music libraries, playlists, and audio files.

## Features

- **Playlist Matching**: Match tracks from various playlist formats to your FLAC library
- **FLAC Database**: Index and query your FLAC collection with SQLite
- **Playlist Copying**: Copy files from playlists to different locations with flexible options
- **FLAC Resampling**: Batch resample FLAC files with non-standard sample rates

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/musictools.git
cd musictools
```

2. Make sure you have all dependencies installed:
```bash
pip install -r requirements.txt
```

3. Make the main script executable:
```bash
chmod +x musictools.py
```

4. Optionally, create a symbolic link in a directory in your PATH:
```bash
mkdir -p ~/bin
ln -sf "$(pwd)/musictools.py" ~/bin/musictools
```

5. Add ~/bin to your PATH if it isn't already:
```bash
# Add to your .bashrc, .zshrc, or equivalent:
export PATH="$HOME/bin:$PATH"
```

## Usage

### General Help

```bash
musictools
```

### Playlist Matching

Match tracks from a playlist file (CSV, M3U, JSON) to your FLAC library:

```bash
musictools match playlist.csv
```

### Copy Playlist Files

Copy files from a playlist to a destination directory:

```bash
musictools copy playlist.m3u /path/to/destination
```

Options:
- `-f, --flat`: Copy files to a flat structure (no subdirectories)
- `-p, --preserve`: Preserve the full directory structure
- `-a, --artist-folders`: Organize by Artist/Album folders
- `-t, --threads N`: Number of parallel copy threads (default: 4)

### FLAC Database Management

Refresh the FLAC library index:

```bash
musictools db refresh --library /path/to/flacs
```

List entries in the database:

```bash
musictools db list --limit 10
musictools db list --where "artist LIKE '%Daft Punk%'"
```

Show details for a specific file:

```bash
musictools db show /path/to/file.flac
```

### FLAC Resampling

Batch resample FLAC files with non-standard sample rates:

```bash
musictools resample
musictools resample --dry-run
```

## Individual Tools

The unified CLI combines these individual scripts that can also be used independently:

- `g.py` - Playlist matching tool
- `flacdb.py` - FLAC database management
- `copy_playlist.py` - Playlist file copying
- `resample_flacs.py` - FLAC resampling utility

## Requirements

- Python 3.7+
- Libraries: rich, fuzzywuzzy, mutagen, tqdm, python-Levenshtein

## License

MIT
