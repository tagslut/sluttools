#!/usr/bin/env python3
"""Setup script for Music Automation Toolkit."""

from setuptools import setup, find_packages
import os

def read_requirements(filename):
    """Read requirements from file."""
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def read_readme():
    """Read README file."""
    with open('README.md', 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name="music-automation-toolkit",
    version="2.0.0",
    author="Georgie",
    description="A comprehensive toolkit for managing and cataloging large music libraries",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    install_requires=read_requirements('requirements.txt'),
    extras_require={
        'dev': read_requirements('requirements-dev.txt'),
    },
    entry_points={
        'console_scripts': [
            'musictools=bin.musictools:main',
            'playlist-matcher=music_automation.playlist_matcher:main',
            'flac-database=music_automation.flac_database:main',
            'playlist-copier=music_automation.playlist_copier:main',
            'audio-processor=music_automation.audio_processor:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Utilities",
    ],
    python_requires=">=3.11",
    keywords="music, flac, playlist, audio, automation, metadata",
    project_urls={
        "Bug Reports": "https://github.com/username/music-automation/issues",
        "Source": "https://github.com/username/music-automation",
        "Documentation": "https://github.com/username/music-automation/wiki",
    },
)
