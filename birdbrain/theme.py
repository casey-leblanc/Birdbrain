"""Themes and fonts for the list page and the keyword window.

Each theme has classic tokens (below) for the classic layout, locked in
ROUND-2-CONTEXT.md (direction E): four text roles on a flat canvas, large light
monospaced headings as structure, accent reserved for overdue work and exams.
Every text role is >= 4.5:1 on every surface it sits on (WCAG AA). In the
default glass layout the same themes are colour schemes defined in glass.py.

Roles
  bg / col / hover / line   canvas, dialog surface, hover wash, hairlines
  text / head               primary text, the title
  struct                    secondary: the Now / This week / Later headings and course codes
  muted                     tertiary: times, labels, the date
  accent / accent_ink       overdue work and exams; text on an accent-filled button
  focus                     keyboard focus ring
"""
from __future__ import annotations

import base64
import ctypes
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
# Web page: Atkinson Hyperlegible Next (variable weight, roman + italic) and Mono.
WEB_FONTS = [("Birdbrain Sans", "AtkinsonHyperlegibleNext-VF.ttf", "200 800", "normal"),
             ("Birdbrain Sans", "AtkinsonHyperlegibleNext-Italic-VF.ttf", "200 800", "italic"),
             ("Birdbrain Mono", "AtkinsonHyperlegibleMono-VF.ttf", "200 800", "normal")]
# Tk can't use variable fonts well, so the keyword window uses the static original cut.
TK_FONT_FILES = ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"]
TK_FONT_FAMILY = "Atkinson Hyperlegible"

THEMES = {
    # Forest follows caseyleblanc.dev: misty greens under a blue sky. It's the default.
    "forest": dict(name="Forest", modes=dict(
        light=dict(bg="#EEF2F4", col="#FFFFFF", hover="#E2E8EC", line="#CAD4DA", text="#1A2226", head="#1A2226",
                   struct="#2D5B47", muted="#56626A", accent="#A3261C", accent_ink="#FFFFFF", focus="#2D5B47"),
        dark=dict(bg="#121A1B", col="#182224", hover="#1F2B2D", line="#304044", text="#E6ECEC", head="#E6ECEC",
                  struct="#95CDB4", muted="#A2AFB1", accent="#FF8F7E", accent_ink="#121A1B", focus="#95CDB4"))),
    "birdbrain": dict(name="Birdbrain", modes=dict(
        light=dict(bg="#F2F4F8", col="#FFFFFF", hover="#E7EAF1", line="#D5D9E3", text="#1A1B22", head="#1A1B22",
                   struct="#4B3F8F", muted="#62646E", accent="#A3261C", accent_ink="#FFFFFF", focus="#4B3F8F"),
        dark=dict(bg="#17182B", col="#1F2138", hover="#272A45", line="#373B5E", text="#ECEDF5", head="#ECEDF5",
                  struct="#B7ABFF", muted="#A6A9BC", accent="#FF8F7E", accent_ink="#17182B", focus="#B7ABFF"))),
    "night": dict(name="Night study", modes=dict(
        dark=dict(bg="#16211D", col="#1B2823", hover="#21312B", line="#2C3E36", text="#E9E6DC", head="#E9E6DC",
                  struct="#86CDBF", muted="#A3AEA6", accent="#F0A24A", accent_ink="#16211D", focus="#F0A24A"),
        light=dict(bg="#EDF1EC", col="#F8FAF6", hover="#E3E9E3", line="#CBD6CE", text="#16211D", head="#16211D",
                   struct="#23645B", muted="#526059", accent="#9A4A0B", accent_ink="#FFFFFF", focus="#23645B"))),
    "contrast": dict(name="High contrast", modes=dict(
        dark=dict(bg="#000000", col="#0A0A0A", hover="#1E1E1E", line="#8A8A8A", text="#FFFFFF", head="#FFFFFF",
                  struct="#7FE0FF", muted="#D6D6D6", accent="#FFE14D", accent_ink="#000000", focus="#FFE14D"),
        light=dict(bg="#FFFFFF", col="#FFFFFF", hover="#EBEBEB", line="#5C5C5C", text="#000000", head="#000000",
                   struct="#004F8C", muted="#2E2E2E", accent="#A8001C", accent_ink="#FFFFFF", focus="#0047CC"))),
    "dusk": dict(name="Dusk", modes=dict(
        dark=dict(bg="#171A2B", col="#1D2135", hover="#252A42", line="#343A5A", text="#E6E2F3", head="#E6E2F3",
                  struct="#8FCBE8", muted="#AAA7C6", accent="#F28FA6", accent_ink="#171A2B", focus="#F5B38A"),
        light=dict(bg="#F1EFF8", col="#FAF9FD", hover="#E7E3F2", line="#D3CFE6", text="#1E2036", head="#2A2D52",
                   struct="#255F82", muted="#57557A", accent="#A8335A", accent_ink="#FFFFFF", focus="#255F82"))),
}
DEFAULT_THEME, DEFAULT_MODE = "forest", "light"
MODES = ("dark", "light", "system")
# The list page's layout: "glass" (frosted panels over a photo, glass.py) or "classic" (flat, report.py).
# Every theme works in both; in glass each theme is a colour scheme with its own day and night photo.
LAYOUTS = ("glass", "classic")
DEFAULT_LAYOUT = "glass"
# The keyword window and the tray icon keep Birdbrain's own violet whatever the page theme.
KEYWORD_WINDOW = THEMES["birdbrain"]["modes"]["light"]


def css_tokens() -> str:
    """One CSS block per theme and mode, keyed on <html data-theme data-mode>."""
    blocks = []
    for key, th in THEMES.items():
        for mode, tokens in th["modes"].items():
            props = [f"--{k.replace('_', '-')}:{v}" for k, v in tokens.items()]
            sel = f":root[data-theme={key}][data-mode={mode}]"
            if key == DEFAULT_THEME and mode == DEFAULT_MODE:
                sel += ",:root:not([data-theme])"
            blocks.append(f"{sel}{{{';'.join(props)};color-scheme:{mode}}}")
    return "".join(blocks)


@lru_cache(maxsize=1)
def font_face_css() -> str:
    """@font-face rules with the fonts embedded, so the page needs no network."""
    rules = []
    for family, name, weight, style in WEB_FONTS:
        path = FONT_DIR / name
        if not path.exists():
            continue
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:{style};'
                     f'font-display:swap;src:url(data:font/ttf;base64,{data}) format("truetype")}}')
    return "".join(rules)


@lru_cache(maxsize=1)
def tk_font_family() -> str:
    """Make the bundled font available to Tk for this process only (nothing is
    installed system-wide) and return the family name to use."""
    try:
        added = sum(ctypes.windll.gdi32.AddFontResourceExW(str(FONT_DIR / n), 0x10, 0)  # FR_PRIVATE
                    for n in TK_FONT_FILES)
        if added:
            return TK_FONT_FAMILY
    except Exception:
        log.exception("Could not load bundled font for the keyword window")
    return "Segoe UI"
