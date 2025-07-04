# 🎵 Music Automation Toolkit → flaccid Integration Guide

This guide shows how to use the music-automation-toolkit as modules within your flaccid project structure.

## 🚀 Quick Setup

### 1. Install as Dependency

```bash
# In your flaccid project root
cd ~/Projects/flaccid
pip install -e ~/Projects/sluttools
```

### 2. Generate Example Files

```bash
# Run the example generator
cd ~/Projects/sluttools
python -c "from src.music_automation.flaccid_examples import write_example_files; write_example_files('~/Projects/flaccid')"
```

### 3. Copy Integration Files

```bash
# Copy the generated examples to your flaccid project
cp -r ~/Projects/flaccid/flaccid_integration_examples/* ~/Projects/flaccid/
```

## 📁 Integration Structure

```
~/Projects/flaccid/
├── get/                    # Your existing modules
├── tag/
│   └── metadata.py        # ← Music automation integration
├── lib/
│   └── music_library.py   # ← Music automation integration
├── core/
│   └── plugin_loader.py   # ← Music automation integration
├── shared/
│   └── music_adapter.py   # ← Music automation adapter
├── tests/
├── docs/
├── set/
├── fla.py                 # Your CLI entrypoint
└── pyproject.toml
```

## 🔧 Module Integration Examples

### flaccid/lib/music_library.py
```python
"""Library indexing and management using music automation tools."""

import sys
sys.path.append('/path/to/sluttools/src')
from music_automation.integration import FlaccidMusicAutomationAdapter, FlaccidConfig

class MusicLibrary:
    def __init__(self):
        config = FlaccidConfig(
            db_path="~/.flaccid_music.db",
            music_dirs=["/path/to/music"],
            output_dir="./output"
        )
        self.adapter = FlaccidMusicAutomationAdapter(config)
        self.lib_functions = self.adapter.get_lib_functions()

    def scan_directory(self, path: str):
        """Scan music directory for indexing."""
        return self.lib_functions['scan_flac_directory'](path)

    def get_library_stats(self):
        """Get comprehensive library statistics."""
        return self.lib_functions['get_library_stats']()

    def check_integrity(self, file_path: str):
        """Check file integrity and corruption."""
        return self.lib_functions['check_corruption'](file_path)
```

### flaccid/tag/metadata.py
```python
"""Metadata enrichment and tagging using music automation tools."""

import sys
sys.path.append('/path/to/sluttools/src')
from music_automation.integration import FlaccidMusicAutomationAdapter, FlaccidConfig

class MetadataManager:
    def __init__(self):
        config = FlaccidConfig()
        self.adapter = FlaccidMusicAutomationAdapter(config)
        self.tag_functions = self.adapter.get_tag_functions()

    def enrich_metadata(self, file_path: str):
        """Enrich file with additional metadata."""
        return self.tag_functions['enrich_metadata'](file_path)

    def normalize_tags(self, file_path: str):
        """Normalize and standardize tags."""
        return self.tag_functions['normalize_tags'](file_path)

    def batch_update(self, file_paths: list, updates: dict):
        """Batch update multiple files."""
        return self.tag_functions['batch_tag_update'](file_paths, updates)
```

### flaccid/core/plugin_loader.py
```python
"""Plugin management using music automation tools."""

import sys
sys.path.append('/path/to/sluttools/src')
from music_automation.integration import FlaccidMusicAutomationAdapter, FlaccidConfig

class PluginManager:
    def __init__(self):
        config = FlaccidConfig()
        self.adapter = FlaccidMusicAutomationAdapter(config)
        self.core_functions = self.adapter.get_core_functions()

    def load_plugins(self):
        """Load all music automation plugins."""
        return self.core_functions['load_music_plugins']()

    def get_plugin_info(self, plugin_name: str):
        """Get detailed plugin information."""
        return self.core_functions['get_plugin_info'](plugin_name)
```

## 🎯 Using in Your fla.py CLI

```python
#!/usr/bin/env python3
"""flaccid CLI with music automation integration."""

import typer
from rich.console import Console

# Import your flaccid modules
from lib.music_library import MusicLibrary
from tag.metadata import MetadataManager
from core.plugin_loader import PluginManager

app = typer.Typer(help="flaccid - Music library management")
console = Console()

# Initialize components
library = MusicLibrary()
metadata_manager = MetadataManager()
plugin_manager = PluginManager()

@app.command()
def scan(path: str = typer.Argument(..., help="Path to scan")):
    """Scan directory for music files."""
    console.print(f"🔍 Scanning {path}...")
    result = library.scan_directory(path)
    console.print(f"✅ Found {result['files_found']} files")

@app.command()
def stats():
    """Show library statistics."""
    console.print("📊 Library Statistics:")
    stats = library.get_library_stats()
    console.print(f"Total files: {stats['total_files']}")
    console.print(f"Total size: {stats['total_size']}")

@app.command()
def enrich(file_path: str = typer.Argument(..., help="File to enrich")):
    """Enrich file metadata."""
    console.print(f"✨ Enriching {file_path}...")
    result = metadata_manager.enrich_metadata(file_path)
    console.print(f"✅ Status: {result['status']}")

@app.command()
def plugins():
    """List loaded plugins."""
    console.print("🔌 Loaded Plugins:")
    plugins = plugin_manager.load_plugins()
    for plugin in plugins['loaded_plugins']:
        console.print(f"  • {plugin}")

if __name__ == "__main__":
    app()
```

## 🔄 Advanced Integration

### Custom Configuration

```python
# flaccid/shared/config.py
from music_automation.integration import FlaccidConfig

# Create custom configuration
config = FlaccidConfig(
    db_path="~/.flaccid_music.db",
    music_dirs=[
        "/Volumes/Music/FLAC",
        "/Users/me/Music/Local"
    ],
    output_dir="./output",
    temp_dir="./temp"
)
```

### Direct Module Access

```python
# For more control, use modules directly
import sys
sys.path.append('/path/to/sluttools/src')

from music_automation.core import database, matcher, processor, copier

# Use functions directly
db_stats = database.get_stats("/path/to/music.db")
matched_playlist = matcher.match_tracks(playlist_path, db_path)
processed_files = processor.batch_resample(file_list)
copied_files = copier.copy_playlist(playlist_path, destination)
```

## 📦 Benefits of This Integration

1. **Modular Design**: Each music automation tool fits into appropriate flaccid module
2. **Consistent Interface**: All tools use the same configuration and adapter pattern
3. **Extensible**: Easy to add new music automation capabilities
4. **Maintainable**: Clear separation between flaccid logic and music automation tools
5. **Testable**: Each integration point can be unit tested independently

## 🧪 Testing Integration

```python
# tests/test_lib_integration.py
import unittest
from lib.music_library import MusicLibrary

class TestLibIntegration(unittest.TestCase):
    def setUp(self):
        self.library = MusicLibrary()

    def test_scan_directory(self):
        result = self.library.scan_directory("/test/path")
        self.assertIn('status', result)
        self.assertEqual(result['status'], 'success')

    def test_get_stats(self):
        stats = self.library.get_library_stats()
        self.assertIn('total_files', stats)
```

## 🚀 Getting Started

1. **Install Dependencies**: `pip install -e ~/Projects/sluttools`
2. **Generate Examples**: Run the example generator script
3. **Copy Integration Files**: Copy generated examples to your flaccid project
4. **Update Paths**: Update import paths to match your project structure
5. **Test Integration**: Run tests to ensure everything works
6. **Customize**: Modify the integration to fit your specific needs

This integration approach gives you all the power of the music automation toolkit within your flaccid project structure, while maintaining clean separation of concerns and modularity!
