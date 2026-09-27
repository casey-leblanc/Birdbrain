"""Themes and fonts for the list page and the keyword window.

THEMES are the Focus layout's colour themes: a flat canvas with lots of room, the list set in
Atkinson Hyperlegible, and colour used for structure and urgency only. Each has a light (day) and a
dark (night) palette, and each has its own character, so they read as different rooms rather than
tints of one. Every text role is >= 4.5:1 on every surface it sits on (WCAG AA); the self-test checks
it. The Glass layout's themes are photo schemes in glass.py. Both layouts also have a Custom theme
built from the student's own choices (custom.py).

Roles
  bg / col / hover / line   canvas, dialog surface, hover wash, hairlines
  text / head               primary text, the date headline
  struct                    headings (now, this week, later), course codes, the primary button
  muted                     secondary text: times, labels, hints
  accent / accent_ink       overdue work (its date chip and the overdue count), and errors; text on an accent fill
  focus                     keyboard focus ring
Worked out from those (heat() below)
  h-today / h-tomorrow      Glass's amber and yellow heat colours, softened into this theme's canvas, as flat chips on
                            the date; -ink is the text on them (4.5:1) and -dot a fuller version for the day labels
  edge                      the outline of text fields, at least 3:1 against the dialog and the field
Exams take the structure colour: a solid chip, and an outlined one for quizzes, so "what it is" stays apart from
"how soon".
"""
from __future__ import annotations

import base64
import colorsys
import ctypes
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
# Web page: Atkinson Hyperlegible Next (variable weight, roman + italic).
WEB_FONTS = [("Birdbrain Sans", "AtkinsonHyperlegibleNext-VF.ttf", "200 800", "normal"),
             ("Birdbrain Sans", "AtkinsonHyperlegibleNext-Italic-VF.ttf", "200 800", "italic")]
# Tk can't use variable fonts well, so the keyword window uses the static original cut.
TK_FONT_FILES = ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"]
TK_FONT_FAMILY = "Atkinson Hyperlegible"

# --- colour arithmetic (sRGB, as the browser composites) ----------------------------------------
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def hexa(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4


def lum(c) -> float:
    r, g, b = rgb(c) if isinstance(c, str) else c
    return .2126 * _lin(r) + .7152 * _lin(g) + .0722 * _lin(b)


def ratio(a, b) -> float:
    x, y = lum(a), lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


def mix(a, b, t: float) -> tuple[float, float, float]:
    """a moved toward b by t (0..1): the colour of b laid over a at opacity t."""
    a = rgb(a) if isinstance(a, str) else a
    b = rgb(b) if isinstance(b, str) else b
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _t(bg, col, hover, line, text, struct, muted, accent, accent_ink, focus, head=None):
    return dict(bg=bg, col=col, hover=hover, line=line, text=text, head=head or text, struct=struct, muted=muted,
                accent=accent, accent_ink=accent_ink, focus=focus)


THEMES = {
    # Forest follows caseyleblanc.dev: sage mist and deep pine, brick red for what's late. The default.
    "forest": dict(name="Forest", modes=dict(
        light=_t("#E8EEE6", "#F6F8F4", "#DDE5DB", "#C3CFC0", "#16211A", "#2C5A43", "#4B5A4F", "#A3261C", "#FFFFFF", "#2C5A43"),
        dark=_t("#0F1914", "#16221B", "#1D2B23", "#2C3E33", "#E3ECE5", "#8ED1AE", "#A0B2A6", "#FF8F7E", "#0F1914", "#8ED1AE"))),
    # Paper: ink on white and nothing else. The quietest room.
    "paper": dict(name="Paper", modes=dict(
        light=_t("#FAFAF7", "#FFFFFF", "#F0F0EB", "#D9D9D2", "#141414", "#141414", "#55554F", "#C1121F", "#FFFFFF", "#141414"),
        dark=_t("#141414", "#1B1B1B", "#232323", "#3A3A3A", "#EDEDEA", "#EDEDEA", "#A9A9A4", "#FF7A7A", "#141414", "#EDEDEA"))),
    # Slate: cool blue-grey and navy, like a winter notebook.
    "slate": dict(name="Slate", modes=dict(
        light=_t("#E7ECF3", "#F7F9FC", "#DAE1EB", "#C2CCDA", "#121A26", "#274C77", "#4B5768", "#B3261E", "#FFFFFF", "#274C77"),
        dark=_t("#0E1520", "#141D2B", "#1B2636", "#2B3A50", "#E4EAF3", "#9CC3F0", "#A2AEBF", "#FF8F7E", "#0E1520", "#9CC3F0"))),
    # Ocean: sea glass and deep teal.
    "ocean": dict(name="Ocean", modes=dict(
        light=_t("#E6F2F3", "#F6FBFB", "#D8EAEC", "#BCD9DC", "#0E2328", "#0D5E6B", "#435E63", "#B3261E", "#FFFFFF", "#0D5E6B"),
        dark=_t("#0A1B20", "#0F242A", "#152E35", "#23444C", "#E2F1F2", "#7ED4E0", "#98B6BA", "#FF9A8A", "#0A1B20", "#7ED4E0"))),
    # Birdbrain: its own lavender and violet.
    "birdbrain": dict(name="Birdbrain", modes=dict(
        light=_t("#EEEBF7", "#FAF9FE", "#E3DFF1", "#CFC8E6", "#1D1930", "#4A3A99", "#5A556D", "#A3261C", "#FFFFFF", "#4A3A99"),
        dark=_t("#17142A", "#1F1B36", "#272243", "#3A3460", "#ECEAF6", "#B9ABFF", "#ABA6C4", "#FF8F7E", "#17142A", "#B9ABFF"))),
    # Dusk: blush and indigo by day, a pink-and-blue evening by night.
    "dusk": dict(name="Dusk", modes=dict(
        light=_t("#F6ECEF", "#FDF8FA", "#EDDFE5", "#DCC6D0", "#221C33", "#3C3A8C", "#5B546B", "#A8335A", "#FFFFFF", "#3C3A8C", head="#2B2552"),
        dark=_t("#1A1830", "#211F3A", "#2A2747", "#3D3964", "#EEE7F4", "#8FCBE8", "#B3ABC8", "#F28FA6", "#1A1830", "#F5B38A"))),
    # Cozy: linen and pine by day; by night a cabin, pine-dark with lamplight amber.
    "night": dict(name="Cozy", modes=dict(
        light=_t("#F2EDE3", "#FBF8F2", "#E8E1D3", "#D5CAB6", "#2A1F16", "#2E5A4C", "#5C5043", "#9A3F0B", "#FFFFFF", "#2E5A4C"),
        dark=_t("#15201B", "#1B2822", "#22312A", "#2F4238", "#EDE6D8", "#E3B26A", "#AEB3A5", "#FF9E7A", "#15201B", "#E3B26A"))),
    # Sunrise: butter and burnt gold, warm and bright.
    "sunrise": dict(name="Sunrise", modes=dict(
        light=_t("#FBF3DC", "#FFFBEF", "#F3E8C8", "#E3D3A4", "#2B2110", "#7A4E00", "#65573A", "#B42318", "#FFFFFF", "#7A4E00"),
        dark=_t("#1C1810", "#242016", "#2D281C", "#453C28", "#F5EBD2", "#FFC857", "#BDB08F", "#FF8A70", "#1C1810", "#FFC857"))),
    "contrast": dict(name="High contrast", modes=dict(
        light=_t("#FFFFFF", "#FFFFFF", "#EBEBEB", "#5C5C5C", "#000000", "#004F8C", "#2E2E2E", "#A8001C", "#FFFFFF", "#0047CC"),
        dark=_t("#000000", "#0A0A0A", "#1E1E1E", "#8A8A8A", "#FFFFFF", "#7FE0FF", "#D6D6D6", "#FF8080", "#000000", "#FFE14D"))),
}
DEFAULT_THEME, DEFAULT_MODE = "forest", "light"
MODES = ("dark", "light", "system")
# The list page's layout: "glass" (frosted panels over a photo, glass.py) or "focus" (a flat, roomy page,
# report.py). Each has its own themes: glass.SCHEMES and THEMES above. "custom" is the student's own, in both.
LAYOUTS = ("glass", "focus")
LAYOUT_NAMES = {"glass": "Glass", "focus": "Focus"}
CUSTOM = "custom"
DEFAULT_LAYOUT = "glass"
# The keyword window and the tray icon keep Birdbrain's own violet whatever the page theme.
KEYWORD_WINDOW = THEMES["birdbrain"]["modes"]["light"]


# Glass's heat colours for "how soon" (glass.py): Oriole amber for today, Goldfinch yellow for tomorrow. Overdue is
# each Focus theme's own accent, its red, so the three read loudest to quietest by day.
HEAT = {"today": "#FFBC5C", "tomorrow": "#FFE27D"}
SOFTEN = {"contrast": 0.0}          # how far each heat colour is softened into the canvas (default .2)


def heat(t: dict, soften: float = .2) -> dict:
    """The roles worked out from a theme's own: a flat chip for today and tomorrow, a dot of each for the day labels,
    and the field edge. Every chip's text holds 4.5:1 and the edge 3:1; the self-test checks it. The dots only repeat
    what the label says, so they need to be seen, not read."""
    bg, text, col = t["bg"], t["text"], t["col"]
    out = {}
    for k, c in HEAT.items():
        for s in (soften, soften * .5, 0):              # soften less if the chip's text would fall short
            fill = hexa(mix(c, bg, s))
            ink = text if ratio(text, fill) >= ratio(bg, fill) else bg
            if ratio(ink, fill) >= 4.5:
                break
        dot = c                                         # the day label's dot: the colour itself at night; by day a
        if lum(bg) > lum(text):                         # deeper, fuller version, so yellow still reads as yellow
            h, sat, _ = colorsys.rgb_to_hsv(*(v / 255 for v in rgb(c)))
            for step in range(21):
                dot = hexa(tuple(v * 255 for v in colorsys.hsv_to_rgb(h, min(1, sat + .45), 1 - step * .025)))
                if ratio(dot, bg) >= 1.8:
                    break
        out.update({f"h_{k}": fill, f"h_{k}_ink": ink, f"h_{k}_dot": dot})
    edge = t["line"]
    for step in range(21):
        edge = hexa(mix(t["line"], text, step / 20))
        if min(ratio(edge, col), ratio(edge, bg)) >= 3:
            break
    out["edge"] = edge
    return out


def css_tokens(themes: dict | None = None) -> str:
    """One CSS block per theme and mode, keyed on <html data-theme data-mode>. By default the built-in
    themes; custom.py passes the Custom theme on its own."""
    blocks = []
    for key, th in (THEMES if themes is None else themes).items():
        for mode, tokens in th["modes"].items():
            tokens = {**tokens, **heat(tokens, SOFTEN.get(key, .2))}
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
