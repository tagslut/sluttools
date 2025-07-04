# Installation Guide

## Requirements

- Python 3.11 or higher
- SoX (for audio processing)
- FLAC tools (for metadata handling)

## System Dependencies

### macOS
```bash
brew install sox flac
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install sox flac
```

### Windows
Download and install:
- [SoX](http://sox.sourceforge.net/)
- [FLAC tools](https://xiph.org/flac/download.html)

## Python Installation

### From Source
```bash
git clone <repository-url>
cd MusicAutomation
python -m pip install -e .
```

### Development Installation
```bash
git clone <repository-url>
cd MusicAutomation
python -m pip install -e ".[dev]"
```

## Configuration

1. Copy the example configuration:
```bash
cp config.example.env config.env
```

2. Edit the configuration file to match your system:
```bash
nano config.env
```

3. Set the FLAC library directory in `music_automation/playlist_matcher.py`:
```python
FLAC_LIBRARY_DIR = "/path/to/your/music/library"
```

## Verification

Test the installation:
```bash
musictools --help
```

Test playlist matching:
```bash
python -m music_automation.playlist_matcher --help
```

## Troubleshooting

### Common Issues

1. **Missing SoX or FLAC tools**
   - Install system dependencies as shown above
   - Verify installation: `sox --version` and `flac --version`

2. **Permission errors**
   - Ensure the user has read access to the music library
   - Ensure write access to the output directory

3. **Import errors**
   - Verify Python version: `python --version` (should be 3.11+)
   - Reinstall dependencies: `pip install -r requirements.txt`

4. **Performance issues**
   - Reduce `MAX_WORKERS` in configuration
   - Use Quick Match mode for small playlists
   - Enable caching for repeated operations
