#!/usr/bin/env python3
"""
Music Tools - Unified CLI for Music Library Automation

This script provides a unified command-line interface to all music automation tools:
- Playlist matching and generation
- FLAC database management  
- Playlist file copying
- FLAC resampling
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up console
console = Console()

def get_default_db_path():
    """Get default database path"""
    return str(Path.home() / ".flac_index.db")

def create_parser():
    """Create the unified command-line argument parser"""
    parser = argparse.ArgumentParser(
        description="Music Tools - Unified music library automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # === PLAYLIST COMMANDS ===

    # Match playlist command (from g.py)
    match_parser = subparsers.add_parser(
        "match",
        help="Match playlist tracks to FLAC library"
    )
    match_parser.add_argument(
        "playlist",
        nargs="?",
        help="Path to playlist file or folder"
    )

    # Copy playlist command (from copy_playlist.py)
    copy_parser = subparsers.add_parser(
        "copy",
        help="Copy files from a playlist to a destination directory"
    )
    copy_parser.add_argument(
        "playlist",
        help="Path to M3U playlist file"
    )
    copy_parser.add_argument(
        "destination",
        help="Destination directory"
    )
    copy_parser.add_argument(
        "-f", "--flat",
        action="store_true",
        help="Flat copy (no directory structure)"
    )
    copy_parser.add_argument(
        "-p", "--preserve",
        action="store_true",
        help="Preserve directory structure"
    )
    copy_parser.add_argument(
        "-a", "--artist-folders",
        action="store_true",
        help="Organize by Artist/Album folders"
    )
    copy_parser.add_argument(
        "-t", "--threads",
        type=int,
        default=4,
        help="Number of parallel copy threads"
    )

    # === FLAC DATABASE COMMANDS ===

    # Database refresh command (from flacdb.py)
    db_parser = subparsers.add_parser(
        "db",
        help="FLAC database management"
    )
    db_subparsers = db_parser.add_subparsers(dest="db_command")

    # DB Refresh command
    refresh_parser = db_subparsers.add_parser(
        "refresh",
        help="Refresh the FLAC library index"
    )
    refresh_parser.add_argument(
        "--db",
        default=get_default_db_path(),
        help="Path to SQLite database"
    )
    refresh_parser.add_argument(
        "--library",
        default="/Volumes/sad/MUSIC2",
        help="Path to FLAC library"
    )

    # DB List command
    list_parser = db_subparsers.add_parser(
        "list",
        help="List entries in the database"
    )
    list_parser.add_argument(
        "--db",
        default=get_default_db_path(),
        help="Path to SQLite database"
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of results"
    )
    list_parser.add_argument(
        "--where",
        help="SQL WHERE clause to filter results"
    )

    # DB Show command
    show_parser = db_subparsers.add_parser(
        "show",
        help="Show details for a single entry"
    )
    show_parser.add_argument(
        "--db",
        default=get_default_db_path(),
        help="Path to SQLite database"
    )
    show_parser.add_argument(
        "path",
        help="Path to the FLAC file"
    )

    # === RESAMPLING COMMANDS ===

    # Resample command (from flacdb.py and resample_flacs.py)
    resample_parser = subparsers.add_parser(
        "resample",
        help="Batch resample FLAC files"
    )
    resample_parser.add_argument(
        "--db",
        default=get_default_db_path(),
        help="Path to SQLite database"
    )
    resample_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying files"
    )
    resample_parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of parallel resampling threads"
    )

    return parser

def show_help():
    """Show help and available commands"""
    console.print("\n[bold cyan]Music Tools - Unified CLI for Music Library Automation[/bold cyan]")
    console.print("[dim]A unified interface to music management tools[/dim]\n")

    table = Table(show_header=True, header_style="bold yellow")
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    table.add_column("Example", style="green")

    table.add_row(
        "match",
        "Match playlist tracks to FLAC library",
        "musictools match playlist.csv"
    )
    table.add_row(
        "copy",
        "Copy files from a playlist to a destination",
        "musictools copy playlist.m3u /destination"
    )
    table.add_row(
        "db refresh",
        "Refresh the FLAC database index",
        "musictools db refresh --library /path/to/flacs"
    )
    table.add_row(
        "db list",
        "List entries in the FLAC database",
        "musictools db list --limit 10"
    )
    table.add_row(
        "db show",
        "Show details for a specific file",
        "musictools db show /path/to/file.flac"
    )
    table.add_row(
        "resample",
        "Batch resample FLAC files",
        "musictools resample"
    )

    console.print(table)
    console.print("\n[bold]For more details on a specific command:[/bold] musictools [command] --help")

def run_script(script_path, args=None):
    """Run a Python script with arguments"""
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running {os.path.basename(script_path)}: {e}[/bold red]")
        return False
    except FileNotFoundError:
        console.print(f"[bold red]Script not found: {script_path}[/bold red]")
        return False
    return True

def main():
    """Main entry point for the unified CLI"""
    parser = create_parser()

    if len(sys.argv) == 1:
        show_help()
        return

    try:
        args = parser.parse_args()

        # Handle playlist matching
        if args.command == "match":
            script_path = os.path.join(os.path.dirname(__file__), "..", "core", "matcher.py")
            if os.path.exists(script_path):
                script_args = []
                if hasattr(args, 'playlist') and args.playlist:
                    script_args.append(args.playlist)
                run_script(script_path, script_args)
            else:
                console.print(f"[bold red]Error: Playlist matching script not found at {script_path}[/bold red]")

        # Handle playlist copying
        elif args.command == "copy":
            script_path = os.path.join(os.path.dirname(__file__), "..", "core", "copier.py")
            if os.path.exists(script_path):
                copy_args = [args.playlist, args.destination]
                if args.flat:
                    copy_args.append("--flat")
                if args.preserve:
                    copy_args.append("--preserve")
                if args.artist_folders:
                    copy_args.append("--artist-folders")
                if args.threads:
                    copy_args.extend(["--threads", str(args.threads)])

                run_script(script_path, copy_args)
            else:
                console.print(f"[bold red]Error: Playlist copy script not found at {script_path}[/bold red]")

        # Handle database commands
        elif args.command == "db":
            script_path = os.path.join(os.path.dirname(__file__), "..", "core", "database.py")
            if not os.path.exists(script_path):
                console.print(f"[bold red]Error: FLAC database script not found at {script_path}[/bold red]")
                return

            if args.db_command == "refresh":
                db_args = ["refresh", "--db", args.db, "--library", args.library]
                run_script(script_path, db_args)

            elif args.db_command == "list":
                db_args = ["list", "--db", args.db]
                if args.limit:
                    db_args.extend(["--limit", str(args.limit)])
                if args.where:
                    db_args.extend(["--where", args.where])
                run_script(script_path, db_args)

            elif args.db_command == "show":
                db_args = ["show", "--db", args.db, args.path]
                run_script(script_path, db_args)

            else:
                console.print("[bold red]Error: Missing database command[/bold red]")
                parser.parse_args(["db", "--help"])

        # Handle resampling
        elif args.command == "resample":
            script_path = os.path.join(os.path.dirname(__file__), "..", "core", "database.py")
            if os.path.exists(script_path):
                resample_args = ["resample", "--db", args.db]
                if args.dry_run:
                    resample_args.append("--dry-run")
                run_script(script_path, resample_args)
            else:
                console.print(f"[bold red]Error: FLAC database script not found at {script_path}[/bold red]")

        # No command specified
        else:
            show_help()

    except Exception as e:
        console.print(f"[bold red]Error executing command: {str(e)}[/bold red]")
        console.print("[yellow]For help, use: musictools --help[/yellow]")

if __name__ == "__main__":
    try:
        console.print("[cyan]Starting Music Tools CLI...[/cyan]")
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Process interrupted by user. Exiting...[/bold red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
