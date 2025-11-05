"""
Provides an advanced, interactive matching wizard with a rich terminal UI.

This module is an alternative to the standard `match` command, offering a full-screen,
animated, and highly interactive experience. It guides the user through playlist
selection, matching, and manual review using a distinct, graphical interface.

It is fully integrated with the application's central configuration and database systems.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.prompt import Confirm, Prompt
from rich.text import Text

# --- Import Handling for Direct Execution vs. Package Import ---
# This block allows the script to be run directly (e.g., `python wizard.py`)
# for development/testing, while still supporting its intended use as
# a module within the 'sluttools' package.
try:
    # Attempt relative imports first (for when wizard.py is imported as part of the sluttools package)
    from .config import CONFIG_FILE, CONFIG_PATH, config, console
    from .database import get_flac_lookup, get_last_n_tracks, refresh_library
    from .matching import get_playlist_tracks, perform_matching_with_review
except ImportError:
    # If relative import fails, it means wizard.py is likely being run directly.
    # Adjust sys.path to allow absolute imports from the project root.
    # Given the typical project structure:
    # project_root/
    # └── sluttools/ (package directory)
    #     ├── wizard.py
    #     └── config.py
    # We need to add 'project_root' to sys.path.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up two levels
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Now, try absolute imports from the 'sluttools' package
    from sluttools.config import CONFIG_FILE, CONFIG_PATH, config, console
    from sluttools.database import get_flac_lookup, get_last_n_tracks, refresh_library
    from sluttools.matching import get_playlist_tracks, perform_matching_with_review


# --- Configuration Wizard ---


def launch_config_wizard():
    """Synchronous entry point for the configuration wizard."""
    try:
        run_config_wizard()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold red]Setup aborted by user. Exiting...[/bold red]")
        sys.exit(0)


def run_config_wizard():
    """Guides the user through setting up the initial configuration."""
    console.clear()
    console.clear()
    console.print("[bold green]Welcome to sluttools! Let's set things up.[/bold green]")

    # 1. Library Roots
    console.print("\n[bold]Enter the absolute paths to your music libraries.[/bold]")
    console.print("Enter one path per line. Press Enter on an empty line to finish.")
    library_roots = []
    while True:
        path = safe_prompt("Library path").strip()
        if not path:
            if library_roots:
                break
            else:
                console.print("[red]You must add at least one library path.[/red]")
                continue
        if os.path.isdir(path):
            library_roots.append(path)
            console.print(f"[cyan]Added: {path}[/cyan]")
        else:
            console.print(f"[red]Error: '{path}' is not a valid directory.[/red]")

    # 2. DB Path
    default_db_path = str(CONFIG_FILE.parent / "sluttools.db")
    db_path = safe_prompt(
        "[bold]Enter the path for the database file[/bold]", default=default_db_path
    )

    # 3. M3U Path
    default_m3u_path = str(Path.home() / "Music/Playlists/{playlist_name}.m3u")
    m3u_path = safe_prompt(
        "[bold]Enter the output path for M3U playlists[/bold]", default=default_m3u_path
    )

    # 4. JSON Path
    default_json_path = str(
        Path.home() / "Music/Playlists/{playlist_name}_unmatched.json"
    )
    json_path = safe_prompt(
        "[bold]Enter the output path for JSON reports[/bold]", default=default_json_path
    )

    # 5. Thresholds
    threshold_auto = safe_prompt(
        "[bold]Enter the auto-match threshold (0-100)[/bold]", default="85"
    )
    review_min = safe_prompt(
        "[bold]Enter the minimum score for manual review (0-100)[/bold]", default="75"
    )

    # Create config dictionary
    new_config = {
        "LIBRARY_ROOTS": library_roots,
        "DB_PATH": db_path,
        "MATCH_OUTPUT_PATH_M3U": m3u_path,  # Fixed key name to match what's used in code
        "MATCH_OUTPUT_PATH_JSON": json_path,  # Fixed key name to match what's used in code
        "THRESHOLD_AUTO_MATCH": int(threshold_auto),
        "THRESHOLD_REVIEW_MIN": int(
            review_min
        ),  # Fixed key name to match what's used in code
    }

    # Save config file
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=4)

    console.print(f"\n[bold green]✓ Configuration saved to {CONFIG_PATH}[/bold green]")
    console.print("You can run 'sluttools config' again to change these settings.")


# --- Matching Wizard ---


def launch_matching_wizard():
    """Synchronous entry point to launch the matching wizard."""
    try:
        asyncio.run(run_matching_wizard())
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold red]Wizard aborted by user. Exiting...[/bold red]")
        sys.exit(0)


async def run_matching_wizard():
    """The main function that executes the interactive matching wizard."""
    try:
        # 1. Initial Setup & UI
        console.clear()

        if Confirm.ask(
            "[bold yellow]Show last 100 tracks from DB before proceeding?[/bold yellow]",
            default=False,
        ):
            with console.status("Loading recent tracks..."):
                recent_tracks = get_last_n_tracks(100)
            if recent_tracks:
                console.print("[bold cyan]Last 100 tracks added:[/bold cyan]")
                for track in recent_tracks:
                    console.print(f"- {Path(track['path']).name}")
            else:
                console.print("[yellow]No tracks found in the database.[/yellow]")

        await animate_title()
        console.clear()

        # 2. Get User Input
        # Keep prompting until a non-empty, existing file path is provided (or user aborts)
        path_in_str = ""
        while True:
            raw = (
                safe_prompt("[bold yellow]Enter path to a playlist file[/bold yellow]")
                .strip("'\"")
                .strip()
            )
            if not raw:
                console.print("[red]Please enter a path to a playlist file.[/red]")
                if not Confirm.ask("Try again?", default=True):
                    return
                continue
            p = Path(raw)
            if not p.exists():
                console.print(f"[red]File not found: {p}[/red]")
                if not Confirm.ask("Try again?", default=True):
                    return
                continue
            path_in_str = raw
            break
        playlist_name = Path(path_in_str).stem

        # 3. Load Library & Playlist
        if Confirm.ask(
            "[bold yellow]Refresh music library database?[/bold yellow]", default=True
        ):
            for library_root in config["LIBRARY_ROOTS"]:
                console.print(f"--- Scanning [bold]{library_root}[/bold] ---")
                refresh_library(config["DB_PATH"], library_root)

        flac_lookup = get_flac_lookup()
        if not flac_lookup:
            console.print(
                "[bold red]Your music library is empty. The wizard cannot continue.[/bold red]"
            )
            return
        console.print(f"FLAC index contains {len(flac_lookup)} entries.")

        entries = get_playlist_tracks(path_in_str)
        if not entries:
            return
        console.print(f"Loaded {len(entries)} track(s) from '{playlist_name}'.")

        # 4. Matching using robust metadata-aware engine with interactive review
        matched_paths = perform_matching_with_review(
            entries,
            flac_lookup,
            playlist_input=path_in_str,
            threshold=int(config.get("THRESHOLD_AUTO_MATCH", 88)),
            review_min=int(config.get("THRESHOLD_REVIEW_MIN", 70)),
        )

        # 4.5 Post-review summary (clarifies any pre-review banners)
        try:
            total_requested = len(entries)
            total_matched = sum(1 for p in matched_paths.values() if p)
            total_unmatched = total_requested - total_matched
            console.print(
                f"[bold cyan]Final summary:[/bold cyan] "
                f"requested: {total_requested}, "
                f"matched: {total_matched}, "
                f"unmatched: {total_unmatched}"
            )
        except Exception as _e:
            console.print(
                f"[yellow]Note: Could not compute final summary ({_e}).[/yellow]"
            )

        # 5. Export Results
        _export_results(matched_paths, playlist_name, config)

    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred in the wizard: {e}[/bold red]"
        )
        import traceback

        console.print(traceback.format_exc())


def _export_results(matched_paths: dict, playlist_name: str, config: dict):
    """
    Handles user confirmation and exporting of matched (M3U) and unmatched (JSON) tracks.

    This function also corrects the file path generation to properly use the
    placeholders from the configuration.
    """
    final_matched = [p for p in matched_paths.values() if p]
    final_unmatched = [e for e, p in matched_paths.items() if p is None]

    # Export M3U for matched tracks
    if final_matched and Confirm.ask(
        f"[bold yellow]Create M3U for {len(final_matched)} matched tracks?[/bold yellow]",
        default=True,
    ):
        m3u_path_template = config["MATCH_OUTPUT_PATH_M3U"]
        # Accept either str or Path in config; always format as string first
        m3u_path_str = str(m3u_path_template).format(playlist_name=playlist_name)
        m3u_path = Path(m3u_path_str)
        m3u_path.parent.mkdir(exist_ok=True, parents=True)
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("\n".join(final_matched) + "\n")
        console.print(f"[cyan]✓ M3U saved to {m3u_path}[/cyan]")

    # Export JSON for unmatched tracks
    if final_unmatched and Confirm.ask(
        f"[bold yellow]Export {len(final_unmatched)} unmatched tracks to JSON?[/bold yellow]",
        default=True,
    ):
        json_path_template = config["MATCH_OUTPUT_PATH_JSON"]
        json_path_str = str(json_path_template).format(playlist_name=playlist_name)
        json_path = Path(json_path_str)
        json_path.parent.mkdir(exist_ok=True, parents=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final_unmatched, f, indent=4)
        console.print(f"[cyan]✓ Unmatched tracks log saved to {json_path}[/cyan]")


# --- UI & Rendering --


def render_design_box(offset: int) -> Text:
    """Renders the animated 'GEORGIE'S PLAYLIST MAGIC BOX' title."""
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
            animated.append(ch, style=f"bold {colors[(i + offset) % 3]}")
        return animated

    box = Text()
    box.append(Text("─" * total_width, style="bold green"))
    box.append("\n")

    heart_colors = ["red", "yellow", "blue"]
    for i in range(3):
        line = Text()
        line.append("♥", style=f"bold {heart_colors[i]}")
        line.append(" " * pad_left, style="bold green")
        line.append(animate_text(text_content, offset))
        line.append(" " * pad_right, style="bold green")
        line.append("♥", style=f"bold {heart_colors[i]}")
        box.append(line)
        box.append("\n")

    arabic_text = "هذا من فضل ربي"
    arabic_length = len(arabic_text)
    available = total_width - arabic_length
    dashes_each = available // 2
    bottom_line = Text("─" * dashes_each, style="bold green")
    bottom_line.append(arabic_text, style="bold dark_green")
    bottom_line.append(
        "─" * (total_width - dashes_each - arabic_length), style="bold green"
    )
    box.append(bottom_line)
    return box


async def animate_title():
    """Animates the title box and waits for the user to press Enter."""
    start_time = asyncio.get_event_loop().time()
    enter_future = asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
    refresh_rate = 0.2
    wait_time = 4.0

    with Live(
        console=console, refresh_per_second=1 / refresh_rate, auto_refresh=False
    ) as live:
        while not enter_future.done():
            elapsed = asyncio.get_event_loop().time() - start_time
            offset = int(elapsed * 5)
            box_text = render_design_box(offset)

            if elapsed >= wait_time:
                prompt_text = (
                    "ENTER" if int(elapsed / refresh_rate) % 2 == 0 else "     "
                )
                pad_left = (70 - len(prompt_text)) // 2
                enter_line = " " * pad_left + prompt_text
                combined = Text("\n\n").join(
                    [box_text, Text(enter_line, style="bold dark_grey")]
                )
                live.update(Align.center(combined), refresh=True)
            else:
                live.update(Align.center(box_text), refresh=True)

            await asyncio.sleep(refresh_rate)


def safe_prompt(prompt_text, **kwargs):
    """A wrapper for Rich's Prompt that handles Ctrl+C and EOF."""
    try:
        return Prompt.ask(prompt_text, **kwargs)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold red]Process aborted by user. Exiting...[/bold red]")
        sys.exit(0)


if __name__ == "__main__":
    # Minimal entrypoint to make wizard.py executable directly.
    # Usage:
    #   python sluttools/wizard.py                 -> config wizard
    #
    #
    #     -> matching wizard
    import argparse

    parser = argparse.ArgumentParser(description="sluttools setup and matching wizards")
    parser.add_argument(
        "--mode",
        choices=["config", "match"],
        default="config",
        help="Which wizard to run: configuration (default) or playlist matching.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Auto-match threshold (0-100) to override config.",
    )
    parser.add_argument(
        "--review",
        type=int,
        default=None,
        help="Minimum score for manual review (0-100) to override config.",
    )
    args = parser.parse_args()

    # Allow CLI to override thresholds
    if args.threshold is not None:
        try:
            config["THRESHOLD_AUTO_MATCH"] = int(args.threshold)
        except Exception:
            pass
    if args.review is not None:
        try:
            config["THRESHOLD_REVIEW_MIN"] = int(args.review)
        except Exception:
            pass

    try:
        if args.mode == "config":
            launch_config_wizard()
        else:
            asyncio.run(run_matching_wizard())
    except (KeyboardInterrupt, EOFError):
        console.print("\n[bold red]Aborted by user. Exiting...[/bold red]")
        sys.exit(0)
