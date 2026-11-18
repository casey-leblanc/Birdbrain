"""Shared by every test: a throwaway data folder (set before Birdbrain's modules are imported, since they read
APPDATA when they load), the import path, a fixed "now" and invented items.

    python -m unittest discover tests
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

_DATA = tempfile.mkdtemp(prefix="birdbrain-tests-")
os.environ["APPDATA"] = _DATA
os.environ["LOCALAPPDATA"] = _DATA
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "birdbrain"))

from store import Item, Store  # noqa: E402

NOW = datetime(2026, 11, 18, 10, 0)   # a Wednesday morning
_n = 0


def store() -> Store:
    """An empty store in its own file."""
    global _n
    _n += 1
    return Store(Path(_DATA) / f"test-{_n}.db")


def item(id: str = "moodle:cm:1", title: str = "Lab report 4", due: datetime | None = NOW + timedelta(days=1),
         kind: str = "assignment", course: str = "2026 Fall CHEM 1202 for A. Teacher", source: str | None = None,
         **more) -> Item:
    source = source or id.split(":")[0]
    return Item(id, source, kind, title, due, course, **more)


def at(days: int = 0, hour: int = 23, minute: int = 59) -> datetime:
    """A time `days` from the test's today."""
    return (NOW + timedelta(days=days)).replace(hour=hour, minute=minute)
