"""Display preferences set on the list page: layout, each layout's theme (`theme` for Glass,
`focus_theme` for Focus), light/dark mode, the Custom theme's colours and photos, the sounds, course
tag colors and nicknames, and which bins are open.

They're kept in Birdbrain's database rather than the browser, because the list
page's address changes whenever Birdbrain restarts and browsers keep storage
per address.
"""
from __future__ import annotations

import json
import re

import glass
import theme
from store import Store

KEY = "ui_prefs"
BINS = ("completed", "archived")
DEFAULTS = {"layout": theme.DEFAULT_LAYOUT, "theme": theme.DEFAULT_THEME, "focus_theme": theme.DEFAULT_THEME,
            "mode": theme.DEFAULT_MODE, "sound": True, "frame": "wide", "courses": {}, "bins": {}, "imported": False,
            # the Custom theme: {"accent", "light": {measured photo}, "dark": {...}} and {"light": {4 colours}, ...}
            "glass_custom": {}, "focus_custom": {}}
GLASS_THEMES = (*glass.SCHEMES, theme.CUSTOM)
FOCUS_THEMES = (*theme.THEMES, theme.CUSTOM)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def load(store: Store) -> dict:
    try:
        saved = json.loads(store.get_meta(KEY) or "{}")
    except ValueError:
        saved = {}
    if "layout" not in saved and saved.get("theme") == "birdbrain":
        saved["theme"] = theme.DEFAULT_THEME   # saved before the glass layout: the old default moves to the new one
    if saved.get("layout") == "classic":        # Classic is now Focus, and keeps the theme it had
        saved["layout"] = "focus"
        saved.setdefault("focus_theme", saved.get("theme"))
    p = {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}
    if p["theme"] not in GLASS_THEMES:
        p["theme"] = theme.DEFAULT_THEME
    if p["focus_theme"] not in FOCUS_THEMES:
        p["focus_theme"] = theme.DEFAULT_THEME
    if p["layout"] not in theme.LAYOUTS:
        p["layout"] = theme.DEFAULT_LAYOUT
    for k in ("glass_custom", "focus_custom"):
        if not isinstance(p[k], dict):
            p[k] = {}
    return p


def active_theme(p: dict) -> str:
    """The theme the page shows: each layout remembers its own."""
    return p["theme"] if p["layout"] == "glass" else p["focus_theme"]


def _save(store: Store, p: dict) -> dict:
    store.set_meta(KEY, json.dumps(p))
    store.touch()
    return p


def set_glass_photo(store: Store, slot: str, info: dict | None) -> dict:
    """Record (or forget) the measured Custom photo for day or night; custom.py does the measuring."""
    p = load(store)
    gc = dict(p["glass_custom"])
    if info:
        gc[slot] = info
    else:
        gc.pop(slot, None)
    p["glass_custom"] = gc
    return _save(store, p)


def update(store: Store, patch: dict) -> dict:
    """Validate and merge `patch` (from the page) into the saved preferences."""
    p = load(store)
    if "layout" in patch:
        if patch["layout"] not in theme.LAYOUTS:
            raise ValueError("Unknown layout.")
        p["layout"] = patch["layout"]
    if "theme" in patch:
        if patch["theme"] not in GLASS_THEMES:
            raise ValueError("Unknown theme.")
        p["theme"] = patch["theme"]
    if "focus_theme" in patch:
        if patch["focus_theme"] not in FOCUS_THEMES:
            raise ValueError("Unknown theme.")
        p["focus_theme"] = patch["focus_theme"]
    if "focus_custom" in patch:   # {"light": {bg, text, struct, accent}, "dark": {...}}
        fc = patch["focus_custom"]
        if not isinstance(fc, dict):
            raise ValueError("Bad theme colours.")
        clean = {}
        for mode in ("light", "dark"):
            picks = fc.get(mode) or {}
            clean[mode] = {r: picks[r].upper() for r in ("bg", "text", "struct", "accent")
                           if isinstance(picks.get(r), str) and _HEX.match(picks[r])}
        p["focus_custom"] = clean
    if "glass_accent" in patch:
        if not (isinstance(patch["glass_accent"], str) and _HEX.match(patch["glass_accent"])):
            raise ValueError("Pick a colour.")
        p["glass_custom"] = {**p["glass_custom"], "accent": patch["glass_accent"].upper()}
    if "mode" in patch:
        if patch["mode"] not in theme.MODES:
            raise ValueError("Unknown mode.")
        p["mode"] = patch["mode"]
    if "frame" in patch:
        if patch["frame"] not in ("wide", "narrow"):
            raise ValueError("Unknown frame width.")
        p["frame"] = patch["frame"]
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
    return _save(store, p)
