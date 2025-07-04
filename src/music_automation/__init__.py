"""
Music Automation Toolkit - Plugin Architecture

This module provides a plugin-style interface for integrating music automation tools
into other projects like flaccid. Each tool can be imported and used independently.
"""

__version__ = "2.0.0"
__author__ = "Georgie"
__description__ = "A comprehensive toolkit for managing and cataloging large music libraries"

# Core functionality exports
from .core import database, matcher, processor, copier

# Plugin-style interface classes
class MusicAutomationPlugin:
    """Base class for music automation plugins."""
    
    def __init__(self, config=None):
        """Initialize plugin with optional configuration."""
        self.config = config or {}
    
    def get_info(self):
        """Return plugin information."""
        return {
            "name": self.__class__.__name__,
            "version": __version__,
            "description": self.__doc__ or "No description available"
        }

class FlacDatabasePlugin(MusicAutomationPlugin):
    """Plugin for FLAC database operations."""
    
    def __init__(self, db_path=None, config=None):
        """Initialize FLAC database plugin."""
        super().__init__(config)
        self.db_path = db_path or self.config.get('db_path', '~/.flac_index.db')
    
    def scan_directory(self, path, recursive=True):
        """Scan directory for FLAC files and add to database."""
        # Delegate to core database module
        return database.scan_directory(path, self.db_path, recursive)
    
    def query_files(self, **filters):
        """Query FLAC files from database."""
        return database.query_files(self.db_path, **filters)
    
    def get_stats(self):
        """Get database statistics."""
        return database.get_stats(self.db_path)

class PlaylistMatcherPlugin(MusicAutomationPlugin):
    """Plugin for playlist matching operations."""
    
    def __init__(self, db_path=None, config=None):
        """Initialize playlist matcher plugin."""
        super().__init__(config)
        self.db_path = db_path or self.config.get('db_path', '~/.flac_index.db')
    
    def match_playlist(self, playlist_path, output_format='m3u', threshold=65):
        """Match playlist tracks to FLAC library."""
        return matcher.match_playlist(
            playlist_path, 
            self.db_path, 
            output_format=output_format,
            threshold=threshold
        )
    
    def get_unmatched_tracks(self, playlist_path):
        """Get tracks that couldn't be matched."""
        return matcher.get_unmatched_tracks(playlist_path, self.db_path)

class AudioProcessorPlugin(MusicAutomationPlugin):
    """Plugin for audio processing operations."""
    
    def __init__(self, config=None):
        """Initialize audio processor plugin."""
        super().__init__(config)
    
    def resample_file(self, input_path, output_path, target_rate=44100):
        """Resample a single audio file."""
        return processor.resample_file(input_path, output_path, target_rate)
    
    def batch_resample(self, file_list, target_rate=44100):
        """Batch resample multiple files."""
        return processor.batch_resample(file_list, target_rate)

class PlaylistCopierPlugin(MusicAutomationPlugin):
    """Plugin for playlist file copying operations."""
    
    def __init__(self, config=None):
        """Initialize playlist copier plugin."""
        super().__init__(config)
    
    def copy_playlist(self, playlist_path, destination, mode='preserve'):
        """Copy files from playlist to destination."""
        return copier.copy_playlist(playlist_path, destination, mode)

# Plugin registry for easy access
PLUGINS = {
    'database': FlacDatabasePlugin,
    'matcher': PlaylistMatcherPlugin,
    'processor': AudioProcessorPlugin,
    'copier': PlaylistCopierPlugin,
}

def get_plugin(name, **kwargs):
    """Get a plugin instance by name."""
    if name not in PLUGINS:
        raise ValueError(f"Plugin '{name}' not found. Available: {list(PLUGINS.keys())}")
    
    return PLUGINS[name](**kwargs)

def list_plugins():
    """List available plugins."""
    return list(PLUGINS.keys())

# Convenience functions for direct module usage
def create_database_handler(db_path=None):
    """Create a database handler instance."""
    return FlacDatabasePlugin(db_path)

def create_matcher(db_path=None):
    """Create a playlist matcher instance."""
    return PlaylistMatcherPlugin(db_path)

def create_processor():
    """Create an audio processor instance."""
    return AudioProcessorPlugin()

def create_copier():
    """Create a playlist copier instance."""
    return PlaylistCopierPlugin()

__all__ = [
    # Plugin classes
    'MusicAutomationPlugin',
    'FlacDatabasePlugin',
    'PlaylistMatcherPlugin', 
    'AudioProcessorPlugin',
    'PlaylistCopierPlugin',
    
    # Plugin registry
    'PLUGINS',
    'get_plugin',
    'list_plugins',
    
    # Convenience functions
    'create_database_handler',
    'create_matcher',
    'create_processor',
    'create_copier',
    
    # Core modules (for direct access)
    'database',
    'matcher',
    'processor',
    'copier'
]
