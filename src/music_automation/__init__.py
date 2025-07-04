"""Music Automation Toolkit - Core package for music library management."""

__version__ = "2.0.0"
__author__ = "Georgie"
__description__ = "A comprehensive toolkit for managing and cataloging large music libraries"

# Import the core modules
from . import core
from . import cli
from . import utils

__all__ = [
    "core",
    "cli", 
    "utils"
]
