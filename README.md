# 🎵 Music Automation Toolkit

## Overview

A comprehensive toolkit for managing and cataloging large music libraries with focus on high-quality FLAC files. Features intelligent playlist matching, metadata extraction, batch resampling, and file copying — all optimized for performance with parallel processing and smart caching.

## ✨ Key Features

### 🎯 Intelligent Playlist Matching

- **Multi-format Support**: JSON, CSV, M3U, and XLSX playlists
- **Smart M3U Parsing**: Automatically extracts metadata from file paths in M3U playlists
- **Fuzzy Matching**: Advanced string matching with normalization and multiple ratio algorithms
- **Performance Modes**: 5 optimization levels from Basic to Quick Match for small playlists
- **Exact Matching**: Direct file path matching for M3U playlists containing existing files
- **Parallel Processing**: Multi-threaded matching for large libraries (up to 8 workers)

### 🔍 Advanced Matching Engine

- **Smart Indexing**: Artist and title indexes for faster candidate selection
- **Normalization Caching**: Disk-based caching of normalized filenames (1-hour TTL)
- **Quick Match Mode**: Optimized for small playlists (≤50 tracks) with targeted search
- **Search String Building**: Combines artist, album, title, track, and ISRC fields
- **Threshold-based Automation**: Configurable auto-match threshold (default: 65%)

### 📊 Export Options

- **Multiple Formats**: M3U playlists, CSV files, or both
- **SongShift Integration**: JSON export for unmatched tracks
- **Detailed Logging**: Comprehensive match details and unmatched track reports
- **Metadata Preservation**: Artist, album, title, and file path information

### 🎵 FLAC Library Management

- **Database Indexing**: SQLite-based FLAC metadata catalog
- **Metadata Extraction**: Tag-level (Mutagen) and format-level (ffprobe) parsing
- **Parallel Scanning**: Multi-threaded library scanning with progress tracking
- **Batch Operations**: Refresh, query, and manage large libraries efficiently

### 🔄 Audio Processing

- **Batch Resampling**: SoX-based resampling with metadata preservation
- **Quality Control**: Identifies non-standard sample rates and formats
- **File Copying**: Intelligent playlist-based file copying with multiple organization modes

### 🎨 User Experience

- **Animated Interface**: Beautiful ASCII art with color-coded progress
- **Interactive Prompts**: Manual matching with candidate scoring
- **Non-interactive Support**: Command-line arguments for automation
- **Rich Feedback**: Progress bars, match details, and error handling

## 🛠 Requirements

- Python 3.11+
- sox and metaflac installed on your system (`brew install sox flac` on macOS)
- Dependencies listed in requirements.txt:

```txt
## 📦 Installation

### From Source

```bash
git clone https://github.com/tagslut/sluttools.git
cd sluttools

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e .[dev]
```

### From PyPI (when available)

```bash
pip install music-automation-toolkit
```

### Requirements

- Python 3.11 or higher
- FFmpeg (for audio processing)
- SoX (for audio resampling)

**Core Dependencies:**
```
mutagen>=1.47.0
pandas>=2.0.0
rich>=13.0.0
fuzzywuzzy>=0.18.0
python-levenshtein>=0.21.0
openpyxl>=3.1.0
```

## 🚀 Usage

### Activate Environment

```bash
# macOS/Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### Quick Start

**Using the CLI wrapper script:**
```bash
# Make sure you're in the project directory
cd /path/to/sluttools

# Match a playlist
./musictools match

# Or match a specific playlist
./musictools match /path/to/playlist.m3u

# Manage FLAC database
./musictools db refresh ~/Music/FLACs
./musictools db list --limit 10

# Copy playlist files
./musictools copy /path/to/playlist.m3u /destination/folder
```

**Using Python module directly:**
```bash
# Make sure you're in the project directory
cd /path/to/sluttools

# Set Python path and run
PYTHONPATH=./src python -m music_automation.cli.main --help
```

**Development Setup:**
```bash
# Install in development mode
pip install -e .

# Run tests
PYTHONPATH=./src python -m pytest tests/

# Format code
black src/ tests/

# Type check
mypy src/
```

**Command Line Mode:**
```bash
python g.py /path/to/playlist.m3u
python g.py /path/to/playlist.json
python g.py /path/to/music/folder
```

**Unified CLI:**
```bash
python musictools.py match /path/to/playlist.m3u
python musictools.py copy playlist.m3u /destination/folder
python musictools.py db refresh /path/to/music/library
```

### Performance Optimization Modes

1. **Basic** - Just normalize filenames
2. **Advanced** - Use search indexes for faster matching (recommended)
3. **Turbo** - Parallel processing with multiple threads (fastest)
4. **Safe Turbo** - Parallel processing without metadata indexing
5. **Quick Match** - Optimized for small playlists (≤50 tracks, auto-selected)

### Supported Playlist Formats

- **M3U** - Supports both track names and file paths
- **JSON** - Streaming service exports (SongShift format)
- **CSV** - Semicolon or comma-delimited with title, artist, album, ISRC columns
- **XLSX** - Excel spreadsheets with metadata columns

## 🧪 FLAC Library Management

### Refresh Library Index

Automatically scans and indexes all FLAC files located in FLAC_LIBRARY_DIR (defined in g2.py).

```bash
python flacdb.py refresh
```

## 🎧 Playlist Operations

### Generate M3U Playlist

Matches playlist text files to FLACs via fuzzy matching and builds .m3u playlists.

```bash
python g2.py
```

### Export SongShift-Compatible JSON

Outputs unmatched tracks to a JSON file ready for import into services like SongShift.

## 🔁 Batch Resampling with SoX

### Script: flacdb.py

This standalone tool resamples FLAC files that use non-standard sample rates (e.g. 88.2 kHz, 96 kHz):

```bash
python flacdb.py resample
```

It:
- Scans your .flac_index.db for rare sample rates
- Prompts you to select one
- Resamples all matching files to 44.1 or 48 kHz
- Preserves metadata and album art via metaflac
- Writes output into a safe resampled/ folder
- Runs multiple conversions in parallel

## 🚀 Recent Improvements

### Version 2.0 Updates

- **Fixed M3U Parsing**: Now correctly handles M3U files with file paths, extracting metadata from actual audio files
- **Exact Matching**: M3U playlists with existing file paths now get 100% accurate matches
- **Performance Boost**: Quick Match mode for small playlists (≤50 tracks) completes in under 1 second
- **Enhanced Caching**: Disk-based normalization cache reduces processing time by 80%
- **Better Error Handling**: Graceful handling of non-interactive environments and corrupted files
- **Command Line Support**: Direct path arguments for automation and scripting
- **Improved Metadata Extraction**: Better handling of edge cases in filename parsing

### Performance Benchmarks

- **25,000+ FLAC Library**: Full scan and indexing in ~2 minutes
- **Small Playlists (≤50 tracks)**: Matching in 0.1-0.4 seconds
- **Large Playlists (100+ tracks)**: Matching in 1-3 seconds with parallel processing
- **Cache Hit Rate**: 95%+ for repeated operations

## 🗃 SQLite Database

### View Schema

```sql
.schema flacs
```

### Query Entries

```sql
SELECT * FROM flacs;
```

### Add Missing Columns

Automatically handled by open_db() in flacdb.py.

### Create Index

```sql
CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm);
```

## 🧯 Troubleshooting

### Common Issues

- **Missing modules**: Run `pip install -r requirements.txt`
- **Missing SoX or metaflac**: Install via system package manager (e.g. brew, apt)
- **Invalid paths**: Check FLAC_LIBRARY_DIR is correct in g.py (line 38)
- **Permission errors**: Verify file access and script execution rights
- **EOFError in non-interactive mode**: Use command line arguments: `python g.py /path/to/playlist`
- **No FLAC files found**: Ensure external drives are mounted and paths are accessible
- **Slow matching**: Use Quick Match mode for playlists ≤50 tracks (auto-selected)

### Configuration

Update the FLAC_LIBRARY_DIR variable in `g.py`:

```python
FLAC_LIBRARY_DIR = "/path/to/your/music/library"
```

### Debug Mode

Enable verbose output:

```bash
DEBUG=1 python g.py /path/to/playlist
```

## 📄 License

MIT License

## 🤝 Contributing

Pull requests are welcome. Please open an issue first to discuss changes or feature proposals.
