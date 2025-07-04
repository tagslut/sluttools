#!/usr/bin/env python3
"""
Find the exact position of the Life track
"""

import os
import sys
import json
from pathlib import Path

# Add the current directory to Python path so we can import from music_automation
sys.path.insert(0, '/Users/georgeskhawam/Downloads/newfiles/MusicAutomation')

from music_automation.playlist_matcher import (
    normalize_string,
    build_search_string,
    combined_fuzzy_ratio_prenormalized,
    find_all_flacs,
    AUTO_MATCH_THRESHOLD
)

def find_life_track():
    # Get all FLAC files
    flacs = find_all_flacs("/Volumes/sad/MUSIC2")
    print(f"Found {len(flacs)} FLAC files")

    # Create the lookup table
    flac_lookup = [(f, normalize_string(os.path.basename(f))) for f in flacs]

    # Test entry
    entry = {'artist': 'Jamie xx', 'track': 'Life', 'album': 'In Waves'}
    ss = build_search_string(entry)
    ss_norm = normalize_string(ss)

    print(f"Search string: '{ss}'")
    print(f"Normalized: '{ss_norm}'")

    # Find all Jamie xx tracks
    jamie_tracks = []
    for i, (orig_path, norm_basename) in enumerate(flac_lookup):
        if "Jamie xx" in orig_path:
            r = combined_fuzzy_ratio_prenormalized(ss_norm, norm_basename)
            jamie_tracks.append((i, orig_path, norm_basename, r))

    print(f"\nFound {len(jamie_tracks)} Jamie xx tracks:")
    jamie_tracks.sort(key=lambda x: x[3], reverse=True)  # Sort by score

    for pos, path, norm, score in jamie_tracks:
        filename = os.path.basename(path)
        print(f"  Position {pos}: {score}% - {filename}")
        if "Life.flac" in filename:
            print(f"    *** THIS IS THE LIFE TRACK - Position {pos} ***")
            print(f"    *** Normalized: '{norm}' ***")

if __name__ == "__main__":
    find_life_track()
