#!/bin/bash
set -euo pipefail

echo "[MUSIC-AUTOMATION] Starting setup..."

# Ensure Python 3 is installed
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 is not installed. Please install Python3."
    exit 1
fi

# Create virtualenv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[MUSIC-AUTOMATION] Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtualenv
echo "[MUSIC-AUTOMATION] Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "[MUSIC-AUTOMATION] Upgrading pip..."
python -m pip install --upgrade pip

# Install main requirements
if [ -f "requirements.txt" ]; then
    echo "[MUSIC-AUTOMATION] Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "[MUSIC-AUTOMATION] No requirements.txt found. Installing in editable mode from pyproject.toml/setup.py..."
    if [[ -f setup.py || -f pyproject.toml ]]; then
        pip install -e .
    else
        echo "[ERROR] No requirements.txt, setup.py, or pyproject.toml found."
        exit 1
    fi
fi

# Install dev requirements if present
if [ -f "requirements-dev.txt" ]; then
    echo "[MUSIC-AUTOMATION] Installing dev dependencies..."
    pip install -r requirements-dev.txt
fi

# Load .env file if present
if [ -f ".env" ]; then
    echo "[MUSIC-AUTOMATION] Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Run tests if tests/ exists
if [ -d "tests" ]; then
    echo "[MUSIC-AUTOMATION] Running tests..."
    export PYTHONPATH=src
    pytest tests/ --maxfail=1 --disable-warnings
else
    echo "[MUSIC-AUTOMATION] No tests directory found. Skipping tests."
fi

echo "[MUSIC-AUTOMATION] Setup complete."
