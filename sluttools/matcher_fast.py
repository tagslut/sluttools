#!/usr/bin/env python3
"""
Fast playlist→FLAC matcher (single-file, no animations, incremental index).

Features
- Incremental, cached SQLite index of your FLAC library
- Streaming filesystem walk with os.scandir (fast, low RAM)
- Exact match by normalized stem; fuzzy fallback via rapidfuzz (or fuzzywuzzy)
- Non‑interactive CLI:
    --refresh auto|yes|no      (default: auto = only if stale/empty)
    --stale-seconds 21600      (6h default staleness window)
    --m3u out.m3u              (write matched file paths to .m3u)
    --export-unmatched out.json (SongShift-style JSON of unmatched)
    --service qobuz|tidal|...  (label in JSON export; default qobuz)

Examples
    python matcher_fast.py match "/path/playlist.json" \
        --library "/Volumes/sad/MUSIC" --db "/Users/you/flibrary.db" \
        --m3u Minimal_Focus.m3u --export-unmatched Minimal_Focus_unmatched.json

    # Force skip refresh even if stale:
    python matcher_fast.py match "/path/playlist.json" --refresh no

    # Force refresh now:
    python matcher_fast.py match "/path/playlist.json" --refresh yes
"""
import os
import re
import csv
import sys
import json
import time
import argparse
import sqlite3
import unicodedata
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# --------- Optional rich progress (falls back to prints) ---------
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    console = Console()
    def info(msg): console.print(msg)
    def start_progress(desc: str):
        p = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=False)
        p.start()
        tid = p.add_task(desc, total=None)
        return p, tid
    def stop_progress(p): p.stop()
    def track_iter(desc: str, total: int):
        p = Progress(TextColumn("[progress.description]{task.description}"), BarColumn(), TimeElapsedColumn(), transient=False)
        p.start()
        tid = p.add_task(desc, total=total)
        def adv():
            p.advance(tid)
        def end():
            p.stop()
        return adv, end
except Exception:
    console = None
    def info(msg): print(msg)
    def start_progress(desc: str):
        print(desc + " ...")
        return None, None
    def stop_progress(p): return
    def track_iter(desc: str, total: int):
        count = {"i":0}
        def adv():
            count["i"] += 1
            if count["i"] % 50 == 0 or count["i"] == total:
                print(f"{desc}: {count['i']}/{total}")
        def end(): pass
        return adv, end

# --------- Fuzzy matcher backend ---------
try:
    from rapidfuzz import fuzz as rf_fuzz
    def ratio(a, b): return rf_fuzz.ratio(a, b)
except Exception:
    try:
        from fuzzywuzzy import fuzz as fw_fuzz
        def ratio(a, b): return fw_fuzz.ratio(a, b)
        info("[yellow]rapidfuzz not installed; using fuzzywuzzy (slower).[/yellow]")
    except Exception:
        def ratio(a, b): return 0

# --------- Defaults (env-overridable) ---------
DEFAULT_LIBRARY = os.environ.get("SLUTTOOLS_FLAC_DIR", "/Volumes/sad/MUSIC")
DEFAULT_DB = os.environ.get("SLUTTOOLS_FLAC_DB", str(Path.home() / "flibrary.db"))
AUTO_MATCH_THRESHOLD = int(os.environ.get("SLUTTOOLS_AUTO_THRESHOLD", "65"))

# --------- Utils ---------
def normalize_string(s: str) -> str:
    """Lowercase, strip accents, drop punctuation, collapse spaces."""
    if not s:
        return ""
    s = "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^\w\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def build_search_string(entry: Dict[str, str]) -> str:
    parts = []
    for k in ("artist","album","track","title"):
        v = entry.get(k) or ""
        if v: parts.append(v)
    return " ".join(parts).strip()

# Extra cleaning: strip versions, years, brackets, and trailing “feat. …”
JUNK_PAT = re.compile(
    r"""
    (\s*-\s*(remaster(ed)?|mono|stereo|single\s+version|album\s+version)\b.*$)|
    (\s*\((bonus|deluxe|remaster(ed)?|\d{4}|live|edit|radio|extended|remix|mix|version)\)[\s-]*)|
    (\s*\[(bonus|deluxe|remaster(ed)?|\d{4}|live|edit|radio|extended|remix|mix|version)\][\s-]*)|
    (\s+feat\.?\s+[^\(\)\[\]]+)$
    """,
    re.IGNORECASE | re.VERBOSE,
)

def strip_junk(s: str) -> str:
    return normalize_string(JUNK_PAT.sub("", s or ""))

def build_alt_keys(entry: dict) -> list[str]:
    """Generate robust normalized keys: artist+title, title-only, fallback combined."""
    title = (entry.get("track") or entry.get("title") or "").strip()
    artist = (entry.get("artist") or "").strip()
    keys: list[str] = []
    if title and artist:
        keys.append(strip_junk(f"{artist} {title}"))
    if title:
        keys.append(strip_junk(title))
    # fallback to raw combined string
    keys.append(strip_junk(build_search_string(entry)))
    # de-dup while preserving order
    seen = set(); out = []
    for k in keys:
        if k and k not in seen:
            out.append(k); seen.add(k)
    return out

# --------- SQLite index ---------
def open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flacs (
            path  TEXT PRIMARY KEY,
            norm  TEXT NOT NULL,
            mtime INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
    """)
    return conn

def meta_get(conn: sqlite3.Connection, key: str, default: Optional[str]=None) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT v FROM meta WHERE k=?", (key,))
    row = cur.fetchone()
    return row[0] if row else default

def meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES (?,?)", (key, str(value)))

def need_refresh(conn: sqlite3.Connection, stale_seconds: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM flacs")
    count = cur.fetchone()[0]
    if count == 0:
        return True
    last = meta_get(conn, "last_scan_ts", "0")
    try:
        last_i = int(last)
    except Exception:
        last_i = 0
    return (int(time.time()) - last_i) > stale_seconds

# --------- Filesystem scan ---------
def iter_flacs(root: str):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False) and e.name.lower().endswith(".flac"):
                        try:
                            yield e.path, int(e.stat().st_mtime)
                        except FileNotFoundError:
                            continue
        except (PermissionError, FileNotFoundError):
            continue

def refresh_library(library_dir: str, db_path: str) -> int:
    conn = open_db(db_path)
    cur = conn.cursor()

    # prune missing
    cur.execute("SELECT path FROM flacs")
    to_delete = []
    for (p,) in cur.fetchall():
        if not os.path.exists(p):
            to_delete.append((p,))
    if to_delete:
        cur.executemany("DELETE FROM flacs WHERE path=?", to_delete)

    batch_new, batch_upd = [], []
    commit_every = 2000
    seen = 0

    p, tid = start_progress("Updating index (streaming)")
    try:
        for p_str, mtime in iter_flacs(library_dir):
            seen += 1
            cur.execute("SELECT mtime FROM flacs WHERE path=?", (p_str,))
            row = cur.fetchone()
            if not row:
                norm = normalize_string(Path(p_str).stem)
                batch_new.append((p_str, norm, mtime))
            elif row[0] != mtime:
                norm = normalize_string(Path(p_str).stem)
                batch_upd.append((norm, mtime, p_str))

            if (len(batch_new) + len(batch_upd)) >= commit_every:
                if batch_new:
                    cur.executemany("INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)", batch_new)
                    batch_new.clear()
                if batch_upd:
                    cur.executemany("UPDATE flacs SET norm=?, mtime=? WHERE path=?", batch_upd)
                    batch_upd.clear()
                conn.commit()
    finally:
        if p: stop_progress(p)

    if batch_new:
        cur.executemany("INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)", batch_new)
    if batch_upd:
        cur.executemany("UPDATE flacs SET norm=?, mtime=? WHERE path=?", batch_upd)

    meta_set(conn, "last_scan_ts", str(int(time.time())))
    conn.commit()
    conn.close()

    info(f"[green]Index refreshed. Scanned {seen} candidate files.[/green]")
    return seen

def fetch_lookup(db_path: str) -> List[Tuple[str, str]]:
    conn = open_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT path, norm FROM flacs")
    rows = cur.fetchall()
    conn.close()
    return rows

# --------- Parsers ---------
def parse_m3u(file_path: str):
    tracks = []
    encodings = ("utf-8","iso-8859-1","windows-1252")
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tracks.append({"artist": "", "album": "", "track": line, "title": ""})
            return Path(file_path).stem, tracks
        except UnicodeDecodeError:
            continue
        except Exception as e:
            info(f"[red]Error reading M3U: {e}[/red]")
            break
    return Path(file_path).stem, tracks

def parse_json_playlist(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
        if isinstance(data, list):
            data = data[0]
        name = data.get("name", Path(file_path).stem)
        out = []
        for r in data.get("tracks", []):
            out.append({
                "artist": r.get("artist",""),
                "album":  r.get("album",""),
                "track":  r.get("track",""),
                "title":  r.get("title",""),
            })
        return name, out
    except Exception as e:
        info(f"[red]Error reading JSON: {e}[/red]")
        return Path(file_path).stem, []

def parse_csv_playlist(file_path: str):
    out = []
    try:
        with open(file_path, "r", encoding="utf-8") as cf:
            rd = csv.DictReader(cf)
            for row in rd:
                out.append({
                    "track": row.get("track") or row.get("title",""),
                    "artist": row.get("artist",""),
                    "album": row.get("album",""),
                    "title": row.get("title",""),
                })
        return Path(file_path).stem, out
    except Exception as e:
        info(f"[red]Error reading CSV: {e}[/red]")
        return Path(file_path).stem, []

def parse_xlsx_playlist(file_path: str):
    out = []
    try:
        import pandas as pd  # optional
        df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            out.append({
                "track": row.get("track") or row.get("title",""),
                "artist": row.get("artist",""),
                "album": row.get("album",""),
                "title": row.get("title",""),
            })
        return Path(file_path).stem, out
    except Exception as e:
        info(f"[yellow]XLSX read failed or pandas missing: {e}[/yellow]")
        return Path(file_path).stem, []

def parse_playlist_file(path: str):
    ext = Path(path).suffix.lower()
    if ext == ".m3u":
        return parse_m3u(path)
    if ext == ".json":
        return parse_json_playlist(path)
    if ext == ".csv":
        return parse_csv_playlist(path)
    if ext in (".xlsx",".xls"):
        return parse_xlsx_playlist(path)
    info("[red]Unsupported playlist format.[/red]")
    return Path(path).stem, []

# --------- Matching ---------
def build_exact_map(lookup: List[Tuple[str,str]]) -> Dict[str, List[str]]:
    exact: Dict[str, List[str]] = {}
    for pth, norm in lookup:
        exact.setdefault(norm, []).append(pth)
    return exact

def match_entry(entry: Dict[str,str], exact_map: Dict[str, List[str]],
                lookup: List[Tuple[str,str]], threshold: int) -> Optional[str]:
    keys = build_alt_keys(entry)
    if not keys:
        return None
    # 1) exact by any alt key
    for k in keys:
        hit = exact_map.get(k)
        if hit:
            return hit[0]
    # 2) cheap substring containment (fast path)
    for k in keys:
        if len(k) >= 8:  # avoid tiny tokens
            for pth, norm_lib in lookup:
                if k in norm_lib or norm_lib in k:
                    return pth
    # 3) fuzzy best match
    best_score, best_path = 0, None
    for k in keys:
        for pth, norm_lib in lookup:
            sc = ratio(k, norm_lib)
            if sc > best_score:
                best_score, best_path = sc, pth
                if best_score >= 95:
                    return best_path
    return best_path if best_score >= threshold else None

# --------- Exporters ---------
def write_m3u(out_path: str, matched_paths: List[str]) -> None:
    if not out_path.lower().endswith(".m3u"):
        out_path += ".m3u"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for p in matched_paths:
            f.write(p + "\n")
    info(f"[green]Created M3U:[/green] {out_path}")

def export_songshift_json(entries: List[Dict[str,str]], matched: List[Optional[str]],
                          output_json: str, playlist_name: str, service: str="qobuz") -> None:
    tracks = []
    for i, m in enumerate(matched):
        if m is None:
            e = entries[i]
            title = e.get("track") or e.get("title") or ""
            artist = (e.get("artist") or "Unknown Artist").strip()
            if title:
                tracks.append({"artist": artist, "track": title.strip()})
    payload = [{
        "service": service,
        "serviceId": None,
        "name": playlist_name,
        "tracks": tracks
    }]
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    info(f"[green]✓ JSON playlist saved:[/green] {output_json}  ([bold]{len(tracks)}[/bold] tracks)")

# --------- CLI ---------
def run_match(args):
    db_path = args.db
    lib_dir = args.library
    stale = args.stale_seconds
    threshold = (args.threshold
                 if getattr(args, "threshold", None) is not None
                 else AUTO_MATCH_THRESHOLD)

    info(f"[cyan]FLAC library:[/cyan] {lib_dir}")
    info(f"[cyan]Index DB:[/cyan] {db_path}")

    if args.refresh == "yes":
        refresh_library(lib_dir, db_path)
    elif args.refresh == "auto":
        conn = open_db(db_path)
        do = need_refresh(conn, stale)
        conn.close()
        if do:
            info("[yellow]Index looks stale or empty: refreshing…[/yellow]")
            refresh_library(lib_dir, db_path)
        else:
            info("[green]Using cached index.[/green]")
    else:  # "no"
        info("[green]Skipping refresh; using cached index.[/green]")

    lookup = fetch_lookup(db_path)
    exact_map = build_exact_map(lookup)
    info(f"[green]FLAC index entries:[/green] {len(lookup)}")

    # Load playlist/directory
    src = args.input
    entries: List[Dict[str,str]] = []
    playlist_name = Path(src).stem

    if os.path.isdir(src):
        info(f"[cyan]Scanning directory as playlist:[/cyan] {src}")
        for p in Path(src).rglob("*.*"):
            if p.suffix.lower() in (".flac",".mp3",".wav",".m4a",".aac"):
                entries.append({"artist":"","album":"","track":p.name,"title":"","path":str(p)})
        info(f"[green]Found {len(entries)} audio files[/green]")
    else:
        playlist_name, entries = parse_playlist_file(src)
        info(f"[green]Loaded {len(entries)} track(s) from[/green] {playlist_name}")

    total = len(entries)
    matched: List[Optional[str]] = [None]*total

    adv, end = track_iter("Matching tracks", total=total)
    for i, e in enumerate(entries, 1):
        matched[i-1] = match_entry(e, exact_map, lookup, threshold)
        adv()
    end()

    n_matched = sum(1 for m in matched if m)
    n_unmatched = total - n_matched
    info(f"[bold green]{n_matched} matched[/bold green], [bold red]{n_unmatched} unmatched[/bold red]")

    if args.m3u:
        final_paths = [m for m in matched if m]
        if final_paths:
            write_m3u(args.m3u, final_paths)
        else:
            info("[yellow]No matches to write to M3U.[/yellow]")

    if args.export_unmatched:
        if n_unmatched:
            export_songshift_json(entries, matched, args.export_unmatched,
                                  playlist_name=playlist_name, service=args.service)
        else:
            info("[green]No unmatched tracks to export.[/green]")

def main():
    ap = argparse.ArgumentParser(prog="matcher_fast.py", description="Fast playlist→FLAC matcher (cached index).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_match = sub.add_parser("match", help="Match a playlist or directory against the FLAC library")
    ap_match.add_argument("input", help="Path to playlist file (.json/.m3u/.csv/.xlsx) or a directory")
    ap_match.add_argument("--library", default=DEFAULT_LIBRARY, help=f"FLAC library root (default: {DEFAULT_LIBRARY})")
    ap_match.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    ap_match.add_argument("--refresh", choices=("auto","yes","no"), default="auto",
                          help="Refresh index: auto (only if stale), yes (force), no (skip)")
    ap_match.add_argument("--stale-seconds", type=int, default=21600, help="Index staleness window (default: 6h)")
    ap_match.add_argument("--m3u", default=None, help="Write matched result to this .m3u")
    ap_match.add_argument("--export-unmatched", default=None, help="Write unmatched as SongShift JSON to this path")
    ap_match.add_argument("--service", default="qobuz", help="Service label for exported JSON (default: qobuz)")
    ap_match.add_argument("--threshold", type=int, default=None, help="Fuzzy accept threshold (overrides env)")

    args = ap.parse_args()
    if args.cmd == "match":
        run_match(args)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        info("[red]Interrupted by user. Exiting.[/red]")
        sys.exit(130)
