#!/usr/bin/env python3
"""
Test script to verify the optimized Quick Match mode is working correctly.
"""
import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from music_automation.playlist_matcher import (
    find_all_flacs, parse_playlist_file, match_entry, 
    normalize_string, AUTO_MATCH_THRESHOLD
)

async def test_quick_match():
    """Test the quick match mode with a test playlist"""
    print("Testing Quick Match mode...")
    
    # Check for test playlist
    playlist_path = "James Blake.m3u"
    if not os.path.exists(playlist_path):
        print(f"Error: Playlist file {playlist_path} not found")
        print("Available playlist files:")
        for f in os.listdir("."):
            if f.endswith((".m3u", ".json", ".csv")):
                print(f"  - {f}")
        return
    
    # Parse the playlist
    playlist_name, entries = await parse_playlist_file(playlist_path)
    print(f"Loaded {len(entries)} tracks from '{playlist_name}'")
    
    # Set up FLAC library directory
    music_dir = "/Volumes/sad/MUSIC2"
    if not os.path.exists(music_dir):
        print(f"Error: Music directory {music_dir} not found")
        return
    
    # Load FLAC files
    print("Loading FLAC files...")
    flac_files = find_all_flacs(music_dir)
    print(f"Found {len(flac_files)} FLAC files")
    
    if not flac_files:
        print("No FLAC files found!")
        return
    
    # Create the lookup table
    print("Creating lookup table...")
    flac_lookup = [(f, normalize_string(os.path.basename(f))) for f in flac_files]
    print(f"Created lookup table with {len(flac_lookup)} entries")
    
    # Test Quick Match mode
    print(f"\nTesting Quick Match mode with {len(entries)} tracks...")
    start_time = time.time()
    
    # Match each entry (simulating Quick Match mode)
    matched_count = 0
    for i, entry in enumerate(entries):
        result = match_entry(entry, flac_lookup, playlist_size=len(entries))
        if result:
            matched_count += 1
        status = "✓ MATCHED" if result else "✗ NO MATCH"
        print(f"Track {i+1:2d}/{len(entries)}: {status}")
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Results
    print(f"\nQuick Match Results:")
    print(f"- Matched: {matched_count}/{len(entries)} tracks ({matched_count/len(entries)*100:.1f}%)")
    print(f"- Processing time: {elapsed:.2f} seconds")
    print(f"- Average time per track: {elapsed/len(entries):.3f} seconds")
    
    if len(entries) <= 50:
        print("✓ Small playlist detected - Quick Match mode should be auto-selected")
    else:
        print("• Large playlist - other optimization modes might be better")
    
    return elapsed, matched_count, len(entries)

if __name__ == "__main__":
    asyncio.run(test_quick_match())
