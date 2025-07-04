"""Music Automation Toolkit - A comprehensive music library management system."""

__version__ = "2.0.0"
__author__ = "Georgie"

from .playlist_matcher import main as match_playlist
from .flac_database import main as manage_database
from .playlist_copier import main as copy_files
from .audio_processor import main as process_audio

__all__ = ["match_playlist", "manage_database", "copy_files", "process_audio"]

