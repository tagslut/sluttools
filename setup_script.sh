#!/bin/zsh
# setup_script.sh - Install the music-automation-toolkit package using pip
# Usage: ./setup_script.sh

set -e

# Ensure we're in the project root
dirname=$(dirname "$0")
cd "$dirname"

# Install the package in editable mode (preferred for development)
pip install -e .

echo "Installation complete!"
