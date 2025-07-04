#!/usr/bin/env python3
"""
Copy Playlist Files

This script reads an M3U playlist file and copies all audio files to a destination directory.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, TaskID
import concurrent.futures

console = Console()

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(description="Copy music files from a playlist to a destination directory")
    parser.add_argument("playlist", help="Path to M3U playlist file")
    parser.add_argument("destination", help="Destination directory")
    parser.add_argument("-f", "--flat", action="store_true", help="Flat copy (no directory structure)")
    parser.add_argument("-p", "--preserve", action="store_true", help="Preserve directory structure")
    parser.add_argument("-a", "--artist-folders", action="store_true", help="Organize by Artist/Album folders")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Number of parallel copy threads")
    return parser

def read_m3u_playlist(playlist_path):
    """Read file paths from an M3U playlist"""
    file_paths = []
    try:
        with open(playlist_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    file_paths.append(line)
        return file_paths
    except Exception as e:
        console.print(f"[bold red]Error reading playlist: {e}[/bold red]")
        sys.exit(1)

def copy_file(args):
    """Copy a single file with progress reporting"""
    source, dest, task_id, progress = args
    try:
        # Create destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        # Get file size for progress reporting
        file_size = os.path.getsize(source)

        # Copy the file
        shutil.copy2(source, dest)

        # Update progress
        progress.update(task_id, advance=1)

        return True, source, dest
    except Exception as e:
        return False, source, str(e)

def main():
    parser = create_parser()
    args = parser.parse_args()

    # Validate arguments
    if not os.path.isfile(args.playlist):
        console.print(f"[bold red]Error: Playlist file not found: {args.playlist}[/bold red]")
        sys.exit(1)

    # Create destination directory if it doesn't exist
    os.makedirs(args.destination, exist_ok=True)

    # Read playlist
    console.print(f"[cyan]Reading playlist: {args.playlist}[/cyan]")
    file_paths = read_m3u_playlist(args.playlist)
    console.print(f"[green]Found {len(file_paths)} files in playlist[/green]")

    # Prepare copy tasks
    copy_tasks = []
    for source in file_paths:
        if not os.path.isfile(source):
            console.print(f"[yellow]Warning: File not found: {source}[/yellow]")
            continue

        if args.flat:
            # Flat structure: just use filename
            dest = os.path.join(args.destination, os.path.basename(source))
        elif args.artist_folders:
            # Try to extract artist and album from path
            # Assumes a structure like /path/to/Artist/Album/file.flac
            parts = Path(source).parts
            if len(parts) >= 3:
                # Assume last 3 parts are Artist/Album/File
                artist = parts[-3]
                album = parts[-2]
                filename = parts[-1]
                dest = os.path.join(args.destination, artist, album, filename)
            else:
                # Fallback to preserving the structure
                rel_path = os.path.relpath(source, os.path.dirname(os.path.dirname(source)))
                dest = os.path.join(args.destination, rel_path)
        elif args.preserve:
            # Preserve full directory structure
            # Use absolute paths to properly preserve structure
            rel_path = os.path.relpath(source, '/')
            dest = os.path.join(args.destination, rel_path)
        else:
            # Default: preserve only one level of directory structure
            rel_path = os.path.relpath(source, os.path.dirname(os.path.dirname(source)))
            dest = os.path.join(args.destination, rel_path)

        copy_tasks.append((source, dest))

    # Copy files with progress tracking
    with Progress() as progress:
        task_id = progress.add_task("[cyan]Copying files...", total=len(copy_tasks))

        # Process in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Add progress to each task
            tasks = [(src, dst, task_id, progress) for src, dst in copy_tasks]
            results = list(executor.map(copy_file, tasks))

    # Report results
    success_count = sum(1 for success, _, _ in results if success)
    fail_count = len(results) - success_count

    console.print(f"[bold green]Successfully copied {success_count} files[/bold green]")
    if fail_count > 0:
        console.print(f"[bold red]Failed to copy {fail_count} files:[/bold red]")
        for success, source, error in results:
            if not success:
                console.print(f"  [red]- {source}: {error}[/red]")

if __name__ == "__main__":
    main()
