"""
Cross-platform compatibility helpers.

Detects terminal encoding and provides safe characters for output formatting.
Works on Windows (cp1252), Linux (UTF-8), macOS (UTF-8).
"""

import sys
import os


def _can_encode_unicode():
    """Check if stdout can handle Unicode box-drawing characters."""
    try:
        enc = sys.stdout.encoding or ""
        if enc.lower().replace("-", "") in ("utf8", "utf16"):
            return True
        # Try encoding a test character
        "\u2500".encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


_UNICODE = _can_encode_unicode()

# Safe formatting characters
LINE = "\u2500" if _UNICODE else "-"       # horizontal line
THETA = "\u0398" if _UNICODE else "TH"     # Greek theta for temperature dim
BULLET = "\u2022" if _UNICODE else "*"      # bullet point
ARROW = "->" if not _UNICODE else "->"      # always ASCII (arrows cause issues even in some UTF-8 terminals)
DASH = "--" if not _UNICODE else "--"       # em-dash replacement


def hline(width=56):
    """Horizontal line for formatting."""
    return LINE * width


def safe_print(*args, **kwargs):
    """Print with fallback encoding for Windows."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        # Replace known problematic characters
        text = text.replace("\u2500", "-")
        text = text.replace("\u2502", "|")
        text = text.replace("\u0398", "TH")
        text = text.replace("\u03b8", "th")
        text = text.replace("\u2014", "--")
        text = text.replace("\u2192", "->")
        text = text.replace("\u2022", "*")
        try:
            print(text, **kwargs)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)
