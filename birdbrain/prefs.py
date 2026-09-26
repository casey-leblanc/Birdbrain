"""Display preferences set on the list page: layout, theme, light/dark mode, the
new-item squawk, course tag colors and nicknames, and which bins are open.

They're kept in Birdbrain's database rather than the browser, because the list
page's address changes whenever Birdbrain restarts and browsers keep storage
per address.
"""
from __future__ import annotations

import json
import re

import theme
from store import Store

KEY = "ui_prefs"
BINS = ("completed", "archived")
DEFAULTS = {"layout": theme.DEFAULT_LAYOUT, "theme": theme.DEFAULT_THEME, "mode": theme.DEFAULT_MODE,
            "sound": True, "courses": {}, "bins": {}, "imported": False}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def load(store: Store) -> dict:
    try:
        saved = json.loads(store.get_meta(KEY) or "{}")
    except ValueError:
        saved = {}
    if "layout" not in saved and saved.get("theme") == "birdbrain":
        saved["theme"] = theme.DEFAULT_THEME   # saved before the glass layout: the old default moves to the new one
    p = {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}
    if p["theme"] not in theme.THEMES:
        p["theme"] = theme.DEFAULT_THEME
    if p["layout"] not in theme.LAYOUTS:
        p["layout"] = theme.DEFAULT_LAYOUT
    return p


def update(store: Store, patch: dict) -> dict:
    """Validate and merge `patch` (from the page) into the saved preferences."""
    p = load(store)
    if "layout" in patch:
        if patch["layout"] not in theme.LAYOUTS:
            raise ValueError("Unknown layout.")
        p["layout"] = patch["layout"]
    if "theme" in patch:
        if patch["theme"] not in theme.THEMES:
            raise ValueError("Unknown theme.")
        p["theme"] = patch["theme"]
    if "mode" in patch:
        if patch["mode"] not in theme.MODES:
            raise ValueError("Unknown mode.")
        p["mode"] = patch["mode"]
    if "sound" in patch:
        p["sound"] = bool(patch["sound"])
    if "courses" in patch:  # {code: {nick, color}} or {code: null} to reset
        if not isinstance(patch["courses"], dict) or len(patch["courses"]) > 100:
            raise ValueError("Bad course settings.")
        courses = dict(p["courses"])
        for code, c in patch["courses"].items():
            code = str(code)[:40]
            if not c:
                courses.pop(code, None)
                continue
            nick = " ".join(str(c.get("nick", "")).split())[:24]
            color = str(c.get("color", ""))
            entry = {k: v for k, v in (("nick", nick), ("color", color.lower() if _HEX.match(color) else "")) if v}
            if entry:
                courses[code] = entry
            else:
                courses.pop(code, None)
        p["courses"] = courses
    if "bins" in patch and isinstance(patch["bins"], dict):
        p["bins"] = {**p["bins"], **{k: bool(v) for k, v in patch["bins"].items() if k in BINS}}
    if patch.get("imported"):
        p["imported"] = True
    store.set_meta(KEY, json.dumps(p))
    store.touch()
    return p
