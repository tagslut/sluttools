#!/usr/bin/env python3
# Script: Early matching utility experiment (archived); contains helper functions and CLI stubs.
"""
LEGACY SCRIPT (archived): g.py

This script is kept only for historical reference and is not part of the
active CLI. Please use the Typer-based sluttools CLI instead:

    poetry run slut ...

Canonical matching functions live in sluttools.matching. This file should not
be executed in normal workflows.
"""
import os
import re
import glob
import csv
import json
import unicodedata
from pathlib import Path
import sqlite3
from typing import Dict, List, Tuple, Optional, Set
from functools import lru_cache
from tqdm import tqdm
# Added missing imports for a complete script
import aiofiles
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console

import typer

app = typer.Typer()

# Placeholder for a fuzzy matching library like 'thefuzz'
# You would install it with: pip install thefuzz
from thefuzz import fuzz

console = Console()

################################################################################
# CONFIGURATION
################################################################################

DEFAULT_FLAC_LIBRARY_DIR = "/Volumes/sad/MUSIC"
DEFAULT_DB_PATH = "/Users/georgeskhawam/Library/Mobile Documents/com~apple~CloudDocs/flibrary.db"
DEFAULT_THRESHOLD = 65

################################################################################
# UTILITY & HELPER FUNCTIONS
################################################################################

# This function was missing from the original script.
# It's a placeholder for a real fuzzy matching algorithm.
def combined_fuzzy_ratio_prenormalized(a: str, b: str) -> int:
    """
    Calculates a combined fuzzy match score.
    This implementation uses token_set_ratio from thefuzz, which is good
    at finding matches even when word order is different.
    """
    return fuzz.token_set_ratio(a, b)

# This function was missing from the original script.
# It requires 'mutagen' to be installed: pip install mutagen
def read_audio_metadata(path: str) -> Dict[str, str]:
    """Reads basic metadata tags from an audio file using mutagen."""
    try:
        from mutagen.flac import FLAC
        audio = FLAC(path)
        return {
            "artist": ", ".join(audio.get("artist", [])),
            "album": ", ".join(audio.get("album", [])),
            "title": ", ".join(audio.get("title", [])),
            "trackno": ", ".join(audio.get("tracknumber", [])),
            "year": ", ".join(audio.get("date", [])),
        }
    except Exception:
        # Fallback for files that can't be read
        return {}

# This function was missing from the original script.
def get_format_json(path: str) -> Dict:
    """Extract format information using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout).get("format", {})
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        # Silently fail if ffprobe isn't installed or fails
        return {}

################################################################################
# FUZZY MATCHING, SCANNING, & M3U GENERATION
################################################################################

def normalize_string(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]+", " ", s).strip()

def find_all_flacs(library_dir):
    return glob.glob(os.path.join(library_dir, "**", "*.flac"), recursive=True)

def load_library_from_db(db_path):
    if not os.path.exists(db_path):
        console.print(f"[red]Database not found at {db_path}[/red]")
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        # Ensure compatibility with old schemas by checking columns dynamically
        cur.execute("PRAGMA table_info(flacs)")
        columns = {row[1] for row in cur.fetchall()}
        if "norm_meta" in columns:
            cur.execute("SELECT path, norm_meta FROM flacs")
        else:
            cur.execute("SELECT path, '' AS norm_meta FROM flacs")
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        console.print(f"[red]Error reading from database: {e}[/red]")
        return []
    finally:
        conn.close()

def parse_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
            # Normalize the JSON structure
            if isinstance(data, list):
                data = data[0] if data else {}

            # Support nested playlist structures like {"playlists": [{...}]}
            if isinstance(data, dict) and "playlists" in data and isinstance(data["playlists"], list):
                data = data["playlists"][0] if data["playlists"] else {}

            # If still not a dict at this point, abort
            if not isinstance(data, dict):
                console.print(f"[red]Unexpected JSON structure in {file_path}[/red]")
                return Path(file_path).stem, []
            nm = data.get("name", Path(file_path).stem)
            raw = data.get("tracks", [])
            out = []
            for r in raw:
                title = r.get("title", "") or r.get("track", "")
                track = r.get("track", "") or r.get("title", "")
                out.append({
                    "artist": r.get("artist", ""),
                    "album": r.get("album", ""),
                    "track": track,
                    "title": title,
                    "isrc": r.get("isrc", "")
                })
            return nm, out
    except Exception as ex:
        console.print(f"[red]Error reading JSON: {ex}[/red]")
    return Path(file_path).stem, []

def parse_csv_file(file_path):
    out = []
    try:
        with open(file_path, "r", encoding="utf-8-sig") as cf: # Use utf-8-sig for BOM
            sample = cf.readline()
            delimiter = ";" if ";" in sample else ","
            cf.seek(0) # Rewind after reading sample
            rd = csv.DictReader(cf, delimiter=delimiter)
            for row in rd:
                entry = {
                    "title": row.get("title", ""),
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                    "track": row.get("track", row.get("title", "")),
                    "isrc": row.get("isrc", "")
                }
                out.append(entry)
        nm = Path(file_path).stem
        return nm, out
    except Exception as e2:
        console.print(f"[red]Error reading CSV: {e2}[/red]")
    return Path(file_path).stem, []

def parse_playlist_file(file_path):
    ext = Path(file_path).suffix.lower()
    if ext == ".json":
        return parse_json_file(file_path)
    elif ext == ".csv":
        return parse_csv_file(file_path)
    else:
        console.print(f"[yellow]Unsupported playlist format: {ext}[/yellow]")
        return Path(file_path).stem, []

def build_search_string(entry):
    parts = [
        entry.get("artist"),
        entry.get("album"),
        entry.get("track"),
        entry.get("title"),
        entry.get("isrc")
    ]
    return " ".join(filter(None, parts)).strip()

@lru_cache(maxsize=1024)
def combined_fuzzy_ratio_cached(a: str, b: str) -> int:
    return combined_fuzzy_ratio_prenormalized(a, b)

def match_entry(
    entry: Dict[str, str],
    flac_lookup: List[Tuple[str, str]],
    playlist_size: int = 100,
    threshold: int = DEFAULT_THRESHOLD
) -> Optional[str]:
    ss = build_search_string(entry)
    if not ss:
        return None

    ss_norm = normalize_string(ss)
    best_match = None
    highest_ratio = -1

    for orig_path, norm_basename in flac_lookup:
        r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
        if r > highest_ratio:
            highest_ratio = r
            best_match = orig_path
        # Early exit for perfect matches
        if r == 100:
            break

    if highest_ratio >= threshold:
        return best_match
    return None

async def create_m3u_file(out_path, matched_paths):
    if not out_path.lower().endswith(".m3u"):
        out_path += ".m3u"
    try:
        async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
            await f.write("#EXTM3U\n")
            for p in matched_paths:
                if p: # Ensure no None paths are written
                    await f.write(p + "\n")
        console.print(f"[bold green]Created M3U: {out_path}[/bold green]")
    except Exception as e2:
        console.print(f"[red]Error writing M3U: {e2}[/red]")

async def create_csv_file(out_path, entries, matched_paths):
    if not out_path.lower().endswith(".csv"):
        out_path += ".csv"
    try:
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["title", "artist", "album", "isrc", "path"])
            for i, path in enumerate(matched_paths):
                if path and i < len(entries): # Only write rows for matched tracks
                    entry = entries[i]
                    writer.writerow([
                        entry.get("title", ""),
                        entry.get("artist", ""),
                        entry.get("album", ""),
                        entry.get("isrc", ""),
                        path
                    ])
        console.print(f"[bold green]Created CSV: {out_path}[/bold green]")
    except Exception as e:
        console.print(f"[red]Error writing CSV: {e}[/red]")

def export_songshift_json_from_entries(entries, matched, output_json, playlist_name="Unmatched Tracks"):
    tracks = []
    for i, m in enumerate(matched):
        if m is None:
            e = entries[i]
            title = e.get("title") or e.get("track") or build_search_string(e)
            artist = e.get("artist") or "Unknown Artist"
            tracks.append({"artist": artist.strip(), "track": title.strip()})

    if not tracks:
        return # Don't create an empty file

    payload = [{
        "service": "qobuz",
        "serviceId": None,
        "name": playlist_name,
        "tracks": tracks
    }]

    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    console.print(f"[bold green]✓ JSON for unmatched tracks saved → {output_json} ({len(tracks)} tracks)[/bold green]")

################################################################################
# DATABASE FUNCTIONS
################################################################################

def open_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create table if it does not exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flacs (
            path TEXT PRIMARY KEY,
            norm TEXT NOT NULL,
            mtime INTEGER NOT NULL,
            artist TEXT,
            album TEXT,
            title TEXT,
            trackno TEXT,
            year TEXT,
            format_json TEXT,
            norm_meta TEXT
        )
    """)

    # Check for missing columns and add them dynamically
    cur.execute("PRAGMA table_info(flacs)")
    columns = {row[1] for row in cur.fetchall()}
    if "norm_meta" not in columns:
        cur.execute("ALTER TABLE flacs ADD COLUMN norm_meta TEXT")

    # Create indexes safely
    cur.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_norm_meta ON flacs(norm_meta)")

    return conn

def refresh_library(library_dir, db_path):
    conn = open_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT path FROM flacs")
    db_paths = {p for (p,) in cur.fetchall()}
    disk_paths = set(glob.glob(os.path.join(library_dir, "**", "*.flac"), recursive=True))

    # Purge vanished files
    vanished = db_paths - disk_paths
    if vanished:
        cur.executemany("DELETE FROM flacs WHERE path=?", [(p,) for p in vanished])
        conn.commit()
        console.print(f"[yellow]Removed {len(vanished)} vanished files from DB.[/yellow]")

    files_to_process = []
    for p in tqdm(disk_paths, desc="Checking for new/modified files", unit="file"):
        m = int(os.path.getmtime(p))
        cur.execute("SELECT mtime FROM flacs WHERE path=?", (p,))
        row = cur.fetchone()
        if not row or row[0] != m:
            files_to_process.append((p, m))

    if not files_to_process:
        console.print("[green]Library is already up-to-date.[/green]")
        conn.close()
        return

    console.print(f"[cyan]Scanning {len(files_to_process)} new/modified FLAC files...[/cyan]")

    def process_file(args):
        p, m = args
        norm_filename = normalize_string(Path(p).stem)
        tags = read_audio_metadata(p)
        fmt_json = json.dumps(get_format_json(p))

        # --- Build the rich, normalized metadata string ---
        meta_parts = [tags.get("artist"), tags.get("title"), tags.get("album")]
        norm_meta = normalize_string(" ".join(filter(None, meta_parts)))
        # ----------------------------------------------------

        return (
            p, norm_filename, m, tags.get("artist"), tags.get("album"),
            tags.get("title"), tags.get("trackno"), tags.get("year"), fmt_json,
            norm_meta  # Add the new field
        )

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(
            tqdm(executor.map(process_file, files_to_process), total=len(files_to_process), desc="Extracting Metadata",
                 unit="file"))

    # Update the REPLACE statement to include the new column
    cur.executemany(
        "REPLACE INTO flacs (path, norm, mtime, artist, album, title, trackno, year, format_json, norm_meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        results
    )
    conn.commit()
    conn.close()

################################################################################
# MAIN FUNCTION
################################################################################

async def main(playlist_path, library_dir, db_path, threshold):
    console.print(f"[cyan]Processing: {playlist_path}[/cyan]")

    # 1. Load library
    console.print("Loading library from database...")
    library_tracks = load_library_from_db(db_path)
    if not library_tracks:
        console.print("[red]Error: Library is empty. Run 'refresh' command first.[/red]")
        return

    flac_lookup = [(track["path"], track["norm_meta"]) for track in library_tracks if track.get("norm_meta")]

    # 2. Parse playlist
    playlist_name, entries = parse_playlist_file(str(playlist_path))
    if not entries:
        console.print(f"[red]Could not parse any tracks from {playlist_path}. Check file format.[/red]")
        return

    # 3. Match tracks
    console.print("Matching tracks...")
    matched_paths = []
    for entry in tqdm(entries, desc="Matching", unit="track"):
        match = match_entry(entry, flac_lookup, playlist_size=len(entries), threshold=threshold)
        matched_paths.append(match)

    # 4. Report and export results
    found_count = sum(1 for p in matched_paths if p)
    console.print(f"\n[bold green]Matched {found_count}/{len(entries)} tracks.[/bold green]")

    if found_count:
        # Create a list of non-None paths for the output files
        final_paths = [p for p in matched_paths if p]
        await create_m3u_file(f"{playlist_name}_matched.m3u", final_paths)
        await create_csv_file(f"{playlist_name}_matched.csv", entries, matched_paths)

    if found_count < len(entries):
        export_songshift_json_from_entries(entries, matched_paths, f"{playlist_name}_unmatched.json", playlist_name)


# Typer CLI commands

@app.command()
def refresh(
    library_dir: Path = typer.Option(DEFAULT_FLAC_LIBRARY_DIR, help="Path to your music library."),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, help="Path to the SQLite database.")
):
    console.print(f"[cyan]Refreshing library from {library_dir} into {db_path}[/cyan]")
    refresh_library(str(library_dir), str(db_path))
    console.print("[bold green]Library refresh complete.[/bold green]")

@app.command()
def match(
    playlist_file: Path = typer.Argument(..., help="Path to the playlist file (.json or .csv)."),
    library_dir: Path = typer.Option(DEFAULT_FLAC_LIBRARY_DIR, help="Path to your music library."),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, help="Path to the SQLite database."),
    threshold: int = typer.Option(DEFAULT_THRESHOLD, help="Fuzzy match sensitivity (0-100).")
):
    console.print(f"[cyan]Matching {playlist_file} with threshold {threshold}...[/cyan]")
    import asyncio
    asyncio.run(main(playlist_file, library_dir, db_path, threshold))

if __name__ == "__main__":
    app()
