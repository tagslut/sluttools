#!/usr/bin/env python3
"""
Simple CLI for Music Library Tools
"""

import os
import sys
import argparse
from rich.console import Console

console = Console()

def main():
    console.print("[bold cyan]Music Tools CLI[/bold cyan]")

    parser = argparse.ArgumentParser(description="Music Tools CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Match command
    match_parser = subparsers.add_parser("match", help="Match playlist")

    # Copy command
    copy_parser = subparsers.add_parser("copy", help="Copy playlist files")

    # DB command
    db_parser = subparsers.add_parser("db", help="Database commands")

    # If no arguments, show help
    if len(sys.argv) == 1:
        console.print("[yellow]Available commands:[/yellow]")
        console.print("  match - Match playlist tracks")
        console.print("  copy  - Copy playlist files")
        console.print("  db    - Database commands")
        return

    # Parse arguments
    args = parser.parse_args()
    console.print(f"You selected: {args.command}")

if __name__ == "__main__":
    main()
