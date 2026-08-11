"""Resolve DEF CON 34 badge USB-serial ports (macOS / Linux)."""

from __future__ import annotations

import glob
import os
import sys


def list_badge_ports() -> list[str]:
    return (
        sorted(glob.glob("/dev/cu.usbmodem*"))
        + sorted(glob.glob("/dev/tty.usbmodem*"))
        + sorted(glob.glob("/dev/ttyACM*"))
    )


def resolve_port(preferred: str | None = None) -> str:
    """Return an existing serial path. Prefer `preferred` if present, else first candidate."""
    cands = list_badge_ports()
    if preferred:
        if os.path.exists(preferred):
            return preferred
        matches = sorted(glob.glob(preferred))
        if matches:
            return matches[0]
    if not cands:
        hint = f" (preferred {preferred!r} missing)" if preferred else ""
        raise SystemExit(
            f"No badge USB serial found{hint}. "
            "Plug in the badge and pass --port /dev/cu.usbmodem… (or /dev/ttyACM0)."
        )
    if preferred and preferred not in cands:
        print(f"note: preferred {preferred} missing; using {cands[0]}", file=sys.stderr)
    elif len(cands) > 1:
        print(f"note: multiple ports {cands}; using {cands[0]}", file=sys.stderr)
    return cands[0]
