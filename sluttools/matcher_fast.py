#!/usr/bin/env python3
"""
Fast playlist→FLAC matcher (cached index, transparent by default).

- Incremental SQLite index of your FLAC library
- Exact by normalized stem → guarded substring/token-overlap → fuzzy (rapidfuzz if present)
- Default transparency: one line per track, plus top-K candidates
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --------- Optional rich progress (falls back to prints) ---------
try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    console = Console()

    def info(msg):
        # print with rich if available; otherwise strip simple [tags]
        if console:
            console.print(msg)
        else:
            import re as _re

            print(_re.sub(r"\[[^\]]+\]", "", str(msg)))

    def start_progress(desc: str):
        p = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=False,
        )
        p.start()
        tid = p.add_task(desc, total=None)
        return p, tid

    def stop_progress(p):
        p.stop()

    def track_iter(desc: str, total: int):
        p = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            transient=False,
        )
        p.start()
        tid = p.add_task(desc, total=total)

        def adv():
            p.advance(tid)

        def end():
            p.stop()

        return adv, end

except Exception:
    console = None

    def info(msg):
        import re as _re

        print(_re.sub(r"\[[^\]]+\]", "", str(msg)))

    def start_progress(desc: str):
        print(desc + " ...")
        return None, None

    def stop_progress(p): ...
    def track_iter(desc: str, total: int):
        c = {"i": 0}

        def adv():
            c["i"] += 1
            if c["i"] % 50 == 0 or c["i"] == total:
                print(f"{desc}: {c['i']}/{total}")

        def end(): ...

        return adv, end


# --------- Fuzzy matcher backend ---------
try:
    from rapidfuzz import fuzz as rf_fuzz

    def ratio(a, b):
        return rf_fuzz.ratio(a, b)

except Exception:
    try:
        from fuzzywuzzy import fuzz as fw_fuzz

        def ratio(a, b):
            return fw_fuzz.ratio(a, b)

        info("[yellow]rapidfuzz not installed; using fuzzywuzzy (slower).[/yellow]")
    except Exception:

        def ratio(a, b):
            return 0


# --------- Defaults ---------
DEFAULT_LIBRARY = os.environ.get("SLUTTOOLS_FLAC_DIR", "/Volumes/sad/MUSIC")
DEFAULT_DB = os.environ.get("SLUTTOOLS_FLAC_DB", str(Path.home() / "flibrary.db"))
AUTO_MATCH_THRESHOLD = int(os.environ.get("SLUTTOOLS_AUTO_THRESHOLD", "65"))

# --------- Utils ---------


def ellipsize(s: str, width: int) -> str:
    if width is None or width <= 4 or len(s) <= width:
        return s
    head = max(1, int(width * 0.6) - 2)
    tail = width - head - 3
    return s[:head] + "..." + s[-tail:]


def fmt_path(p: Optional[str], path_col: str, relative_root: Optional[str]) -> str:
    if not p:
        return ""
    if path_col == "basename":
        return Path(p).name
    if path_col == "relative" and relative_root:
        try:
            return os.path.relpath(p, start=relative_root)
        except Exception:
            return p
    return p


def normalize_string(s: str) -> str:
    if not s:
        return ""
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^\w\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_search_string(entry: Dict[str, str]) -> str:
    parts = []
    for k in ("artist", "album", "track", "title"):
        v = entry.get(k) or ""
        if v:
            parts.append(v)
    return " ".join(parts).strip()


# strip versions/years/brackets/feat
JUNK_PAT = re.compile(
    r"""
    (\s*-\s*(remaster(ed)?|mono|stereo|single\s+version|album\s+version)\b.*$)|
    (\s*\((bonus|deluxe|remaster(ed)?|\d{4}|live|edit|radio|extended|remix|mix|version)\)[\s-]*)|
    (\s*\[(bonus|deluxe|remaster(ed)?|\d{4}|live|edit|radio|extended|remix|mix|version)]\s*-*)|
    (\s+feat\.?\s+[^()\[\]]+)$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def strip_junk(s: str) -> str:
    return normalize_string(JUNK_PAT.sub("", s or ""))


def build_alt_keys(entry: dict) -> list[str]:
    title = (entry.get("track") or entry.get("title") or "").strip()
    artist = (entry.get("artist") or "").strip()
    keys: list[str] = []
    if title and artist:
        keys.append(strip_junk(f"{artist} {title}"))
    if title:
        keys.append(strip_junk(title))
    keys.append(strip_junk(build_search_string(entry)))  # fallback combined
    out, seen = [], set()
    for k in keys:
        if k and k not in seen:
            out.append(k)
            seen.add(k)
    return out


# path quality heuristics for substring step
GENERIC_PAT = re.compile(
    r"\[unknown artist\]|\(xxxx\)\s*\[unknown album\]|/unknown/|/various/",
    re.IGNORECASE,
)


def is_generic_path(p: str) -> bool:
    return GENERIC_PAT.search(p.replace("\\", "/")) is not None


def token_overlap(q_norm: str, lib_norm: str, min_tok: int = 2) -> bool:
    qtoks = [t for t in q_norm.split() if len(t) >= 3]
    if not qtoks:
        return False
    ltoks = set(t for t in lib_norm.split() if len(t) >= 3)
    common = sum(1 for t in qtoks if t in ltoks)
    return common >= min_tok


# --------- SQLite index ---------
def open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS flacs (path TEXT PRIMARY KEY, norm TEXT NOT NULL, mtime INTEGER NOT NULL)"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)"""
    )
    return conn


def meta_get(
    conn: sqlite3.Connection, key: str, default: Optional[str] = None
) -> Optional[str]:
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


def iter_flacs(root: str):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False) and e.name.lower().endswith(
                        ".flac"
                    ):
                        # ignore AppleDouble metadata files
                        if e.name.startswith("._"):
                            continue
                        try:
                            yield e.path, int(e.stat().st_mtime)
                        except FileNotFoundError:
                            continue
        except (PermissionError, FileNotFoundError):
            continue


def refresh_library(library_dir: str, db_path: str) -> int:
    conn = open_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT path FROM flacs")
    to_delete = [(p,) for (p,) in cur.fetchall() if not os.path.exists(p)]
    if to_delete:
        cur.executemany("DELETE FROM flacs WHERE path=?", to_delete)

    batch_new = []
    batch_upd = []
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
                    cur.executemany(
                        "INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)",
                        batch_new,
                    )
                    batch_new.clear()
                if batch_upd:
                    cur.executemany(
                        "UPDATE flacs SET norm=?, mtime=? WHERE path=?", batch_upd
                    )
                    batch_upd.clear()
                conn.commit()
    finally:
        if p:
            stop_progress(p)

    if batch_new:
        cur.executemany(
            "INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)", batch_new
        )
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
    encodings = ("utf-8", "iso-8859-1", "windows-1252")
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tracks.append(
                            {"artist": "", "album": "", "track": line, "title": ""}
                        )
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
            out.append(
                {
                    "artist": r.get("artist", ""),
                    "album": r.get("album", ""),
                    "track": r.get("track", ""),
                    "title": r.get("title", ""),
                }
            )
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
                out.append(
                    {
                        "track": row.get("track") or row.get("title", ""),
                        "artist": row.get("artist", ""),
                        "album": row.get("album", ""),
                        "title": row.get("title", ""),
                    }
                )
        return Path(file_path).stem, out
    except Exception as e:
        info(f"[red]Error reading CSV: {e}[/red]")
        return Path(file_path).stem, []


def parse_xlsx_playlist(file_path: str):
    out = []
    try:
        import pandas as pd

        df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            out.append(
                {
                    "track": row.get("track") or row.get("title", ""),
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                    "title": row.get("title", ""),
                }
            )
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
    if ext in (".xlsx", ".xls"):
        return parse_xlsx_playlist(path)
    info("[red]Unsupported playlist format.[/red]")
    return Path(path).stem, []


# --------- Matching ---------
def build_exact_map(lookup: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    exact: Dict[str, List[str]] = {}
    for pth, norm in lookup:
        exact.setdefault(norm, []).append(pth)
    return exact


@dataclass
class MatchInfo:
    path: Optional[str]
    method: str  # "exact" | "substr" | "fuzzy" | "none"
    score: int
    key_used: str
    topk: Optional[List[Tuple[int, str]]] = None  # [(score, path)]


def match_entry(
    entry: Dict[str, str],
    exact_map: Dict[str, List[str]],
    lookup: List[Tuple[str, str]],
    threshold: int,
    want_topk: int = 0,
    allow_substr: bool = True,
) -> MatchInfo:
    keys = build_alt_keys(entry)
    if not keys:
        return MatchInfo(None, "none", 0, "", None)

    # 1) exact
    for k in keys:
        hit = exact_map.get(k)
        if hit:
            return MatchInfo(hit[0], "exact", 100, k, None)

    # 2) guarded substring/token overlap
    if allow_substr:
        for k in keys:
            if len(k) >= 8:
                for pth, norm_lib in lookup:
                    if is_generic_path(pth):
                        continue
                    if token_overlap(k, norm_lib, min_tok=2):
                        return MatchInfo(pth, "substr", 100, k, None)

    # 3) fuzzy
    best_score, best_path, best_key = 0, None, keys[0]

    def adjust(sc: int, pth: str, key_used: str) -> int:
        """Bias toward right artist/title, penalize generic dump paths."""
        base = sc
        name = Path(pth).name.lower()
        bonus = 0
        artist = (entry.get("artist") or "").lower().strip()
        if artist and artist.split()[0] in name:
            bonus += 10
        # if a long token from the query key is in the filename, nudge up
        for t in key_used.split():
            if len(t) >= 5 and t in name:
                bonus += 5
                break
        penalty = 15 if is_generic_path(pth) else 0
        return max(0, min(100, int(base + bonus - penalty)))

    collected: List[Tuple[int, str]] = []
    for k in keys:
        for pth, norm_lib in lookup:
            sc = ratio(k, norm_lib)
            adj = adjust(int(sc), pth, k)
            if want_topk:
                collected.append((int(sc), pth))
            if adj > best_score:
                best_score, best_path, best_key = adj, pth, k
                if best_score >= 95 and not want_topk:
                    return MatchInfo(
                        best_path, "fuzzy", int(best_score), best_key, None
                    )
    topk = None
    if want_topk and collected:
        collected.sort(key=lambda x: x[0], reverse=True)
        topk = collected[:want_topk]
    if best_path and best_score >= threshold:
        return MatchInfo(best_path, "fuzzy", int(best_score), best_key, topk)
    return MatchInfo(None, "none", int(best_score), best_key, topk)


# --------- Exporters ---------
def write_m3u(out_path: str, matched_paths: List[str]) -> None:
    if not out_path.lower().endswith(".m3u"):
        out_path += ".m3u"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for p in matched_paths:
            f.write(p + "\n")
    info(f"[green]Created M3U:[/green] {out_path}")


def export_songshift_json(
    entries: List[Dict[str, str]],
    matched: List[Optional[str]],
    output_json: str,
    playlist_name: str,
    service: str = "qobuz",
) -> None:
    tracks = []
    for i, m in enumerate(matched):
        if m is None:
            e = entries[i]
            title = e.get("track") or e.get("title") or ""
            artist = (e.get("artist") or "Unknown Artist").strip()
            if title:
                tracks.append({"artist": artist, "track": title.strip()})
    payload = [
        {"service": service, "serviceId": None, "name": playlist_name, "tracks": tracks}
    ]
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    info(
        f"[green]✓ JSON playlist saved:[/green] {output_json}  ([bold]{len(tracks)}[/bold] tracks)"
    )


# --------- CLI ---------
def run_match(args):
    db_path = args.db
    lib_dir = args.library
    stale = args.stale_seconds
    threshold = args.threshold if args.threshold is not None else AUTO_MATCH_THRESHOLD

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
    else:
        info("[green]Skipping refresh; using cached index.[/green]")

    lookup = fetch_lookup(db_path)
    exact_map = build_exact_map(lookup)
    info(f"[green]FLAC index entries:[/green] {len(lookup)}")

    src = args.input
    entries = []
    playlist_name = Path(src).stem
    if os.path.isdir(src):
        info(f"[cyan]Scanning directory as playlist:[/cyan] {src}")
        for p in Path(src).rglob("*.*"):
            if p.suffix.lower() in (".flac", ".mp3", ".wav", ".m4a", ".aac"):
                entries.append(
                    {
                        "artist": "",
                        "album": "",
                        "track": p.name,
                        "title": "",
                        "path": str(p),
                    }
                )
        info(f"[green]Found {len(entries)} audio files[/green]")
    else:
        playlist_name, entries = parse_playlist_file(src)
        info(f"[green]Loaded {len(entries)} track(s) from[/green] {playlist_name}")

    total = len(entries)
    matched: List[Optional[str]] = [None] * total
    explains: List[MatchInfo] = [
        MatchInfo(None, "none", 0, "", None) for _ in range(total)
    ]

    adv, end = track_iter("Matching tracks", total=total)
    for i, e in enumerate(entries, 1):
        mi = match_entry(
            e,
            exact_map,
            lookup,
            threshold,
            want_topk=(args.topk or 0) if args.explain else 0,
            allow_substr=args.allow_substr,
        )
        explains[i - 1] = mi
        matched[i - 1] = mi.path
        adv()
    end()

    n_matched = sum(1 for m in matched if m)
    n_unmatched = total - n_matched
    info(
        f"[bold green]{n_matched} matched[/bold green], [bold red]{n_unmatched} unmatched[/bold red]"
    )

    # --------- views ---------
    def as_query(e):
        title = (e.get("track") or e.get("title") or "").strip()
        artist = (e.get("artist") or "").strip()
        return (artist + " - " + title).strip(" -")

    def print_compact(rows_idx):
        try:
            from rich.table import Table
        except Exception:
            Table = None
        # If rich.Table is unavailable OR console is disabled (e.g., --no-color), use plain text fallback
        if Table is None or not console:
            header = f"{'#':>3}  {'Query':<40}  {'Match':<30}  {'How':<6}  {'Score':>5}"
            info(header)
            for i in rows_idx:
                e = entries[i]
                mi = explains[i]
                q = ellipsize(as_query(e), args.truncate)
                path_disp = ellipsize(
                    fmt_path(mi.path, args.path_col, args.relative_root), args.truncate
                )
                how = mi.method if mi.path else "UNMATCHED"
                sc = f"{mi.score}" if mi.path else "-"
                info(f"{i+1:03d}  {q:<40}  {path_disp:<30}  {how:<6}  {sc:>5}")
            return
        # rich table
        tbl = Table(show_header=True, header_style="bold", box=None)
        tbl.add_column("#", justify="right", no_wrap=True)
        tbl.add_column("Query")
        tbl.add_column("Match")
        tbl.add_column("How", no_wrap=True)
        tbl.add_column("Score", justify="right", no_wrap=True)
        for i in rows_idx:
            e = entries[i]
            mi = explains[i]
            q = ellipsize(as_query(e), args.truncate)
            path_disp = ellipsize(
                fmt_path(mi.path, args.path_col, args.relative_root), args.truncate
            )
            how = mi.method if mi.path else "[red]UNMATCHED[/red]"
            sc = str(mi.score) if mi.path else "-"
            tbl.add_row(f"{i+1:03d}", q, path_disp, how, sc)
        console.print(tbl)

    if args.explain:
        if args.view == "full":
            for i, e in enumerate(entries):
                mi = explains[i]
                q = as_query(e)
                if mi.path:
                    path_disp = fmt_path(mi.path, args.path_col, args.relative_root)
                    info(
                        f"[green]{i+1:03d}[/green] {ellipsize(q, args.truncate)}  →  [cyan]{ellipsize(path_disp, args.truncate)}[/cyan]  "
                        f"[dim]({mi.method}, score={mi.score}, key='{ellipsize(mi.key_used, args.truncate)}')[/dim]"
                    )
                    if args.topk and mi.topk:
                        tops = ", ".join(
                            f"{s}:{Path(p).name}" for s, p in mi.topk[: args.topk]
                        )
                        info(f"      top{args.topk}: {ellipsize(tops, args.truncate)}")
                else:
                    info(
                        f"[red]{i+1:03d}[/red] {ellipsize(q, args.truncate)}  →  [bold]UNMATCHED[/bold]  "
                        f"[dim](best_score={mi.score}, key='{ellipsize(mi.key_used, args.truncate)}')[/dim]"
                    )
        else:
            if args.view == "unmatched":
                rows = [i for i, mi in enumerate(explains) if not mi.path]
                if not rows:
                    info("No unmatched tracks.")  # quick message instead of empty table
                    return
            else:  # compact (default)
                rows = list(range(len(entries)))
            print_compact(rows)

    if args.print_paths:
        for p in (m for m in matched if m):
            print(p)

    if args.m3u:
        final_paths = [m for m in matched if m]
        if final_paths:
            write_m3u(args.m3u, final_paths)
        else:
            info("[yellow]No matches to write to M3U.[/yellow]")

    if args.export_unmatched:
        if n_unmatched:
            export_songshift_json(
                entries,
                matched,
                args.export_unmatched,
                playlist_name=playlist_name,
                service=args.service,
            )
        else:
            info("[green]No unmatched tracks to export.[/green]")


def main():
    ap = argparse.ArgumentParser(
        prog="matcher_fast.py", description="Fast playlist→FLAC matcher (cached index)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    apm = sub.add_parser(
        "match", help="Match a playlist or directory against the FLAC library"
    )
    apm.add_argument(
        "input", help="Path to playlist file (.json/.m3u/.csv/.xlsx) or a directory"
    )
    apm.add_argument(
        "--library",
        default=DEFAULT_LIBRARY,
        help=f"FLAC library root (default: {DEFAULT_LIBRARY})",
    )
    apm.add_argument(
        "--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})"
    )
    apm.add_argument(
        "--refresh",
        choices=("auto", "yes", "no"),
        default="auto",
        help="Refresh index: auto (only if stale), yes (force), no (skip)",
    )
    apm.add_argument(
        "--stale-seconds",
        type=int,
        default=21600,
        help="Index staleness window (default: 6h)",
    )
    apm.add_argument("--m3u", default=None, help="Write matched result to this .m3u")
    apm.add_argument(
        "--export-unmatched",
        default=None,
        help="Write unmatched as SongShift JSON to this path",
    )
    apm.add_argument(
        "--service",
        default="qobuz",
        help="Service label for exported JSON (default: qobuz)",
    )
    apm.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Fuzzy accept threshold (overrides env)",
    )
    # views & transparency defaults
    apm.add_argument(
        "--view",
        choices=("compact", "unmatched", "full"),
        default="compact",
        help="How to render results: compact table (default), only unmatched, or full verbose",
    )
    apm.add_argument(
        "--no-explain",
        dest="explain",
        action="store_false",
        help="Disable per-track output",
    )
    apm.add_argument(
        "--topk",
        type=int,
        default=5,
        help="When --view full, show top-K candidates (0=off)",
    )
    apm.add_argument(
        "--truncate", type=int, default=80, help="Max column width; 0 = no truncation"
    )
    apm.add_argument(
        "--path-col",
        choices=("basename", "relative", "full"),
        default="basename",
        help="How to display matched path",
    )
    apm.add_argument(
        "--relative-root",
        default=None,
        help="Base directory used when --path-col=relative",
    )
    apm.add_argument("--no-color", action="store_true", help="Disable colored output")
    apm.add_argument(
        "--print-paths", action="store_true", help="Print only matched paths to stdout"
    )
    # control substring fast path
    apm.add_argument(
        "--no-substr",
        dest="allow_substr",
        action="store_false",
        help="Disable guarded substring/token-overlap fast path",
    )
    apm.set_defaults(explain=True, allow_substr=True)

    args = ap.parse_args()
    if getattr(args, "no_color", False) and console:
        # crude: strip color tags by disabling console and info() already strips tags on fallback
        globals()["console"] = None
    if args.cmd == "match":
        run_match(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        info("[red]Interrupted by user. Exiting.[/red]")
        sys.exit(130)
