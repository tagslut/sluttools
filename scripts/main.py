# Script: Thin wrapper to run the sluttools CLI (same as `python -m sluttools`).
"""Entry point wrapper. Equivalent to `python -m sluttools`."""
from __future__ import annotations

from sluttools.__main__ import app

if __name__ == "__main__":
    app()
