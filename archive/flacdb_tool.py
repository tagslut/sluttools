#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path

def refresh_library(db_path, library_dir):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS flacs (path TEXT PRIMARY KEY, norm TEXT NOT NULL, mtime INTEGER NOT NULL)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")

    for p in Path(library_dir).rglob("*.flac"):
        mtime = int(p.stat().st_mtime)
        norm = p.stem.lower()
        cur.execute("REPLACE INTO flacs (path, norm, mtime) VALUES (?, ?, ?)", (str(p), norm, mtime))

    conn.commit()
    conn.close()

def list_flacs(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for row in cur.execute("SELECT path, norm, mtime FROM flacs"):
        print(row)
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="FLAC DB Tool")
    parser.add_argument("command", choices=["refresh", "list"], help="Command to execute")
    parser.add_argument("--db", default=str(Path.home() / ".flac_index.db"), help="Path to SQLite database")
    parser.add_argument("--library", default=str(Path.home() / "Projects" / "MusicAutomation" / "mishmash"), help="Path to FLAC library")

    args = parser.parse_args()

    if args.command == "refresh":
        refresh_library(args.db, args.library)
    elif args.command == "list":
        list_flacs(args.db)

if __name__ == "__main__":
    main()
