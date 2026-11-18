"""Which build this is. build.py writes assets/build.json into a packaged app; run from source there is none."""
from __future__ import annotations

import json
from pathlib import Path

from version import VERSION

TAG_PREFIX = "exp-"   # experimental builds are pre-releases tagged exp-<version>-<commit>


def tag_for(version: str, commit: str) -> str:
    return f"{TAG_PREFIX}{version}-{commit[:7]}"


def current() -> dict:
    """{"version": "2.0.0", "commit": "73d77c1", "tag": "exp-2.0.0-73d77c1"}. Run from source, commit and tag are
    empty: there is nothing to update, pull the repository instead."""
    try:
        info = json.loads((Path(__file__).parent / "assets" / "build.json").read_text(encoding="utf-8"))
        return {"version": info["version"], "commit": info["commit"], "tag": info["tag"]}
    except (OSError, ValueError, KeyError):
        return {"version": VERSION, "commit": "", "tag": ""}


def name(info: dict | None = None) -> str:
    """'2.0.0 (73d77c1)'."""
    info = info or current()
    return info["version"] + (f" ({info['commit']})" if info["commit"] else " (from source)")
