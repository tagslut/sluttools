#!/usr/bin/env python3
"""
Quick test script to debug the matching logic
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
    parse_json_file,
    match_entry
)

async def test_matching():
    # Load the test JSON file
    test_file = "/Users/georgeskhawam/Downloads/newfiles/MusicAutomation/test_real_tracks.json"

    with open(test_file, 'r') as f:
        data = json.load(f)

    # Parse the tracks
    tracks = data[0]['tracks']

    # Get all FLAC files
    flacs = find_all_flacs("/Volumes/sad/MUSIC2")
    print(f"Found {len(flacs)} FLAC files")

    # Create the lookup table
    flac_lookup = [(f, normalize_string(os.path.basename(f))) for f in flacs]

    # Test each track
    for i, track in enumerate(tracks):
        print(f"\n=== Testing Track {i+1}: {track.get('title', 'Unknown')} by {track.get('artist', 'Unknown')} ===")

        # Build search string
        search_str = build_search_string(track)
        search_norm = normalize_string(search_str)

        print(f"Search string: '{search_str}'")
        print(f"Normalized: '{search_norm}'")

        # Test matching
        result = match_entry(track, flac_lookup, None, None, len(tracks))

        if result:
            print(f"✓ MATCHED: {result}")
        else:
            print("✗ NO MATCH")

            # Find best candidates manually
            candidates = []
            for orig_path, norm_basename in flac_lookup:
                score = combined_fuzzy_ratio_prenormalized(search_norm, norm_basename)
                if score >= 50:  # Only show decent matches
                    candidates.append((orig_path, score))

            # Sort by score
            candidates.sort(key=lambda x: x[1], reverse=True)

            print("Top 5 candidates:")
            for j, (path, score) in enumerate(candidates[:5]):
                print(f"  {j+1}. {score}% - {os.path.basename(path)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_matching())
