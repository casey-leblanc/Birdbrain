"""The Custom theme, in both layouts: the student's own colours (Focus) or photos (Glass).

Focus: four colours for day and four for night (background, text, headings with course codes and exams, and
overdue work). The softer shades (dialog surface, hover, hairlines, secondary text) are worked out from
those four, the secondary text as soft as it can be while still reaching 4.5:1. focus_warnings() names any
chosen pair that falls short, so the page can say so while the student picks.

Glass: a day photo and a night photo, copied into Birdbrain's data folder at a sensible size. Each is measured
the way the built-in photos were (DESIGN.md, the Measured Glass Rule): the glass is tinted with the photo's own
hue and darkened just enough that the softest text on it holds 4.5:1 over the brightest part of the picture,
and the window buttons take white or dark ink, whichever holds 3:1 over the top of it.
"""
from __future__ import annotations

import colorsys
import io
import time
from typing import Callable

from PIL import Image, ImageFilter, ImageOps

import glass
import prefs
import theme
from config import DATA_DIR

PHOTO_DIR = DATA_DIR / "photos"
SLOTS = ("light", "dark")
FOCUS_ROLES = ("bg", "text", "struct", "accent")
ROLE_NAMES = {"bg": "background", "text": "text", "struct": "headings and exams", "accent": "overdue"}
MAX_UPLOAD = 25 * 1024 * 1024
MAX_SIDE = 2560                       # plenty for a full-screen background, and quick to load
GLASS_ACCENT = "#DCD0FF"              # Forest's lavender until the student picks another
FALLBACK = {"light": dict(glass="rgba(36,41,51,.76)", sheet="rgba(34,39,50,.92)", bg="#7FA3D2"),
            "dark": dict(glass="rgba(16,22,34,.64)", sheet="rgba(18,24,36,.92)", bg="#0A1230")}
WHITE, BLACK = theme.WHITE, theme.BLACK


# colour arithmetic lives in theme.py; custom's callers use it from here too
rgb, hexa, lum, ratio, mix = theme.rgb, theme.hexa, theme.lum, theme.ratio, theme.mix


# --- Focus -----------------------------------------------------------------------------------------
def focus_default() -> dict:
    """A new Custom theme starts as a copy of Forest, day and night."""
    f = theme.THEMES["forest"]["modes"]
    return {m: {r: f[m][r] for r in FOCUS_ROLES} for m in SLOTS}


def focus_picks(p: dict) -> dict:
    fc = p.get("focus_custom") or {}
    d = focus_default()
    return {m: {r: (fc.get(m) or {}).get(r) or d[m][r] for r in FOCUS_ROLES} for m in SLOTS}


def focus_tokens(pick: dict) -> dict:
    """Every Focus role from the four chosen colours."""
    bg, text, struct, accent = (pick[r] for r in FOCUS_ROLES)
    dark = lum(bg) < lum(text)
    col = hexa(mix(bg, WHITE, .04 if dark else .6))          # dialogs: a touch lighter than the page
    muted = text
    for step in range(1, 61):                                   # as soft as it can be and still read
        t = step / 100
        c = hexa(mix(text, bg, t))
        if min(ratio(c, bg), ratio(c, col)) < 4.6:
            break
        muted = c
    ink = hexa(WHITE) if ratio(WHITE, accent) >= ratio(bg, accent) else bg
    return dict(bg=bg, col=col, hover=hexa(mix(bg, text, .07)), line=hexa(mix(bg, text, .2)), text=text, head=text,
                struct=struct, muted=muted, accent=accent, accent_ink=ink, focus=struct)


def focus_warnings(p: dict) -> dict:
    """Plain-language warnings for any chosen colour that won't read on the background, per mode."""
    out = {}
    for m, pick in focus_picks(p).items():
        msgs = []
        for role in ("text", "struct", "accent"):
            r = ratio(pick[role], pick["bg"])
            if r < 4.5:
                msgs.append(f"The {ROLE_NAMES[role]} colour is hard to read on this background "
                            f"({r:.1f}:1; it needs 4.5). Try a {'lighter' if lum(pick['bg']) < .2 else 'darker'} one.")
        out[m] = msgs
    return out


# --- Glass -----------------------------------------------------------------------------------------
def measure(img: Image.Image) -> dict:
    """The glass, sheet and window-button colours a photo needs (see the module docstring)."""
    small = img.copy()
    small.thumbnail((320, 320))
    # The frame blurs what's behind it (6px on a ~1366px window), so judge the blurred picture.
    blurred = small.filter(ImageFilter.GaussianBlur(radius=max(1.0, small.width / 1366 * 6)))
    px = sorted(blurred.getdata(), key=lum)
    bright = px[int(len(px) * .995)]                            # the brightest part text could land on
    avg = tuple(sum(c[i] for c in px) / len(px) for i in range(3))
    h, s, _ = colorsys.rgb_to_hsv(*(v / 255 for v in avg))
    tint = tuple(v * 255 for v in colorsys.hsv_to_rgb(h, min(s * 1.1, .45), .2))   # the photo's own hue, dark

    def reads(a: float) -> bool:
        frame = mix(bright, tint, a)
        pane = mix(frame, WHITE, .055)       # the columns' faint wash
        button = mix(frame, WHITE, .15)      # the glass buttons' wash, the lightest surface text sits on
        return (ratio(mix(pane, WHITE, .88), pane) >= 4.8 and ratio(mix(frame, WHITE, .88), frame) >= 4.8
                and ratio(mix(button, WHITE, .92), button) >= 4.7)

    alpha = next((a / 100 for a in range(50, 93) if reads(a / 100)), .92)
    sheet = tuple(v * .9 for v in tint)
    out = dict(glass="rgba(%d,%d,%d,%.2f)" % (*map(round, tint), alpha), sheet="rgba(%d,%d,%d,.92)" % tuple(map(round, sheet)),
               bg=hexa(avg), alpha=alpha)
    # The window buttons sit on the top-right of the photo behind a faint dark fade.
    w, hgt = small.size
    corner = sorted(small.crop((int(w * .75), 0, w, max(1, int(hgt * .12)))).getdata(), key=lum)
    top = corner[int(len(corner) * .95)]
    if ratio(WHITE, mix(top, BLACK, .36)) < 3:
        out.update(tb_fg="#16212B", tb_shadow="0 0 6px rgba(255,255,255,.8)",
                   tb_bg="linear-gradient(rgba(255,255,255,.4),rgba(255,255,255,.12) 70%,rgba(255,255,255,0))")
    return out


def save_photo(store, slot: str, data: bytes) -> dict:
    """Keep a copy of the student's photo for the day or night slot, measure it, and remember it."""
    if slot not in SLOTS:
        raise ValueError("Choose the day or the night photo.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("That picture is over 25 MB. Choose a smaller one.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise ValueError("That file isn't a picture Birdbrain can read. Use a JPEG, PNG or WebP.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < 360:
        raise ValueError("That picture is too small to fill the window. Choose one at least 1000 pixels wide.")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PHOTO_DIR / f"custom-{slot}.jpg", "JPEG", quality=86, optimize=True, progressive=True)
    ImageOps.fit(img, (340, 200), Image.LANCZOS).save(PHOTO_DIR / f"custom-{slot}-thumb.jpg", "JPEG", quality=82)
    return prefs.set_glass_photo(store, slot, {**measure(img), "v": int(time.time() * 1000) % 10**9})


def remove_photo(store, slot: str) -> dict:
    if slot not in SLOTS:
        raise ValueError("Choose the day or the night photo.")
    for name in (f"custom-{slot}.jpg", f"custom-{slot}-thumb.jpg"):
        (PHOTO_DIR / name).unlink(missing_ok=True)   # Birdbrain's own copy; the student's original is untouched
    return prefs.set_glass_photo(store, slot, None)


def glass_scheme(p: dict) -> dict:
    gc = p.get("glass_custom") or {}
    accent = gc.get("accent") or GLASS_ACCENT
    ink = "#141018" if ratio(accent, "#141018") >= ratio(accent, WHITE) else "#FFFFFF"
    modes = {}
    for m in SLOTS:
        info = gc.get(m) or {}
        modes[m] = {k: info[k] for k in ("glass", "sheet", "bg", "tb_fg", "tb_shadow", "tb_bg") if info.get(k)} or FALLBACK[m]
    return dict(name="Custom", common=dict(title=hexa(mix(accent, WHITE, .45)), lav=accent, lav_ink=ink, focus="#FFFFFF"),
                light=modes["light"], dark=modes["dark"])


def has_photo(p: dict, slot: str) -> bool:
    return bool((p.get("glass_custom") or {}).get(slot)) and glass.photo_path(f"custom-{slot}").exists()


def thumbs(p: dict, photo: Callable[[str], str | None]) -> dict:
    """The addresses of the day and night thumbnails (None where there's no photo yet)."""
    gc = p.get("glass_custom") or {}
    out = {}
    for m in SLOTS:
        url = photo(f"custom-{m}-thumb") if has_photo(p, m) else None
        out[m] = url + ("&" if "?" in url else "?") + f"v={gc[m]['v']}" if url else None
    return out


def css(p: dict, photo: Callable[[str], str | None]) -> str:
    """The Custom theme's CSS for both layouts, kept in its own <style> so it can change while the page is open."""
    focus = theme.css_tokens({"custom": dict(name="Custom", modes={m: focus_tokens(k) for m, k in focus_picks(p).items()})})
    gc = p.get("glass_custom") or {}
    shown = lambda name: photo(name) if has_photo(p, name.split("-")[1]) else None
    versions = {m: (gc.get(m) or {}).get("v") for m in SLOTS}
    return focus + glass.scheme_css("custom", glass_scheme(p), shown, versions)
