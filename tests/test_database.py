"""Functional tests for the database module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from music_automation.core import database


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE flacs (
            path TEXT PRIMARY KEY,
            norm TEXT NOT NULL,
            mtime INTEGER NOT NULL,
            artist TEXT,
            album TEXT,
            title TEXT,
            trackno TEXT,
            year TEXT,
            format_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE formats (
            path TEXT PRIMARY KEY,
            nb_streams TEXT,
            nb_programs TEXT,
            nb_stream_groups TEXT,
            format_name TEXT,
            format_long_name TEXT,
            start_time TEXT,
            duration TEXT,
            size TEXT,
            bit_rate TEXT,
            probe_score TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE flac_tags (
            path TEXT,
            tag_key TEXT,
            tag_value TEXT
        )
        """
    )


def test_refresh_library_updates_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure refresh_library inserts new entries and skips unchanged files."""

    db_path = tmp_path / "test.db"
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    conn = sqlite3.connect(db_path)
    create_table(conn)
    conn.close()
    f1 = lib_dir / "one.flac"
    f2 = lib_dir / "two.flac"
    f1.write_text("a")
    f2.write_text("b")

    calls: list[Path] = []

    def fake_gather_metadata(p: Path):
        calls.append(p)
        row = (
            str(p),
            f"norm-{p.stem}",
            int(p.stat().st_mtime),
            "Artist",
            "Album",
            p.stem,
            "1",
            "2020",
            "{}",
        )
        return (row, None, [])

    monkeypatch.setattr(database, "gather_metadata", fake_gather_metadata)

    database.refresh_library(str(db_path), str(lib_dir))

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT path FROM flacs"))
    conn.close()

    assert {Path(r[0]).name for r in rows} == {"one.flac", "two.flac"}
    assert len(calls) == 2

    calls.clear()
    database.refresh_library(str(db_path), str(lib_dir))
    assert calls == []  # second run should skip unchanged files


def test_get_problematic_sample_rates(tmp_path: Path) -> None:
    """Verify only non-standard sample rates are returned."""

    db_path = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db_path)
    create_table(conn)
    conn.executemany(
        "INSERT INTO flacs VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                str(tmp_path / "a.flac"),
                "a",
                1,
                None,
                None,
                None,
                None,
                None,
                '{"tags": {"SAMPLERATE": "96000"}}',
            ),
            (
                str(tmp_path / "b.flac"),
                "b",
                1,
                None,
                None,
                None,
                None,
                None,
                '{"tags": {"SAMPLERATE": "44100"}}',
            ),
        ],
    )
    conn.commit()
    conn.close()

    rates = database.get_problematic_sample_rates(str(db_path))
    assert rates == [96000]


def test_batch_resample_invokes_sox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure batch_resample chooses nearest rate and calls SoX."""

    db_path = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db_path)
    create_table(conn)
    conn.execute(
        "INSERT INTO flacs VALUES (?,?,?,?,?,?,?,?,?)",
        (
            str(tmp_path / "song.flac"),
            "s",
            1,
            None,
            None,
            None,
            None,
            None,
            '{"tags": {"SAMPLERATE": "88200"}}',
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        database,
        "get_problematic_sample_rates",
        lambda _: [88200],
    )

    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    runs: list[list[str]] = []
    monkeypatch.setattr(
        database.subprocess,
        "run",
        lambda cmd: runs.append(cmd),
    )

    database.batch_resample(str(db_path), dry_run=False)

    assert runs, "Expected subprocess.run to be called"
    assert runs[0][0] == "sox"
    assert runs[0][4].endswith("48000.flac")


def test_batch_resample_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dry run should not invoke SoX."""

    db_path = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db_path)
    create_table(conn)
    conn.execute(
        "INSERT INTO flacs VALUES (?,?,?,?,?,?,?,?,?)",
        (
            str(tmp_path / "song.flac"),
            "s",
            1,
            None,
            None,
            None,
            None,
            None,
            '{"tags": {"SAMPLERATE": "88200"}}',
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        database,
        "get_problematic_sample_rates",
        lambda _: [88200],
    )

    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    runs: list[list[str]] = []
    monkeypatch.setattr(
        database.subprocess,
        "run",
        lambda cmd: runs.append(cmd),
    )

    database.batch_resample(str(db_path), dry_run=True)

    assert runs == []
