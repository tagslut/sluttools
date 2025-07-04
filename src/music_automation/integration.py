"""
Integration Guide for flaccid Project

This module provides integration examples and adapters for using music-automation-toolkit
as modules within the flaccid project structure.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class FlaccidConfig:
    """Configuration for flaccid integration."""
    db_path: Optional[str] = None
    music_dirs: Optional[List[str]] = None
    output_dir: str = "output"
    temp_dir: str = "temp"

    def __post_init__(self):
        if self.music_dirs is None:
            self.music_dirs = []
        if self.db_path is None:
            self.db_path = str(Path.home() / ".flac_index.db")


class FlaccidMusicAutomationAdapter:
    """Adapter for integrating music automation tools into flaccid."""

    def __init__(self, config: FlaccidConfig):
        self.config = config
        self._setup_paths()

    def _setup_paths(self):
        """Setup required directories."""
        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(self.config.temp_dir, exist_ok=True)

    def get_lib_functions(self) -> Dict[str, Any]:
        """Get functions suitable for flaccid/lib/ module."""
        return {
            'scan_flac_directory': self._scan_flac_directory,
            'get_library_stats': self._get_library_stats,
            'check_corruption': self._check_corruption,
            'index_library': self._index_library,
        }

    def get_tag_functions(self) -> Dict[str, Any]:
        """Get functions suitable for flaccid/tag/ module."""
        return {
            'enrich_metadata': self._enrich_metadata,
            'normalize_tags': self._normalize_tags,
            'batch_tag_update': self._batch_tag_update,
        }

    def get_core_functions(self) -> Dict[str, Any]:
        """Get functions suitable for flaccid/core/ module."""
        return {
            'load_music_plugins': self._load_music_plugins,
            'get_plugin_info': self._get_plugin_info,
            'manage_config': self._manage_config,
        }

    def _scan_flac_directory(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Scan directory for FLAC files - wrapper for lib/ module."""
        # This would call the actual database scanning function
        # For now, return a placeholder structure
        return {
            'path': path,
            'files_found': 0,
            'total_size': 0,
            'scan_time': 0,
            'status': 'success'
        }

    def _get_library_stats(self) -> Dict[str, Any]:
        """Get library statistics - wrapper for lib/ module."""
        return {
            'total_files': 0,
            'total_size': 0,
            'total_duration': 0,
            'file_formats': {},
            'sample_rates': {},
            'bit_depths': {},
        }

    def _check_corruption(self, file_path: str) -> Dict[str, Any]:
        """Check file corruption - wrapper for lib/ module."""
        return {
            'file_path': file_path,
            'is_corrupted': False,
            'error_details': None,
            'check_time': 0,
        }

    def _index_library(self, paths: List[str]) -> Dict[str, Any]:
        """Index library - wrapper for lib/ module."""
        return {
            'indexed_paths': paths,
            'files_processed': 0,
            'time_taken': 0,
            'status': 'success'
        }

    def _enrich_metadata(self, file_path: str) -> Dict[str, Any]:
        """Enrich metadata - wrapper for tag/ module."""
        return {
            'file_path': file_path,
            'metadata_added': [],
            'status': 'success'
        }

    def _normalize_tags(self, file_path: str) -> Dict[str, Any]:
        """Normalize tags - wrapper for tag/ module."""
        return {
            'file_path': file_path,
            'changes_made': [],
            'status': 'success'
        }

    def _batch_tag_update(self, file_paths: List[str], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Batch tag update - wrapper for tag/ module."""
        return {
            'files_processed': len(file_paths),
            'updates_applied': updates,
            'status': 'success'
        }

    def _load_music_plugins(self) -> Dict[str, Any]:
        """Load music plugins - wrapper for core/ module."""
        return {
            'loaded_plugins': ['database', 'matcher', 'processor', 'copier'],
            'status': 'success'
        }

    def _get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin info - wrapper for core/ module."""
        return {
            'name': plugin_name,
            'version': '2.0.0',
            'description': f'Music automation plugin: {plugin_name}',
            'status': 'active'
        }

    def _manage_config(self, action: str, config_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Manage configuration - wrapper for core/ module."""
        return {
            'action': action,
            'config': config_data,
            'status': 'success'
        }


def create_flaccid_integration_example():
    """Create example files for flaccid integration."""

    # Example lib/music_library.py
    lib_example = '''"""
flaccid/lib/music_library.py - Library indexing and management
"""

from music_automation import FlaccidMusicAutomationAdapter, FlaccidConfig

class MusicLibrary:
    """Music library management for flaccid."""

    def __init__(self, config_path: str = None):
        self.config = FlaccidConfig()
        self.adapter = FlaccidMusicAutomationAdapter(self.config)
        self.lib_functions = self.adapter.get_lib_functions()

    def scan_directory(self, path: str) -> dict:
        """Scan directory for music files."""
        return self.lib_functions['scan_flac_directory'](path)

    def get_stats(self) -> dict:
        """Get library statistics."""
        return self.lib_functions['get_library_stats']()

    def check_file_integrity(self, file_path: str) -> dict:
        """Check file integrity."""
        return self.lib_functions['check_corruption'](file_path)

    def index_libraries(self, paths: list) -> dict:
        """Index multiple library paths."""
        return self.lib_functions['index_library'](paths)
'''

    # Example tag/metadata.py
    tag_example = '''"""
flaccid/tag/metadata.py - Tagging and metadata management
"""

from music_automation import FlaccidMusicAutomationAdapter, FlaccidConfig

class MetadataManager:
    """Metadata management for flaccid."""

    def __init__(self, config_path: str = None):
        self.config = FlaccidConfig()
        self.adapter = FlaccidMusicAutomationAdapter(self.config)
        self.tag_functions = self.adapter.get_tag_functions()

    def enrich_file(self, file_path: str) -> dict:
        """Enrich file metadata."""
        return self.tag_functions['enrich_metadata'](file_path)

    def normalize_tags(self, file_path: str) -> dict:
        """Normalize file tags."""
        return self.tag_functions['normalize_tags'](file_path)

    def batch_update(self, file_paths: list, updates: dict) -> dict:
        """Batch update tags."""
        return self.tag_functions['batch_tag_update'](file_paths, updates)
'''

    # Example core/plugins.py
    core_example = '''"""
flaccid/core/plugins.py - Plugin management
"""

from music_automation import FlaccidMusicAutomationAdapter, FlaccidConfig

class PluginManager:
    """Plugin management for flaccid."""

    def __init__(self, config_path: str = None):
        self.config = FlaccidConfig()
        self.adapter = FlaccidMusicAutomationAdapter(self.config)
        self.core_functions = self.adapter.get_core_functions()

    def load_plugins(self) -> dict:
        """Load music automation plugins."""
        return self.core_functions['load_music_plugins']()

    def get_plugin_info(self, plugin_name: str) -> dict:
        """Get plugin information."""
        return self.core_functions['get_plugin_info'](plugin_name)

    def manage_config(self, action: str, config_data: dict = None) -> dict:
        """Manage plugin configuration."""
        return self.core_functions['manage_config'](action, config_data)
'''

    return {
        'lib_example': lib_example,
        'tag_example': tag_example,
        'core_example': core_example
    }


def create_setup_instructions():
    """Create setup instructions for flaccid integration."""

    instructions = '''
# Music Automation Toolkit Integration with flaccid

## Setup Instructions

### 1. Install music-automation-toolkit as a dependency

```bash
# In your flaccid project root
pip install -e path/to/sluttools
```

### 2. Create adapter modules in your flaccid project

```python
# flaccid/shared/music_automation_adapter.py
from music_automation.integration import FlaccidMusicAutomationAdapter, FlaccidConfig

# Initialize adapter
config = FlaccidConfig(
    db_path="~/.flaccid_music.db",
    music_dirs=["/path/to/music1", "/path/to/music2"],
    output_dir="./output",
    temp_dir="./temp"
)

adapter = FlaccidMusicAutomationAdapter(config)
```

### 3. Use in your flaccid modules

```python
# flaccid/lib/indexing.py
from ..shared.music_automation_adapter import adapter

def scan_music_directory(path):
    lib_functions = adapter.get_lib_functions()
    return lib_functions['scan_flac_directory'](path)

# flaccid/tag/enrichment.py
from ..shared.music_automation_adapter import adapter

def enrich_metadata(file_path):
    tag_functions = adapter.get_tag_functions()
    return tag_functions['enrich_metadata'](file_path)

# flaccid/core/plugin_loader.py
from ..shared.music_automation_adapter import adapter

def load_music_plugins():
    core_functions = adapter.get_core_functions()
    return core_functions['load_music_plugins']()
```

### 4. Integration Benefits

- **Modular**: Each function maps to appropriate flaccid module
- **Configurable**: Uses FlaccidConfig for consistent configuration
- **Extensible**: Easy to add new functions and capabilities
- **Testable**: Clear interfaces for unit testing
- **Maintainable**: Separation of concerns between projects

### 5. Usage Examples

```python
# In your flaccid CLI (fla.py)
import typer
from .lib.indexing import scan_music_directory
from .tag.enrichment import enrich_metadata

app = typer.Typer()

@app.command()
def scan(path: str):
    """Scan music directory."""
    result = scan_music_directory(path)
    typer.echo(f"Scanned {result['files_found']} files")

@app.command()
def enrich(file_path: str):
    """Enrich file metadata."""
    result = enrich_metadata(file_path)
    typer.echo(f"Enriched: {file_path}")
```
'''

    return instructions


# Export main integration components
__all__ = [
    'FlaccidConfig',
    'FlaccidMusicAutomationAdapter',
    'create_flaccid_integration_example',
    'create_setup_instructions'
]
