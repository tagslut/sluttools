#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="music-automation-toolkit",
    version="2.0.0",
    description="A comprehensive toolkit for managing and cataloging large music libraries",
    author="Georgie",
    author_email="geoooooorges@gmail.com",
    url="https://github.com/tagslut/sluttools",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=[
        "mutagen>=1.47.0",
        "pandas>=2.0.0",
        "rich>=13.0.0",
        "fuzzywuzzy>=0.18.0",
        "python-levenshtein>=0.21.0",
        "openpyxl>=3.1.0",
        "aiofiles",
        "requests",
        "sqlite-utils",
        "tqdm",
        "rapidfuzz",
    ],
    entry_points={
        'console_scripts': [
            'musictools=music_automation.cli.main:main',
            'playlist-matcher=music_automation.core.matcher:main',
            'flac-database=music_automation.core.database:main',
            'playlist-copier=music_automation.core.copier:main',
            'audio-processor=music_automation.core.processor:main',
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
