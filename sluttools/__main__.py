"""
Main entry point for the sluttools application.

This file allows the package to be executed as a script, e.g., by running `python -m sluttools`.
It imports the Typer application object from the `cli` module and invokes it.
"""

from .cli import app

if __name__ == "__main__":
    app()
