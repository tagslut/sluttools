#!/bin/bash
# setup_script.sh - Install the music-automation-toolkit package using pip
# Usage: ./setup_script.sh

set -e

# Check for setup.py or pyproject.toml in the current directory
if [[ ! -f setup.py && ! -f pyproject.toml ]]; then
  echo "ERROR: setup.py or pyproject.toml not found in $(pwd)."
  echo "This script must be run from the project root or a directory containing your project files."
  echo "If running in an automated environment, ensure the full project is present, not just this script."
  exit 1
fi

# Get the absolute path to the directory containing this script
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# Install the package in editable mode (preferred for development)
python3 -m pip install -e .

echo "Installation complete!"
