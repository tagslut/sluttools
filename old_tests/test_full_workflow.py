#!/usr/bin/env python3
"""
Test script to verify the complete playlist matching workflow
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the current directory to Python path so we can import from music_automation
sys.path.insert(0, '/Users/georgeskhawam/Downloads/newfiles/MusicAutomation')

from music_automation.playlist_matcher import (
    parse_playlist_file,
    find_all_flacs,
    normalize_string,
    match_entry,
    FLAC_LIBRARY_DIR
)

async def test_full_workflow():
    print("=== TESTING FULL PLAYLIST MATCHING WORKFLOW ===")
    
    # Parse the test playlist
    test_file = "/Users/georgeskhawam/Downloads/newfiles/MusicAutomation/test_real_tracks.json"
    nm, tracks = await parse_playlist_file(test_file)
    
    print(f"Loaded {len(tracks)} tracks from {nm}")
    
    # Get all FLAC files
    all_flacs = find_all_flacs(FLAC_LIBRARY_DIR)
    print(f"Found {len(all_flacs)} FLAC files")
    
    # Create the lookup table
    flac_lookup = [(f, normalize_string(os.path.basename(f))) for f in all_flacs]
    print("Created FLAC lookup table")
    
    # Test matching for each track
    matched_count = 0
    for i, track in enumerate(tracks, 1):
        print(f"\nTesting Track {i}: {track.get('title', 'Unknown')} - {track.get('artist', 'Unknown')}")
        
        result = match_entry(track, flac_lookup, None, None, len(tracks))
        
        if result:
            print(f"  ✅ MATCHED: {os.path.basename(result)}")
            matched_count += 1
        else:
            print(f"  ❌ NO MATCH")
    
    print(f"\n=== RESULTS ===")
    print(f"Total tracks: {len(tracks)}")
    print(f"Automatically matched: {matched_count}")
    print(f"Unmatched: {len(tracks) - matched_count}")
    print(f"Success rate: {(matched_count/len(tracks)*100):.1f}%")
    
    if matched_count == len(tracks):
        print("🎉 ALL TRACKS SUCCESSFULLY MATCHED!")
    else:
        print("⚠️  Some tracks were not matched")

if __name__ == "__main__":
    asyncio.run(test_full_workflow())
