"""Music Automation Toolkit - Core package for music library management."""

__version__ = "2.0.0"
__author__ = "Georgie"
__description__ = "A comprehensive toolkit for managing and cataloging large music libraries"

from .core.database import FlacDatabase
from .core.matcher import PlaylistMatcher
from .core.processor import AudioProcessor
from .core.copier import PlaylistCopier

__all__ = [
    "FlacDatabase",
    "PlaylistMatcher", 
    "AudioProcessor",
    "PlaylistCopier"
]
