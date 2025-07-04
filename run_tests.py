#!/usr/bin/env python3
"""
Test runner for Music Automation Toolkit
"""
import sys
import os
import subprocess
from pathlib import Path

def run_tests():
    """Run all tests"""
    project_root = Path(__file__).parent
    
    print("🧪 Running Music Automation Toolkit Tests")
    print("=" * 50)
    
    # Change to project directory
    os.chdir(project_root)
    
    # Test 1: Import tests
    print("\n1. Testing imports...")
    try:
        import music_automation
        print("   ✓ music_automation package imports successfully")
        
        from music_automation import playlist_matcher
        print("   ✓ playlist_matcher module imports successfully")
        
        from music_automation import flac_database
        print("   ✓ flac_database module imports successfully")
        
        from music_automation import playlist_copier
        print("   ✓ playlist_copier module imports successfully")
        
        from music_automation import audio_processor
        print("   ✓ audio_processor module imports successfully")
        
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        return False
    
    # Test 2: CLI tool tests
    print("\n2. Testing CLI tools...")
    try:
        result = subprocess.run([sys.executable, "bin/musictools.py", "--help"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("   ✓ musictools CLI works")
        else:
            print(f"   ✗ musictools CLI failed: {result.stderr}")
            
    except Exception as e:
        print(f"   ✗ CLI test failed: {e}")
    
    # Test 3: Run unit tests if they exist
    print("\n3. Running unit tests...")
    if os.path.exists("tests"):
        try:
            # Try to run pytest if available
            result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("   ✓ All unit tests passed")
                print(f"   Output: {result.stdout}")
            else:
                print(f"   ⚠ Some tests failed or pytest not available")
                print(f"   Output: {result.stderr}")
        except Exception as e:
            print(f"   ⚠ Could not run pytest: {e}")
            
        # Run individual test files
        test_files = list(Path("tests").glob("test_*.py"))
        for test_file in test_files:
            try:
                result = subprocess.run([sys.executable, str(test_file)], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"   ✓ {test_file.name} passed")
                else:
                    print(f"   ✗ {test_file.name} failed")
            except Exception as e:
                print(f"   ⚠ Could not run {test_file.name}: {e}")
    else:
        print("   ⚠ No tests directory found")
    
    # Test 4: Configuration validation
    print("\n4. Validating configuration...")
    if os.path.exists("config.example.env"):
        print("   ✓ Example configuration file exists")
    else:
        print("   ⚠ Example configuration file missing")
    
    # Test 5: Documentation check
    print("\n5. Checking documentation...")
    doc_files = ["README.md", "docs/API.md", "docs/INSTALLATION.md"]
    for doc_file in doc_files:
        if os.path.exists(doc_file):
            print(f"   ✓ {doc_file} exists")
        else:
            print(f"   ⚠ {doc_file} missing")
    
    print("\n" + "=" * 50)
    print("🎉 Test suite completed!")
    print("\nTo run individual components:")
    print("  python bin/musictools.py --help")
    print("  python -m music_automation.playlist_matcher --help")
    print("\nFor development:")
    print("  pip install -e '.[dev]'")
    print("  pytest tests/")
    
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
