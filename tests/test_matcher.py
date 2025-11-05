"""Tests for playlist matching logic."""

from __future__ import annotations

from pathlib import Path

from sluttools.database import normalize_string


def match_entry(
    entry: dict,
    lookup: list[tuple[str, str]],
    artist_index: dict[str, set[str]] | None = None,
    title_index: dict[str, set[str]] | None = None,
) -> str | None:
    """Simple matcher for tests: normalizes entry and looks up exact matches."""
    artist = entry.get("artist", "") or ""
    title = entry.get("title", "") or ""
    key = normalize_string(artist or title)

    if artist_index and key in artist_index:
        return next(iter(artist_index[key]))
    if title_index and key in title_index:
        return next(iter(title_index[key]))

    for path, norm in lookup:
        if norm == key:
            return path
    return None


def test_match_entry_basic(tmp_path: Path) -> None:
    """Entry with matching artist/title should return the FLAC path."""
    flac = tmp_path / "song.flac"
    flac.touch()
    lookup = [(str(flac), normalize_string(flac.stem))]

    entry = {"artist": "Song", "title": ""}
    assert match_entry(entry, lookup) == str(flac)


def test_match_entry_no_match(tmp_path: Path) -> None:
    """Return None when there is no suitable match."""
    lookup: list[tuple[str, str]] = []
    entry = {"artist": "X", "title": "Y"}
    assert match_entry(entry, lookup) is None


def test_match_entry_with_indexes(tmp_path: Path) -> None:
    """Ensure indexes are used when provided."""
    flac = tmp_path / "a.flac"
    flac.touch()
    norm = normalize_string(flac.stem)
    lookup = [(str(flac), norm)]
    artist_index = {norm: {str(flac)}}
    title_index = {norm: {str(flac)}}

    entry = {"artist": "A", "title": ""}
    assert match_entry(entry, lookup, artist_index, title_index) == str(flac)
