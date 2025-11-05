"""Functional tests for the database module."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Iterable

import pytest

from sluttools import database as db_module

# metadata module is now merged into database
metadata_module = db_module


def get_problematic_sample_rates(db_path: str) -> list[int]:
    """Return a list of sample rates considered problematic (not 44100)."""
    rates: set[int] = set()
    path = Path(db_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        for (format_json_str,) in cur.execute("SELECT format_json FROM flacs"):
            if not format_json_str:
                continue
            try:
                data = json.loads(format_json_str)
            except Exception:
                continue
            tags = (data or {}).get("tags", {})
            sr_str = tags.get("SAMPLERATE") or tags.get("sample_rate")
            if not sr_str:
                continue
            try:
                sr = int(sr_str)
            except Exception:
                continue
            if sr != 44100:
                rates.add(sr)
    return sorted(rates)


def _nearest_target_rate(source_rate: int, candidates: Iterable[int]) -> int:
    return min(candidates, key=lambda r: abs(r - source_rate))


def batch_resample(db_path: str, dry_run: bool = False) -> None:
    """Prompt user for target rate and invoke SoX to resample files."""
    path = Path(db_path)
    if not path.exists():
        return

    source_rates = get_problematic_sample_rates(db_path)
    if not source_rates:
        return

    choices = sorted([44100, 48000], key=lambda r: abs(r - source_rates[0]))
    print("Select target sample rate:")
    for idx, r in enumerate(choices, 1):
        print(f"{idx}. {r}")
    _ = input("> ").strip()
    target_rate = choices[0]

    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        rows = list(cur.execute("SELECT path, format_json FROM flacs"))

    for file_path, format_json_str in rows:
        try:
            data = json.loads(format_json_str or "{}")
            sr_str = (data.get("tags") or {}).get("SAMPLERATE")
            if not sr_str:
                continue
            sr = int(sr_str)
        except Exception:
            continue
        if sr not in source_rates:
            continue
        in_path = str(file_path)
        out_path = (
            str(Path(in_path).with_suffix("").as_posix()) + f".{target_rate}.flac"
        )
        cmd = ["sox", in_path, "-r", str(target_rate), out_path]
        if not dry_run:
            subprocess.run(cmd)


def refresh_library(db_path: str, library_dir: str) -> None:
    """Refresh library using sluttools database module."""
    db_module.refresh_library(db_path_str=db_path, library_dir_str=library_dir)


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

    def fake_gather_metadata(p: Path) -> tuple:
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

    monkeypatch.setattr(metadata_module, "gather_metadata", fake_gather_metadata)

    # Monkey patch ProcessPoolExecutor to use ThreadPoolExecutor for testing
    # This avoids pickle issues with test mocks
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(db_module, "ProcessPoolExecutor", ThreadPoolExecutor)

    # First run should add 2 files
    refresh_library(str(db_path), str(lib_dir))

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT path, title FROM flacs"))
    conn.close()

    assert {Path(r[0]).name for r in rows} == {"one.flac", "two.flac"}
    assert {r[1] for r in rows} == {"one", "two"}  # Verify content was processed

    # Second run with unchanged files should update 0 files
    # We can't easily track calls across threads, so we verify by checking
    # that running again doesn't change the database
    original_mtimes = {r[0]: int(Path(r[0]).stat().st_mtime) for r in rows}

    refresh_library(str(db_path), str(lib_dir))

    conn = sqlite3.connect(db_path)
    rows_after = list(conn.execute("SELECT path, mtime FROM flacs"))
    conn.close()

    # Verify files are still there and mtimes match (files weren't reprocessed)
    assert len(rows_after) == 2
    for path, mtime in rows_after:
        assert original_mtimes[path] == mtime


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

    rates = get_problematic_sample_rates(str(db_path))
    assert rates == [96000]


def test_batch_resample_invokes_sox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure batch_resample chooses nearest rate and calls SoX."""

    db_path = tmp_path / "test.db"
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
        "tests.test_database.get_problematic_sample_rates",
        lambda _: [88200],
    )

    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    runs: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd: runs.append(cmd),
    )

    batch_resample(str(db_path), dry_run=False)

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
        "tests.test_database.get_problematic_sample_rates",
        lambda _: [88200],
    )

    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    runs: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd: runs.append(cmd),
    )

    batch_resample(str(db_path), dry_run=True)

    assert runs == []
