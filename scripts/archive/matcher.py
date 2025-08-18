#!/usr/bin/env python3
# Script: Legacy full-featured matcher prototype kept for reference (archived).
import os
import re
import glob
import csv
import json
import random
import asyncio
import aiofiles
import unicodedata
import logging
import sys
import sqlite3
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import time
from collections import defaultdict
from typing import List, Optional, Union, Tuple, Dict, Set, Any
from tqdm import tqdm

import pandas as pd
from fuzzywuzzy import fuzz
from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.align import Align
from mutagen._file import File as MutagenFile  # For audio metadata

################################################################################
# CONFIGURATION
################################################################################

console = Console()

# Configure rotating file logging to a safe location
try:
    downloads_dir = Path.home() / "Downloads"
    log_dir = downloads_dir if downloads_dir.is_dir() else (Path.home() / ".sluttools" / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "script.log"
    file_handler = RotatingFileHandler(str(log_path), maxBytes=1024 * 1024, backupCount=5, encoding="utf-8")
    logging.getLogger().addHandler(file_handler)
except Exception:
    # Fallback to console logging if file handler cannot be created
    logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))

FLAC_LIBRARY_DIR = "/Volumes/sad/MUSIC"
AUTO_MATCH_THRESHOLD = 60
# Extra safeguard: minimum fuzzy ratio between *titles* (source vs. candidate)
TITLE_MATCH_THRESHOLD = 70

# Root folder where all playlist‑matching output is stored
MATCHING_ROOT = Path.home() / "Music" / "Playlists" / "matching"
MATCHING_ROOT.mkdir(parents=True, exist_ok=True)

# OUTPUT DIRECTORY – all generated files land here
# Set OUTPUT_DIR to the directory of the file/folder being processed (path_in)
OUTPUT_DIR = None  # Will be set dynamically in main()

# SQLite index for FLAC library
DB_PATH = Path("/Users/georgeskhawam/Library/Mobile Documents/com~apple~CloudDocs/flibrary.db")
CACHE_TTL = 3600  # seconds

# Path to qobuz-dl skip database
SKIP_DB_PATH = Path.home() / ".config/qobuz-dl/qobuz_dl.db"

################################################################################
# SAFE INPUT HELPERS
################################################################################


def safe_prompt(prompt_text, default=None):
    try:
        if default is not None:
            answer = Prompt.ask(prompt_text, default=default)
        else:
            answer = Prompt.ask(prompt_text)
        if answer.strip().lower() == "abort":
            console.print("[bold red]Process aborted by user.[/bold red]")
            sys.exit(0)
        return answer
    except EOFError:
        console.print("[bold red]No interactive terminal detected.[/bold red]")
        if default is not None:
            console.print(f"[yellow]Using default: {default}[/yellow]")
            return default
        else:
            console.print(
                "[red]No default value available. Please run this script in an interactive terminal.[/red]"
            )
            sys.exit(1)
    except KeyboardInterrupt:
        console.print(
            "[bold red]Process interrupted by user (Ctrl+C). Exiting...[/bold red]"
        )
        sys.exit(0)


def safe_confirm(prompt_text, default=True):
    default_str = "y" if default else "n"
    answer = Prompt.ask(
        prompt_text + " (y/n) [or type 'abort' to exit]", default=default_str
    )
    if answer.strip().lower() == "abort":
        console.print("[bold red]Process aborted by user.[/bold red]")
        sys.exit(0)
    return answer.strip().lower() in ["y", "yes"]


################################################################################
# DESIGN RENDERER – EXACT LAYOUT
################################################################################


def render_design_box(offset: int) -> Text:
    """
    Build a 70-character wide box matching your design:

      - A top border of dashes in bold green.

      - Three interior lines, each 70 characters wide.
        Each interior line consists of:
          • A left heart and a right heart.
             Line 1: hearts in red,
             Line 2: hearts in yellow,
             Line 3: hearts in blue.
          • In between, the text "♫ GEORGIE'S PLAYLIST MAGIC BOX ♫" is centered.
             The interior text is animated per character by shifting colors in a R→Y→B cycle,
             based on the given offset.

      - A bottom border consisting solely of dashes (in bold green)
        with the Arabic text "هذا من فضل ربي" centered in bold dark green.
    """
    total_width = 70
    interior_width = total_width - 2  # account for the left/right heart

    text_content = "♫ GEORGIE'S PLAYLIST MAGIC BOX ♫"
    text_length = len(text_content)  # expected to be 31
    total_padding = interior_width - text_length  # e.g., 68 - 31 = 37
    pad_left = total_padding // 2
    pad_right = total_padding - pad_left

    # Function to animate interior text per character
    def animate_text(text: str, offset: int) -> Text:
        colors = ["red", "yellow", "blue"]
        animated = Text()
        for i, ch in enumerate(text):
            animated.append(ch, style=f"bold {colors[(i + offset) % 3]}")
        return animated

    box = Text()
    # Add top border: a full-width line of dashes in bold green.
    top_line = Text("─" * total_width, style="bold green")
    box.append(top_line)
    box.append("\n")

    # Build three interior lines with fixed hearts (colors fixed per line)
    heart_colors = ["red", "yellow", "blue"]
    for i in range(3):
        line = Text()
        line.append("♥", style=f"bold {heart_colors[i]}")
        line.append(" " * pad_left, style="bold green")
        # Animate the text content with the offset (each character already styled)
        line.append(animate_text(text_content, offset))
        line.append(" " * pad_right, style="bold green")
        line.append("♥", style=f"bold {heart_colors[i]}")
        box.append(line)
        box.append("\n")

    # Build bottom border: only dashes with Arabic text centered.
    arabic_text = "هذا من فضل ربي"
    arabic_length = len(arabic_text)  # expected 14
    available = total_width - arabic_length  # 70 - 14 = 56
    dashes_each = available // 2  # e.g., 28 on each side
    bottom_line = Text("─" * dashes_each, style="bold green")
    bottom_line.append(arabic_text, style="bold dark_green")
    bottom_line.append("─" * dashes_each, style="bold green")
    box.append(bottom_line)
    return box


################################################################################
# ANIMATED TITLE WITH BLINKING ENTER PROMPT
################################################################################


class PlaylistUI:
    def __init__(self):
        self.console = Console()

    async def animate_title(self, refresh_rate: float = 0.2, wait_time: float = 4.0):
        """
        Animate the design box for 'wait_time' seconds.
        After wait_time seconds, add a blinking "ENTER" prompt (in bold dark grey)
        centered below the box, blinking on/off at the same refresh rate until the user presses Enter.
        The interior text colors animate by shifting per-character colors based on the offset.
        """
        start_time = asyncio.get_event_loop().time()
        # Wait for user input in a background thread.
        enter_future = asyncio.get_event_loop().run_in_executor(None, input, "")
        with Live(
            console=self.console, refresh_per_second=int(1 / refresh_rate)
        ) as live:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                offset = int(elapsed * 2)  # adjust speed of color shift as needed
                box_text = render_design_box(offset)
                if elapsed >= wait_time:
                    # Blinking ENTER prompt: alternate between "ENTER" and spaces.
                    if int(elapsed / refresh_rate) % 2 == 0:
                        prompt_text = "ENTER"
                    else:
                        prompt_text = "     "
                    pad_left = (70 - len("ENTER")) // 2
                    pad_right = 70 - len("ENTER") - pad_left
                    enter_line = " " * pad_left + prompt_text + " " * pad_right

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
# FUZZY MATCHING, SCANNING, & M3U GENERATION (UNCHANGED)
################################################################################


def normalize_string(s: str) -> str:
    """
    Normalize strings for fuzzy matching:

    1.  Lower‑cases and strips accents/diacritics.
    2.  Replaces common language‑specific variants with ASCII equivalents
        (e.g., Turkish dotless “ı” → “i”, dotted capital “İ” → “i”).
    3.  Removes non‑alphanumeric characters except whitespace.
    """
    # Step 1 – NFD decomposition & accent removal
    s = "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )

    # Step 2 – language‑specific character fixes
    translation_table = {
        "ı": "i",  # Turkish dotless i
        "İ".lower(): "i",  # Turkish dotted capital I
    }
    s = "".join(translation_table.get(ch, ch) for ch in s)

    # Step 3 – strip punctuation
    s = re.sub(r"[^\w\s]+", " ", s).strip()
    return s


def combined_fuzzy_ratio(a, b):
    a_norm = normalize_string(a)
    b_norm = normalize_string(b)
    score1 = fuzz.ratio(a_norm, b_norm)
    score2 = fuzz.partial_ratio(a_norm, b_norm)
    score3 = fuzz.token_set_ratio(a_norm, b_norm)
    return max(score1, score2, score3)


def combined_fuzzy_ratio_prenormalized(a_norm, b_norm):
    """Version that works with already normalized strings"""
    score1 = fuzz.ratio(a_norm, b_norm)
    score2 = fuzz.partial_ratio(a_norm, b_norm)
    score3 = fuzz.token_set_ratio(a_norm, b_norm)
    return max(score1, score2, score3)


def find_all_flacs(library_dir):
    return glob.glob(os.path.join(library_dir, "**", "*.flac"), recursive=True)


def read_audio_metadata(path: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    try:
        # First try using mutagen with a timeout
        try:
            audio = MutagenFile(path, easy=True)
            if audio:
                if "artist" in audio and audio["artist"]:
                    meta["artist"] = audio["artist"][0]
                if "album" in audio and audio["album"]:
                    meta["album"] = audio["album"][0]
                if "title" in audio and audio["title"]:
                    meta["title"] = audio["title"][0]
                if "tracknumber" in audio and audio["tracknumber"]:
                    tn = audio["tracknumber"][0].split("/")[0]
                    meta["track"] = tn
                if "date" in audio and audio["date"]:
                    meta["year"] = audio["date"][0]
                return meta
        except Exception as e:
            # Silent failure, we'll try to extract from filename below
            pass

        # If mutagen fails, try to extract info from the filename
        basename = os.path.basename(path)
        m1 = PATTERN_FULL.match(basename)
        if m1:
            gd = m1.groupdict()
            meta.setdefault("artist", gd["artist"])
            meta.setdefault("album", gd["album"])
            meta.setdefault("title", gd["title"])
            meta.setdefault("year", gd["year"])
            meta.setdefault("track", gd["track"])
            return meta

        # Try simpler pattern
        m2 = PATTERN_SINGLE.match(basename)
        if m2:
            gd2 = m2.groupdict()
            meta.setdefault("title", gd2["title"])
            meta.setdefault("track", gd2["track"])
            return meta

    except Exception as e:
        # Only print error if in verbose mode
        if os.environ.get("DEBUG"):
            console.print(f"[red]Error reading metadata for {path}: {e}[/red]")

    # Use filename as a last resort
    if not meta.get("title"):
        meta["title"] = os.path.basename(path)

    return meta


# Helper to extract a candidate’s title from its path
def extract_title_from_path(path: str) -> str:
    """
    Best‑effort extraction of the track title from a FLAC path.
    Works with patterns like:
        "... - 04. Track Name.flac"
        "... - Track Name.flac"
    Falls back to basename without extension.
    """
    base = os.path.basename(path)
    name = os.path.splitext(base)[0]
    # Try to strip off disc / track numbers:  "02. Title"  or  "04. Title"
    m = re.match(r".*? - (?:\d{2}\.\s*)?(.*)$", name)
    if m:
        return m.group(1).strip()
    return name


PATTERN_FULL = re.compile(
    r"^(?P<artist>.*?) - \((?P<year>\d{4})\) (?P<album>.*?) - (?P<disc>\d{2})-(?P<track>\d{2})\.\s(?P<title>.*)\.(?P<ext>\w+)$"
)
PATTERN_SINGLE = re.compile(r"^(?P<track>\d{2})\.\s(?P<title>.*)\.(?P<ext>\w+)$")


def scan_audio_directory(dir_path):
    exts = [".mp3", ".flac", ".wav", ".m4a", ".aac"]
    audio_files = glob.glob(os.path.join(dir_path, "**", "*.*"), recursive=True)
    results = []
    for f in audio_files:
        _, extension = os.path.splitext(f)
        extension = extension.lower()
        if extension not in exts:
            continue
        embed = read_audio_metadata(f)
        if not embed.get("artist") or not embed.get("title"):
            base = os.path.basename(f)
            m1 = PATTERN_FULL.match(base)
            if m1:
                gd = m1.groupdict()
                embed.setdefault("artist", gd["artist"])
                embed.setdefault("album", gd["album"])
                embed.setdefault("title", gd["title"])
                embed.setdefault("year", gd["year"])
                embed.setdefault("track", gd["track"])
            else:
                m2 = PATTERN_SINGLE.match(base)
                if m2:
                    gd2 = m2.groupdict()
                    embed.setdefault("artist", "Unknown Artist")
                    embed.setdefault("album", "Unknown Album")
                    embed.setdefault("year", "Unknown Year")
                    embed.setdefault("track", gd2["track"])
                    embed.setdefault("title", gd2["title"])
        final = {
            "artist": embed.get("artist", "Unknown Artist"),
            "album": embed.get("album", "Unknown Album"),
            "title": embed.get("title", "Unknown Title"),
            "track": embed.get("track", "00"),
            "year": embed.get("year", "Unknown Year"),
            "path": f,
        }
        results.append(final)
    return results


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
                        # Check if this is a file path (contains / or \)
                        if "/" in line or "\\" in line:
                            # This is a file path - extract metadata from the path
                            try:
                                # Try to read metadata from the file if it exists
                                if os.path.exists(line):
                                    metadata = read_audio_metadata(line)
                                    # Use the actual file path as the search target since we want exact matches
                                    tracks.append(
                                        {
                                            "artist": metadata.get("artist", ""),
                                            "album": metadata.get("album", ""),
                                            "track": metadata.get("track", ""),
                                            "title": metadata.get("title", ""),
                                            "path": line,  # Store the original path
                                            "exact_match": line,  # Mark this for exact matching
                                        }
                                    )
                                else:
                                    # File doesn't exist, try to parse from filename
                                    basename = os.path.basename(line)
                                    # Try pattern matching
                                    m1 = PATTERN_FULL.match(basename)
                                    if m1:
                                        gd = m1.groupdict()
                                        tracks.append(
                                            {
                                                "artist": gd["artist"],
                                                "album": gd["album"],
                                                "track": gd["track"],
                                                "title": gd["title"],
                                                "path": line,
                                            }
                                        )
                                    else:
                                        # Fallback to using the full line as track name
                                        tracks.append(
                                            {
                                                "artist": "",
                                                "album": "",
                                                "track": line,
                                                "title": "",
                                                "path": line,
                                            }
                                        )
                            except Exception as e:
                                # If metadata extraction fails, use the full line as track name
                                tracks.append(
                                    {
                                        "artist": "",
                                        "album": "",
                                        "track": line,
                                        "title": "",
                                        "path": line,
                                    }
                                )
                        else:
                            # This is just a track name - use empty strings for missing metadata
                            tracks.append(
                                {"artist": "", "album": "", "track": line, "title": ""}
                            )
            nm = os.path.splitext(os.path.basename(file_path))[0]
            return nm, tracks
        except UnicodeDecodeError:
            continue
        except Exception as e2:
            console.print(f"[red]Error reading M3U: {e2}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], tracks


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
                # Map 'track' to 'title' if title is missing (common in streaming service exports)
                title = r.get("title", "") or r.get("track", "")
                track = r.get("track", "") or r.get("title", "")

                out.append(
                    {
                        "artist": r.get("artist", ""),
                        "album": r.get("album", ""),
                        "track": track,
                        "title": title,
                        "isrc": r.get(
                            "isrc", ""
                        ),  # Add ISRC support for JSON files too
                    }
                )
            return nm, out
    except Exception as ex:
        console.print(f"[red]Error reading JSON: {ex}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []


async def parse_csv_file(file_path):
    out = []
    try:
        # Try to detect the delimiter - check for semicolon first
        with open(file_path, "r", encoding="utf-8") as cf:
            sample = cf.readline()
            delimiter = ";" if ";" in sample else ","

        with open(file_path, "r", encoding="utf-8") as cf:
            rd = csv.DictReader(cf, delimiter=delimiter)
            for row in rd:
                # For togo.csv format with title;artist;album;isrc columns
                entry = {
                    "title": row.get("title", ""),
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                    "track": row.get(
                        "track", row.get("title", "")
                    ),  # Use title as fallback for track
                    "isrc": row.get("isrc", ""),  # Add ISRC support
                }
                out.append(entry)
        nm = os.path.splitext(os.path.basename(file_path))[0]
        return nm, out
    except Exception as e2:
        console.print(f"[red]Error reading CSV: {e2}[/red]")
    return os.path.splitext(os.path.basename(file_path))[0], []


async def parse_xlsx_file(file_path):
    out = []
    try:
        df = pd.read_excel(file_path)
        nm = os.path.splitext(os.path.basename(file_path))[0]
        for _, row in df.iterrows():
            t = row.get("track", row.get("title", ""))
            a = row.get("artist", "")
            al = row.get("album", "")
            out.append(
                {"track": t, "artist": a, "album": al, "title": row.get("title", "")}
            )
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


def interactive_manual_select(search_str, flac_candidates):
    # Sort candidates by ratio (descending)
    flac_candidates.sort(key=lambda x: x[1], reverse=True)
    top5 = flac_candidates[:5]
    console.print(f"[yellow]No automatic match found for: {search_str}[/yellow]")
    console.print("[bold]Top 5 Candidates:[/bold]")

    for i, (pth, rat) in enumerate(top5, 1):
        # Get metadata to display more info
        meta = read_audio_metadata(pth)
        title = meta.get("title", os.path.basename(pth))
        artist = meta.get("artist", "Unknown")
        album = meta.get("album", "Unknown")

        # Display enhanced candidate information with ratio and metadata
        console.print(
            f"  [cyan]{i})[/cyan] [bold]Match {int(rat)}%[/bold] - {title} - {artist} ({album})"
        )
        console.print(f"     {pth}")

    console.print(
        "\n[bold yellow]Enter a number [1-5], 's' to skip, 'q' to quit matching, or 'm' for manual path:[/bold yellow]"
    )
    while True:
        ans = safe_prompt("Choice")
        if ans in ["q", "quit"]:
            return "QUIT"
        if ans in ["s", "skip"]:
            return None
        if ans in ["m", "manual"]:
            mp = safe_prompt("Manual path to .flac?")
            if os.path.isfile(mp) and mp.lower().endswith(".flac"):
                return mp
            console.print("[red]Invalid path or not a .flac file[/red]")
            continue
        try:
            num = int(ans)
            if 1 <= num <= len(top5):
                # Return the original path of the selected candidate
                return top5[num - 1][0]
            console.print("[red]Out of range[/red]")
        except:
            console.print("[red]Invalid choice[/red]")


@lru_cache(maxsize=1024)
def combined_fuzzy_ratio_cached(a: str, b: str) -> int:
    """Cached version of combined_fuzzy_ratio for better performance with pre-normalized strings"""
    return combined_fuzzy_ratio_prenormalized(a, b)


def match_entry(
    entry: Dict[str, str],
    flac_lookup: List[Tuple[str, str]],
    artist_index: Optional[Dict[str, Set[str]]] = None,
    title_index: Optional[Dict[str, Set[str]]] = None,
    playlist_size: int = 100,
) -> Optional[str]:
    """Finds the best FLAC match for a playlist entry using pre-normalized lookup and indexes."""

    # Check for exact match first (for M3U files with file paths)
    if "exact_match" in entry:
        exact_path = entry["exact_match"]
        if os.path.exists(exact_path) and exact_path.lower().endswith(".flac"):
            return exact_path

    ss = build_search_string(entry)
    if not ss:
        return None

    # Normalize the search string once
    ss_norm = normalize_string(ss)

    # Use indexes for faster matching if available
    candidate_paths = None
    if artist_index and title_index:
        artist = normalize_string(entry.get("artist", ""))
        title = normalize_string(entry.get("title", ""))

        # Get potential candidates from the indexes
        artist_candidates = set()
        if artist:
            for key in artist_index:
                if key in artist or artist in key:
                    artist_candidates.update(artist_index[key])

        title_candidates = set()
        if title:
            for key in title_index:
                if key in title or title in key:
                    title_candidates.update(title_index[key])

        # Use intersection if we have both, otherwise use either set
        if artist_candidates and title_candidates:
            candidate_paths = artist_candidates.intersection(title_candidates)
        elif artist_candidates:
            candidate_paths = artist_candidates
        elif title_candidates:
            candidate_paths = title_candidates

    results = []

    # Early termination: Check only the most likely candidates first
    if candidate_paths:
        # First check indexed candidates
        for orig_path in candidate_paths:
            # Get the normalized basename from flac_lookup using binary search or dict
            for path, norm_basename in flac_lookup:
                if path == orig_path:
                    r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                    # Extra title ratio guard
                    title_src_norm = normalize_string(entry.get("title", ""))
                    if title_src_norm:
                        cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                        title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                        if title_ratio < TITLE_MATCH_THRESHOLD:
                            continue  # Skip this candidate – title too different
                    if r >= AUTO_MATCH_THRESHOLD:
                        return orig_path
                    results.append((orig_path, r))
                    break

    # If no match found with indexes or indexes not available, try scanning
    if not results:
        # For Quick Match mode (small playlists), use much more targeted approach
        if playlist_size <= 50:
            # Extract search terms for targeted matching
            search_terms = [
                normalize_string(entry.get("artist", "")),
                normalize_string(entry.get("title", "")),
                normalize_string(entry.get("album", "")),
            ]
            search_terms = [term for term in search_terms if term]  # Remove empty terms

            artist = normalize_string(entry.get("artist", ""))
            title = normalize_string(entry.get("title", ""))

            # If we have no search terms, fall back to limited sampling
            if not search_terms:
                search_limit = min(1000, len(flac_lookup))
                for i, (orig_path, norm_basename) in enumerate(
                    flac_lookup[:search_limit]
                ):
                    r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                    # Extra title ratio guard
                    title_src_norm = normalize_string(entry.get("title", ""))
                    if title_src_norm:
                        cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                        title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                        if title_ratio < TITLE_MATCH_THRESHOLD:
                            continue  # Skip this candidate – title too different
                    if r >= AUTO_MATCH_THRESHOLD:
                        return orig_path
                    results.append((orig_path, r))
            else:
                # Targeted search: only check files that contain our search terms, with stricter filtering
                matches_found = 0
                for orig_path, norm_basename in flac_lookup:
                    # Mandatory terms: always include artist; include title if non‑empty
                    mandatory_terms = []
                    if artist:
                        mandatory_terms.append(artist)
                    if title:
                        mandatory_terms.append(title)

                    # Skip if any mandatory term is missing
                    if mandatory_terms and not all(mt in norm_basename for mt in mandatory_terms):
                        continue

                    # Optional album/other terms can still relax the filter
                    if not any(term in norm_basename for term in search_terms):
                        continue

                    r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                    # Extra title ratio guard
                    title_src_norm = normalize_string(entry.get("title", ""))
                    if title_src_norm:
                        cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                        title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                        if title_ratio < TITLE_MATCH_THRESHOLD:
                            continue  # Skip this candidate – title too different
                    if r >= AUTO_MATCH_THRESHOLD:
                        return orig_path
                    results.append((orig_path, r))
                    matches_found += 1

                    # Limit the number of matches we check for small playlists
                    if matches_found > 500:  # Process at most 500 potential matches
                        break

                # If we found very few matches, do a broader search with sampling
                if matches_found < 10:
                    sample_size = min(2000, len(flac_lookup))
                    step = max(1, len(flac_lookup) // sample_size)
                    for i in range(0, len(flac_lookup), step):
                        orig_path, norm_basename = flac_lookup[i]
                        r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                        # Extra title ratio guard
                        title_src_norm = normalize_string(entry.get("title", ""))
                        if title_src_norm:
                            cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                            title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                            if title_ratio < TITLE_MATCH_THRESHOLD:
                                continue  # Skip this candidate – title too different
                        if r >= AUTO_MATCH_THRESHOLD:
                            return orig_path
                        results.append((orig_path, r))

                # FINAL fallback: do a full scan if still no high‑score match
                if not any(r >= AUTO_MATCH_THRESHOLD for _, r in results):
                    for orig_path, norm_basename in flac_lookup:
                        r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                        # Extra title ratio guard
                        title_src_norm = normalize_string(entry.get("title", ""))
                        if title_src_norm:
                            cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                            title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                            if title_ratio < TITLE_MATCH_THRESHOLD:
                                continue  # Skip this candidate – title too different
                        if r >= AUTO_MATCH_THRESHOLD:
                            return orig_path
                        # Only append if we don't already have this candidate
                        if not any(p == orig_path for p, _ in results):
                            results.append((orig_path, r))
        else:
            # For larger playlists, search all files (original behavior)
            search_limit = len(flac_lookup)

            # Iterate through (original_path, normalized_basename) tuples
            for i, (orig_path, norm_basename) in enumerate(flac_lookup[:search_limit]):
                # Compare normalized search string with pre-normalized basename
                r = combined_fuzzy_ratio_cached(ss_norm, norm_basename)
                # Extra title ratio guard
                title_src_norm = normalize_string(entry.get("title", ""))
                if title_src_norm:
                    cand_title_norm = normalize_string(extract_title_from_path(orig_path))
                    title_ratio = fuzz.token_set_ratio(title_src_norm, cand_title_norm)
                    if title_ratio < TITLE_MATCH_THRESHOLD:
                        continue  # Skip this candidate – title too different
                results.append((orig_path, r))  # Store original path with ratio

    if (
        not results
    ):  # Handle case where flac_lookup might be empty or no ratios calculated
        return None

    # Sort by ratio (descending)
    results.sort(key=lambda x: x[1], reverse=True)
    best = results[0]

    # Return the original path if above threshold, and ensure best is valid
    if best and best[1] >= AUTO_MATCH_THRESHOLD:
        return best[0]
    return None


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


async def create_csv_file(out_path, entries, matched_paths):
    if not out_path.lower().endswith(".csv"):
        out_path += ".csv"
    try:
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            # Write header row
            writer.writerow(["title", "artist", "album", "isrc", "path"])

            # For each matched entry, write a row
            for i, path in enumerate(matched_paths):
                if i < len(entries):
                    entry = entries[i]
                    writer.writerow(
                        [
                            entry.get("title", ""),
                            entry.get("artist", ""),
                            entry.get("album", ""),
                            entry.get("isrc", ""),
                            path,
                        ]
                    )
        console.print(f"[bold green]Created CSV: {out_path}[/bold green]")
    except Exception as e:
        console.print(f"[red]Error writing CSV: {e}[/red]")


# -------------------------------------------------
# SongShift JSON Export
# -------------------------------------------------
def export_songshift_json_from_entries(
    entries, matched, output_json, playlist_name="Unmatched Tracks"
):
    """Exports unmatched tracks to SongShift-ready JSON format."""
    tracks = []
    for i, m in enumerate(matched):
        if m is None:
            e = entries[i]
            title = e.get("title") or e.get("track") or build_search_string(e)
            artist = e.get("artist") or "Unknown Artist"
            tracks.append({"artist": artist.strip(), "track": title.strip()})

    payload = [
        {"service": "qobuz", "serviceId": None, "name": playlist_name, "tracks": tracks}
    ]

    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    console.print(
        f"[bold green]✓ JSON playlist saved → {output_json} ({len(tracks)} tracks)[/bold green]"
    )


################################################################################
# DATABASE FUNCTIONS
################################################################################


def open_db():
    """Opens and initializes the SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
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

    # Add missing columns if necessary
    expected_columns = ["artist", "album", "title", "trackno", "year", "format_json"]
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(flacs)")
    existing_columns = [row[1] for row in cur.fetchall()]

    for column in expected_columns:
        if column not in existing_columns:
            cur.execute(f"ALTER TABLE flacs ADD COLUMN {column} TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artist ON flacs(artist)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_album ON flacs(album)")
    return conn


def refresh_library(library_dir):
    """Refreshes the FLAC library database."""
    conn = open_db()
    cur = conn.cursor()

    # Purge vanished files
    for (p,) in cur.execute("SELECT path FROM flacs"):
        if not os.path.exists(p):
            cur.execute("DELETE FROM flacs WHERE path=?", (p,))

    # Add/update changed files
    files = glob.glob(os.path.join(library_dir, "**", "*.flac"), recursive=True)
    console.print(f"[cyan]Scanning {len(files)} FLAC files in library…[/cyan]")

    def process_file(p):
        # Create a new connection for each thread
        thread_conn = sqlite3.connect(DB_PATH)
        thread_conn.execute(
            "PRAGMA busy_timeout = 3000"
        )  # Wait up to 3 seconds if locked
        thread_cur = thread_conn.cursor()

        m = int(os.path.getmtime(p))
        thread_cur.execute("SELECT mtime FROM flacs WHERE path=?", (p,))
        row = thread_cur.fetchone()
        norm = normalize_string(Path(p).stem)

        if row and row[0] == m:
            # Skip unchanged files
            thread_conn.close()
            return

        # Read tags via Mutagen
        tags = read_audio_metadata(p)
        # Read full ffprobe format JSON
        fmt = get_format_json(p)
        fmt_json = json.dumps(fmt) if fmt else None

        values = (
            p,
            norm,
            m,
            tags.get("artist"),
            tags.get("album"),
            tags.get("title"),
            tags.get("trackno"),
            tags.get("year"),
            fmt_json,
        )

        # Retry logic for database locked
        for attempt in range(5):
            try:
                if not row:
                    thread_cur.execute(
                        """
                        INSERT INTO flacs (
                            path, norm, mtime, artist, album, title, trackno, year, format_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                else:
                    thread_cur.execute(
                        """
                        REPLACE INTO flacs (
                            path, norm, mtime, artist, album, title, trackno, year, format_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                thread_conn.commit()
                break  # Success
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.2 * (attempt + 1))  # Exponential backoff
                else:
                    raise
        thread_conn.close()

    # Parallelize file processing
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            tqdm(
                executor.map(process_file, files),
                total=len(files),
                desc="Scanning FLACs",
                unit="file",
            )
        )

    conn.close()


def get_format_json(path):
    """Extract format information using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(
                f"[yellow]Warning: ffprobe failed for {path}. Skipping file.[/yellow]"
            )
            return {}
        return json.loads(result.stdout).get("format", {})
    except json.JSONDecodeError as e:
        console.print(
            f"[yellow]Warning: Invalid JSON from ffprobe for {path}. Skipping file.[/yellow]"
        )
        return {}
    except Exception as e:
        console.print(f"[red]Error running ffprobe for {path}: {e}[/red]")
        return {}


################################################################################
# MAIN FUNCTION
################################################################################


async def main():
    # Check for command line arguments
    import sys

    if len(sys.argv) > 1:
        path_in = sys.argv[1].strip().strip("'\"")
        # Skip the UI animation if run with command line args
        console.print(f"[cyan]Processing: {path_in}[/cyan]")
    else:
        os.system("clear")
        console.clear()

        # 1) Run animated title with custom box and blinking ENTER prompt.
        ui = PlaylistUI()
        await ui.animate_title(refresh_rate=0.2, wait_time=4.0)

        os.system("clear")
        console.clear()

        path_in = (
            safe_prompt(
                "[bold yellow]Enter a path (folder or playlist file)[/bold yellow]"
            )
            .strip()
            .strip("'\"")
        )

    if not os.path.exists(path_in):
        console.print(f"[red]Invalid path: {path_in}[/red]")
        return

    # Set OUTPUT_DIR inside ~/Music/Playlists/matching/<playlist_name>
    playlist_stem = Path(path_in).stem if path_in else "output"
    OUTPUT_DIR = MATCHING_ROOT / playlist_stem
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    source_name = os.path.basename(path_in)
    if os.path.isdir(path_in):
        console.print(f"[cyan]Scanning directory: {path_in}[/cyan]")
        with console.status("[green]Reading metadata...[/green]", spinner="dots12"):
            dir_data = scan_audio_directory(path_in)
        console.print(f"[green]Found {len(dir_data)} audio files[/green]")
        entries = dir_data
        source_name = os.path.basename(os.path.normpath(path_in))
    else:
        nm, tracks = await parse_playlist_file(path_in)
        console.print(f"[green]Loaded {len(tracks)} track(s) from {nm}[/green]")
        if not tracks:
            return
        entries = tracks
        source_name = nm

    console.print(f"[cyan]Scanning {FLAC_LIBRARY_DIR} for .flac...[/cyan]")
    all_flacs = find_all_flacs(FLAC_LIBRARY_DIR)
    console.print(
        f"[green]Found {len(all_flacs)} flac files in {FLAC_LIBRARY_DIR}[/green]"
    )

    # Start timing for performance measurement
    start_time = time.time()

    # Ask for optimization level
    console.print("[bold yellow]Choose matching mode:[/bold yellow]")
    console.print("1) Auto - Automatically match tracks")
    console.print("2) Quick - Fast mode for small playlists")
    console.print("3) Thorough - Comprehensive matching")

    # Recommend Quick mode for ≤50 tracks, but let the user decide
    default_mode = "2" if len(entries) <= 50 else "1"
    console.print(
        f"[cyan]Recommended default mode: {default_mode} ({'Quick' if default_mode=='2' else 'Auto'})[/cyan]"
    )
    match_mode = safe_prompt("Matching mode [1-3]", default=default_mode)

    # Pre-compute normalized basenames for faster matching with caching
    cache_file = Path.home() / ".music_tools_cache.json"
    flac_lookup = []

    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_TTL:
        console.print("[cyan]Loading cached FLAC normalization...[/cyan]")
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
                # Verify cache is still valid (same files)
                if len(cached_data) == len(all_flacs):
                    # Re-normalize cached norms to apply updated normalization rules
                    flac_lookup = [
                        (item["path"], normalize_string(item["norm"]))
                        for item in cached_data
                    ]
                    console.print("[green]Cache loaded successfully.[/green]")
                else:
                    console.print("[yellow]Cache outdated, rebuilding...[/yellow]")
                    flac_lookup = []
        except Exception as e:
            console.print(f"[yellow]Cache read failed: {e}, rebuilding...[/yellow]")
            flac_lookup = []

    if not flac_lookup:
        console.print("[cyan]Normalizing FLAC filenames for matching...[/cyan]")
        with console.status("[green]Normalizing...", spinner="dots12"):
            flac_lookup = [
                (f, normalize_string(os.path.basename(f))) for f in all_flacs
            ]

        # Save to cache
        console.print("[cyan]Saving normalization cache...[/cyan]")
        try:
            cache_data = [{"path": path, "norm": norm} for path, norm in flac_lookup]
            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            console.print(f"[yellow]Cache save failed: {e}[/yellow]")

        console.print("[green]Normalization complete.[/green]")

    # Debug: Show sample FLAC files for verification (condensed)
    console.print(
        f"[cyan]Loaded FLAC cache with {len(flac_lookup)} normalized entries[/cyan]"
    )

    # Create additional indexes for advanced matching
    artist_index = None
    title_index = None

    # Skip indexing for Quick Match mode
    if match_mode == "2":
        console.print(
            "[yellow]Quick Match mode: Skipping indexing for faster processing[/yellow]"
        )
    else:
        # Only build indexes if we have many tracks to match or many FLAC files
        should_index = match_mode in ["3"] and (
            len(entries) > 50 or len(all_flacs) > 10000
        )

        if should_index:
            # Confirm with the user before starting a potentially long indexing pass
            if safe_confirm(
                f"[yellow]Build search indexes for faster matching? "
                f"This will scan up to 5\u202f000 of {len(all_flacs)} FLAC files and may take a while.[/yellow]"
            ):
                try:
                    artist_index, title_index = build_search_indexes(
                        all_flacs, max_files=5000
                    )
                except Exception as e:
                    console.print(f"[bold red]Error building indexes: {e}[/bold red]")
                    console.print(
                        "[yellow]Falling back to basic mode without indexes[/yellow]"
                    )
                    artist_index = None
                    title_index = None
            else:
                console.print("[yellow]Skipped index build at user request.[/yellow]")
        else:
            console.print(
                f"[yellow]Skipping indexing (only {len(entries)} tracks to match)[/yellow]"
            )

    matched: List[Optional[str]] = [None] * len(
        entries
    )  # List that will contain file paths (str) or None
    unmatched_indices: List[int] = []
    total_entries = len(entries)
    console.print(f"[cyan]Attempting to match {total_entries} entries...[/cyan]")

    # Use parallel processing for Turbo modes and Quick Match
    if match_mode in ["2", "3"] and total_entries > 5:
        console.print("[cyan]Using parallel processing for faster matching...[/cyan]")

        # Define a worker function for parallel processing
        def match_worker(idx_entry):
            idx, entry = idx_entry
            track_info = (
                f"{entry.get('title', 'Unknown')} - {entry.get('artist', 'Unknown')}"
            )
            result = match_entry(
                entry, flac_lookup, artist_index, title_index, len(entries)
            )
            return idx, result, track_info

        # Prepare items for parallel processing
        items = list(enumerate(entries))

        # Determine the number of workers based on CPU cores (but limit to 8 max)
        max_workers = min(os.cpu_count() or 4, 8)

        # Create a matched_results list to store results
        matched_results = []

        # Process in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(match_worker, item): item for item in items}

            # Create a progress display
            with console.status(
                f"[green]Matching in parallel with {max_workers} workers...",
                spinner="dots12",
            ):
                # Process results as they complete
                for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                    idx, result, track_info = future.result()
                    console.print(
                        f"[yellow]Matched {i}/{total_entries}: [/yellow]{track_info}",
                        end="",
                    )

                    if result:
                        matched[idx] = result
                        meta = read_audio_metadata(result)
                        console.print(" [bold green]✓ MATCHED[/bold green]")
                        matched_results.append((idx, result, meta))
                    else:
                        console.print(" [bold red]✗ NO MATCH[/bold red]")
                        unmatched_indices.append(idx)

        # Display match details after parallel processing
        if matched_results:
            console.print("\n[bold cyan]Match details:[/bold cyan]")
            for idx, result, meta in matched_results:
                src = entries[idx]
                # Source info
                src_title = src.get("title") or src.get("track") or "Unknown"
                src_artist = src.get("artist", "Unknown")
                src_album = src.get("album", "Unknown")
                # Matched info
                m_title = meta.get("title", os.path.basename(result))
                m_artist = meta.get("artist", "Unknown Artist")
                m_album = meta.get("album", "Unknown Album")

                console.print(f"[bold]Source:[/bold]  {src_title}  |  {src_artist}  |  {src_album}")
                console.print(f"[bold green]Matched:[/bold green] {m_title}  |  {m_artist}  |  {m_album}")
                console.print(f"[blue]Path:[/blue] {result}\n")

    else:
        # Sequential processing for Basic and Advanced modes
        for i, e in enumerate(entries):
            # Create a single line with track info (title - artist)
            track_info = f"{e.get('title', 'Unknown')} - {e.get('artist', 'Unknown')}"
            console.print(
                f"[yellow]Matching ({i+1}/{total_entries}): [/yellow]{track_info}",
                end="",
            )

            # Pass the pre-computed lookup table and indexes
            res = match_entry(e, flac_lookup, artist_index, title_index, len(entries))

            if res:
                # Extract metadata from the matched file
                meta = read_audio_metadata(res)
                console.print(" [bold green]✓ MATCHED[/bold green]")

                # Display match details in parallel "Source" vs "Matched" form
                src_title = e.get("title") or e.get("track") or "Unknown"
                src_artist = e.get("artist", "Unknown")
                src_album = e.get("album", "Unknown")
                m_title = meta.get("title", os.path.basename(res))
                m_artist = meta.get("artist", "Unknown Artist")
                m_album = meta.get("album", "Unknown Album")

                console.print(f"[bold]Source:[/bold]  {src_title}  |  {src_artist}  |  {src_album}")
                console.print(f"[bold green]Matched:[/bold green] {m_title}  |  {m_artist}  |  {m_album}")
                console.print(f"[blue]Path:[/blue] {res}\n")

                matched[i] = res
            else:
                console.print(" [bold red]✗ NO MATCH[/bold red]")
                unmatched_indices.append(i)

    # Display timing information
    elapsed = time.time() - start_time
    console.print(f"[bold cyan]Matching completed in {elapsed:.2f} seconds[/bold cyan]")

    # --- Post‑match validation ---
    validated_matched = []
    used_paths: Set[str] = set()
    for idx, (entry, pth) in enumerate(zip(entries, matched)):
        if (
            pth
            and os.path.exists(pth)
            and pth not in used_paths
            and combined_fuzzy_ratio(build_search_string(entry), os.path.basename(pth)) >= AUTO_MATCH_THRESHOLD
            and fuzz.token_set_ratio(
                    normalize_string(entry.get("title", "")),
                    normalize_string(extract_title_from_path(pth))
                ) >= TITLE_MATCH_THRESHOLD
        ):
            validated_matched.append(pth)
            used_paths.add(pth)
        else:
            # Treat as unmatched if validation fails
            matched[idx] = None
            if idx not in unmatched_indices:
                unmatched_indices.append(idx)

    auto_matched_count = len(validated_matched)
    auto_unmatched_count = total_entries - auto_matched_count
    console.print(
        f"[bold green]{auto_matched_count} automatically matched[/bold green], [bold red]{auto_unmatched_count} unmatched[/bold red]"
    )

    if auto_unmatched_count > 0 and safe_confirm(
        "[bold yellow]Do you want to attempt manual matching on unmatched tracks?[/bold yellow]"
    ):
        manual_match_count = 0
        for idx in unmatched_indices:
            e = entries[idx]
            # Show detailed track info with title, artist, album
            title = e.get("title", "Unknown Title")
            artist = e.get("artist", "Unknown Artist")
            album = e.get("album", "Unknown Album")

            console.print("\n" + "─" * 70)
            console.print(
                f"[bold cyan]Manually matching track {idx+1}/{total_entries}:[/bold cyan]"
            )
            console.print(f"[bold]Title:[/bold] {title}")
            console.print(f"[bold]Artist:[/bold] {artist}")
            console.print(f"[bold]Album:[/bold] {album}")

            search_str = build_search_string(e)
            if not search_str:
                console.print("[yellow]Skipping entry with no search data.[/yellow]")
                continue

            # Calculate ratios against the normalized lookup for candidates
            search_str_norm = normalize_string(search_str)
            candidates = [
                (orig_path, combined_fuzzy_ratio(search_str_norm, norm_basename))
                for orig_path, norm_basename in flac_lookup
            ]

            res = interactive_manual_select(
                search_str, candidates
            )  # Pass original paths and ratios
            if res == "QUIT":
                console.print("[yellow]User opted to quit manual matching.[/yellow]")
                break
            if res and res != "QUIT":  # res is the selected original path or None
                matched[idx] = res

                # Display the match details
                meta = read_audio_metadata(res)
                console.print(f"[bold green]✓ MATCHED with:[/bold green]")
                console.print(
                    f"  [green]→ Title: {meta.get('title', os.path.basename(res))}[/green]"
                )
                console.print(
                    f"  [green]→ Artist: {meta.get('artist', 'Unknown Artist')}[/green]"
                )
                console.print(
                    f"  [green]→ Album: {meta.get('album', 'Unknown Album')}[/green]"
                )
                console.print(f"  [green]→ Path: {res}[/green]")

                manual_match_count += 1
        console.print(
            f"[bold green]{manual_match_count} tracks manually matched.[/bold green]"
        )

    if any(m is None for m in matched):
        if safe_confirm(
            "[bold yellow]Some tracks remain unmatched. Generate a log file for these tracks?[/bold yellow]"
        ):
            log_path = OUTPUT_DIR / f"{source_name}_unmatched.log"
            try:
                with open(log_path, "w", encoding="utf-8") as lf:
                    for i, m in enumerate(matched):
                        if m is None:
                            e = entries[i]
                            lf.write(f"Index {i+1}: {build_search_string(e)}\n")
                console.print(
                    f"[bold green]Unmatched log written to {str(log_path)}[/bold green]"
                )
            except Exception as e:
                console.print(f"[red]Error writing log: {e}[/red]")

    # Collect only matched entries and their paths
    final_matches = []
    final_entries = []
    for i, m in enumerate(matched):
        if m is not None:
            final_matches.append(m)
            final_entries.append(entries[i])

    # Initialize choice variable
    choice = None

    if final_matches:
        # Ask for export format
        console.print("[bold yellow]Choose export format:[/bold yellow]")
        console.print("1) M3U playlist")
        console.print("2) CSV file")
        console.print("3) Both M3U and CSV")
        console.print("4) Skip export")

        choice = safe_prompt("Choice [1-4]", default="1")

        # M3U export
        if choice in ["1", "3"]:
            def_name_m3u = OUTPUT_DIR / f"{source_name}_matched.m3u"
            outp_m3u = (
                safe_prompt("M3U filename", default=str(def_name_m3u)).strip().strip("'\"")
            )
            await create_m3u_file(outp_m3u, final_matches)

        # CSV export
        if choice in ["2", "3"]:
            def_name_csv = OUTPUT_DIR / f"{source_name}_matched.csv"
            outp_csv = (
                safe_prompt("CSV filename", default=str(def_name_csv)).strip().strip("'\"")
            )
            await create_csv_file(outp_csv, final_entries, final_matches)

        if choice == "4":
            console.print("[yellow]Skipping file exports.[/yellow]")

    # Export unmatched tracks as SongShift JSON if requested
    if any(m is None for m in matched):
        if safe_confirm(
            "[bold yellow]Export unmatched tracks as a SongShift-ready JSON playlist?[/bold yellow]"
        ):
            json_name = OUTPUT_DIR / f"{source_name}_songshift.json"
            export_songshift_json_from_entries(
                entries, matched, json_name, playlist_name=source_name
            )
    else:
        console.print("[yellow]No matches to export.[/yellow]")

    if final_matches and choice not in ["2", "3", "4"] and safe_confirm(
        "[bold yellow]Create CSV with the current matched flacs?[/bold yellow]"
    ):
        def_name_csv = OUTPUT_DIR / f"{source_name}_matched.csv"
        outp_csv = (
            safe_prompt("CSV filename", default=str(def_name_csv)).strip().strip("'\"")
        )
        await create_csv_file(outp_csv, entries, final_matches)
    else:
        console.print("[yellow]Skipping CSV creation.[/yellow]")


async def create_txt_file(out_path, unmatched_entries):
    """Creates a TXT file for unmatched entries."""
    try:
        async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
            for entry in unmatched_entries:
                title = (
                    entry.get("title")
                    or entry.get("track")
                    or build_search_string(entry)
                )
                artist = entry.get("artist") or "Unknown Artist"
                await f.write(f"{artist} - {title}\n")
        console.print(
            f"[bold green]✓ TXT file saved → {out_path} ({len(unmatched_entries)} lines)[/bold green]"
        )
    except Exception as e:
        console.print(f"[red]Error writing TXT file: {e}[/red]")


def build_search_indexes(
    flac_files: List[str], max_files: int = 5000
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Build artist and title indexes for faster matching"""
    artist_index: Dict[str, Set[str]] = defaultdict(set)
    title_index: Dict[str, Set[str]] = defaultdict(set)
    error_count = 0
    indexed_count = 0
    skipped_count = 0

    # Limit the number of files to index for performance
    files_to_process = (
        flac_files[:max_files] if len(flac_files) > max_files else flac_files
    )

    console.print(
        f"[cyan]Building search indexes for {len(files_to_process)} FLAC files (limited from {len(flac_files)})...[/cyan]"
    )

    # Use tqdm for better progress reporting
    with tqdm(total=len(files_to_process), desc="Indexing files", unit="file") as pbar:
        for f in files_to_process:
            try:
                # Extract file metadata with error handling
                meta = {}
                try:
                    meta = read_audio_metadata(f)
                except Exception as e:
                    error_count += 1
                    # Try to extract info from filename if metadata read fails
                    base = os.path.basename(f)
                    m1 = PATTERN_FULL.match(base)
                    if m1:
                        gd = m1.groupdict()
                        meta = {
                            "artist": gd["artist"],
                            "album": gd["album"],
                            "title": gd["title"],
                            "year": gd["year"],
                            "track": gd["track"],
                        }
                    else:
                        skipped_count += 1
                        pbar.update(1)
                        continue  # Skip this file if we can't get metadata

                # Index artist information
                if "artist" in meta and meta["artist"]:
                    artist_norm = normalize_string(meta["artist"])
                    words = artist_norm.split()
                    # Index by full artist name and individual words
                    artist_index[artist_norm].add(f)
                    for word in words:
                        if len(word) > 3:  # Only index meaningful words
                            artist_index[word].add(f)

                # Index title information
                if "title" in meta and meta["title"]:
                    title_norm = normalize_string(meta["title"])
                    words = title_norm.split()
                    # Index by full title and individual words
                    title_index[title_norm].add(f)
                    for word in words:
                        if len(word) > 3:  # Only index meaningful words
                            title_index[word].add(f)

                indexed_count += 1

            except Exception as e:
                # Log the error and continue with next file
                error_count += 1
                skipped_count += 1

            pbar.update(1)

    console.print(
        f"[green]Indexing complete. Created {len(artist_index)} artist and {len(title_index)} title entries.[/green]"
    )
    if error_count > 0:
        console.print(
            f"[yellow]Note: {error_count} files had metadata read errors, {skipped_count} files were skipped.[/yellow]"
        )
    console.print(f"[green]Successfully indexed {indexed_count} files.[/green]")
    return artist_index, title_index


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[red]Process interrupted by user (Ctrl+C). Exiting...[/red]")
        sys.exit(0)
