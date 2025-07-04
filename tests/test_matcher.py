"""Tests for playlist matching logic."""

from __future__ import annotations

from pathlib import Path

from music_automation.core.matcher import match_entry, normalize_string


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
