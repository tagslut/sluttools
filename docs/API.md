# API Documentation

## Music Automation Toolkit API

### Core Modules

#### `music_automation.playlist_matcher`

Main playlist matching functionality.

**Functions:**
- `main()` - Main entry point for playlist matching
- `match_entry(entry, flac_lookup, ...)` - Match a single playlist entry
- `parse_playlist_file(file_path)` - Parse various playlist formats
- `normalize_string(s)` - Normalize strings for matching

**Classes:**
- `PlaylistUI` - Animated user interface

#### `music_automation.flac_database`

FLAC database management and audio processing.

**Functions:**
- `main()` - Main entry point for database operations
- `refresh_library(library_dir)` - Refresh FLAC database
- `open_db()` - Open and initialize database connection

#### `music_automation.playlist_copier`

File copying functionality for playlists.

**Functions:**
- `main()` - Main entry point for file copying
- `copy_files_from_playlist(...)` - Copy files based on playlist

#### `music_automation.audio_processor`

Audio processing and resampling functionality.

**Functions:**
- `main()` - Main entry point for audio processing
- `resample_flac(...)` - Resample FLAC files

### Usage Examples

```python
import asyncio
from music_automation import match_playlist

# Match a playlist
asyncio.run(match_playlist())
```

```python
from music_automation.flac_database import refresh_library

# Refresh FLAC database
refresh_library("/path/to/music/library")
```

### Configuration

The toolkit uses the following configuration variables (can be set in environment or modified in source):

- `FLAC_LIBRARY_DIR` - Path to FLAC music library
- `AUTO_MATCH_THRESHOLD` - Automatic matching threshold (default: 65)
- `MAX_WORKERS` - Maximum parallel workers (default: 8)

### Error Handling

All modules include comprehensive error handling for:
- File not found errors
- Permission errors
- Metadata extraction failures
- Non-interactive environment detection
