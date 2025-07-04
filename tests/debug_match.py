#!/usr/bin/env python3
"""
Debug a specific match to understand what's happening
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

def debug_match_entry(entry, flac_lookup):
    """Debug version of match_entry with detailed logging"""
    print(f"\n=== DEBUGGING MATCH_ENTRY ===")
    print(f"Entry: {entry}")

    ss = build_search_string(entry)
    if not ss:
        print("No search string - returning None")
        return None

    print(f"Search string: '{ss}'")

    # Normalize the search string once
    ss_norm = normalize_string(ss)
    print(f"Normalized search string: '{ss_norm}'")

    results = []
    print(f"Checking {len(flac_lookup)} FLAC files...")

    # Check first 10 files for debugging
    for i, (orig_path, norm_basename) in enumerate(flac_lookup[:10]):
        r = combined_fuzzy_ratio_prenormalized(ss_norm, norm_basename)
        print(f"  {i+1}. {r}% - {os.path.basename(orig_path)}")

        if r >= AUTO_MATCH_THRESHOLD:
            print(f"    ✓ ABOVE THRESHOLD ({AUTO_MATCH_THRESHOLD}) - would return: {orig_path}")
            return orig_path

        results.append((orig_path, r))

    print(f"No early matches found in first 10 files")

    # Continue with the rest but limit output
    life_found = False
    for i, (orig_path, norm_basename) in enumerate(flac_lookup[10:], 11):
        r = combined_fuzzy_ratio_prenormalized(ss_norm, norm_basename)

        # Check if this is the "Life" track we're looking for
        if "Life.flac" in orig_path and "Jamie xx" in orig_path:
            print(f"  {i}. {r}% - {os.path.basename(orig_path)} *** THIS IS THE LIFE TRACK ***")
            life_found = True

        if r >= AUTO_MATCH_THRESHOLD + 15:  # Higher threshold for immediate match
            print(f"  {i}. {r}% - {os.path.basename(orig_path)} ✓ IMMEDIATE MATCH")
            return orig_path

        results.append((orig_path, r))

        # Show only high-scoring matches
        if r >= 90:
            print(f"  {i}. {r}% - {os.path.basename(orig_path)} (high score)")

    if not life_found:
        print("*** WARNING: The 'Life' track was not found in the FLAC files! ***")

    if not results:
        print("No results found - returning None")
        return None

    # Sort by ratio (descending)
    results.sort(key=lambda x: x[1], reverse=True)
    best = results[0]

    print(f"\nBest match: {best[1]}% - {os.path.basename(best[0])}")
    print(f"Threshold: {AUTO_MATCH_THRESHOLD}")

    # Return the original path if above threshold
    if best[1] >= AUTO_MATCH_THRESHOLD:
        print(f"✓ ABOVE THRESHOLD - returning: {best[0]}")
        return best[0]
    else:
        print(f"✗ BELOW THRESHOLD - returning None")
        return None

async def test_debug():
    # Load the test JSON file
    test_file = "/Users/georgeskhawam/Downloads/newfiles/MusicAutomation/test_real_tracks.json"

    with open(test_file, 'r') as f:
        data = json.load(f)

    # Get track 4 (Jamie xx - Life)
    track = data[0]['tracks'][3]  # 0-indexed, so track 4 is index 3

    print(f"Testing track: {track}")

    # Get all FLAC files
    flacs = find_all_flacs("/Volumes/sad/MUSIC2")
    print(f"Found {len(flacs)} FLAC files")

    # Create the lookup table
    flac_lookup = [(f, normalize_string(os.path.basename(f))) for f in flacs]

    # Test the problematic track
    result = debug_match_entry(track, flac_lookup)

    if result:
        print(f"\n✓ FINAL RESULT: {result}")
    else:
        print(f"\n✗ FINAL RESULT: No match")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_debug())
