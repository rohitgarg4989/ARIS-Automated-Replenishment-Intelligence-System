"""
utils/console.py
================
Windows-safe Rich console factory.
Ensures UTF-8 output even in cmd/PowerShell environments.
"""
import sys
import io
from rich.console import Console


def get_console() -> Console:
    """Return a Rich Console with UTF-8 encoding on Windows."""
    if sys.platform == "win32":
        try:
            # Re-wrap stdout with UTF-8 and replace unmappable chars
            utf8_stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
            return Console(file=utf8_stdout, force_terminal=True, highlight=False)
        except AttributeError:
            pass
    return Console()
