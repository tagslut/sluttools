#!/usr/bin/env python3
import os
import re
import unicodedata
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

# Import fuzzy matching functions
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

console = Console()

def normalize_string(s: str) -> str:
    """Normalize string for comparison (copied from archive/gg.py)"""
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]+", " ", s).strip()

def combined_fuzzy_ratio(s1, s2):
    """Calculate a combined fuzzy ratio using multiple metrics"""
    r1 = ratio(s1, s2)
    r2 = partial_ratio(s1, s2)
    r3 = token_set_ratio(s1, s2)
    return (r1 + r2 + r3) / 3

def visualize_match_scores(entry, candidates, auto_threshold, top_n=5):
    """Visualize the match scores for a track"""
    search_str = build_search_string(entry)
    search_norm = normalize_string(search_str)

    # Table of top candidates
    table = Table(title=f"Match Results for: {search_str}")
    table.add_column("#", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Combined", justify="right")
    table.add_column("Match Type", style="cyan")
    table.add_column("File Path", style="green")

    # Sort candidates by score
    scored_candidates = []
    for path, norm in candidates:
        basic_score = ratio(search_norm, norm)
        partial_score = partial_ratio(search_norm, norm)
        token_score = token_set_ratio(search_norm, norm)
        combined_score = (basic_score + partial_score + token_score) / 3
        scored_candidates.append((path, basic_score, combined_score, norm))

    # Sort by basic score (main criteria)
    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    # Display top N results
    for i, (path, score, combined, norm) in enumerate(scored_candidates[:top_n], 1):
        match_type = "[green]AUTO[/green]" if score >= auto_threshold else "[yellow]MANUAL[/yellow]"
        file_name = os.path.basename(path)

        # Highlight parts that match
        highlighted_path = Text(file_name)

        table.add_row(
            str(i),
            f"{score:.1f}%",
            f"{combined:.1f}%",
            match_type,
            path
        )

    console.print(table)
    console.print(Panel(
        f"[cyan]Search normalized: [bold]{search_norm}[/bold][/cyan]\n"
        f"[yellow]Auto-match threshold: {auto_threshold}%[/yellow]",
        title="Match Details"
    ))

    return scored_candidates

def build_search_string(entry):
    """Build search string from entry fields (copied from archive/gg.py)"""
    parts = []
    for k in ["artist", "album", "track", "title"]:
        val = entry.get(k)
        if val:
            parts.append(val)
    return " ".join(parts).strip()

def interactive_match_selection(entry, flac_lookup, auto_threshold=65):
    """Interactive matching with visualization of scoring process"""
    search_str = build_search_string(entry)
    if not search_str:
        return None

    console.print(f"\n[bold cyan]Matching track: [/bold cyan][yellow]{search_str}[/yellow]")

    # First pass - calculate scores and find potential auto-match
    search_norm = normalize_string(search_str)
    best_score = 0
    best_path = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("Analyzing match scores...", total=None)
        for orig, norm in flac_lookup:
            score = ratio(search_norm, norm)
            if score > best_score:
                best_score = score
                best_path = orig

    # Visualize the matching process
    candidates = visualize_match_scores(entry, flac_lookup, auto_threshold)

    # Determine if we have an automatic match
    if best_score >= auto_threshold:
        console.print(f"[bold green]✓ Auto-matched[/bold green] (score: {best_score:.1f}%): {best_path}")
        return best_path

    # No auto-match, prompt for manual selection
    console.print(f"[bold yellow]No automatic match found[/bold yellow] (best score: {best_score:.1f}%)")

    # Offer manual matching options
    console.print("Options: [1-5] select match, [s] skip, [m] manual path entry")
    choice = Prompt.ask("Your choice", choices=["1", "2", "3", "4", "5", "s", "m"], default="s")

    if choice == "s":
        return None
    elif choice == "m":
        manual_path = Prompt.ask("Enter full path to match")
        if os.path.isfile(manual_path):
            return manual_path
        console.print("[bold red]Invalid file path[/bold red]")
        return None
    else:
        idx = int(choice) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx][0]  # Return the path

    return None
