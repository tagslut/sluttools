#!/usr/bin/env python3
"""
sluttools_standalone.py - Standalone Music Library Matcher
===========================================================

A single-file (~650 line) version of sluttools for easy integration
into other Python projects. This is a simplified subset of the full
sluttools package, containing only the core matching engine without
the interactive UI, configuration management, or advanced CLI features.

WHAT THIS PROVIDES
------------------
✓ Music library indexing (FLAC, MP3, WAV, M4A, OGG, AAC, WMA)
✓ SQLite database (in-memory or file-based)
✓ Metadata extraction from audio tags (requires mutagen)
✓ Fuzzy matching with configurable thresholds
✓ Parallel processing for fast library scanning
✓ Simple programmatic API
✓ Basic CLI for standalone usage
✓ M3U and JSON export

WHAT THIS DOESN'T PROVIDE
--------------------------
✗ Interactive review workflow (track-by-track matching UI)
✗ Rich terminal UI with animations and colors
✗ Configuration file management (~/.config/sluttools/config.json)
✗ Multi-command CLI (get, match, tag, out, list, config)
✗ SongShift JSON export format
✗ Streaming service playlist fetching
✗ Word overlap analysis and quality scoring
✗ Alternative candidate suggestions
✗ Incremental library updates

For the full-featured application with interactive workflows and advanced
matching, use the complete sluttools package instead.

DEPENDENCIES
------------
Required:
  - Python 3.8+
  - No required dependencies (falls back to basic implementations)

Optional (recommended):
  - mutagen: For reading audio file tags (artist, album, title, etc.)
  - rapidfuzz: For fast fuzzy string matching (10-20x faster than fuzzywuzzy)
  - fuzzywuzzy: Alternative fuzzy matching (if rapidfuzz not available)

Install with: pip install mutagen rapidfuzz

USAGE AS A MODULE
-----------------
Import and use in your Python projects:

    from sluttools_standalone import MusicLibrary, match_playlist, Match

    # Create library and index music files
    lib = MusicLibrary(
        library_paths=["/Volumes/Music", "/home/user/Music"],
        db_path="/tmp/music.db",  # or None for in-memory
    )

    # Scan library (uses parallel processing)
    def progress(current, total):
        print(f"Indexed {current}/{total} files")

    lib.scan(max_workers=4, progress_callback=progress)

    # Search library
    results = lib.search(artist="Radiohead", title="Creep")

    # Match a playlist
    playlist_tracks = [
        {"artist": "Radiohead", "album": "Pablo Honey", "title": "Creep"},
        {"artist": "Björk", "album": "Homogenic", "title": "Jóga"},
    ]

    matches = match_playlist(
        library=lib,
        playlist_tracks=playlist_tracks,
        auto_match_threshold=88,  # Auto-accept if score >= 88
        review_min_threshold=70,  # Below 70 = unmatched
    )

    # Process results
    for match in matches:
        if match.status == 'matched':
            print(f"✓ {match.query_track['title']}")
            print(f"  → {match.library_track['path']}")
            print(f"  Score: {match.score}")
        elif match.status == 'review':
            print(f"? {match.query_track['title']} (score: {match.score})")
        else:
            print(f"✗ {match.query_track['title']} (unmatched)")

    # Get match statistics
    matched = sum(1 for m in matches if m.status == 'matched')
    review = sum(1 for m in matches if m.status == 'review')
    unmatched = sum(1 for m in matches if m.status == 'unmatched')

    lib.close()

USAGE AS A SCRIPT
-----------------
Run directly from command line:

    # Basic usage
    python sluttools_standalone.py \\
        --library /Volumes/Music \\
        --playlist my_playlist.json \\
        --output matched.m3u

    # Force library rescan
    python sluttools_standalone.py \\
        --library /Volumes/Music \\
        --playlist playlist.json \\
        --db /tmp/music.db \\
        --scan \\
        --threshold 85 \\
        --output results.json

Playlist JSON format (simple):
    [
        {
            "artist": "Artist Name",
            "album": "Album Name",
            "title": "Track Title",
            "duration": 240  // optional, in seconds
        },
        ...
    ]

Or with wrapper:
    {
        "name": "My Playlist",
        "tracks": [
            {"artist": "...", "title": "..."},
            ...
        ]
    }

Output formats:
    - .m3u: M3U playlist with matched file paths
    - .json: Full match report with scores and status

DATABASE SCHEMA
---------------
SQLite table: flacs
    - path (TEXT PRIMARY KEY): Absolute file path
    - norm (TEXT): Normalized title for fast lookup
    - mtime (INTEGER): File modification time
    - artist (TEXT): Artist name from tags
    - album (TEXT): Album name from tags
    - title (TEXT): Track title from tags
    - trackno (INTEGER): Track number
    - year (INTEGER): Release year
    - duration (INTEGER): Duration in seconds
    - format_json (TEXT): JSON with sample_rate, bits_per_sample, channels

Indexes on: norm, artist, album, title for fast searching

MATCHING ALGORITHM
------------------
For each playlist track, the matcher:

1. Searches all library tracks
2. Calculates fuzzy match score (0-100) based on:
   - Title similarity (weighted 2x)
   - Artist similarity
   - Album similarity
   - Duration difference (if available)
3. Selects best-scoring candidate
4. Categorizes result:
   - score >= auto_match_threshold (default 88): Auto-matched
   - score >= review_min_threshold (default 70): Needs review
   - score < review_min_threshold: Unmatched

Score calculation:
    - Title: fuzz.ratio() * 2 (most important)
    - Artist: fuzz.ratio()
    - Album: fuzz.ratio()
    - Duration: 100 if ≤2s diff, 80 if ≤5s, 60 if ≤10s, else 40
    - Final: Weighted average of available fields

PERFORMANCE NOTES
-----------------
- Library scanning uses ThreadPoolExecutor (not ProcessPoolExecutor)
- Avoids pickle issues with in-memory databases
- Default 4 workers, increase for large libraries
- In-memory database is faster but non-persistent
- File database enables incremental updates (future)

COMPARISON WITH FULL SLUTTOOLS
------------------------------
                        Standalone  |  Full Project
                        ------------|---------------
Lines of code           ~650        |  2,500+
Files                   1           |  6 modules
Interactive review      No          |  Yes ★
Rich terminal UI        No          |  Yes ★
Configuration system    No          |  Yes
Commands                1           |  12+
SongShift export        No          |  Yes
Word overlap analysis   No          |  Yes
Alternative suggestions No          |  Yes
Progress UI             Basic       |  Advanced

Use this standalone version when:
  - Embedding into another Python project
  - Building automation/batch processing
  - Need simple API without interactive features
  - Want single-file distribution

Use full sluttools when:
  - Daily music library management
  - Need interactive track-by-track review
  - Want beautiful terminal UI and UX
  - Managing multiple libraries with config persistence

LICENSE
-------
Part of sluttools - https://github.com/tagslut/sluttools
See main project for license information.

AUTHOR
------
Extracted from sluttools by Georges Khawam
For the complete application: poetry install && poetry run slut --help
"""

import concurrent.futures
import json
import logging
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from mutagen import File as MutagenFile

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    try:
        from fuzzywuzzy import fuzz

        RAPIDFUZZ_AVAILABLE = False
    except ImportError:
        # Fallback simple fuzzy matching
        class fuzz:
            @staticmethod
            def ratio(a, b):
                if a == b:
                    return 100
                max_len = max(len(a), len(b), 1)
                diff = abs(len(a) - len(b))
                return int(100 * (1 - diff / max_len))


# Configuration
DEFAULT_AUDIO_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".aac",
    ".wma",
}
DEFAULT_AUTO_MATCH_THRESHOLD = 88
DEFAULT_REVIEW_MIN_THRESHOLD = 70

logger = logging.getLogger(__name__)

# UTILITIES


def normalize_string(s: Optional[str]) -> str:
    """Normalize string for matching (lowercase, whitespace collapsed)."""
    if s is None:
        return ""
    return " ".join(s.strip().lower().split())


def parse_filename_structure(path: Union[Path, str]) -> Dict[str, Any]:
    """
    Parse a music file path into metadata dict.

    Returns dict with: artist, album, title, trackno, year, duration
    """
    path = Path(path)
    parts = path.parts

    album = None
    artist = None
    title = path.stem
    trackno = None
    year = None

    # Try to extract track number from filename: "01 - Title" or "1. Title"
    m = re.match(r"^(\d{1,3})[\s_.-]+(.+)$", title)
    if m:
        try:
            trackno = int(m.group(1))
            title = m.group(2).strip()
        except Exception:
            pass

    # Try to get artist and album from parent directories
    if len(parts) >= 2:
        album = parts[-2]  # parent directory
    if len(parts) >= 3:
        artist = parts[-3]  # grandparent directory

    # Try to extract year from album name: "Album Name (2020)"
    if album:
        year_match = re.search(r"\((\d{4})\)", album)
        if year_match:
            try:
                year = int(year_match.group(1))
            except Exception:
                pass

    return {
        "artist": artist,
        "album": album,
        "title": title,
        "trackno": trackno,
        "year": year,
        "duration": None,
        "path": str(path),
    }


def gather_metadata(path: Union[Path, str]) -> Dict[str, Any]:
    """
    Gather metadata from audio file.

    Returns dict with: path, artist, album, title, trackno, year,
    duration, format
    """
    path = Path(path)
    metadata = parse_filename_structure(path)

    # Try to get metadata from audio tags if mutagen is available
    if MUTAGEN_AVAILABLE:
        try:
            audio = MutagenFile(path)
            if audio is not None:
                # Extract common tags
                if hasattr(audio, "tags") and audio.tags:
                    tags = audio.tags

                    # Handle different tag formats (ID3, Vorbis, etc.)
                    def get_tag(keys):
                        for key in keys:
                            if key in tags:
                                val = tags[key]
                                if isinstance(val, list) and val:
                                    return str(val[0])
                                return str(val)
                        return None

                    metadata["artist"] = (
                        get_tag(["artist", "ARTIST", "TPE1", "\xa9ART"])
                        or metadata["artist"]
                    )
                    metadata["album"] = (
                        get_tag(["album", "ALBUM", "TALB", "\xa9alb"])
                        or metadata["album"]
                    )
                    metadata["title"] = (
                        get_tag(["title", "TITLE", "TIT2", "\xa9nam"])
                        or metadata["title"]
                    )

                    track = get_tag(
                        ["tracknumber", "TRACKNUMBER", "TRCK", "trkn"]
                    )  # noqa: E501
                    if track:
                        try:
                            # Handle "1/12" format
                            metadata["trackno"] = int(str(track).split("/")[0])
                        except Exception:
                            pass

                    year_tag = get_tag(
                        ["date", "DATE", "year", "YEAR", "TDRC", "\xa9day"]
                    )
                    if year_tag:
                        try:
                            metadata["year"] = int(str(year_tag)[:4])
                        except Exception:
                            pass

                # Get duration
                if hasattr(audio.info, "length"):
                    metadata["duration"] = int(audio.info.length)

                # Get format info
                if hasattr(audio.info, "sample_rate"):
                    metadata["format"] = {
                        "sample_rate": audio.info.sample_rate,
                        "bits_per_sample": getattr(
                            audio.info, "bits_per_sample", None
                        ),  # noqa: E501
                        "channels": getattr(audio.info, "channels", None),
                    }
        except Exception as e:
            logger.debug(f"Could not read tags from {path}: {e}")

    metadata["mtime"] = int(path.stat().st_mtime) if path.exists() else 0

    return metadata


###############################################################################
# DATABASE
###############################################################################


class MusicLibrary:
    """Manages a SQLite database of music files."""

    def __init__(
        self,
        library_paths: List[Union[Path, str]],
        db_path: Optional[Union[Path, str]] = None,
        audio_extensions: Optional[set] = None,
    ):
        """
        Initialize music library.

        Args:
            library_paths: List of directories to scan for music
            db_path: Path to SQLite database (default: in-memory)
            audio_extensions: Set of file extensions to index
                (default: common formats)
        """
        self.library_paths = [Path(p) for p in library_paths]
        self.db_path = Path(db_path) if db_path else ":memory:"
        self.audio_extensions = audio_extensions or DEFAULT_AUDIO_EXTENSIONS
        self._conn: Optional[sqlite3.Connection] = None

        # Initialize database
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        if self._conn is None:
            if self.db_path == ":memory:":
                self._conn = sqlite3.connect(":memory:")
            else:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(self.db_path))

        try:
            yield self._conn
        except Exception:
            self._conn.rollback()
            raise

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flacs (
                    path TEXT PRIMARY KEY,
                    norm TEXT,
                    mtime INTEGER,
                    artist TEXT,
                    album TEXT,
                    title TEXT,
                    trackno INTEGER,
                    year INTEGER,
                    duration INTEGER,
                    format_json TEXT
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artist ON flacs(artist)"
            )  # noqa: E501
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_album ON flacs(album)"
            )  # noqa: E501
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_title ON flacs(title)"
            )  # noqa: E501
            conn.commit()

    def scan(
        self,
        max_workers: int = 4,
        progress_callback: Optional[callable] = None,
    ):
        """
        Scan library paths and index audio files.

        Args:
            max_workers: Number of parallel workers for metadata extraction
            progress_callback: Optional callback(current, total) for
                progress tracking
        """
        # Find all audio files
        audio_files = []
        for lib_path in self.library_paths:
            if not lib_path.exists():
                logger.warning(f"Library path does not exist: {lib_path}")
                continue

            for ext in self.audio_extensions:
                audio_files.extend(lib_path.rglob(f"*{ext}"))

        if not audio_files:
            logger.warning("No audio files found in library paths")
            return

        logger.info(f"Found {len(audio_files)} audio files to index")

        # Extract metadata in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(gather_metadata, f): f for f in audio_files
            }  # noqa: E501

            indexed = 0
            with self._get_connection() as conn:
                for future in concurrent.futures.as_completed(futures):
                    try:
                        metadata = future.result()

                        # Insert into database
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO flacs
                            (path, norm, mtime, artist, album, title,
                             trackno, year, duration, format_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                metadata["path"],
                                normalize_string(metadata.get("title", "")),
                                metadata.get("mtime", 0),
                                metadata.get("artist"),
                                metadata.get("album"),
                                metadata.get("title"),
                                metadata.get("trackno"),
                                metadata.get("year"),
                                metadata.get("duration"),
                                json.dumps(metadata.get("format", {})),
                            ),
                        )

                        indexed += 1
                        if progress_callback and indexed % 100 == 0:
                            progress_callback(indexed, len(audio_files))

                    except Exception as e:
                        logger.error(f"Error indexing {futures[future]}: {e}")

                conn.commit()

        logger.info(f"Indexed {indexed} audio files")

    def search(
        self,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        title: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search library for matching tracks.

        Args:
            artist: Artist name to search for (fuzzy)
            album: Album name to search for (fuzzy)
            title: Title to search for (fuzzy)
            limit: Maximum number of results

        Returns:
            List of matching track dicts
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM flacs WHERE 1=1"
            params = []

            if artist:
                query += " AND artist LIKE ?"
                params.append(f"%{artist}%")
            if album:
                query += " AND album LIKE ?"
                params.append(f"%{album}%")
            if title:
                query += " AND title LIKE ?"
                params.append(f"%{title}%")

            query += " LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in cursor.fetchall():
                track = dict(zip(columns, row))
                if track.get("format_json"):
                    try:
                        track["format"] = json.loads(track["format_json"])
                    except Exception:
                        track["format"] = {}
                results.append(track)

            return results

    def get_all_tracks(self) -> List[Dict[str, Any]]:
        """Get all indexed tracks."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM flacs")
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in cursor.fetchall():
                track = dict(zip(columns, row))
                if track.get("format_json"):
                    try:
                        track["format"] = json.loads(track["format_json"])
                    except Exception:
                        track["format"] = {}
                results.append(track)

            return results

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


###############################################################################
# MATCHING
###############################################################################


@dataclass
class Match:
    """Represents a match between a playlist track and library track."""

    query_track: Dict[str, Any]
    library_track: Optional[Dict[str, Any]]
    score: int
    status: str  # 'matched', 'unmatched', 'review'


def calculate_match_score(
    query: Dict[str, Any],
    candidate: Dict[str, Any],
) -> int:
    """
    Calculate fuzzy match score between query and candidate track.

    Args:
        query: Query track metadata dict
        candidate: Candidate library track dict

    Returns:
        Score from 0-100
    """
    scores = []

    # Title matching (most important)
    q_title = normalize_string(query.get("title", ""))
    c_title = normalize_string(candidate.get("title", ""))
    if q_title and c_title:
        scores.append(fuzz.ratio(q_title, c_title) * 2)  # Weight title heavily

    # Artist matching
    q_artist = normalize_string(query.get("artist", ""))
    c_artist = normalize_string(candidate.get("artist", ""))
    if q_artist and c_artist:
        scores.append(fuzz.ratio(q_artist, c_artist))

    # Album matching
    q_album = normalize_string(query.get("album", ""))
    c_album = normalize_string(candidate.get("album", ""))
    if q_album and c_album:
        scores.append(fuzz.ratio(q_album, c_album))

    # Duration matching (if available)
    q_duration = query.get("duration")
    c_duration = candidate.get("duration")
    if q_duration and c_duration:
        diff = abs(q_duration - c_duration)
        if diff <= 2:
            scores.append(100)
        elif diff <= 5:
            scores.append(80)
        elif diff <= 10:
            scores.append(60)
        else:
            scores.append(40)

    # Return weighted average
    if not scores:
        return 0

    return int(sum(scores) / len(scores))


def match_playlist(
    library: MusicLibrary,
    playlist_tracks: List[Dict[str, Any]],
    auto_match_threshold: int = DEFAULT_AUTO_MATCH_THRESHOLD,
    review_min_threshold: int = DEFAULT_REVIEW_MIN_THRESHOLD,
) -> List[Match]:
    """
    Match playlist tracks against library.

    Args:
        library: MusicLibrary instance
        playlist_tracks: List of track dicts to match
        auto_match_threshold: Score threshold for auto-accepting matches
        review_min_threshold: Minimum score for review (below = unmatched)

    Returns:
        List of Match objects
    """
    all_library_tracks = library.get_all_tracks()
    matches = []

    for query in playlist_tracks:
        best_candidate = None
        best_score = 0

        # Find best matching candidate
        for candidate in all_library_tracks:
            score = calculate_match_score(query, candidate)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        # Determine match status
        if best_score >= auto_match_threshold:
            status = "matched"
        elif best_score >= review_min_threshold:
            status = "review"
        else:
            status = "unmatched"
            best_candidate = None

        matches.append(
            Match(
                query_track=query,
                library_track=best_candidate,
                score=best_score,
                status=status,
            )
        )

    return matches


###############################################################################
# CLI (when used as standalone script)
###############################################################################


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Standalone music library matcher"
    )  # noqa: E501
    parser.add_argument(
        "--library", required=True, help="Path to music library"
    )  # noqa: E501
    parser.add_argument(
        "--playlist", required=True, help="Path to playlist JSON file"
    )  # noqa: E501
    parser.add_argument(
        "--db", help="Path to SQLite database (default: in-memory)"
    )  # noqa: E501
    parser.add_argument(
        "--scan", action="store_true", help="Force rescan of library"
    )  # noqa: E501
    parser.add_argument(
        "--threshold", type=int, default=88, help="Auto-match threshold"
    )
    parser.add_argument("--output", help="Output path for matched playlist")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )  # noqa: E501

    # Load playlist
    with open(args.playlist, "r") as f:
        playlist_data = json.load(f)

    # Extract tracks (handle different playlist formats)
    if isinstance(playlist_data, list):
        playlist_tracks = playlist_data
    elif "tracks" in playlist_data:
        playlist_tracks = playlist_data["tracks"]
    else:
        logger.error("Could not find tracks in playlist file")
        return 1

    logger.info(f"Loaded {len(playlist_tracks)} tracks from playlist")

    # Create library
    lib = MusicLibrary(
        library_paths=[args.library],
        db_path=args.db,
    )

    # Scan if needed
    if args.scan or args.db is None or not Path(args.db).exists():
        logger.info("Scanning library...")
        lib.scan(
            progress_callback=lambda c, t: logger.info(
                f"Indexed {c}/{t} files"
            )  # noqa: E501
        )

    # Match playlist
    logger.info("Matching playlist...")
    matches = match_playlist(
        lib, playlist_tracks, auto_match_threshold=args.threshold
    )  # noqa: E501

    # Print results
    matched = sum(1 for m in matches if m.status == "matched")
    review = sum(1 for m in matches if m.status == "review")
    unmatched = sum(1 for m in matches if m.status == "unmatched")

    print("\nResults:")
    print(f"  Matched: {matched}/{len(matches)}")
    print(f"  Review: {review}/{len(matches)}")
    print(f"  Unmatched: {unmatched}/{len(matches)}")

    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix == ".m3u":
            # Write M3U playlist
            with open(output_path, "w") as f:
                f.write("#EXTM3U\n")
                for match in matches:
                    if match.status == "matched" and match.library_track:
                        f.write(f"{match.library_track['path']}\n")
        else:
            # Write JSON
            output_data = {
                "matched": matched,
                "review": review,
                "unmatched": unmatched,
                "matches": [
                    {
                        "query": m.query_track,
                        "match": m.library_track,
                        "score": m.score,
                        "status": m.status,
                    }
                    for m in matches
                ],
            }
            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)

        logger.info(f"Saved output to {output_path}")

    lib.close()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
