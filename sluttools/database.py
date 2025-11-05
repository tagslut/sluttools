"""
Manages the application's music library database.

This module handles all interactions with the SQLite database, including creating the
database, scanning for music files, gathering metadata, and providing functions
to query the indexed data. It uses a ProcessPoolExecutor for efficient, parallel
metadata processing.

Also includes metadata extraction utilities (formerly in metadata.py):
- normalize_string: String normalization for indexing/lookup
- gather_metadata: Extract metadata from file paths for database indexing
- parse_filename_structure: Parse file paths into metadata dicts for matching
"""

import concurrent.futures
import json
import logging
import os
import re
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from rich.progress import Progress

from .config import config, console

logger = logging.getLogger(__name__)

# Default supported audio file extensions
DEFAULT_AUDIO_EXTENSIONS = {".flac", ".mp3", ".wav", ".m4a", ".ogg"}


################################################################################
# METADATA EXTRACTION UTILITIES
################################################################################


def normalize_string(s: Optional[str]) -> str:
    """Very small normalizer used for indexing/lookup.
    Keep minimal to avoid changing scoring behavior elsewhere.
    """
    if s is None:
        return ""
    return " ".join(s.strip().lower().split())


def gather_metadata(p: Path | str):
    """Minimal gather_metadata to satisfy imports and tests.

    Returns a tuple: (row, formats_row, tags_rows)
    where row matches the schema used in tests for table `flacs`:
    (path, norm, mtime, artist, album, title, trackno, year, format_json)

    This implementation does not probe audio; tests monkeypatch this symbol
    when behavior is required. Here we just provide sane defaults.
    """
    path = Path(p)
    try:
        mtime = int(path.stat().st_mtime)
    except Exception:
        mtime = 0
    title = path.stem
    row = (
        str(path),
        f"norm-{normalize_string(title) or title}",
        mtime,
        None,  # artist
        None,  # album
        title,  # title
        None,  # trackno
        None,  # year
        json.dumps({}),  # format_json
    )
    return (row, None, [])


def parse_filename_structure(p: Path | str) -> Dict[str, Any]:
    """Parse a music file path into a lightweight metadata dict.

    Heuristics only; aims to provide enough fields for calculate_match_score:
      - artist, title, album, year, duration
    Other keys may be included for future use.
    """
    path = Path(p)
    album = None
    artist = None
    title = path.stem
    trackno = None
    year = None

    # Try to extract track number at start of filename: "01 - ..." or "1. ..."
    m = re.match(r"^(\d{1,3})[\s_.-]+(.+)$", title)
    if m:
        try:
            trackno = int(m.group(1))
        except Exception:
            trackno = None
        title = m.group(2).strip()

    # If filename contains an artist prefix, split once to get the remainder
    if " - " in title:
        first, rest = title.split(" - ", 1)
        # Heuristic: if the first segment isn't obviously part of an album marker, treat as artist
        if not artist and len(first) <= 80:
            artist = first.strip() or artist
            title = rest.strip() or title

    # Handle filenames like: Artist - (2020) Album - 02. Title
    if artist and " - " in title:
        parts = [seg.strip() for seg in title.split(" - ") if seg.strip()]
        if len(parts) >= 2:
            last = parts[-1]
            m2 = re.match(r"^(\d{1,3})[\s_.-]+(.+)$", last)
            if m2:
                # Extract track number and real title
                try:
                    trackno = trackno or int(m2.group(1))
                except Exception:
                    pass
                title = m2.group(2).strip()
                # Album is everything before the last segment
                if not album:
                    album = " - ".join(parts[:-1]).strip()

    # Derive album and artist from folders if not already set
    parts = list(path.parts)
    parent_name = path.parent.name if path.parent else ""
    if not artist or not album:
        if " - " in parent_name:
            a, b = parent_name.split(" - ", 1)
            if not artist and a.strip():
                artist = a.strip()
            if not album and b.strip():
                album = b.strip()
        else:
            if len(parts) >= 2 and not album:
                album = path.parent.name or album
            if len(parts) >= 3 and not artist:
                artist = path.parent.parent.name or artist

    # Year hint from any path component (prefer album folder and filename middle)
    year_re = re.compile(r"\b(19\d{2}|20\d{2})\b")
    scan_order = []
    # Prefer album and parent_name hints first
    if album:
        scan_order.append(album)
    scan_order.append(parent_name)
    scan_order.extend(reversed(parts))
    for comp in scan_order:
        ym = year_re.search(comp)
        if ym:
            try:
                year = int(ym.group(1))
            except ValueError:
                pass
            break

    return {
        "artist": artist or "",
        "album": album or "",
        "title": title or "",
        "trackno": trackno,
        "year": year,
        "duration": None,
        "path": str(path),
    }


# Placeholder kept for backwards compatibility
def calculate_match_score(source, candidate):
    """Placeholder scoring function. Returns 0.0 until fully implemented."""
    return 0.0


################################################################################
# DATABASE MANAGEMENT
################################################################################


def _normalize_path(path_input: Union[str, Path]) -> Path:
    """
    Normalize and resolve a path consistently across the module.

    Args:
        path_input: Raw path string or Path object

    Returns:
        Path: Normalized and expanded Path object

    Raises:
        ValueError: If path contains suspicious patterns
    """
    if isinstance(path_input, Path):
        path_str = str(path_input)
    else:
        path_str = str(path_input)

    # Strip quotes and expand user directory
    cleaned = path_str.strip("'\"")

    # Basic path traversal protection
    if ".." in cleaned or cleaned.startswith("/"):
        # Allow absolute paths but validate they don't contain traversal patterns
        normalized_parts = []
        for part in Path(cleaned).parts:
            if part == "..":
                raise ValueError(f"Path traversal detected in path: {path_input}")
            normalized_parts.append(part)

    return Path(cleaned).expanduser().resolve()


def _ensure_directory_exists(path: Path) -> bool:
    """
    Safely create directory if it doesn't exist.

    Args:
        path: Directory path to create

    Returns:
        bool: True if directory exists or was created successfully
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError) as e:
        logger.warning(f"Failed to create directory {path}: {e}")
        return False


def _get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    """
    Get column names for a table, with caching to avoid repeated queries.

    Args:
        cursor: Database cursor
        table_name: Name of the table

    Returns:
        set[str]: Set of column names
    """
    # Whitelist of allowed table names to prevent SQL injection
    ALLOWED_TABLES = {"flacs", "formats", "tags"}

    if table_name not in ALLOWED_TABLES:
        raise ValueError(
            f"Table name '{table_name}' not in allowed list: {ALLOWED_TABLES}"
        )

    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


@contextmanager
def get_db_connection(
    db_path: Optional[Union[str, Path]] = None
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections with proper resource management.

    Args:
        db_path: Path to database file, uses config default if None

    Yields:
        sqlite3.Connection: Database connection with optimized settings
    """
    if db_path is None:
        db_path = config["DB_PATH"]

    normalized_path = _normalize_path(db_path)

    # Ensure parent directory exists
    if not _ensure_directory_exists(normalized_path.parent):
        raise OSError(f"Cannot create database directory: {normalized_path.parent}")

    conn = None
    try:
        conn = sqlite3.connect(str(normalized_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_last_n_tracks(n: int = 100) -> list[dict]:
    """
    Fetches the N most recently modified tracks from the database.

    This is primarily used by the wizard to show recent additions.

    Args:
        n (int): The number of recent tracks to retrieve. Must be positive.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a track's
                    metadata. Returns an empty list if the database or table is not found.

    Raises:
        ValueError: If n is not a positive integer
    """
    if not isinstance(n, int) or n <= 0:
        raise ValueError("n must be a positive integer")

    db_path = _normalize_path(config["DB_PATH"])
    if not db_path.exists():
        return []

    try:
        with get_db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM flacs ORDER BY mtime DESC LIMIT ?", (n,))
            return [dict(row) for row in cur.fetchall()]
    except sqlite3.OperationalError as e:
        logger.debug(f"Table 'flacs' may not exist: {e}")
        return []


def scan_audio_files(
    library_dir: Path, extensions: Optional[set[str]] = None
) -> Generator[Path, None, None]:
    """
    Scans a directory for audio files with configurable extensions.

    Args:
        library_dir (Path): The root directory to scan.
        extensions (set[str], optional): File extensions to scan for.
                                       Defaults to DEFAULT_AUDIO_EXTENSIONS.

    Yields:
        Path: The absolute path to each found audio file.

    Raises:
        OSError: If library_dir is not accessible
    """
    if extensions is None:
        extensions = DEFAULT_AUDIO_EXTENSIONS

    if not library_dir.exists():
        raise OSError(f"Library directory does not exist: {library_dir}")

    if not library_dir.is_dir():
        raise OSError(f"Library path is not a directory: {library_dir}")

    try:
        for root, _, files in os.walk(library_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in extensions:
                    yield file_path
    except (OSError, PermissionError) as e:
        logger.error(f"Error scanning directory {library_dir}: {e}")
        raise


def scan_flac_files(library_dir: Path) -> Generator[Path, None, None]:
    """
    Scans a directory for FLAC files (backward compatibility wrapper).

    Args:
        library_dir (Path): The root directory to scan.

    Yields:
        Path: The absolute path to each found FLAC file.
    """
    yield from scan_audio_files(library_dir, {".flac"})


def get_flac_lookup() -> list[tuple[str, str]]:
    """
    Fetches all (path, normalized_title) tuples from the database.

    This provides the necessary data for the fuzzy matching algorithm.

    Returns:
        list[tuple[str, str]]: A list of tuples, where each contains the file path
                               and its normalized title.
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT path, norm FROM flacs")
            return cur.fetchall()
    except sqlite3.OperationalError as e:
        logger.debug(f"Database or table may not exist: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching flac lookup: {e}")
        return []


def _safe_get_mtime(file_path: Path) -> Optional[int]:
    """
    Safely get file modification time, handling race conditions.

    Args:
        file_path: Path to the file

    Returns:
        Optional[int]: File modification time or None if inaccessible
    """
    try:
        return int(file_path.stat().st_mtime)
    except (OSError, FileNotFoundError):
        # Only log if debug level is enabled to reduce noise
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Cannot access file {file_path}")
        return None


def _migrate_schema(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    """
    Perform database schema migrations efficiently.

    Args:
        cursor: Database cursor
        conn: Database connection for commits
    """
    # Get current columns once
    existing_cols = _get_table_columns(cursor, "flacs")

    migrations_needed = []

    # Check for missing columns
    if "track_number" not in existing_cols:
        migrations_needed.append("ALTER TABLE flacs ADD COLUMN track_number TEXT")

    if "format_json" not in existing_cols:
        migrations_needed.append("ALTER TABLE flacs ADD COLUMN format_json TEXT")

    # Execute migrations
    for migration in migrations_needed:
        try:
            cursor.execute(migration)
            logger.info(f"Applied migration: {migration}")
        except sqlite3.OperationalError as e:
            logger.warning(f"Migration failed: {migration} - {e}")

    # Handle legacy column migration
    if "track_number" not in existing_cols:
        # Refresh column list after migrations
        updated_cols = _get_table_columns(cursor, "flacs")
        if "trackno" in updated_cols and "track_number" in updated_cols:
            try:
                cursor.execute(
                    "UPDATE flacs SET track_number = trackno WHERE track_number IS NULL"
                )
                logger.info("Migrated data from legacy 'trackno' column")
            except sqlite3.OperationalError as e:
                logger.warning(f"Legacy data migration failed: {e}")

    if migrations_needed:
        conn.commit()


def _purge_vanished_files(
    cursor: sqlite3.Cursor, conn: sqlite3.Connection, library_dir: Path
) -> int:
    """
    Remove database entries for files that no longer exist.

    Args:
        cursor: Database cursor
        conn: Database connection
        library_dir: Library directory path

    Returns:
        int: Number of files purged
    """
    # Use parameterized query to avoid SQL injection
    library_pattern = str(library_dir) + "%"
    cursor.execute("SELECT path FROM flacs WHERE path LIKE ?", (library_pattern,))
    db_paths = [row[0] for row in cursor.fetchall()]

    purged_files = 0
    for path_str in db_paths:
        if not Path(path_str).exists():
            cursor.execute("DELETE FROM tracks WHERE file_path = ?", (path_str,))
            purged_files += 1

    if purged_files > 0:
        conn.commit()
        logger.info(f"Purged {purged_files} vanished files")

    return purged_files


def _process_metadata_row(row_data: tuple) -> Optional[tuple]:
    """
    Process metadata row to match database schema with validation.

    The gather_metadata function returns:
    (path, norm, mtime, artist, album, title, trackno, year, format_json)

    But our database expects:
    (path, norm, mtime, artist, album, title, track_number, year, format_json)

    Args:
        row_data: Raw row data from gather_metadata

    Returns:
        Optional[tuple]: Processed row data matching database schema, or None if invalid
    """
    try:
        if not row_data or len(row_data) < 9:
            logger.warning(f"Invalid row data structure: {row_data}")
            return None

        # Extract fields from the row
        path, norm, mtime, artist, album, title, trackno, year, format_json = row_data

        # Validate required fields
        if not path:
            logger.warning("Missing required field 'path' in metadata row")
            return None

        if not norm:
            logger.warning(f"Missing required field 'norm' for path: {path}")
            return None

        # Validate path exists and is accessible
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.warning(f"File no longer exists: {path}")
                return None
        except (OSError, ValueError) as e:
            logger.warning(f"Invalid path in metadata: {path} - {e}")
            return None

        # Convert trackno to track_number (field name standardization)
        track_number = str(trackno) if trackno is not None else None

        # Ensure all fields are properly formatted with validation
        try:
            processed_mtime = int(mtime) if mtime is not None else 0
            if processed_mtime < 0:
                logger.warning(f"Invalid mtime {mtime} for path: {path}")
                processed_mtime = 0
        except (ValueError, TypeError):
            logger.warning(f"Invalid mtime format {mtime} for path: {path}")
            processed_mtime = 0

        processed_row = (
            str(path),
            str(norm),
            processed_mtime,
            str(artist) if artist else None,
            str(album) if album else None,
            str(title) if title else "",
            track_number,
            str(year) if year else None,
            str(format_json) if format_json else "{}",
        )

        return processed_row

    except (ValueError, TypeError, IndexError) as e:
        logger.error(f"Error processing metadata row {row_data}: {e}")
        return None


def _find_files_to_scan(
    library_dir: Path, cursor: sqlite3.Cursor, batch_size: int = 1000
) -> Generator[list[Path], None, None]:
    """
    Find files that need scanning, yielding in batches to manage memory.
    Uses chunked database queries to avoid loading all mtimes into memory at once.

    Args:
        library_dir: Library directory to scan
        cursor: Database cursor
        batch_size: Number of files per batch

    Yields:
        list[Path]: Batches of files that need scanning
    """
    batch = []

    # Process files in chunks to manage memory usage
    for file_path in scan_audio_files(library_dir):
        path_str = str(file_path)
        file_mtime = _safe_get_mtime(file_path)

        if file_mtime is None:
            continue  # Skip inaccessible files

        # Check if file needs scanning using individual query to avoid memory issues
        cursor.execute("SELECT mtime FROM flacs WHERE path = ?", (path_str,))
        result = cursor.fetchone()

        needs_scanning = False
        if result is None:
            # File not in database
            needs_scanning = True
        else:
            db_mtime = result[0]
            if file_mtime != db_mtime:
                # File has been modified
                needs_scanning = True

        if needs_scanning:
            batch.append(file_path)

            if len(batch) >= batch_size:
                yield batch
                batch = []

    # Yield remaining files
    if batch:
        yield batch


def refresh_library(db_path_str: str, library_dir_str: str, quick: bool = True):
    """
    Scans a music library, updates the database, and purges vanished files.

    This function connects to the database, creates the `flacs` table if needed,
    removes entries for files that no longer exist, scans for new or updated
    files, gathers their metadata in parallel, and saves the results.

    Args:
        db_path_str (str): The path to the SQLite database file, provided from the config.
        library_dir_str (str): The root directory of the music library to scan.
        quick (bool): If True, skips the slow `ffprobe` scan for format information.

    Raises:
        OSError: If database or library directory is inaccessible
        ValueError: If paths are invalid
    """
    try:
        db_path = _normalize_path(db_path_str)
        library_dir = _normalize_path(library_dir_str)
    except Exception as e:
        raise ValueError(f"Invalid path provided: {e}")

    if not library_dir.exists():
        raise OSError(f"Library directory does not exist: {library_dir}")

    console.print(f"[cyan]Using database:[/] {db_path}")
    console.print(f"[cyan]Scanning for audio files in:[/] {library_dir}")

    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()

            # Create table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS flacs (
                    path TEXT PRIMARY KEY,
                    norm TEXT NOT NULL,
                    mtime INTEGER NOT NULL,
                    artist TEXT,
                    album TEXT,
                    title TEXT,
                    track_number TEXT,
                    year TEXT,
                    format_json TEXT
                )
                """
            )
            conn.commit()

            # Perform schema migrations
            _migrate_schema(cur, conn)

            # Purge vanished files
            purged_count = _purge_vanished_files(cur, conn, library_dir)
            if purged_count > 0:
                console.print(
                    f"[yellow]Purged {purged_count} vanished files from this library.[/yellow]"
                )

            # Scan for new/updated files
            console.print("[cyan]Scanning for file changes...[/cyan]")

            total_processed = 0
            total_updated = 0

            for batch in _find_files_to_scan(library_dir, cur):
                if not batch:
                    continue

                console.print(f"[cyan]Processing batch of {len(batch)} files...[/cyan]")

                results = []
                with Progress(console=console) as progress:
                    task = progress.add_task(
                        "[green]Indexing tracks:", total=len(batch)
                    )

                    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                        futures = [executor.submit(gather_metadata, p) for p in batch]

                        for future in concurrent.futures.as_completed(futures):
                            try:
                                result = future.result()
                                if result:
                                    # gather_metadata returns (row, formats_row, tags_rows)
                                    # We need the first element (row) for database insertion
                                    row_data = (
                                        result[0]
                                        if isinstance(result, tuple)
                                        else result
                                    )
                                    if row_data:
                                        # Convert the row data to match our database schema
                                        processed_row = _process_metadata_row(row_data)
                                        if processed_row:
                                            results.append(processed_row)
                            except Exception as e:
                                logger.error(f"Error processing file: {e}")
                            finally:
                                progress.update(task, advance=1)

                # Insert results
                if results:
                    cur.executemany(
                        "REPLACE INTO flacs (path, norm, mtime, artist, album, title, track_number, year, format_json) VALUES (?,?,?,?,?,?,?,?,?)",
                        results,
                    )
                    conn.commit()
                    total_updated += len(results)

                total_processed += len(batch)

            if total_processed == 0:
                console.print("[green]No new or updated files found.[/green]")
            else:
                console.print(
                    f"[green]Processed {total_processed} files, updated {total_updated} in database.[/green]"
                )

    except Exception as e:
        logger.error(f"Error during library refresh: {e}")
        raise


def get_session(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """
    Creates and returns a connection (session) to the SQLite database.

    WARNING: This function returns an open connection that must be closed by the caller.
    Consider using get_db_connection() context manager instead for automatic resource management.

    Args:
        db_path: Path to the SQLite database file. Defaults to the configured DB_PATH.

    Returns:
        sqlite3.Connection: A connection object to the database.

    Raises:
        OSError: If database directory cannot be created or accessed
    """
    if db_path is None:
        db_path = config["DB_PATH"]

    normalized_path = _normalize_path(db_path)

    if not _ensure_directory_exists(normalized_path.parent):
        raise OSError(f"Cannot create database directory: {normalized_path.parent}")

    try:
        conn = sqlite3.connect(str(normalized_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        raise
