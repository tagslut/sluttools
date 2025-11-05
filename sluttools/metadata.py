from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def normalize_string(s: Optional[str]) -> str:
    """Very small normalizer used for indexing/lookup.
    Keep minimal to avoid changing scoring behavior elsewhere.
    """
    if s is None:
        return ""
    return " ".join(s.strip().lower().split())


def gather_metadata(p: Path | str):
    """Minimal gather_metadata to satisfy imports and tests.

    Returns a tuple: (row, formats_row, tags_rows)
    where row matches the schema used in tests for table `flacs`:
    (path, norm, mtime, artist, album, title, trackno, year, format_json)

    This implementation does not probe audio; tests monkeypatch this symbol
    when behavior is required. Here we just provide sane defaults.
    """
    path = Path(p)
    try:
        mtime = int(path.stat().st_mtime)
    except Exception:
        mtime = 0
    title = path.stem
    row = (
        str(path),
        f"norm-{normalize_string(title) or title}",
        mtime,
        None,  # artist
        None,  # album
        title,  # title
        None,  # trackno
        None,  # year
        json.dumps({}),  # format_json
    )
    return (row, None, [])


# Existing placeholder kept (not used by current tests)
# Included to avoid breaking imports referencing it elsewhere.
def calculate_match_score(source, candidate):
    """Placeholder scoring function. Returns 0.0 until fully implemented."""
    return 0.0


def parse_filename_structure(p: Path | str) -> Dict[str, Any]:
    """Parse a music file path into a lightweight metadata dict.

    Heuristics only; aims to provide enough fields for calculate_match_score:
      - artist, title, album, year, duration
    Other keys may be included for future use.
    """
    path = Path(p)
    album = None
    artist = None
    title = path.stem
    trackno = None
    year = None

    # Try to extract track number at start of filename: "01 - ..." or "1. ..."
    m = re.match(r"^(\d{1,3})[\s_.-]+(.+)$", title)
    if m:
        try:
            trackno = int(m.group(1))
        except Exception:
            trackno = None
        title = m.group(2).strip()

    # If filename contains an artist prefix, split once to get the remainder
    if " - " in title:
        first, rest = title.split(" - ", 1)
        # Heuristic: if the first segment isn't obviously part of an album marker, treat as artist
        if not artist and len(first) <= 80:
            artist = first.strip() or artist
            title = rest.strip() or title

    # Handle filenames like: Artist - (2020) Album - 02. Title
    if artist and " - " in title:
        parts = [seg.strip() for seg in title.split(" - ") if seg.strip()]
        if len(parts) >= 2:
            last = parts[-1]
            m2 = re.match(r"^(\d{1,3})[\s_.-]+(.+)$", last)
            if m2:
                # Extract track number and real title
                try:
                    trackno = trackno or int(m2.group(1))
                except Exception:
                    pass
                title = m2.group(2).strip()
                # Album is everything before the last segment
                if not album:
                    album = " - ".join(parts[:-1]).strip()

    # Derive album and artist from folders if not already set
    parts = list(path.parts)
    parent_name = path.parent.name if path.parent else ""
    if not artist or not album:
        if " - " in parent_name:
            a, b = parent_name.split(" - ", 1)
            if not artist and a.strip():
                artist = a.strip()
            if not album and b.strip():
                album = b.strip()
        else:
            if len(parts) >= 2 and not album:
                album = path.parent.name or album
            if len(parts) >= 3 and not artist:
                artist = path.parent.parent.name or artist

    # Year hint from any path component (prefer album folder and filename middle)
    year_re = re.compile(r"\b(19\d{2}|20\d{2})\b")
    scan_order = []
    # Prefer album and parent_name hints first
    if album:
        scan_order.append(album)
    scan_order.append(parent_name)
    scan_order.extend(reversed(parts))
    for comp in scan_order:
        ym = year_re.search(comp)
        if ym:
            try:
                year = int(ym.group(1))
            except ValueError:
                pass
            break

    return {
        "artist": artist or "",
        "album": album or "",
        "title": title or "",
        "trackno": trackno,
        "year": year,
        "duration": None,
        "path": str(path),
    }
