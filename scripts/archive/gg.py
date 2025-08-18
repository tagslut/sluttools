#!/usr/bin/env python3
# Script: Animated interactive matcher prototype (archived); kept for historical reference.
import os
import sys
import json
import glob
import sqlite3
import time
import asyncio
import unicodedata
from pathlib import Path

import aiofiles
from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# fuzzy matching backend: prefer rapidfuzz
try:
    from rapidfuzz import fuzz as rf_fuzz

    def ratio(a, b):
        return rf_fuzz.ratio(a, b)

    def partial_ratio(a, b):
        return rf_fuzz.partial_ratio(a, b)

    def token_set_ratio(a, b):
        return rf_fuzz.token_set_ratio(a, b)
except ImportError:
    from fuzzywuzzy import fuzz as fw_fuzz  # slower fallback

    def ratio(a, b):
        return fw_fuzz.ratio(a, b)

    def partial_ratio(a, b):
        return fw_fuzz.partial_ratio(a, b)

    def token_set_ratio(a, b):
        return fw_fuzz.token_set_ratio(a, b)

    Console().print("[yellow]Warning: rapidfuzz not installed; falling back to fuzzywuzzy (slower).[/yellow]")

from mutagen import File as MutagenFile  # audio metadata

################################################################################
# CONFIG
################################################################################

console = Console()
FLAC_LIBRARY_DIR = "/Volumes/sad/MUSIC"
AUTO_MATCH_THRESHOLD = 65
DB_PATH = Path.home() / "/Users/georgeskhawam/Library/Mobile Documents/com~apple~CloudDocs/flibrary.db"
CACHE_REFRESH_SECONDS = 3600  # if you want time-based refresh when not using file mtime

################################################################################
# SAFE INPUT HELPERS
################################################################################

def safe_prompt(prompt_text, default=None):
    if default is not None:
        answer = Prompt.ask(prompt_text, default=default)
    else:
        answer = Prompt.ask(prompt_text)
    if answer.strip().lower() == "abort":
        console.print("[bold red]Process aborted by user.[/bold red]")
        sys.exit(0)
    return answer

def safe_confirm(prompt_text, default=True):
    default_str = "y" if default else "n"
    answer = Prompt.ask(f"{prompt_text} (y/n) [or type 'abort' to exit]", default=default_str)
    if answer.strip().lower() == "abort":
        console.print("[bold red]Process aborted by user.[/bold red]")
        sys.exit(0)
    return answer.strip().lower() in ["y", "yes"]

################################################################################
# INTRO ANIMATION
################################################################################

def render_design_box(offset: int) -> Text:
    total_width = 70
    interior_width = total_width - 2
    text_content = "♫ GEORGIE'S PLAYLIST MAGIC BOX ♫"
    text_length = len(text_content)
    total_padding = interior_width - text_length
    pad_left = total_padding // 2
    pad_right = total_padding - pad_left

    def animate_text(text: str, offset: int) -> Text:
        colors = ["red", "yellow", "blue"]
        animated = Text()
        for i, ch in enumerate(text):
            animated.append(ch, style=f"bold {colors[(i + offset) % len(colors)]}")
        return animated

    box = Text()
    top_line = Text("─" * total_width, style="bold green")
    box.append(top_line + "\n")

    heart_colors = ["red", "yellow", "blue"]
    for i in range(3):
        line = Text()
        line.append("♥", style=f"bold {heart_colors[i]}")
        line.append(" " * pad_left)
        line.append(animate_text(text_content, offset))
        line.append(" " * pad_right)
        line.append("♥", style=f"bold {heart_colors[i]}")
        box.append(line + "\n")

    arabic_text = "هذا من فضل ربي"
    arabic_length = len(arabic_text)
    available = total_width - arabic_length
    dashes_each = available // 2
    bottom_line = Text("─" * dashes_each, style="bold green")
    bottom_line.append(arabic_text, style="bold dark_green")
    bottom_line.append("─" * dashes_each, style="bold green")
    box.append(bottom_line)
    return box

class PlaylistUI:
    def __init__(self):
        self.console = Console()

    async def animate_title(self, refresh_rate: float = 0.2, wait_time: float = 4.0):
        start_time = asyncio.get_event_loop().time()
        enter_future = asyncio.get_event_loop().run_in_executor(None, input, "")
        with Live(console=self.console, refresh_per_second=int(1 / refresh_rate)) as live:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                offset = int(elapsed * 2)
                box_text = render_design_box(offset)
                if elapsed >= wait_time:
                    if int(elapsed / refresh_rate) % 2 == 0:
                        prompt_text = "ENTER"
                    else:
                        prompt_text = "     "
                    pad_left = (70 - len("ENTER")) // 2
                    enter_line = " " * pad_left + prompt_text
                    combined = Text()
                    combined.append(box_text)
                    combined.append("\n\n")
                    combined.append(enter_line, style="bold dark_grey")
                    live.update(Align.center(combined))
                else:
                    live.update(Align.center(box_text))
                if enter_future.done():
                    break
                await asyncio.sleep(refresh_rate)

################################################################################
# SQLITE FLAC INDEX (delta-scan)
################################################################################

def open_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flacs (
            path TEXT PRIMARY KEY,
            norm TEXT NOT NULL,
            mtime INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    return conn

def normalize_string(s: str) -> str:
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return __import__("re").sub(r"[^\w\s]+", " ", s).strip()

def refresh_library(library_dir: str):
    conn = open_db()
    cur = conn.cursor()

    # 1) remove missing
    cur.execute("SELECT path FROM flacs")
    for (path,) in cur.fetchall():
        if not os.path.exists(path):
            cur.execute("DELETE FROM flacs WHERE path=?", (path,))

    # 2) add/update changed
    flac_paths = list(Path(library_dir).rglob("*.flac"))
    for p in flac_paths:
        p_str = str(p)
        mtime = int(p.stat().st_mtime)
        cur.execute("SELECT mtime FROM flacs WHERE path=?", (p_str,))
        row = cur.fetchone()
        norm = normalize_string(p.stem)
        if not row:  # new
            cur.execute("INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)", (p_str, norm, mtime))
        elif row[0] != mtime:  # modified
            cur.execute("UPDATE flacs SET norm=?, mtime=? WHERE path=?", (norm, mtime, p_str))
    conn.commit()
    conn.close()

def get_flac_lookup():
    conn = open_db()
    cur = conn.cursor()
    cur.execute("SELECT path, norm FROM flacs")
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (path, norm)

def get_last_n_flacs(n=100):
    conn = open_db()
    cur = conn.cursor()
    cur.execute("SELECT path, norm, mtime FROM flacs ORDER BY rowid DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    console.print(f"[bold cyan]Last {len(rows)} entries from FLAC DB:[/bold cyan]")
    for path, norm, mtime in rows:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        console.print(f"{t} | {norm} → {path}")

################################################################################
# PLAYLIST PARSING
################################################################################

async def parse_m3u_file(file_path):
    tracks = []
    encodings = ["utf-8", "iso-8859-1", "windows-1252"]
    for enc in encodings:
        try:
            async with aiofiles.open(file_path, "r", encoding=enc) as fh:
                lines = await fh.readlines()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tracks.append({"artist": "", "album": "", "track": line, "title": ""})
            nm = os.path.splitext(os.path.basename(file_path))[0]
            return nm, tracks
        except UnicodeDecodeError:
            continue
        except Exception as e2:
            console.print(f"[red]Error reading M3U: {e2}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []

async def parse_json_file(file_path):
    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as jf:
            cont = await jf.read()
            data = json.loads(cont)
            if isinstance(data, list):
                data = data[0]
            nm = data.get("name", os.path.splitext(os.path.basename(file_path))[0])
            raw = data.get("tracks", [])
            out = []
            for r in raw:
                out.append({
                    "artist": r.get("artist", ""),
                    "album": r.get("album", ""),
                    "track": r.get("track", ""),
                    "title": r.get("title", "")
                })
            return nm, out
    except Exception as ex:
        console.print(f"[red]Error reading JSON: {ex}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []

async def parse_csv_file(file_path):
    out = []
    try:
        with open(file_path, "r", encoding="utf-8") as cf:
            import csv
            rd = csv.DictReader(cf)
            for row in rd:
                out.append({
                    "track": row.get("track", row.get("title", "")),
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                    "title": row.get("title", "")
                })
        nm = os.path.splitext(os.path.basename(file_path))[0]
        return nm, out
    except Exception as e2:
        console.print(f"[red]Error reading CSV: {e2}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []

async def parse_xlsx_file(file_path):
    out = []
    try:
        import pandas as pd  # lazy
        df = pd.read_excel(file_path)
        nm = os.path.splitext(os.path.basename(file_path))[0]
        for _, row in df.iterrows():
            t = row.get("track", row.get("title", ""))
            a = row.get("artist", "")
            al = row.get("album", "")
            out.append({"track": t, "artist": a, "album": al, "title": row.get("title", "")})
        return nm, out
    except Exception as e2:
        console.print(f"[red]Error reading XLSX: {e2}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []

async def parse_playlist_file(file_path):
    ext = file_path.lower().split(".")[-1]
    if ext == "m3u":
        return await parse_m3u_file(file_path)
    elif ext == "json":
        return await parse_json_file(file_path)
    elif ext == "csv":
        return await parse_csv_file(file_path)
    elif ext in ("xlsx", "xls"):
        return await parse_xlsx_file(file_path)
    else:
        console.print("[bold red]Unsupported playlist format.[/bold red]")
        return os.path.splitext(os.path.basename(file_path))[0], []

def build_search_string(entry):
    parts = []
    for k in ["artist", "album", "track", "title"]:
        val = entry.get(k)
        if val:
            parts.append(val)
    return " ".join(parts).strip()

def match_entry(entry, flac_lookup):
    search = build_search_string(entry)
    if not search:
        return None
    search_norm = normalize_string(search)
    best_score = 0
    best_path = None
    for orig, norm in flac_lookup:
        if search_norm == norm:
            return orig  # exact
        score = ratio(search_norm, norm)
        if score > best_score:
            best_score = score
            best_path = orig
            if best_score >= 95:
                break  # early exit
    if best_score >= AUTO_MATCH_THRESHOLD:
        return best_path
    return None

################################################################################
# EXPORTERS
################################################################################

async def create_m3u_file(out_path, matched_paths):
    if not out_path.lower().endswith(".m3u"):
        out_path += ".m3u"
    try:
        async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
            await f.write("#EXTM3U\n")
            for p in matched_paths:
                await f.write(p + "\n")
        console.print(f"[bold green]Created M3U: {out_path}[/bold green]")
    except Exception as e2:
        console.print(f"[red]Error writing M3U: {e2}[/red]")

def export_songshift_json_from_entries(entries, matched, output_json, playlist_name="Unmatched Tracks", service="qobuz"):
    tracks = []
    for i, m in enumerate(matched):
        if m is None:
            entry = entries[i]
            title = entry.get("track") or entry.get("title") or ""
            artist = entry.get("artist") or "Unknown Artist"
            if title:
                tracks.append({"artist": artist.strip(), "track": title.strip()})
    payload = [{
        "service": service,
        "serviceId": None,
        "name": playlist_name,
        "tracks": tracks
    }]
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        console.print(f"[bold green]✓ JSON playlist saved:[/] {output_json}  ({len(tracks)} tracks)")
    except Exception as e:
        console.print(f"[red]Error writing JSON playlist: {e}[/red]")

################################################################################
# MAIN
################################################################################

async def main():
    console.clear()
    # Optionally show last 100 entries first
    if safe_confirm("[bold cyan]Show last 100 tracks from FLAC DB before proceeding?[/bold cyan]", default=False):
        get_last_n_flacs(100)

    # animated intro
    ui = PlaylistUI()
    await ui.animate_title(refresh_rate=0.2, wait_time=3.0)
    console.clear()

    path_in = safe_prompt("[bold yellow]Enter a path (folder or playlist file)[/bold yellow]").strip().strip("'\"")
    if not os.path.exists(path_in):
        console.print(f"[red]Invalid path: {path_in}[/red]")
        return

    entries = []
    source_name = os.path.basename(path_in)
    if os.path.isdir(path_in):
        console.print(f"[cyan]Scanning directory: {path_in}[/cyan]")
        # fallback to metadata-based scanning if needed
        entries = []
        # reuse a simple file scan (could be expanded)
        for p in Path(path_in).rglob("*.*"):
            if p.suffix.lower() in [".flac", ".mp3", ".wav", ".m4a", ".aac"]:
                entries.append({
                    "artist": "",
                    "album": "",
                    "track": p.name,
                    "title": "",
                    "path": str(p)
                })
        console.print(f"[green]Found {len(entries)} audio files in directory playlist mode[/green]")
        source_name = os.path.basename(os.path.normpath(path_in))
    else:
        nm, tracks = await parse_playlist_file(path_in)
        console.print(f"[green]Loaded {len(tracks)} track(s) from {nm}[/green]")
        if not tracks:
            return
        entries = tracks
        source_name = nm

    # Refresh FLAC library index (delta-scan)
    console.print(f"[cyan]Refreshing FLAC library index at {FLAC_LIBRARY_DIR}…[/cyan]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as prog:
        prog.add_task(description="Updating index", total=None)
        refresh_library(FLAC_LIBRARY_DIR)
    flac_lookup = get_flac_lookup()
    console.print(f"[green]FLAC index contains {len(flac_lookup)} entries[/green]")

    # Matching
    matched = [None] * len(entries)
    unmatched_indices = []
    total_entries = len(entries)
    console.print(f"[cyan]Attempting to match {total_entries} entries…[/cyan]")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        transient=False
    ) as progress:
        task = progress.add_task("Matching tracks", total=total_entries)
        for i, e in enumerate(entries, start=1):
            progress.update(task, description=f"Track {i}/{total_entries}")
            res = match_entry(e, flac_lookup)
            if res:
                matched[i - 1] = res
            else:
                unmatched_indices.append(i - 1)
            progress.advance(task)
    auto_matched_count = len([x for x in matched if x])
    auto_unmatched_count = total_entries - auto_matched_count
    console.print(f"[bold green]{auto_matched_count} matched[/bold green], [bold red]{auto_unmatched_count} unmatched[/bold red]")

    # Manual matching fallback
    if auto_unmatched_count > 0 and safe_confirm("[bold yellow]Attempt manual matching on unmatched tracks?[/bold yellow]"):
        manual_match_count = 0
        for idx in unmatched_indices:
            e = entries[idx]
            search_str = build_search_string(e)
            if not search_str:
                continue
            console.print(f"\n[cyan]Manual match for entry {idx+1}: '{search_str}'[/cyan]")
            # build candidate scores
            candidates = []
            for orig, norm in flac_lookup:
                sc = ratio(normalize_string(search_str), norm)
                candidates.append((orig, sc))
            candidates.sort(key=lambda x: x[1], reverse=True)
            top5 = candidates[:5]
            console.print("Top 5 candidates:")
            for i, (pth, rat) in enumerate(top5, 1):
                console.print(f"{i}) ratio={rat:.1f} -> {pth}")
            console.print("Enter choice [1..5], 's' skip, or manual path:")
            ans = safe_prompt("Choice")
            if ans.lower() in ["s", "skip"]:
                continue
            if ans.isdigit() and 1 <= int(ans) <= len(top5):
                matched[idx] = top5[int(ans)-1][0]
                manual_match_count += 1
            elif os.path.isfile(ans):
                matched[idx] = ans
                manual_match_count += 1
        console.print(f"[bold green]{manual_match_count} tracks manually matched.[/bold green]")

    # Export unmatched as SongShift JSON (minimal)
    if any(m is None for m in matched):
        if safe_confirm("[bold yellow]Export unmatched tracks as a SongShift-ready JSON playlist?[/bold yellow]"):
            json_name = f"{source_name}_songshift.json"
            # Assume service; you could prompt or infer
            service = "qobuz"
            export_songshift_json_from_entries(entries, matched, json_name, playlist_name=source_name, service=service)

    # Create M3U if there are final matches
    final_matches = [m for m in matched if m]
    if final_matches and safe_confirm("[bold yellow]Create .m3u with the current matched flacs?[/bold yellow]"):
        def_name = f"{source_name}_matched.m3u"
        outp = safe_prompt("M3U filename", default=def_name).strip().strip("'\"")
        await create_m3u_file(outp, final_matches)
    else:
        console.print("[yellow]Skipping M3U creation.[/yellow]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[red]Interrupted by user. Exiting.[/red]")
        sys.exit(0)