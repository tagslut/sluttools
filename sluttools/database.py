"""
Manages the application's music library database.

This module handles all interactions with the SQLite database, including creating the
database, scanning for music files, gathering metadata, and providing functions
to query the indexed data. It uses a ProcessPoolExecutor for efficient, parallel
metadata processing.
"""

import os
import sqlite3
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures

from rich.progress import Progress

from .config import console, config
from .metadata import gather_metadata


def get_last_n_tracks(n: int = 100) -> list[dict]:
    """
    Fetches the N most recently modified tracks from the database.

    This is primarily used by the wizard to show recent additions.

    Args:
        n (int): The number of recent tracks to retrieve.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a track's
                    metadata. Returns an empty list if the database or table is not found.
    """
    db_path = Path(config['DB_PATH'])
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM flacs ORDER BY mtime DESC LIMIT ?", (n,))
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            # This can happen if the table 'flacs' does not exist yet.
            return []


def scan_flac_files(library_dir: Path):
    """
    Scans a directory for FLAC files.

    Args:
        library_dir (Path): The root directory to scan.

    Yields:
        Path: The absolute path to each found FLAC file.
    """
    for root, _, files in os.walk(library_dir):
        for file in files:
            if file.lower().endswith(".flac"):
                yield Path(root) / file


def get_flac_lookup() -> list[tuple[str, str]]:
    """
    Fetches all (path, normalized_title) tuples from the database.

    This provides the necessary data for the fuzzy matching algorithm.

    Returns:
        list[tuple[str, str]]: A list of tuples, where each contains the file path
                               and its normalized title.
    """
    # Resolve DB path robustly and handle missing DB/table gracefully.
    db_path = Path(str(config['DB_PATH']).strip("'\"")).expanduser()
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if not db_path.exists():
        # No database yet; return empty lookup instead of crashing.
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT path, norm FROM flacs")
            return cur.fetchall()
    except sqlite3.OperationalError:
        # DB exists but table may not; treat as empty index.
        return []


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
    """
    db_path = Path(str(db_path_str).strip('\'"')).expanduser()
    library_dir = Path(str(library_dir_str).strip('\'"')).expanduser()

    console.print(f"[cyan]Using database:[/] {db_path}")
    console.print(f"[cyan]Scanning for .flac files in:[/] {library_dir}")

    # Ensure DB parent directory exists to avoid sqlite 'unable to open' errors
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = OFF")
        cur = conn.cursor()
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

        # Lightweight schema migration: ensure required columns exist for older DBs.
        cur.execute("PRAGMA table_info('flacs')")
        existing_cols = {row[1] for row in cur.fetchall()}
        # Add track_number if missing; backfill from legacy 'trackno' if present.
        if "track_number" not in existing_cols:
            cur.execute("ALTER TABLE flacs ADD COLUMN track_number TEXT")
            # If legacy column exists, copy values over.
            cur.execute("PRAGMA table_info('flacs')")
            existing_cols = {row[1] for row in cur.fetchall()}
            if "trackno" in existing_cols:
                try:
                    cur.execute("UPDATE flacs SET track_number = trackno WHERE track_number IS NULL")
                except sqlite3.OperationalError:
                    # If trackno column isn't usable for some reason, ignore backfill.
                    pass
            conn.commit()
        # Ensure format_json exists, as older schemas might lack it.
        cur.execute("PRAGMA table_info('flacs')")
        existing_cols = {row[1] for row in cur.fetchall()}
        if "format_json" not in existing_cols:
            cur.execute("ALTER TABLE flacs ADD COLUMN format_json TEXT")
            conn.commit()

        # Purge vanished files
        all_db_paths = {row[0] for row in cur.execute("SELECT path FROM flacs WHERE path LIKE ?", (f"{library_dir}%",))}
        purged_files = 0
        for p_str in all_db_paths:
            if not Path(p_str).exists():
                cur.execute("DELETE FROM flacs WHERE path=?", (p_str,))
                purged_files += 1
        if purged_files > 0:
            conn.commit()
            console.print(f"[yellow]Purged {purged_files} vanished files from this library.[/yellow]")

        # Scan for new/updated files
        console.print("[cyan]Scanning for file changes...[/cyan]")
        all_disk_paths = list(scan_flac_files(library_dir))
        db_mtimes = dict(cur.execute("SELECT path, mtime FROM flacs"))

        to_scan = [
            p for p in all_disk_paths
            if str(p) not in db_mtimes or int(p.stat().st_mtime) != db_mtimes.get(str(p))
        ]

        if not to_scan:
            console.print(f"[green]No new or updated files found.[/green]")
            return

        console.print(f"[cyan]Indexing {len(to_scan)} new/updated files...[/cyan]")

        results = []
        with Progress(console=console) as progress:
            task = progress.add_task("[green]Indexing tracks:", total=len(to_scan))
            with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                futures = [executor.submit(gather_metadata, p, with_format=not quick) for p in to_scan]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        results.append(result)
                    progress.update(task, advance=1)

        if results:
            cur.executemany(
                "REPLACE INTO flacs (path, norm, mtime, artist, album, title, track_number, year, format_json) VALUES (?,?,?,?,?,?,?,?,?)",
                results,
            )
            conn.commit()
            console.print(f"[green]Updated {len(results)} files in the database.[/green]")

def get_session(db_path: str | Path | None = None):
    """
    Creates and returns a connection (session) to the SQLite database.

    Args:
        db_path (str): Path to the SQLite database file. Defaults to the configured DB_PATH.

    Returns:
        sqlite3.Connection: A connection object to the database.
    """
    raw = Path(db_path) if db_path else Path(str(config['DB_PATH']))
    dbp = Path(str(raw).strip("'\"")).expanduser()
    try:
        dbp.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    conn = sqlite3.connect(str(dbp))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    return conn
