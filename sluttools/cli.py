import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import typer
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.text import Text

from .config import CONFIG_FILE, CONFIG_PATH, config
from .database import get_flac_lookup, refresh_library
from .matching import (
    find_matches,
    get_playlist_tracks,
    perform_matching_with_review,
    write_match_json,
    write_match_m3u,
    write_songshift_json,
)

app = typer.Typer(help="Get. Match. Tag. Out.")

# Sub-apps
get_app = typer.Typer(help="Fetch data (library, playlists)")
match_app = typer.Typer(help="Match tracks against your library")
tag_app = typer.Typer(help="Tag operations (apply/review)")
out_app = typer.Typer(
    help="Export results: create M3U, JSON mapping, or SongShift JSON from a playlist input"
)
list_app = typer.Typer(help="List information from the DB")
config_app = typer.Typer(help="Edit or show configuration")

console = Console()


################################################################################
# ANIMATED ASCII ART HEADER
################################################################################


def render_design_box(offset: int) -> Text:
    """Render the animated ASCII art header with cycling colors"""
    total_width = 70
    interior_width = total_width - 2
    text_content = "♫ SLUT ♫"
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


async def animate_title(
    refresh_rate: float = 0.2, wait_time: float = 4.0, plain: bool = False
):
    """Display animated title with enter prompt"""
    if plain or os.getenv("NO_COLOR") or os.getenv("SLUT_PLAIN"):
        # Simple non-animated header
        console.print("♫ SLUT ♫", style="bold")
        console.print("(type 'abort' to exit)", style="dim")
        return
    start_time = asyncio.get_event_loop().time()
    enter_future = asyncio.get_event_loop().run_in_executor(None, input, "")
    with Live(console=console, refresh_per_second=int(1 / refresh_rate)) as live:
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            offset = int(elapsed * 2)
            box_text = render_design_box(offset)
            if elapsed >= wait_time:
                if int(elapsed / refresh_rate) % 2 == 0:
                    prompt_text = "ENTER (type 'abort' to exit)"
                else:
                    prompt_text = " " * len("ENTER (type 'abort' to exit)")
                pad_left = (70 - len("ENTER (type 'abort' to exit)")) // 2
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


def safe_prompt(prompt_text, default=None):
    """Safe prompt that allows 'abort' to exit"""
    if default is not None:
        answer = Prompt.ask(prompt_text, default=default)
    else:
        answer = Prompt.ask(prompt_text)
    if answer.strip().lower() == "abort":
        console.print("[bold red]Process aborted by user.[/bold red]")
        raise typer.Exit(0)
    return answer


def safe_confirm(prompt_text, default=True):
    """Safe confirmation prompt that allows 'abort' to exit"""
    default_str = "y" if default else "n"
    answer = Prompt.ask(
        f"{prompt_text} (y/n) [or type 'abort' to exit]", default=default_str
    )
    if answer.strip().lower() == "abort":
        console.print("[bold red]Process aborted by user.[/bold red]")
        raise typer.Exit(0)
    return answer.strip().lower() in ["y", "yes"]


@app.command(hidden=True)
def wizard():
    """Deprecated: use 'slut match review' instead."""
    console.print(
        "[yellow]The wizard command is deprecated. Use 'slut match review' instead.[/yellow]"
    )
    raise typer.Exit(1)


@config_app.command(name="edit")
def config_edit():
    """Run the interactive setup wizard to configure the application."""
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
        "MATCH_OUTPUT_PATH_M3U": m3u_path,
        "MATCH_OUTPUT_PATH_JSON": json_path,
        "THRESHOLD_AUTO_MATCH": int(threshold_auto),
        "THRESHOLD_REVIEW_MIN": int(review_min),
    }

    # Save config file
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=4)

    console.print(f"\n[bold green]✓ Configuration saved to {CONFIG_PATH}[/bold green]")
    console.print("You can run 'slut config edit' again to change these settings.")


@config_app.command(name="show")
def config_show():
    """Show current configuration values."""
    for k, v in config.items():
        console.print(f"[cyan]{k}[/cyan]=[white]{v}[/white]")


@get_app.command(name="library")
def get_library():
    """
    Scan the music library paths and update the database.

    This command walks through the library directories defined in your configuration,
    collecting metadata for all supported audio files found. It is the first step you should
    run, as all other commands depend on an up-to-date database.
    """
    console.print("[cyan]Scanning library paths and updating database...[/cyan]")
    if not config.get("LIBRARY_ROOTS"):
        console.print(
            "[bold red]No library roots configured. Please run 'slut config edit' first.[/bold red]"
        )
        raise typer.Exit(1)
    for library_path in config["LIBRARY_ROOTS"]:
        refresh_library(db_path_str=config["DB_PATH"], library_dir_str=library_path)
    console.print("\n[bold green]✓ Database refresh complete.[/bold green]")


@get_app.command(name="playlist")
def get_playlist(
    playlist: str = typer.Argument(
        ..., help="Path to the playlist file (JSON: SongShift or simple, M3U/M3U8/TXT)"
    )
):
    """Load a playlist and print a brief summary."""
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]No tracks loaded from playlist.[/red]")
        raise typer.Exit(1)
    console.print(
        f"[green]Loaded {len(tracks)} track(s) from {Path(playlist).name}[/green]"
    )


@match_app.command(name="auto")
def match_auto(
    playlist: str = typer.Argument(
        ..., help="Path to the playlist file (JSON: SongShift or simple, M3U/M3U8/TXT)"
    ),
    backend: str = typer.Option(
        "smart",
        "--backend",
        help="Matching backend: smart (metadata-aware) or simple (gg.py-style)",
        case_sensitive=False,
    ),
):
    """
    Non-interactive matching. Computes matches and prints a summary.
    Use 'slut out ...' to write outputs.
    """
    console.print(f"Loading tracks from {playlist}...")
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]Could not load any tracks. Aborting.[/red]")
        raise typer.Exit(1)

    console.print("Finding matches...")
    flac_lookup = get_flac_lookup()
    backend_lc = (backend or "smart").strip().lower()
    if backend_lc not in ("smart", "simple"):
        console.print(
            f"[yellow]Unknown backend '{backend}'. Falling back to 'smart'.[/yellow]"
        )
        backend_lc = "smart"

    if backend_lc == "simple":
        from .matching import simple_find_matches

        matches = simple_find_matches(
            tracks,
            flac_lookup,
            playlist_input=playlist,
            threshold=config["THRESHOLD_AUTO_MATCH"],
        )
    else:
        matches = find_matches(
            tracks,
            flac_lookup,
            playlist_input=playlist,
            threshold=config["THRESHOLD_AUTO_MATCH"],
            review_min=config["THRESHOLD_REVIEW_MIN"],
            interactive=False,
        )

    console.print("\n[bold green]Successful Matches:[/bold green]")
    for track, path in matches.items():
        if path:
            console.print(f"  '{track}' → '{path}'")

    matched_count = len([m for m in matches.values() if m is not None])
    unmatched_count = len(tracks) - matched_count
    console.print(
        f"[bold green]{matched_count} matched[/bold green], [bold red]{unmatched_count} unmatched[/bold red]"
    )
    console.print("Use 'slut out m3u/json/songshift <playlist>' to produce outputs.")


@match_app.command(name="review")
def match_review(
    playlist: str = typer.Argument(
        ..., help="Path to the playlist file (JSON: SongShift or simple, M3U/M3U8/TXT)"
    ),
    plain: bool = typer.Option(False, "--plain", help="Disable animation/colors"),
    no_refresh: bool = typer.Option(
        False, "--no-refresh", help="Skip library reindex for faster review"
    ),
):
    """
    Interactive matching with animated UI and manual review options.
    """
    asyncio.run(_interactive_match_async(playlist, plain=plain, no_refresh=no_refresh))


async def _interactive_match_async(
    playlist: str, plain: bool = False, no_refresh: bool = False
):
    """Async implementation of interactive matching"""
    console.clear()
    # Show last tracks option
    if safe_confirm(
        "[bold cyan]Show last 100 tracks from the index before proceeding?[/bold cyan]",
        default=False,
    ):
        _show_last_tracks(100)
    # Animated intro
    await animate_title(refresh_rate=0.2, wait_time=3.0, plain=plain)
    console.clear()
    # Load playlist
    console.print(f"[green]Loading tracks from {Path(playlist).name}...[/green]")
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]Could not load any tracks. Aborting.[/red]")
        return
    playlist_name = Path(playlist).stem
    console.print(f"[green]Loaded {len(tracks)} track(s) from {playlist_name}[/green]")
    # Refresh library with progress (unless --no-refresh)
    if not no_refresh:
        console.print(f"[cyan]Refreshing library index...[/cyan]")
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}")
        ) as prog:
            prog.add_task(description="Updating index", total=None)
            for library_path in config["LIBRARY_ROOTS"]:
                refresh_library(
                    library_dir_str=library_path, db_path_str=config["DB_PATH"]
                )
    else:
        console.print(
            f"[yellow]Skipping library reindex (--no-refresh set). Using existing DB.[/yellow]"
        )
    flac_lookup = get_flac_lookup()
    console.print(f"[green]Library index contains {len(flac_lookup)} entries[/green]")
    # Enhanced matching with interactive review
    console.print(f"[cyan]Attempting to match {len(tracks)} entries...[/cyan]")
    matches = perform_matching_with_review(
        tracks,
        flac_lookup,
        playlist_input=playlist,
        threshold=config["THRESHOLD_AUTO_MATCH"],
        review_min=config["THRESHOLD_REVIEW_MIN"],
    )

    # Count results
    matched_count = len([m for m in matches.values() if m is not None])
    unmatched_count = len(tracks) - matched_count
    console.print(
        f"[bold green]{matched_count} matched[/bold green], [bold red]{unmatched_count} unmatched[/bold red]"
    )

    # Export unmatched as SongShift JSON
    if unmatched_count > 0 and safe_confirm(
        "[bold yellow]Export unmatched tracks as a SongShift-ready JSON playlist?[/bold yellow]"
    ):
        unmatched_tracks = [
            {"artist": "", "track": track}
            for track, match in matches.items()
            if match is None
        ]
        json_name = f"{playlist_name}_songshift.json"
        write_songshift_json(unmatched_tracks, json_name, playlist_name=playlist_name)

    # Create M3U with custom naming
    matched_paths = [path for path in matches.values() if path is not None]
    if matched_paths and safe_confirm(
        "[bold yellow]Create .m3u with the current matched flacs?[/bold yellow]"
    ):
        default_name = f"{playlist_name}_matched.m3u"
        m3u_filename = (
            safe_prompt("M3U filename", default=default_name).strip().strip("'\"")
        )
        if not m3u_filename.lower().endswith(".m3u"):
            m3u_filename += ".m3u"

        # Write M3U file
        try:
            with open(m3u_filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for path in matched_paths:
                    f.write(f"{path}\n")
            console.print(f"[bold green]Created M3U: {m3u_filename}[/bold green]")
        except Exception as e:
            console.print(f"[red]Error writing M3U: {e}[/red]")
    else:
        console.print("[yellow]Skipping M3U creation.[/yellow]")


def _show_last_tracks(n=100):
    """Show last n tracks from database"""
    from .database import get_last_n_tracks

    tracks = get_last_n_tracks(n)
    console.print(f"[bold cyan]Last {len(tracks)} entries from FLAC DB:[/bold cyan]")
    for track in tracks:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(track["mtime"]))
        console.print(f"{t} | {track['norm']} → {track['path']}")


@list_app.command(name="tracks")
def list_tracks_cmd():
    """
    List all tracks currently in the database.
    """
    flac_lookup = get_flac_lookup()
    for path, _ in flac_lookup:
        console.print(path)


@list_app.command(name="recent")
def list_recent_cmd(n: int = typer.Option(100, help="How many recent tracks to show")):
    _show_last_tracks(n)


@out_app.command(name="m3u")
def out_m3u(
    playlist: Optional[str] = typer.Argument(
        None,
        help="Playlist input file path. Supported: JSON (SongShift or simple), M3U/M3U8, or TXT.",
    ),
    output: str = typer.Option(
        "",
        "--output",
        help="Where to write the .m3u. Defaults to MATCH_OUTPUT_PATH_M3U with {playlist_name} from input filename.",
    ),
):
    """
    Generate an .m3u playlist of matched FLAC files for the given playlist input.

    - Input (<PLAYLIST_INPUT>): JSON (SongShift or simple), M3U/M3U8, or TXT file path.
    - Matching: Uses your FLAC library index and current thresholds to resolve tracks.
    - Output: Writes only successfully matched file paths.
    - Default path: Uses config MATCH_OUTPUT_PATH_M3U (supports {playlist_name}).

    Examples:
      poetry run slut out m3u "/path/playlist.txt"
      poetry run slut out m3u "/path/playlist.json" --output "/tmp/out.m3u"
    """
    if not playlist:
        console.print("[red]Missing parameter: playlist[/red]")
        console.print("Usage: slut out m3u <PLAYLIST_INPUT>")
        raise typer.Exit(2)
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]No tracks loaded from playlist.[/red]")
        raise typer.Exit(1)
    flac_lookup = get_flac_lookup()
    matches = find_matches(
        tracks,
        flac_lookup,
        playlist_input=playlist,
        threshold=config["THRESHOLD_AUTO_MATCH"],
        review_min=config["THRESHOLD_REVIEW_MIN"],
    )
    playlist_name = Path(playlist).stem
    out_path = output or str(config["MATCH_OUTPUT_PATH_M3U"]).format(
        playlist_name=playlist_name
    )
    write_match_m3u(matches, output_path=out_path)
    console.print(f"[bold green]✓ Wrote M3U:[/bold green] {out_path}")


@out_app.command(name="json")
def out_json(
    playlist: Optional[str] = typer.Argument(
        None,
        help="Playlist input file path. Supported: JSON (SongShift or simple), M3U/M3U8, or TXT.",
    ),
    output: str = typer.Option(
        "",
        "--output",
        help="Where to write the .json mapping. Defaults to MATCH_OUTPUT_PATH_JSON with {playlist_name} from input filename.",
    ),
):
    """
    Write a JSON mapping of input tracks to matched FLAC file paths and scores.

    - Input (<PLAYLIST_INPUT>): JSON (SongShift or simple), M3U/M3U8, or TXT file path.
    - Contents: Each input track maps to a path (or null if unmatched) with scoring details.
    - Default path: Uses config MATCH_OUTPUT_PATH_JSON (supports {playlist_name}).

    Examples:
      poetry run slut out json "/path/playlist.m3u8"
      poetry run slut out json "/path/playlist.json" --output "/tmp/matches.json"
    """
    if not playlist:
        console.print("[red]Missing parameter: playlist[/red]")
        console.print("Usage: slut out json <PLAYLIST_INPUT>")
        raise typer.Exit(2)
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]No tracks loaded from playlist.[/red]")
        raise typer.Exit(1)
    flac_lookup = get_flac_lookup()
    matches = find_matches(
        tracks,
        flac_lookup,
        playlist_input=playlist,
        threshold=config["THRESHOLD_AUTO_MATCH"],
        review_min=config["THRESHOLD_REVIEW_MIN"],
    )
    playlist_name = Path(playlist).stem
    out_path = output or str(config["MATCH_OUTPUT_PATH_JSON"]).format(
        playlist_name=playlist_name
    )
    write_match_json(matches, output_path=out_path)
    console.print(f"[bold green]✓ Wrote JSON:[/bold green] {out_path}")


@out_app.command(name="songshift")
def out_songshift(
    playlist: Optional[str] = typer.Argument(
        None,
        help="Playlist input file path. Supported: JSON (SongShift or simple), M3U/M3U8, or TXT.",
    ),
    output: str = typer.Option(
        "",
        "--output",
        help="Where to write the SongShift-ready JSON of unmatched tracks. Defaults to '{playlist_name}_songshift.json'.",
    ),
):
    """
    Export unmatched tracks as a SongShift-compatible JSON playlist for streaming services.

    - Input (<PLAYLIST_INPUT>): JSON (SongShift or simple), M3U/M3U8, or TXT file path.
    - Contents: Only tracks that were not matched to local files are included.
    - Default filename: {playlist_name}_songshift.json next to the current working directory unless --output is set.

    Examples:
      poetry run slut out songshift "/path/playlist.txt"
      poetry run slut out songshift "/path/playlist.m3u" --output "/tmp/playlist_songshift.json"
    """
    if not playlist:
        console.print("[red]Missing parameter: playlist[/red]")
        console.print("Usage: slut out songshift <PLAYLIST_INPUT>")
        raise typer.Exit(2)
    tracks = get_playlist_tracks(playlist)
    if not tracks:
        console.print("[red]No tracks loaded from playlist.[/red]")
        raise typer.Exit(1)
    flac_lookup = get_flac_lookup()
    matches = find_matches(
        tracks,
        flac_lookup,
        playlist_input=playlist,
        threshold=config["THRESHOLD_AUTO_MATCH"],
        review_min=config["THRESHOLD_REVIEW_MIN"],
    )
    playlist_name = Path(playlist).stem
    unmatched_tracks = [
        {"artist": "", "track": track}
        for track, match in matches.items()
        if match is None
    ]
    out_path = output or f"{playlist_name}_songshift.json"
    write_songshift_json(unmatched_tracks, out_path, playlist_name=playlist_name)
    console.print(f"[bold green]✓ Wrote SongShift JSON:[/bold green] {out_path}")


# Tag subcommands (stubs)
@tag_app.command(name="apply")
def tag_apply():
    console.print("[yellow]Tag apply is not implemented yet.[/yellow]")


@tag_app.command(name="review")
def tag_review():
    console.print("[yellow]Tag review is not implemented yet.[/yellow]")


# Mount sub-apps
app.add_typer(get_app, name="get")
app.add_typer(match_app, name="match")
app.add_typer(tag_app, name="tag")
app.add_typer(out_app, name="out")
app.add_typer(list_app, name="list")
app.add_typer(config_app, name="config")


# --- Argparse CLI for 'fla' entrypoint ---


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _wire_match_subparser(sub):
    import argparse

    mp = sub.add_parser("match", help="Match a playlist/folder to local FLACs")
    mp.add_argument("path", help="Playlist file or folder")
    mp.add_argument("--mode", choices=["auto", "quick", "thorough"], default="auto")
    mp.add_argument("--out", choices=["m3u", "csv", "both", "none"], default="m3u")
    mp.add_argument(
        "--no-manual",
        action="store_true",
        help="Run headless: skip interactive prompts",
    )
    mp.add_argument(
        "--library", default=os.getenv("SLUT_LIBRARY", "/Volumes/sad/MUSIC")
    )
    mp.add_argument(
        "--threshold", type=int, default=_env_int("SLUT_AUTO_THRESHOLD", 60)
    )
    mp.add_argument(
        "--title-threshold", type=int, default=_env_int("SLUT_TITLE_THRESHOLD", 70)
    )
    mp.set_defaults(func=_dispatch_match)
    return mp


def _dispatch_match(args):
    import asyncio

    try:
        from sluttools.matching import run_matcher
    except ImportError as e:
        print(f"[fatal] Matcher engine is not available in sluttools.matching: {e}")
        return

    asyncio.run(
        run_matcher(
            path_in=args.path,
            mode=args.mode,
            out=args.out,
            manual=not args.no_manual,
            library=args.library,
            threshold=args.threshold,
            title_threshold=args.title_threshold,
        )
    )


def main():
    import argparse

    ap = argparse.ArgumentParser(
        prog="fla",
        description="A command-line tool for matching playlists to a local FLAC library.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Wire up subcommands
    _wire_match_subparser(sub)

    args = ap.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    app()
