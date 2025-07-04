#!/usr/bin/env python3
"""
Test FLAC scanning directly
"""

import os
import sys
import glob
from pathlib import Path

# Add the current directory to Python path so we can import from music_automation
sys.path.insert(0, '/Users/georgeskhawam/Downloads/newfiles/MusicAutomation')

from music_automation.playlist_matcher import find_all_flacs, FLAC_LIBRARY_DIR

def test_flac_scan():
    print(f"Testing FLAC scanning...")
    print(f"FLAC_LIBRARY_DIR: {FLAC_LIBRARY_DIR}")
    print(f"Path exists: {os.path.exists(FLAC_LIBRARY_DIR)}")
    
    if not os.path.exists(FLAC_LIBRARY_DIR):
        print("ERROR: FLAC library directory does not exist!")
        return
    
    # Test direct glob
    print(f"\nTesting direct glob...")
    pattern = os.path.join(FLAC_LIBRARY_DIR, "**", "*.flac")
    print(f"Pattern: {pattern}")
    
    direct_files = glob.glob(pattern, recursive=True)
    print(f"Direct glob found: {len(direct_files)} files")
    
    if len(direct_files) > 0:
        print(f"First 5 files:")
        for i, f in enumerate(direct_files[:5]):
            print(f"  {i+1}. {f}")
    
    # Test the function from g.py
    print(f"\nTesting find_all_flacs function...")
    func_files = find_all_flacs(FLAC_LIBRARY_DIR)
    print(f"Function found: {len(func_files)} files")
    
    if len(func_files) > 0:
        print(f"First 5 files:")
        for i, f in enumerate(func_files[:5]):
            print(f"  {i+1}. {f}")
    
    # Test with a smaller subdirectory
    print(f"\nTesting with first subdirectory...")
    try:
        subdirs = [d for d in os.listdir(FLAC_LIBRARY_DIR) if os.path.isdir(os.path.join(FLAC_LIBRARY_DIR, d))]
        if subdirs:
            test_subdir = os.path.join(FLAC_LIBRARY_DIR, subdirs[0])
            print(f"Test subdir: {test_subdir}")
            
            subdir_pattern = os.path.join(test_subdir, "**", "*.flac")
            subdir_files = glob.glob(subdir_pattern, recursive=True)
            print(f"Subdir found: {len(subdir_files)} files")
            
            if len(subdir_files) > 0:
                print(f"First 3 files:")
                for i, f in enumerate(subdir_files[:3]):
                    print(f"  {i+1}. {f}")
    except Exception as e:
        print(f"Error testing subdirectory: {e}")

if __name__ == "__main__":
    test_flac_scan()
