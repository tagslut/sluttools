# music-automation-toolkit

A comprehensive toolkit for managing and cataloging large music libraries.

## Features

- Audio file scanning and metadata extraction
- Playlist matching and copying
- FLAC database management
- CLI tools for automation

## Installation

### With pip

```sh
pip install -e .
```

### With Poetry

```sh
poetry install
```

## Usage

See the CLI help:

```sh
musictools --help
```

## Development

- Run all checks: `make check` or `bash scripts/check_all.sh`
- Run tests: `pytest`
- Lint: `black . && isort . && flake8 . && mypy src/`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
