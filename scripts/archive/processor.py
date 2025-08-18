#!/usr/bin/env python3
# Script: Batch resamples FLACs from nonstandard sample rates using SoX; exports/imports tags.
import sqlite3
import os
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_nonstandard_rates(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rates = set()
    for row in cur.execute(
        "SELECT DISTINCT json_extract(format_json, '$.tags.SAMPLERATE') FROM flacs"
    ):
        try:
            rate = int(row[0])
            if rate not in (44100, 48000):
                rates.add(rate)
        except:
            continue
    conn.close()
    return sorted(rates)


def prompt_user_choice(options):
    for i, rate in enumerate(options, 1):
        print(f"{i}. {rate} Hz")
    try:
        sel = int(input("Select a sample rate to process: ")) - 1
        return options[sel]
    except:
        print("Invalid selection.")
        return None


def get_matching_files(db_path, rate):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT path FROM flacs WHERE json_extract(format_json, '$.tags.SAMPLERATE') = ?",
        (str(rate),),
    )
    files = [row[0] for row in cur.fetchall()]
    conn.close()
    return files


def resample_file(src, target_rate, dest_folder):
    src = Path(src)
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest = dest_folder / src.name

    # Export metadata
    tag_file = dest.with_suffix(".tags.txt")
    subprocess.run(["metaflac", f"--export-tags-to={tag_file}", str(src)], check=False)

    # Export artwork (if any)
    art_file = dest.with_suffix(".cover.jpg")
    subprocess.run(
        ["metaflac", f"--export-picture-to={art_file}", str(src)], check=False
    )

    # Resample with SoX
    subprocess.run(
        ["sox", str(src), "-r", str(target_rate), str(dest), "rate", "-v"], check=True
    )

    # Re-apply metadata
    if tag_file.exists():
        subprocess.run(
            ["metaflac", f"--import-tags-from={tag_file}", str(dest)], check=False
        )
        tag_file.unlink()
    if art_file.exists():
        subprocess.run(
            ["metaflac", f"--import-picture-from={art_file}", str(dest)], check=False
        )
        art_file.unlink()

    print(f"✅ Resampled: {src} → {dest}")


def main():
    db_path = os.path.expanduser("~/.flac_index.db")
    dest_root = "resampled"

    rates = get_nonstandard_rates(db_path)
    if not rates:
        print("All files are already at standard sample rates (44.1 kHz or 48 kHz).")
        return

    chosen = prompt_user_choice(rates)
    if not chosen:
        return

    target_rate = 44100 if abs(chosen - 44100) <= abs(chosen - 48000) else 48000
    print(f"\nResampling files with {chosen} Hz → {target_rate} Hz\n")

    files = get_matching_files(db_path, chosen)
    if not files:
        print("No matching files found.")
        return

    max_workers = os.cpu_count() or 4
    print(f"Using {max_workers} parallel workers to process {len(files)} files.\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(resample_file, f, target_rate, dest_root): f for f in files
        }
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Error processing {futures[future]} — {e}")


if __name__ == "__main__":
    main()
