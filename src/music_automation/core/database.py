def get_problematic_sample_rates(db_path):
    """Return a list of distinct sample rates that are not 44100 or 48000."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    results = []
    for row in cur.execute(
        "SELECT DISTINCT json_extract(format_json, '$.tags.SAMPLERATE') FROM flacs"
    ):
        try:
            sr = int(row[0])
            if sr not in (44100, 48000):
                results.append(sr)
        except:
            continue
    conn.close()
    return sorted(set(results))


def batch_resample(db_path, dry_run=False):
    """Prompt for sample rate and resample all matching files using SoX."""
    rates = get_problematic_sample_rates(db_path)
    if not rates:
        print("No non-standard sample rates found.")
        return
    print("Problematic sample rates found:")
    for i, rate in enumerate(rates, start=1):
        print(f"{i}: {rate} Hz")
    choice = input("Select a sample rate to resample: ")
    try:
        choice = int(choice)
        selected_rate = rates[choice - 1]
    except:
        print("Invalid selection.")
        return

    # Choose nearest standard rate (44100 or 48000)
    # If closer to 44100, use 44100; else use 48000
    if abs(selected_rate - 44100) <= abs(selected_rate - 48000):
        target_rate = 44100
    else:
        target_rate = 48000
    print(f"Resampling all files with {selected_rate} Hz to {target_rate} Hz")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT path FROM flacs WHERE json_extract(format_json, '$.tags.SAMPLERATE') = ?",
        (str(selected_rate),),
    )
    files = [row[0] for row in cur.fetchall()]
    conn.close()

    for src in files:
        dest = src.replace(".flac", f".{target_rate}.flac")
        cmd = ["sox", src, "-r", str(target_rate), dest, "rate", "-v"]
        print(" ".join(cmd))
        if not dry_run:
            subprocess.run(cmd)


#!/usr/bin/env python3
import sqlite3
import json
import subprocess
import argparse
from pathlib import Path
import os
from mutagen.flac import FLAC
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures


def normalize_string(s):
    """Normalize a string for fuzzy matching."""
    import unicodedata
    import re

    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]+", " ", s).strip()


def read_tags(path):
    """Extract tags from a FLAC file."""
    try:
        audio = FLAC(path)

        def get_tag(audio, key):
            val = audio.get(key)
            if isinstance(val, list) and val:
                return val[0]
            if isinstance(val, str):
                return val
            return None

        return {
            "artist": get_tag(audio, "artist"),
            "album": get_tag(audio, "album"),
            "title": get_tag(audio, "title"),
            "trackno": get_tag(audio, "tracknumber"),
            "year": get_tag(audio, "date"),
        }
    except Exception as e:
        print(f"Error reading tags for {path}: {e}")
        return {}


def get_format_json(path):
    """Extract format information using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout).get("format", {})
    except Exception as e:
        print(f"Error running ffprobe for {path}: {e}")
        return {}


def gather_metadata(p):
    m = int(p.stat().st_mtime)
    tags = read_tags(p)
    fmt_json = json.dumps(get_format_json(p))
    # Prepare all DB fields and parsed format data for this file
    row = (
        str(p),
        normalize_string(p.stem),
        m,
        tags.get("artist"),
        tags.get("album"),
        tags.get("title"),
        tags.get("trackno"),
        tags.get("year"),
        fmt_json,
    )
    # Also parse format data for the formats and flac_tags tables
    try:
        fmt_data = json.loads(fmt_json) if fmt_json else {}
        formats_row = (
            str(p),
            fmt_data.get("nb_streams"),
            fmt_data.get("nb_programs"),
            fmt_data.get("nb_stream_groups"),
            fmt_data.get("format_name"),
            fmt_data.get("format_long_name"),
            fmt_data.get("start_time"),
            fmt_data.get("duration"),
            fmt_data.get("size"),
            fmt_data.get("bit_rate"),
            fmt_data.get("probe_score"),
        )
        tag_items = []
        for key, val in fmt_data.get("tags", {}).items():
            tag_items.append((str(p), key, val))
    except Exception:
        formats_row = None
        tag_items = []
    return (row, formats_row, tag_items)


def refresh_library(db_path, library_dir):
    """Refresh the FLAC library index with periodic progress updates and safe abort handling."""
    conn = sqlite3.connect(db_path)
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
            trackno TEXT,
            year TEXT,
            format_json TEXT
        )
        """
    )

    try:
        # Purge vanished files
        purged_files = 0
        for (p,) in cur.execute("SELECT path FROM flacs"):
            if not os.path.exists(p):
                cur.execute("DELETE FROM flacs WHERE path=?", (p,))
                purged_files += 1
        print(f"Purged {purged_files} vanished files.")

        # Scan files in parallel
        flacs = [p for p in Path(library_dir).rglob("*.flac")]
        to_scan = []
        for p in flacs:
            m = int(p.stat().st_mtime)
            cur.execute("SELECT mtime FROM flacs WHERE path=?", (str(p),))
            row = cur.fetchone()
            if not row or row[0] != m:
                to_scan.append(p)
        print(f"Rescanning {len(to_scan)} files...")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for i, result in enumerate(executor.map(gather_metadata, to_scan), start=1):
                results.append(result)
                if i % 100 == 0 or i == len(to_scan):
                    print(f"Processed {i}/{len(to_scan)} files...")

        # Write results in batch
        updated_files = 0
        for row, formats_row, tag_items in results:
            cur.execute(
                "REPLACE INTO flacs (path,norm,mtime,artist,album,title,trackno,year,format_json) VALUES (?,?,?,?,?,?,?,?,?)",
                row,
            )
            updated_files += 1
            if formats_row:
                cur.execute(
                    "REPLACE INTO formats (path, nb_streams, nb_programs, nb_stream_groups, format_name, format_long_name, start_time, duration, size, bit_rate, probe_score) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    formats_row,
                )
            cur.execute("DELETE FROM flac_tags WHERE path=?", (row[0],))
            for tag in tag_items:
                cur.execute(
                    "INSERT INTO flac_tags (path, tag_key, tag_value) VALUES (?,?,?)",
                    tag,
                )
        conn.commit()
        print(f"Updated {updated_files} files in the database.")

    except KeyboardInterrupt:
        print("Process interrupted. Committing partial updates...")
        conn.commit()
    finally:
        conn.close()


def list_entries(db_path, limit=None, where=None):
    """List entries in the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    query = "SELECT path, artist, album, title, year FROM flacs"
    if where:
        query += f" WHERE {where}"
    if limit:
        query += f" LIMIT {limit}"
    for row in cur.execute(query):
        print(" | ".join(str(x) if x else "" for x in row))
    conn.close()


def show_entry(db_path, path):
    """Show a single entry from the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM flacs WHERE path=?", (path,)).fetchone()
    conn.close()
    if row:
        columns = [desc[0] for desc in cur.description]
        print(json.dumps(dict(zip(columns, row)), indent=2))
    else:
        print(f"No entry found for {path}")


def main():
    parser = argparse.ArgumentParser(description="FLAC Cataloguing Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Resample command
    resample_parser = subparsers.add_parser(
        "resample", help="Batch resample problematic sample rates"
    )
    resample_parser.add_argument(
        "--db",
        default=str(Path.home() / ".flac_index.db"),
        help="Path to SQLite database",
    )
    resample_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying files",
    )

    # Refresh command
    refresh_parser = subparsers.add_parser(
        "refresh", help="Refresh the FLAC library index"
    )
    refresh_parser.add_argument(
        "--db",
        default=str(Path.home() / ".flac_index.db"),
        help="Path to SQLite database",
    )
    refresh_parser.add_argument(
        "--library", default="/Volumes/sad/MUSIC2", help="Path to FLAC library"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List entries in the database")
    list_parser.add_argument(
        "--db",
        default=str(Path.home() / ".flac_index.db"),
        help="Path to SQLite database",
    )
    list_parser.add_argument("--limit", type=int, help="Limit the number of results")
    list_parser.add_argument("--where", help="SQL WHERE clause to filter results")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show details for a single entry")
    show_parser.add_argument(
        "--db",
        default=str(Path.home() / ".flac_index.db"),
        help="Path to SQLite database",
    )
    show_parser.add_argument("path", help="Path to the FLAC file")

    args = parser.parse_args()

    if args.command == "refresh":
        refresh_library(args.db, args.library)
    elif args.command == "list":
        list_entries(args.db, args.limit, args.where)
    elif args.command == "show":
        show_entry(args.db, args.path)
    elif args.command == "resample":
        batch_resample(args.db, args.dry_run)


if __name__ == "__main__":
    main()
