#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

# Import our modules
from transparent_matching import batch_match_entries, refresh_library, get_flac_lookup
from config import ensure_config_exists, load_config, get_auto_match_threshold

console = Console()

async def main():
    """Example script showing transparent matching process"""
    # Ensure config exists
    config = ensure_config_exists()

    # Get library directory and threshold from config
    library_dir = config["library_dir"]
    auto_threshold = get_auto_match_threshold()

    console.print(Panel(
        f"[cyan]Library directory:[/cyan] {library_dir}\n" 
        f"[cyan]Auto-match threshold:[/cyan] {auto_threshold}%",
        title="Configuration"
    ))

    # Prompt for playlist to match
    playlist_path = Prompt.ask(
        "Enter path to playlist file or folder",
        default=str(Path.home() / "Downloads" / "playlist.json")
    )

    if not os.path.exists(playlist_path):
        console.print(f"[bold red]Error:[/bold red] Path '{playlist_path}' not found")
        return

    # Refresh the library database
    console.print("[cyan]Refreshing library database...[/cyan]")
    stats = refresh_library(library_dir)
    console.print(f"[green]Library refreshed:[/green] {stats['total']} tracks total")
    console.print(f"  - {stats['new']} new, {stats['updated']} updated, {stats['removed']} removed")

    # Load entries from playlist
    # (This would be replaced with actual playlist parsing code)
    # For this example, we'll create some dummy entries
    entries = [
        {"artist": "The Beatles", "title": "Hey Jude"},
        {"artist": "Queen", "title": "Bohemian Rhapsody"},
        {"artist": "Led Zeppelin", "title": "Stairway to Heaven"},
        {"artist": "Pink Floyd", "title": "Comfortably Numb"},
        {"artist": "The Rolling Stones", "title": "Paint It Black"}
    ]

    console.print(f"[cyan]Loaded {len(entries)} tracks from playlist[/cyan]")

    # Get flac lookup data
    flac_lookup = get_flac_lookup()
    console.print(f"[cyan]Loaded {len(flac_lookup)} tracks from library database[/cyan]")

    # Match entries with transparent visualization
    matched, unmatched = batch_match_entries(
        entries, 
        flac_lookup, 
        auto_threshold=auto_threshold,
        interactive=True,
        show_progress=False  # Turn off progress bar for clearer visualization
    )

    # Display final results
    console.print(Panel(
        f"[green]Matched:[/green] {len([x for x in matched if x])} / {len(entries)}\n"
        f"[yellow]Unmatched:[/yellow] {len(unmatched)}",
        title="Final Results"
    ))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
