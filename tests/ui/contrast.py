"""Measuring whether text can be read: its colour against what is really drawn behind it.

The page is photographed twice, once as it is and once with the text made invisible, so the second picture is the
background alone: glass over a photo, a coloured chip, a plain page, whatever it is. For each piece of text, the
worst pixel behind its letters is found (the lightest behind light text, the darkest behind dark text, ignoring a
few stray pixels) and the WCAG contrast ratio worked out. 4.5:1 is the bar for ordinary text, 3:1 for large text
(24px and up, or 18.66px and up in bold).
"""
from __future__ import annotations

import io

from PIL import Image

# What a student reads on the list, by selector.
TEXT = (".band h2", ".band h2 .n", ".grp", ".row .t", ".row .code", ".row .lab", ".row time.w", ".row .kind", ".row .in",
        ".row .unsure", ".row .rep", ".row .snz", ".row .detail", ".row .act", ".empty", ".dayclear", ".clear-head", ".clear-sub", ".clear-next",
        ".bin-title", ".bin .hint", "#status-dot .st")

COLLECT = """(selectors) => {
  const out = [];
  for (const sel of selectors) for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    if (el.closest('[hidden]') || (el.closest('details') && !el.closest('details').open && !el.closest('summary'))) continue;
    let opacity = 1; for (let n = el; n && n.nodeType === 1; n = n.parentElement) opacity *= +getComputedStyle(n).opacity;
    // where this element's own letters are: not its padding, border or marker, and not a button or chip inside it
    for (const node of el.childNodes) {
      if (node.nodeType !== 3 || !node.nodeValue.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      out.push({sel, text: node.nodeValue.trim().slice(0, 40), x: r.left, y: r.top, w: r.width, h: r.height, color: cs.color,
                size: parseFloat(cs.fontSize), weight: +cs.fontWeight || 400, opacity});
      // words the stylesheet draws beside a heading (a day's load) sit on the same ground as the heading
      const after = getComputedStyle(el, '::after');
      if (el.dataset.load && after.content !== 'none')
        out.push({sel: sel + '::after', text: el.dataset.load, x: r.left, y: r.top, w: r.width, h: r.height, color: after.color,
                  size: parseFloat(after.fontSize), weight: +after.fontWeight || 400, opacity});
    }
  }
  return out;
}"""
HIDE = """(selectors) => { for (const sel of selectors) for (const el of document.querySelectorAll(sel)) {
  el.style.setProperty('color', 'transparent', 'important'); el.style.setProperty('text-shadow', 'none', 'important');
  el.style.setProperty('text-decoration-color', 'transparent', 'important'); } }"""


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def lum(rgb) -> float:
    return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])


def ratio(a, b) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _rgba(css: str) -> tuple[float, float, float, float]:
    nums = [float(x) for x in css[css.index("(") + 1:css.index(")")].replace("/", ",").split(",")]
    return (nums[0], nums[1], nums[2], nums[3] if len(nums) > 3 else 1.0)


def measure(page, selectors=TEXT) -> list[dict]:
    """Every piece of text on the page that matches, with its contrast against what's behind it."""
    found = page.evaluate(COLLECT, list(selectors))
    page.evaluate(HIDE, list(selectors))
    page.wait_for_timeout(120)
    behind = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    width, height = behind.size
    out = []
    for f in found:
        box = (max(0, int(f["x"])), max(0, int(f["y"])), min(width, int(f["x"] + f["w"]) + 1), min(height, int(f["y"] + f["h"]) + 1))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            continue
        pixels = sorted(behind.crop(box).getdata(), key=lum)
        r, g, b, a = _rgba(f["color"])
        a *= f["opacity"]
        mid = pixels[len(pixels) // 2]
        ink = tuple(a * c + (1 - a) * m for c, m in zip((r, g, b), mid))      # see-through text takes on what's behind it
        light_text = lum(ink) > lum(mid)
        worst = pixels[int(len(pixels) * (.95 if light_text else .05))]
        large = f["size"] >= 24 or (f["size"] >= 18.66 and f["weight"] >= 700)
        out.append({**f, "ratio": round(ratio(ink, worst), 2), "need": 3.0 if large else 4.5})
    return out


def failures(page, selectors=TEXT) -> list[str]:
    return [f'{m["sel"]} “{m["text"]}” {m["ratio"]}:1 (needs {m["need"]})' for m in measure(page, selectors) if m["ratio"] < m["need"]]
