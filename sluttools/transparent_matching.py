#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from match_visualizer import (
    build_search_string,
    interactive_match_selection,
    normalize_string,
    visualize_match_scores,
)
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

console = Console()

# Default settings (can be overridden in config)
DEFAULT_FLAC_LIBRARY_DIR = "~/Music"
DEFAULT_DB_PATH = Path.home() / ".config/sluttools/flibrary.db"
DEFAULT_AUTO_MATCH_THRESHOLD = 65


def open_db(db_path: Path = DEFAULT_DB_PATH):
    """Open and initialize the database connection"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS flacs (
            path TEXT PRIMARY KEY,
            norm TEXT NOT NULL,
            mtime INTEGER NOT NULL
        )
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_norm ON flacs(norm)")
    return conn


def refresh_library(library_dir: str, db_path: Path = DEFAULT_DB_PATH):
    """Refresh the FLAC library index (delta-scan)"""
    conn = open_db(db_path)
    cur = conn.cursor()

    # 1) Remove missing files
    cur.execute("SELECT path FROM flacs")
    removed_count = 0
    for (path,) in cur.fetchall():
        if not os.path.exists(path):
            cur.execute("DELETE FROM flacs WHERE path=?", (path,))
            removed_count += 1

    # 2) Add/update changed files
    flac_paths = list(Path(library_dir).rglob("*.flac"))
    updated_count = 0
    new_count = 0

    for p in flac_paths:
        p_str = str(p)
        mtime = int(p.stat().st_mtime)
        cur.execute("SELECT mtime FROM flacs WHERE path=?", (p_str,))
        row = cur.fetchone()
        norm = normalize_string(p.stem)

        if not row:  # new file
            cur.execute(
                "INSERT OR REPLACE INTO flacs(path,norm,mtime) VALUES (?,?,?)",
                (p_str, norm, mtime),
            )
            new_count += 1
        elif row[0] != mtime:  # modified file
            cur.execute(
                "UPDATE flacs SET norm=?, mtime=? WHERE path=?", (norm, mtime, p_str)
            )
            updated_count += 1

    conn.commit()
    conn.close()

    return {
        "removed": removed_count,
        "updated": updated_count,
        "new": new_count,
        "total": len(flac_paths),
    }


def get_flac_lookup(db_path: Path = DEFAULT_DB_PATH):
    """Get all FLAC entries from the database"""
    conn = open_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT path, norm FROM flacs")
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (path, norm)


def batch_match_entries(
    entries: List[Dict[str, Any]],
    flac_lookup: List[Tuple[str, str]],
    auto_threshold: int = DEFAULT_AUTO_MATCH_THRESHOLD,
    interactive: bool = True,
    show_progress: bool = True,
):
    """Match a batch of entries with transparent scoring and optional interactive mode"""
    matched = [None] * len(entries)
    unmatched_indices = []
    total_entries = len(entries)

    console.print(f"[cyan]Attempting to match {total_entries} entries...")

    if show_progress:
        progress_ctx = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
        )
    else:
        # Use a dummy context manager when no progress display is needed
        from contextlib import nullcontext

        progress_ctx = nullcontext()

    with progress_ctx as progress:
        if show_progress:
            task = progress.add_task("Matching tracks", total=total_entries)

        for i, entry in enumerate(entries):
            if show_progress:
                progress.update(task, description=f"Track {i+1}/{total_entries}")

            # First try automatic matching
            search = build_search_string(entry)
            if not search:
                unmatched_indices.append(i)
                continue

            search_norm = normalize_string(search)
            best_score = 0
            best_path = None

            # Find best match
            for orig, norm in flac_lookup:
                if search_norm == norm:
                    best_path = orig  # exact match
                    best_score = 100
                    break

                score = ratio(search_norm, norm)
                if score > best_score:
                    best_score = score
                    best_path = orig
                    if best_score >= 95:  # early exit for very high scores
                        break

            # Auto-match if score is high enough
            if best_score >= auto_threshold:
                matched[i] = best_path
                # Optional visual feedback for auto-matches
                if not show_progress:
                    console.print(
                        f"[green]✓[/green] Auto-matched ({best_score:.1f}%): {search} → {os.path.basename(best_path)}"
                    )
            else:
                unmatched_indices.append(i)
                # Optional visual feedback for non-matches
                if not show_progress:
                    console.print(
                        f"[yellow]?[/yellow] No auto-match: {search} (best: {best_score:.1f}%)"
                    )

            if show_progress:
                progress.advance(task)

    # Stats after batch matching
    auto_matched_count = len([x for x in matched if x])
    auto_unmatched_count = total_entries - auto_matched_count
    console.print(
        f"[bold green]{auto_matched_count} auto-matched[/bold green], "
        f"[bold yellow]{auto_unmatched_count} need review[/bold yellow]"
    )

    # Interactive matching for unmatched entries
    if interactive and unmatched_indices:
        console.print(
            Panel(
                "[bold]Starting interactive matching for unmatched tracks[/bold]",
                title="Manual Matching",
                border_style="yellow",
            )
        )

        manual_match_count = 0
        for idx in unmatched_indices:
            entry = entries[idx]
            result = interactive_match_selection(entry, flac_lookup, auto_threshold)
            if result:
                matched[idx] = result
                manual_match_count += 1

        console.print(
            f"[bold green]{manual_match_count} tracks manually matched.[/bold green]"
        )

    return matched, unmatched_indices


# Import fuzzy matching functions (copied from match_visualizer to avoid circular imports)
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
