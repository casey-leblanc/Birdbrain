"""Records a short film of the list being used, to look at the motion: Glass at night and Focus by day, with motion
at Full and then Off. Invented data, the app's own page, a real pointer.

    python tests/ui/preview_recording.py <folder>

Writes motion-preview.mp4 into the folder. Needs ffmpeg; without it the frames are left in <folder>/frames. Not a
test: nothing here is asserted. The pointer and the caption in the film are drawn by this script, not by Birdbrain.
The film is made of the frames Chromium hands over as the page changes, so it can be a little less smooth than the
app itself.
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from page import PageTest  # first: it sets the import path

import prefs  # noqa: E402

SIZE = {"width": 1280, "height": 800}

# Headless Chromium films the page without a pointer, so one is drawn; the caption says which look is on screen.
OVERLAY = """
addEventListener('DOMContentLoaded', () => {
  const dot = document.createElement('div'), cap = document.createElement('div');
  dot.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;' +
    'background:rgba(255,255,255,.9);box-shadow:0 0 0 1.5px rgba(0,0,0,.55),0 2px 6px rgba(0,0,0,.4);z-index:2147483647;pointer-events:none;' +
    'transition:width .12s,height .12s,margin .12s';
  cap.style.cssText = 'position:fixed;left:50%;top:10px;transform:translateX(-50%);padding:6px 14px;border-radius:999px;' +
    'background:rgba(0,0,0,.72);color:#fff;font:600 14px system-ui,sans-serif;z-index:2147483647;pointer-events:none';
  document.documentElement.append(dot, cap);
  const at = e => { dot.style.transform = `translate(${e.clientX}px,${e.clientY}px)`; };
  addEventListener('mousemove', at, true);
  addEventListener('mousedown', e => { at(e); dot.style.width = dot.style.height = '13px'; dot.style.margin = '-6.5px 0 0 -6.5px'; }, true);
  addEventListener('mouseup', () => { dot.style.width = dot.style.height = '18px'; dot.style.margin = '-9px 0 0 -9px'; }, true);
  window.__caption = t => { cap.textContent = t; };
  window.__caption(sessionStorage.getItem('caption') || '');
});
"""


class Film(PageTest):
    out: Path = Path(".")

    def context_options(self) -> dict:
        return {"viewport": SIZE}

    def open(self):
        if not getattr(self, "_overlaid", False):
            self.page.add_init_script(OVERLAY)
            self._overlaid = True
        super().open()

    # --- the camera -------------------------------------------------------------------------------------------
    def film(self):
        """Keep every frame Chromium draws from now on, with the moment it was drawn."""
        self.frames_dir = self.out / "frames"
        shutil.rmtree(self.frames_dir, ignore_errors=True)
        self.frames_dir.mkdir(parents=True)
        self.shots: list[float] = []
        self.cdp = self.context.new_cdp_session(self.page)

        def frame(e):
            (self.frames_dir / f"{len(self.shots):05d}.jpg").write_bytes(base64.b64decode(e["data"]))
            self.shots.append(e["metadata"]["timestamp"])
            self.cdp.send("Page.screencastFrameAck", {"sessionId": e["sessionId"]})
        self.cdp.on("Page.screencastFrame", frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": SIZE["width"],
                                               "maxHeight": SIZE["height"], "everyNthFrame": 1})

    def cut(self) -> Path | None:
        """Stop filming and put the frames together, each shown for as long as it was on screen."""
        self.wait(300)
        self.cdp.send("Page.stopScreencast")
        times = self.shots + [self.shots[-1] + 0.5]
        lines = ["ffconcat version 1.0"]
        for n in range(len(self.shots)):
            lines += [f"file '{n:05d}.jpg'", f"duration {max(0.001, times[n + 1] - times[n]):.4f}"]
        lines.append(f"file '{len(self.shots) - 1:05d}.jpg'")
        (self.frames_dir / "frames.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if not shutil.which("ffmpeg"):
            return None
        film = self.out / "motion-preview.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(self.frames_dir / "frames.txt"),
                        "-vf", "fps=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-movflags", "+faststart",
                        str(film)], check=True)
        shutil.rmtree(self.frames_dir, ignore_errors=True)
        return film

    # --- the hand ---------------------------------------------------------------------------------------------
    def wait(self, ms: int):
        self.page.wait_for_timeout(int(ms * .75) if ms > 300 else ms)   # the pauses between scenes, kept brisk

    def glide(self, x: float, y: float, ms: int = 450):
        """Move the pointer there the way a hand does: quick in the middle, gentle at both ends."""
        x0, y0 = getattr(self, "_at", (640, 400))
        steps = max(4, ms // 16)
        for n in range(1, steps + 1):
            t = n / steps
            k = t * t * (3 - 2 * t)
            self.page.mouse.move(x0 + (x - x0) * k, y0 + (y - y0) * k)
            self.page.wait_for_timeout(16)
        self._at = (x, y)

    def point(self, row, dx: float = 150, dy: float | None = None, ms: int = 450):
        b = row.bounding_box()
        self.glide(b["x"] + dx, b["y"] + (b["height"] / 2 if dy is None else dy), ms)
        return b

    def title_of(self, row):
        b = row.locator(".t").bounding_box()
        return b["x"] + 14, b["y"] + b["height"] / 2

    def drag(self, row, to_x: float, to_y: float, ms: int = 900, hold: int = 350):
        x, y = self.title_of(row)
        self.glide(x, y)
        self.page.mouse.down()
        self.wait(120)
        self.glide(x + 6, y + 10, 120)
        self.glide(to_x, to_y, ms)
        self.wait(hold)
        self.page.mouse.up()

    def caption(self, text: str):
        self.page.evaluate("t => { sessionStorage.setItem('caption', t); window.__caption(t); }", text)

    def look(self, **changes):
        prefs.update(self.store, changes)
        self.page.reload()
        self.page.wait_for_selector(".row")

    def quick(self, words: str):
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for()
        self.wait(350)
        self.page.keyboard.type(words, delay=55)
        self.wait(500)
        self.page.keyboard.press("Enter")

    def dock(self, kind: str):
        b = self.page.locator(f".dock [data-bin={kind}]").bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

    # --- the film ---------------------------------------------------------------------------------------------
    def runTest(self):
        row = self.row
        self.look(layout="glass", mode="dark", motion="full")
        self.caption("Glass, night · motion Full")
        self.film()
        self.wait(700)
        for title in ("Oxidase", "Dentist", "Chapter 7 Quiz"):                   # the sheen follows the pointer
            self.point(row(title), 190, ms=300)
            self.point(row(title), 70, ms=220)
        self.glide(*self._tick(row("Dentist")), 300)                             # tick: ripple, the check, the flight
        self.click()
        self.wait(1500)
        b = self.page.locator(".toast-undo").bounding_box()                      # Undo: it flies home
        self.glide(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, 350)
        self.click()
        self.wait(1200)
        self.quick("call mom fri 5pm")                                           # quick write: it drops in
        self.wait(1500)
        d = row("Dentist").bounding_box()                                        # reorder within a day
        self.drag(row("Catalase"), d["x"] + 90, d["y"] + 8, ms=700)
        self.wait(1000)
        o = row("Oxidase").bounding_box()                                        # a later card, planned for today
        self.drag(row("Urease"), o["x"] + 90, o["y"] + o["height"] - 6, ms=800)
        self.wait(1200)
        q = row("Chapter 7 Quiz").bounding_box()                                 # past its deadline: refused
        self.drag(row("Oxidase"), q["x"] + 90, q["y"] + 10, ms=700, hold=450)
        self.wait(1700)
        x, y = self.title_of(row("Chapter 7 Quiz"))                              # onto Completed
        self.glide(x, y, 350)
        self.page.mouse.down()
        self.wait(120)
        self.glide(x + 6, y + 10, 120)
        self.glide(*self.dock("completed"), 700)
        self.wait(300)
        self.page.mouse.up()
        self.wait(1300)
        row("Exam 2").locator(".tick").focus()                                   # the keyboard: M, arrows, Enter
        self.caption("Glass, night · keyboard: M, arrows, Enter")
        self.wait(400)
        for key, pause in (("m", 450), ("ArrowDown", 400), ("ArrowLeft", 450), ("ArrowDown", 400), ("Enter", 1200)):
            self.page.keyboard.press(key)
            self.wait(pause)

        self.look(layout="focus", mode="light", motion="full")
        self.caption("Focus, day · motion Full (quieter: no ripple, no sheen)")
        self.wait(700)
        self.glide(*self._tick(row("Dentist")), 400)
        self.click()
        self.wait(1400)
        b = self.page.locator(".bands ul.day[data-day] .row").nth(1).bounding_box()
        self.drag(row("Catalase"), b["x"] + 90, b["y"] + 8, ms=700)
        self.wait(1000)
        self.page.keyboard.press("@")                                            # filter: the rest glide together
        self.wait(250)
        self.page.keyboard.type("chem", delay=50)
        self.page.keyboard.press("Enter")
        self.wait(1200)
        self.page.keyboard.press("Escape")
        self.wait(900)

        self.look(layout="glass", mode="dark", motion="off")
        self.caption("Motion Off · nothing moves, everything still works")
        self.wait(800)
        self.glide(*self._tick(row("Exam 2")), 400)
        self.click()
        self.wait(1000)
        d = row("Oxidase").bounding_box()
        self.drag(row("call mom"), d["x"] + 90, d["y"] + 8, ms=700)
        self.wait(1200)
        film = self.cut()
        print("Saved", film or self.frames_dir)

    def click(self):
        self.page.mouse.down()
        self.wait(90)
        self.page.mouse.up()

    def _tick(self, row):
        b = row.locator(".tick").bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2



if __name__ == "__main__":
    Film.out = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    Film.out.mkdir(parents=True, exist_ok=True)
    result = unittest.TextTestRunner(verbosity=0).run(unittest.TestSuite([Film()]))
    sys.exit(0 if result.wasSuccessful() else 1)
