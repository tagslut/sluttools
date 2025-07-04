#!/bin/bash
# setup_script.sh - Install the music-automation-toolkit package using pip
# Usage: ./setup_script.sh

set -e

# Get the absolute path to the directory containing this script
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# Install the package in editable mode (preferred for development)
python3 -m pip install -e .

echo "Installation complete!"
