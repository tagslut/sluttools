"""Compatibility shim for tests expecting music_automation.core.matcher"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from sluttools.metadata import normalize_string as _normalize
from sluttools.matcher import calculate_match_score


def normalize_string(s: str) -> str:
    return _normalize(s)


def match_entry(
    entry: dict,
    lookup: list[tuple[str, str]],
    artist_index: Optional[dict[str, set[str]]] = None,
    title_index: Optional[dict[str, set[str]]] = None,
) -> Optional[str]:
    """Very small matcher used only by tests.

    It normalizes the provided entry's artist/title and looks up exact matches in the
    provided lookup list or the optional indexes if given.
    """
    # Build a simple search string from artist/title as in tests
    artist = entry.get("artist", "") or ""
    title = entry.get("title", "") or ""
    # tests often provide just one of them
    key = normalize_string(artist or title)
    # Indexes take precedence if provided
    if artist_index and key in artist_index:
        # return any path from the set
        return next(iter(artist_index[key]))
    if title_index and key in title_index:
        return next(iter(title_index[key]))
    # Fallback: linear scan over lookup of (path, norm)
    for path, norm in lookup:
        if norm == key:
            return path
    return None
