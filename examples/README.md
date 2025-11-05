# Examples Directory

This directory contains example scripts demonstrating various features of sluttools.

## Available Examples

### `example_usage.py`

Demonstrates the transparent matching workflow (deprecated API).

**Note**: This example uses an older API with `transparent_matching` and direct `config` imports. For current usage, please refer to the main CLI commands documented in the project README:

```bash
# Modern equivalents:
poetry run slut get library          # Refresh library
poetry run slut match review <file>  # Interactive matching
poetry run slut out m3u <file>       # Export M3U playlist
```

## Migration Guide

If you're using code from these examples, please migrate to the current CLI API:

| Old Pattern | New Pattern |
|-------------|-------------|
| `from transparent_matching import ...` | Use `sluttools.matching` module |
| `from config import ...` | Use `sluttools.config` module |
| Direct function calls | Use CLI commands via `poetry run slut` |

See the main [README.md](../README.md) and [USAGE-CONFIG.md](../USAGE-CONFIG.md) for complete documentation.
