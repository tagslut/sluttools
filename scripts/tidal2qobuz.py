# Script: Delegates to the legacy tidal2qobuz.py in the repo root for backward compatibility.
"""Wrapper script to run the legacy tidal2qobuz utility from scripts/.
Prefer using this script path instead of the root-level file.
"""
from __future__ import annotations

import runpy
from pathlib import Path

# Execute the legacy script for backward compatibility
LEGACY = Path(__file__).resolve().parents[1] / "tidal2qobuz.py"
runpy.run_path(str(LEGACY), run_name="__main__")
