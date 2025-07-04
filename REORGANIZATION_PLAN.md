# Repository Reorganization Plan

## Current Issues
1. **Scattered code**: `music_automation/`, `bin/`, `scripts/`, `src/`
2. **Root clutter**: Too many files in root directory
3. **Generated files**: `The xx_matched.*` files in root
4. **Inconsistent naming**: Mix of underscores and hyphens
5. **Empty directories**: `src/` appears unused

## Proposed New Structure

```
music-automation-toolkit/
├── README.md
├── LICENSE
├── setup.py
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── .env.example
├── pyproject.toml
├──
├── src/
│   └── music_automation/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── database.py         # flac_database.py
│       │   ├── matcher.py          # playlist_matcher.py
│       │   ├── processor.py        # audio_processor.py
│       │   └── copier.py           # playlist_copier.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py             # bin/musictools.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├──
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_matcher.py
│   ├── test_processor.py
│   └── test_copier.py
├──
├── docs/
│   ├── installation.md
│   ├── api.md
│   └── usage.md
├──
├── examples/
│   ├── playlists/
│   └── configs/
├──
└── .github/
    └── workflows/
        └── ci.yml
```

## Actions Required
1. Create new `src/music_automation/` structure
2. Move and rename core modules
3. Consolidate CLI entry points
4. Update imports throughout codebase
5. Update setup.py with new structure
6. Clean up root directory
7. Move generated files to appropriate locations
8. Update documentation
