#!/usr/bin/env python3
"""
Centralized configuration for sluttools with env var overrides.
- User config file: ~/.config/sluttools/config.json
- Precedence: environment > user config file > built-in defaults
- Types exposed to the app:
  - LIBRARY_ROOTS: list[Path]
  - DB_PATH: Path
  - MATCH_OUTPUT_PATH_M3U: Path or format string Path (may include {playlist_name})
  - MATCH_OUTPUT_PATH_JSON: Path or format string Path (may include {playlist_name})
  - THRESHOLD_AUTO_MATCH: int
  - THRESHOLD_REVIEW_MIN: int
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.prompt import Prompt

# Paths
CONFIG_DIR = Path.home() / ".config" / "sluttools"
CONFIG_FILE = CONFIG_DIR / "config.json"
# Back-compat alias some modules might import
CONFIG_PATH = CONFIG_FILE

console = Console()

# Built-in defaults (sane, user-agnostic)
DEFAULTS = {
    "LIBRARY_ROOTS": [],  # first run wizard will prompt
    "DB_PATH": str(Path.home() / ".config" / "sluttools" / "flibrary.db"),
    "MATCH_OUTPUT_PATH_M3U": "{playlist_name}.m3u",
    "MATCH_OUTPUT_PATH_JSON": str(Path.cwd() / "json" / "{playlist_name}.json"),
    "THRESHOLD_AUTO_MATCH": 88,
    "THRESHOLD_REVIEW_MIN": 70,
    # Word overlap thresholds for matcher (fractions 0..1)
    # - WORD_OVERLAP_REJECT: below this, a fuzzy match is rejected outright
    # - WORD_OVERLAP_REVIEW: below this, we try to find a better alternative
    # Defaults are deliberately permissive to avoid over-rejecting valid matches
    "WORD_OVERLAP_REJECT": 0.15,
    "WORD_OVERLAP_REVIEW": 0.40,
}

# Environment variable mapping
ENV_MAP = {
    "LIBRARY_ROOTS": "SLUT_LIBRARY_ROOTS",  # comma-separated list
    "DB_PATH": "SLUT_DB_PATH",
    "MATCH_OUTPUT_PATH_M3U": "SLUT_MATCH_OUTPUT_PATH_M3U",
    "MATCH_OUTPUT_PATH_JSON": "SLUT_MATCH_OUTPUT_PATH_JSON",
    "THRESHOLD_AUTO_MATCH": "SLUT_THRESHOLD_AUTO_MATCH",
    "THRESHOLD_REVIEW_MIN": "SLUT_THRESHOLD_REVIEW_MIN",
}


def _create_config_interactively() -> Dict[str, Any]:
    # Check if we're in a non-interactive environment (like pytest)
    import sys

    if not sys.stdin.isatty() or os.environ.get("PYTEST_CURRENT_TEST"):
        # Return defaults without prompting during tests
        return DEFAULTS.copy()

    console.print("[bold yellow]Welcome to sluttools! First-time setup.[/bold yellow]")
    console.print("Where is your music library?")
    prompt_text = (
        "[bold green]Enter full path(s) to your music library[/bold green]\n"
        "[dim]Multiple paths allowed; separate by comma[/dim]"
    )
    default_paths = ",".join(DEFAULTS.get("LIBRARY_ROOTS", []))
    paths_str = Prompt.ask(prompt_text, default=default_paths)
    user_roots = [p.strip() for p in paths_str.split(",") if p.strip()]
    data = DEFAULTS.copy()
    data["LIBRARY_ROOTS"] = user_roots
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    console.print(f"[bold green]Configuration saved to {CONFIG_FILE}[/bold green]")
    return data


def _load_user_file() -> Dict[str, Any]:
    # Skip file loading during tests - just return defaults
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return DEFAULTS.copy()

    if not CONFIG_FILE.exists():
        return _create_config_interactively()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    # ensure keys exist
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data


def _apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    for key, env_name in ENV_MAP.items():
        val = os.getenv(env_name)
        if val is None:
            continue
        if key == "LIBRARY_ROOTS":
            out[key] = [s for s in (v.strip() for v in val.split(",")) if s]
        elif key in ("THRESHOLD_AUTO_MATCH", "THRESHOLD_REVIEW_MIN"):
            try:
                out[key] = int(val)
            except ValueError:
                pass  # ignore bad env and keep existing
        else:
            out[key] = val
    return out


def _coerce_types(eff: Dict[str, Any]) -> Dict[str, Any]:
    # Convert to Path objects expected by the app
    eff["LIBRARY_ROOTS"] = [Path(p).expanduser() for p in eff.get("LIBRARY_ROOTS", [])]
    eff["DB_PATH"] = Path(eff["DB_PATH"]).expanduser()
    eff["MATCH_OUTPUT_PATH_M3U"] = Path(str(eff["MATCH_OUTPUT_PATH_M3U"]))
    eff["MATCH_OUTPUT_PATH_JSON"] = Path(str(eff["MATCH_OUTPUT_PATH_JSON"]))
    # Validate thresholds
    for k in ("THRESHOLD_AUTO_MATCH", "THRESHOLD_REVIEW_MIN"):
        try:
            eff[k] = int(eff[k])
        except Exception:
            eff[k] = DEFAULTS[k]
    return eff


def load_config() -> Dict[str, Any]:
    """Load effective config: env > file > defaults, coerced to expected types."""
    file_cfg = _load_user_file()
    merged = DEFAULTS | file_cfg
    merged = _apply_env_overrides(merged)
    effective = _coerce_types(merged)
    return effective


# Exposed module-level config used by the CLI
config = load_config()
