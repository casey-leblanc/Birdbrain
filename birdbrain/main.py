"""Birdbrain: a system-tray app that keeps a daily list of assignments,
tests and events from Moodle and Outlook on the web, shown in its own window.

Run with:  pythonw main.py   (no console window), or the packaged Birdbrain.exe.
Add --background to start in the tray without opening the window (for Startup).
"""
from __future__ import annotations

import os
import sys

if "--selftest" in sys.argv:   # packaged-build check: use a throwaway data folder, never the real one
    import tempfile
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="birdbrain-selftest-")
if getattr(sys, "frozen", False):
    # Packaged app: keep the scanner's browser in Playwright's usual shared folder. Left alone,
    # Playwright would look inside the app folder, where browser.install_browser() doesn't put it.
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",
                          os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ms-playwright"))

import logging
import re
import threading
import time
import webbrowser
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import pystray
from PIL import Image, ImageDraw, ImageFont

import appwindow
import autostart
import backup
import buildinfo
import filters
import hotkey
import instance
import notices
import phone
import power
import prefs
import report
import states
import theme
import toast
import trouble
import updater
from browser import NeedsLogin, interactive_login, open_context
from config import (CONFIG_PATH, DATA_DIR, LOG_PATH, STATE_PATH, Settings, clean_moodle_url, clean_outlook_url,
                    migrate_old_data)
from reader import is_receipt
from moodle import Moodle
from gradescope import Gradescope
from mcgraw import McGraw
from outlook import Outlook
from report import write as write_report
from server import ListServer
from store import Store

log = logging.getLogger("birdbrain")
SQUAWK = Path(__file__).parent / "assets" / "sounds" / "squawk.wav"
CHIRP = Path(__file__).parent / "assets" / "sounds" / "chirp.wav"


def squawk(sound: Path = SQUAWK) -> None:
    """The little squawk for something new that's due, or the chirp when today's list is done (Settings can turn both off)."""
    try:
        import winsound
        winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        log.exception("Couldn't play %s", sound.name)
SHOW_EVENT = "Local\\BirdbrainShowWindow"   # a second launch sets this to bring the window up

# The browser's errors for an address that leads nowhere: no such site, nothing answering there, or not a site it trusts.

class Progress:
    """How far a scan has got, for the list page's progress bar. Each site takes a share of the bar (a full Moodle scan,
    which reads every course, a bigger one) and says how far through itself it is, and what it's reading, as it goes.
    With no sites to share it out (an inbox scan, which can't know how many emails there are), the bar shows that
    something is happening rather than how much is left."""

    def __init__(self, sites: list[tuple[str, int]]):
        self.sites, self.total = sites, sum(w for _, w in sites)
        self.site, self.part, self.detail = (sites[0][0] if sites else ""), 0.0, ""

    def at(self, site: str, part: float = 0.0, detail: str = "") -> None:
        self.site, self.part, self.detail = site, min(max(part, 0.0), 1.0), detail

    def view(self) -> dict:
        """{"value": 0 to 1, or None when there's no telling, "text": "Scanning Moodle: CHEM 1212 (course 3 of 8)"}"""
        text = f"Scanning {self.site}" + (f": {self.detail}" if self.detail else "")
        before = 0
        for name, weight in self.sites:
            if name == self.site:
                return {"value": round((before + weight * self.part) / self.total, 3), "text": text}
            before += weight
        return {"value": None, "text": text}


def _and(names: list[str]) -> str:
    """'Moodle', 'Moodle and Outlook', 'Moodle, Outlook and Gradescope'."""
    return " and ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " and " + names[-1]


# The perched bird from the page's "all clear" drawing (report.PERCH), in its 96 x 60 drawing units: the body as
# straight runs and cubic curves, the eye, and the two strokes of the wing.
_BIRD = [(30, 40), ((32, 30), (40, 23), (50, 21)), ((51, 14), (56, 9), (62, 9)), ((67, 9), (70, 12), (71, 16)),
         (77, 17.5), (71, 19.5), ((71, 29), (64, 39), (52, 42.5)), ((46, 44.5), (40, 44.5), (36, 43.5)), (18, 52), (15, 49.5)]
_EYE = (64, 14.8, 1.6)
_WING = [[(34, 36), ((40, 29), (48, 27), (55, 30))], [(37.5, 40), ((43, 36.5), (49, 35.5), (53.5, 37))]]


def _trace(path: list) -> list[tuple[float, float]]:
    """A path's points: a pair is a point to go to in a straight line, a triple is a cubic curve (two controls, end)."""
    pts = [path[0]]
    for step in path[1:]:
        if isinstance(step[0], tuple):
            (x0, y0), ((x1, y1), (x2, y2), (x3, y3)) = pts[-1], step
            for i in range(1, 17):
                t = i / 16
                a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
                pts.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
        else:
            pts.append(step)
    return pts


def _reveal(path: Path) -> None:
    """Show a file in its folder, selected."""
    import subprocess
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])


def make_icon(badge: int | None = None, size: int = 64) -> Image.Image:
    """Tray/app icon: the perched bird in white on a Birdbrain-violet tile, with the due-today count in the accent colour
    at the top left (over the empty space above the tail, so it never covers the bird). Drawn large and scaled down, so
    every size is smooth; the wing's strokes only show at 48px and up, where they can be seen."""
    t = theme.THEMES["birdbrain"]["modes"]["light"]
    big = max(size, 16) * 8
    s = big / 64
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2 * s, 2 * s, 62 * s, 62 * s), 12 * s, fill=t["struct"])
    # the bird's 15..77 by 9..52.5 fitted to 54 of the tile's 64 units; its weight is in the head and body, so it
    # sits a little left of and above the middle of its outline to look centred
    w = 54 / 62
    k, ox, oy = w * s, 30.5 * s - 46 * w * s, 32 * s - 30.75 * w * s
    at = lambda x, y: (ox + x * k, oy + y * k)
    d.polygon([at(x, y) for x, y in _trace(_BIRD)], fill="#FFFFFF")
    if size >= 24:   # smaller, the eye is a stray pixel
        ex, ey, er = _EYE
        d.ellipse((*at(ex - er * 1.2, ey - er * 1.2), *at(ex + er * 1.2, ey + er * 1.2)), fill=t["struct"])
    if size >= 48:
        for stroke in _WING:
            d.line([at(x, y) for x, y in _trace(stroke)], fill=t["struct"], width=max(1, round(1.6 * k)), joint="curve")
    if badge:
        bold = theme.FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"
        d.ellipse((0, 0, 31 * s, 31 * s), fill=t["accent"], outline="#FFFFFF", width=round(1.5 * s))
        d.text((15.5 * s, 15.5 * s), str(min(badge, 9)), fill="#FFFFFF", anchor="mm",
               font=ImageFont.truetype(str(bold), int(22 * s)))
    return img.resize((size, size), Image.LANCZOS)


class App:
    def __init__(self):
        self.settings = Settings.load()
        self.store = Store()
        self._drop_receipts()
        self.lock = threading.Lock()          # one browser session at a time
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.force_full = False
        self.status = "Not scanned yet"
        self.last_sign_in_problems: list[str] = []
        self.problems: list[str] = []
        self._busy, self._busy_lock = 0, threading.Lock()   # scans running or about to (see scanning)
        self.scanning = False
        self.progress: Progress | None = None  # how far the scan running now has got
        self.signing_in = threading.Event()    # the sign-in window is open
        self.signed: list[str] = []            # ...and, while it is, the sites signed in so far
        self.waiting: list[str] = []           # ...and the ones it's still waiting on
        self.early_scan = False                # the signed-in sites were read while the window was still open
        self.mail_since: date | None = None   # inbox scan requested from the list page
        self.inbox_scanning = False
        self.stop_mail = threading.Event()     # "Stop" on that scan: what it has already added stays
        self.server: ListServer | None = None
        self.window: appwindow.AppWindow | None = None
        self.shortcut = hotkey.Shortcut(hotkey.Hotkey(self.on_quick), save=self._save_hotkey)
        self.quick_window: appwindow.QuickWindow | None = None
        self.offline = False   # the last scan couldn't reach any site at all
        self.quick_asks = 0   # times the shortcut was pressed with no small window to open: the list page opens quick write
        self.notices = notices.Notices(self.store, self.settings)   # what to say unasked, and when
        self.toasts = toast.Toasts(lambda title, text: self.notify(text, title), self.notices, self.on_show,
                                   enabled=lambda: self.settings.notify)
        self.phone = phone.Phone(self.store, self.settings, add=self._add_from_phone)   # off unless turned on (Advanced)
        self.phone.actions["scan"] = lambda: self.api_scan({})
        self.toasts.also.append(self.phone.tell)
        self.updater = updater.Updater()
        self.update: updater.Release | None = None   # a newer build, once a check has found one
        self.update_progress: dict | None = None     # while one is being downloaded and installed
        self.updating = threading.Lock()
        self.last_update_check = 0.0
        self.window_coming = threading.Event()   # set while the app window is being made
        self.set_up = threading.Event()        # the Moodle (and Outlook) addresses are known
        if self.settings.moodle_url:
            self.set_up.set()
        # Left-click runs the default item: open the app window.
        self.icon = pystray.Icon("Birdbrain", make_icon(), "Birdbrain", menu=pystray.Menu(
            pystray.MenuItem("Open Birdbrain", self.on_show, default=True),
            pystray.MenuItem("Quick write", lambda: self.on_quick()),
            pystray.MenuItem("Scan now", self.on_refresh),
            pystray.MenuItem("Sign in to your school sites…", self.on_login),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit),   # everything else is in the window: Settings, and the menu in its corner
        ))

    @property
    def scanning(self) -> bool:
        """A scan is running or about to. The loop's scan and an early one (while the sign-in window is open) can
        overlap, so each start counts up and each end counts down, and one ending doesn't hide the other."""
        return self._busy > 0

    @scanning.setter
    def scanning(self, on: bool) -> None:
        with self._busy_lock:
            self._busy = self._busy + 1 if on else max(self._busy - 1, 0)

    # --- menu actions -----------------------------------------------------------
    def on_show(self, *_):
        if self.window_coming.is_set() and not self.window:   # a click while the window is still being made: wait for it
            threading.Thread(target=self._show_once_made, daemon=True).start()
            return
        if self.window:
            threading.Thread(target=self.window.show, daemon=True).start()   # waits for the window if it's starting
        elif self.server:
            webbrowser.open(self.server.url)
        else:  # server didn't start: fall back to the read-only copy
            path, _ = write_report(self.store, self.settings, self.status)
            webbrowser.open(f"file:///{path}")

    def _drop_receipts(self) -> None:
        """Earlier versions read some receipt emails as work due (Gradescope's "Successfully submitted to HW3" showed as
        overdue). Take those off the list; the emails themselves are untouched, and they won't be read as work again."""
        gone = [i for i in self.store.items_between(datetime(2000, 1, 1), datetime(2100, 1, 1))
                if i.source == "outlook-mail" and is_receipt(f"{i.title} {i.detail}")]
        for i in gone:
            self.store.delete(i.id)
        if gone:
            log.info("Took %d receipt emails off the list", len(gone))

    def _notify_soon(self, msg: str) -> None:
        """A notification a moment after start, once the tray icon it comes from is showing."""
        threading.Timer(3, self.notify, args=(msg, "Birdbrain")).start()

    def _show_once_made(self) -> None:
        deadline = time.monotonic() + 30
        while self.window_coming.is_set() and not self.window and time.monotonic() < deadline:
            time.sleep(0.1)
        self.window_coming.clear()
        self.on_show()

    # --- list page (served by server.ListServer) ---------------------------------
    def _render(self, token: str, board: bool = False, app_window: bool = False) -> str:
        now = datetime.now()
        b = report.build(self.store, self.settings, now)
        saved = prefs.load(self.store)
        if not self.set_up.is_set() and not board:   # first run: ask for the addresses
            return report.render_setup(token, saved, app_window, self.settings.outlook_url, autostart=autostart.available())
        p = self._progress_view()
        if board:
            return report.render_board(b, self.settings, self.status, now, self.store.version, saved, progress=p,
                                       sign_in=self._needs_sign_in())
        return report.render(b, self.settings, self.status, now, token, self.store.version, saved, app_window, progress=p,
                             sign_in=self._needs_sign_in(), update=self._update_view(), hotkey=self.shortcut.view())

    def _progress_view(self) -> dict | None:
        """What the status line's progress bar shows: an update going in, else the scan that's running."""
        return self.update_progress or (self.progress.view() if self.progress else None)

    def _needs_sign_in(self) -> list[str]:
        """The sites the last scan couldn't read because they want signing in to again (none while the sign-in
        window is already open)."""
        if self.signing_in.is_set():
            return []
        return [p.replace(" needs sign-in", "") for p in self.problems if "sign-in" in p]

    def _page_status(self) -> dict:
        return {"version": self.store.version, "status": self.status,
                "progress": self._progress_view(), "signing_in": self.signing_in.is_set(), "quick": self.quick_asks,
                "focus": self.toasts.view(),
                "scanning": self.scanning or self.mail_since is not None,
                "inbox": self.inbox_scanning or self.mail_since is not None}

    def request_mail_scan(self, since: date) -> None:
        self.stop_mail.clear()
        self.mail_since = since
        self._set_status(f"Inbox scan back to {since:%b} {since.day} is queued…")
        self.wake.set()

    def _start_server(self) -> None:
        try:
            self.server = ListServer(self.store, render_page=self._render,
                                     render_board=lambda token: self._render(token, board=True),
                                     status=self._page_status, request_mail_scan=self.request_mail_scan,
                                     on_change=self._refresh_view, port=self._last_port(),
                                     actions=self._page_actions(),
                                     render_quick=lambda token: report.render_quick(token, prefs.load(self.store)))
            self.server.start()
            self.store.set_meta("server_port", str(self.server.port))
        except Exception:
            log.exception("Could not start the list server; the list will open read-only")
            self.server = None

    def _last_port(self) -> int:
        """Reuse last run's port, so a browser sees the same site each time."""
        saved = self.store.get_meta("server_port")
        if saved:
            return int(saved)
        try:  # first run after the rename: the old version logged its port
            ports = re.findall(r"List page served at http://127\.0\.0\.1:(\d+)/",
                               LOG_PATH.read_text(encoding="utf-8", errors="ignore"))
            return int(ports[-1]) if ports else 0
        except OSError:
            return 0

    # --- the tray menu's actions, for the Settings sheet on the list page -------------
    def _page_actions(self) -> dict:
        return {"scan": self.api_scan, "scan-stop": self.api_scan_stop, "sign-in": self.api_sign_in, "sites": self.api_sites, "keywords": self.api_keywords,
                "open": self.api_open, "quit": self.api_quit, "sound": self.api_sound, "chirp": self.api_chirp,
                "setup": self.api_setup, "addresses": self.api_addresses, "update": self.api_update,
                "hotkey": self.shortcut.use, "quick-hide": self.api_quick_hide, "notifications": self.api_notifications,
                "telegram": self.api_telegram, "problem": self.api_problem, "backup": self.api_backup,
                "autostart": self.api_autostart}

    def api_autostart(self, body: dict) -> dict:
        """Settings > Notifications: start with the computer, or not (autostart.py); with no "on", just how it is."""
        if "on" in body:
            if not autostart.available():
                raise ValueError("Only an installed copy of Birdbrain on Windows can start by itself.")
            if not autostart.turn(bool(body["on"])):
                raise ValueError("Windows wouldn't let Birdbrain change that. Nothing was changed.")
            log.info("Start with Windows: %s", "on" if body["on"] else "off")
        v = autostart.view()
        return {"ok": True, **v, "message": "" if "on" not in body else
                "Birdbrain will start in the tray when you sign in to Windows." if v["on"] else
                "Birdbrain won't start by itself. Reminders come only while it is running."}

    def api_backup(self, body: dict) -> dict:
        """Settings > Advanced > Backup (backup.py): export what is the student's own to a file, or import one."""
        out = backup.action(self.store, body, reveal=_reveal)
        if "import" in body:
            self._refresh_view()
        return out

    def api_problem(self, body: dict) -> dict:
        """Report a problem (trouble.py): what would go in the zip, or the zip itself, saved and shown in its folder.
        Nothing is sent anywhere."""
        return trouble.action(self.store, body, self.status, reveal=_reveal)

    # --- the phone, through the student's own Telegram bot (phone.py); off unless turned on -----
    def _add_from_phone(self, text: str) -> dict:
        if not self.server:
            raise ValueError("Birdbrain's list isn't running on the PC right now, so that couldn't be added.")
        return self.server.quick({"text": text, "save": True})

    def api_telegram(self, body: dict) -> dict:
        """Settings > Advanced > Telegram: the bot's token (step 2), unlink, turn off, send a test, or just how far
        the setup has got."""
        self.phone.settings = self.settings
        if "token" in body:
            view = self.phone.use_token(str(body["token"]))
        elif body.get("unlink"):
            view = self.phone.unlink()
        elif body.get("off"):
            view = self.phone.turn_off()
        elif body.get("test"):
            if not self.phone.on:
                raise ValueError("Link your phone first: send the bot the /start code.")
            if not self.phone.tell(self.notices.sample()):
                raise ValueError(f"The message didn't go: {self.phone.tg.problem or 'Telegram is out of reach'}.")
            return {"ok": True, **self.phone.view(), "message": "Sent. Look at Telegram on your phone."}
        else:
            view = self.phone.view()
        return {"ok": True, **view}

    def _chat_loop(self) -> None:
        """While Telegram is on: one request held open that Telegram answers the moment something comes in."""
        while not self.stop.is_set():
            self.phone.settings = self.settings
            try:
                changed = self.phone.chat(25)
            except Exception:
                log.exception("Reading the phone's chat failed")
                changed = None
            if changed is None:
                self.stop.wait(15)   # off, or Telegram out of reach: look again shortly
            elif changed:
                self._refresh_view()

    # --- notifications on this PC (notices.py says what and when; toast.py shows them) --------
    def api_notifications(self, body: dict) -> dict:
        """Settings > Notifications: on or off, the two times, the one before a test; or {"test": true} to see one."""
        if body.get("test"):
            sample = self.notices.sample()
            try:
                self.icon.notify(sample.text, sample.title)   # shown even while notifications are off: it was asked for
            except Exception:
                log.exception("notify failed")
                return {"ok": False, "error": "Windows wouldn't show a notification. Check they're allowed for Birdbrain in Windows Settings › System › Notifications."}
            self.toasts.last = sample
            return {"ok": True, "message": f"Sent: “{sample.line}”. Look by the clock. Clicking it opens Birdbrain."}
        s = Settings.load()
        if "on" in body:
            s.notify = bool(body["on"])
        if "tests" in body:
            s.test_reminders = bool(body["tests"])
        for key, field in (("morning", "morning_list"), ("evening", "evening_list")):
            if key in body:
                text = str(body[key] or "").strip()
                if text and not notices.hhmm(text):
                    return {"ok": False, "error": "That isn't a time. Use the clock, like 07:30."}
                setattr(s, field, text[:5])
        s.save()
        self.settings = self.notices.settings = self.phone.settings = s
        return {"ok": True, "on": s.notify, "morning": s.morning_list, "evening": s.evening_list, "tests": s.test_reminders,
                "message": "Saved." if s.notify else "Notifications are off. Your list still updates by itself."}

    def _notice_loop(self) -> None:
        """Every half minute: say what has come due, one notification at a time."""
        while not self.stop.wait(30):
            self.notices.settings = self.settings
            if self.set_up.is_set():
                self.toasts.tick()

    # --- quick write from anywhere: the system-wide shortcut and its small window -----------
    def on_quick(self) -> None:
        """The shortcut was pressed. The small always-on-top window opens; where Birdbrain has no window of its own,
        the list comes up with quick write open instead."""
        log.info("Quick write opened by its shortcut")
        if self.window and self.server:
            try:
                if self.quick_window is None:
                    self.quick_window = appwindow.QuickWindow(self.server.url.replace("/?token=", "/quick?token="))
                self.quick_window.show()
                return
            except Exception:
                log.exception("The quick write window couldn't open; using the main window")
        self.quick_asks += 1
        self.on_show()

    def api_quick_hide(self, body: dict) -> dict:
        if self.quick_window:
            self.quick_window.hide()
        return {"ok": True}

    def _save_hotkey(self, combo: str) -> None:
        s = Settings.load()
        s.quick_hotkey = self.settings.quick_hotkey = combo
        s.save()

    def _start_hotkey(self) -> None:
        """Put the saved shortcut in force. If another program has it, say so once; Settings offers others."""
        problem = self.shortcut.start(self.settings.quick_hotkey)
        if problem and self.store.get_meta("hotkey:told") != self.settings.quick_hotkey:
            self.store.set_meta("hotkey:told", self.settings.quick_hotkey)
            self._notify_soon(f"{problem} Pick another shortcut for quick write in Settings, under Keys.")

    # --- updates: Birdbrain's own builds on GitHub ---------------------------------------
    def _update_view(self) -> dict:
        """For the page: this build, and the newer one waiting, if a check found one."""
        return {"current": buildinfo.name(), "available": self.update.label if self.update else "",
                "notes": self.update.notes if self.update else "", "packaged": bool(getattr(sys, "frozen", False))}

    def check_update(self) -> str:
        """Ask GitHub for the newest build; what was found, in words. Raises updater.UpdateError with the reason."""
        self.last_update_check = time.monotonic()
        rel = self.updater.available()
        changed = (rel.tag if rel else "") != (self.update.tag if self.update else "")
        self.update = rel
        if changed:
            self.store.touch()   # open list pages hear about it
        if not rel:
            return f"Birdbrain {buildinfo.name()} is the newest version."
        if not getattr(sys, "frozen", False):
            return f"The newest build is {rel.label}. This copy runs from source: pull the repository to update it."
        return f"Birdbrain {rel.label} is available."

    def api_update(self, body: dict) -> dict:
        """Settings > App > Updates: check, or install."""
        try:
            if body.get("install"):
                if not self.update:
                    self.check_update()
                return {"ok": True, "message": self.start_update(), **self._update_view()}
            return {"ok": True, "message": self.check_update(), **self._update_view()}
        except updater.UpdateError as e:
            raise ValueError(str(e))

    def start_update(self) -> str:
        """Install the build a check found, on its own thread; what's happening, in words."""
        if not getattr(sys, "frozen", False):
            return "This copy of Birdbrain runs from source: pull the repository to update it."
        if self.signing_in.is_set():
            return "Finish signing in first (the sign-in window is open), then update."
        if self.updating.locked():
            return "Already updating."
        threading.Thread(target=self._install_update, daemon=True, name="update").start()
        return "Updating. Birdbrain restarts by itself in a minute or two."

    def _install_update(self) -> None:
        if not self.updating.acquire(blocking=False):
            return
        step = lambda text, value=None: setattr(self, "update_progress", {"text": text, "value": value})
        try:
            step("Checking for the newest version")
            rel = self.update or self.updater.available()
            if not rel:
                self._set_status(f"Birdbrain {buildinfo.name()} is already the newest version.")
                return
            what = f"Birdbrain {rel.label}"
            zip_path = self.updater.download(rel, lambda part: step(f"Downloading {what}", round(part, 3)))
            step(f"Checking {what} runs on this PC")
            new_app = self.updater.stage(zip_path, rel)
            step(f"Installing {what} once the scan running now ends" if self.scanning else f"Installing {what}")
            with self.lock:   # no scan is using the browser, and none starts
                step(f"Installing {what}: Birdbrain is restarting")
                self.updater.install(new_app, rel, [])
                log.info("Quitting for the update to %s", rel.tag)
                self.on_quit()
        except updater.UpdateError as e:
            log.warning("Update failed: %s", e)
            self._set_status(f"The update didn't go in: {e}")
        except Exception:
            log.exception("Update failed")
            self._set_status("The update didn't go in (the log says why). Birdbrain is as it was.")
        finally:
            self.update_progress = None
            self.updating.release()

    def _update_result(self) -> None:
        """Just restarted by an update: say how it went."""
        got = updater.last_result()
        if not got:
            return
        if got.get("ok"):
            msg = f"Updated to Birdbrain {buildinfo.name()}."
        else:
            msg = (f"The update couldn't be installed ({got.get('why', 'see update.log')}). Birdbrain is as it was; "
                   f"{updater.UPDATE_DIR / 'update.log'} says more.")
        log.info("%s", msg)
        self.status = msg + " " + self.status
        self._notify_soon(msg)

    def _auto_check_update(self) -> None:
        """A few times a day: look for a new build, and say so once in the tray. Settings has the Update button."""
        if not (self.settings.update_check and getattr(sys, "frozen", False)) or self.updating.locked():
            return
        if self.last_update_check and time.monotonic() - self.last_update_check < 6 * 3600:
            return
        try:
            self.check_update()
        except updater.UpdateError as e:
            log.info("Update check: %s", e)
            return
        rel = self.update
        if rel and self.store.get_meta("update:told") != rel.tag:
            self.store.set_meta("update:told", rel.tag)
            self.notify(f"Open Birdbrain's Settings and choose Update to {rel.label}.", f"Birdbrain {rel.label} is ready")

    def api_setup(self, body: dict) -> dict:
        """The welcome page. With "check", just tidy and check the addresses (step 1); otherwise save them and
        the chosen look (step 2), and sign-in and scanning can start."""
        s = Settings.load()
        moodle = clean_moodle_url(str(body.get("moodle", "")))
        outlook = None if body.get("no_outlook") else clean_outlook_url(str(body.get("outlook", "")))
        if body.get("check"):
            return {"ok": True, "moodle": moodle, "outlook": outlook}
        s.moodle_url = moodle
        s.scan_gradescope, s.scan_mcgraw = bool(body.get("gradescope")), bool(body.get("mcgraw"))
        if outlook is None:
            s.scan_outlook_mail = s.scan_outlook_calendar = False
        else:
            s.outlook_url = outlook
            s.scan_outlook_mail = s.scan_outlook_calendar = True
        s.save()
        look = {k: body[k] for k in ("layout", "theme", "focus_theme", "mode") if k in body}
        if look:
            prefs.update(self.store, look)
        self.settings = s
        if autostart.available() and body.get("autostart", True):   # offered on the welcome page, already ticked
            autostart.turn(True)
        log.info("Set up: Moodle %s, Outlook %s", s.moodle_url, "off" if body.get("no_outlook") else s.outlook_url)
        self.set_up.set()
        return {"ok": True, "moodle": s.moodle_url}

    def api_addresses(self, body: dict) -> dict:
        """Settings > Scanning: change where Moodle and Outlook are (one mistyped at setup, say). A new address needs
        signing in to, so the sign-in window opens for it, and the first scan of a new Moodle reads every course page."""
        s = Settings.load()
        moodle = clean_moodle_url(str(body.get("moodle", "")))
        outlook = None if body.get("no_outlook") else clean_outlook_url(str(body.get("outlook", "")))
        was_on = s.scan_outlook_mail or s.scan_outlook_calendar
        new_moodle = moodle != s.moodle_url
        new_outlook = outlook is not None and (outlook != s.outlook_url or not was_on)
        outlook_off = outlook is None and was_on
        if new_moodle:
            s.moodle_url = moodle
            if not all(u.startswith(moodle + "/") for u in (s.mcgraw_launch, s.mcgraw_course) if u):
                s.mcgraw_launch = s.mcgraw_launch_name = s.mcgraw_course = ""   # the McGraw Hill link was on the old one
        if outlook is None:
            s.scan_outlook_mail = s.scan_outlook_calendar = False
        else:
            s.outlook_url = outlook
            if not was_on:
                s.scan_outlook_mail = s.scan_outlook_calendar = True
        s.save()
        self.settings = s
        log.info("Addresses now: Moodle %s, Outlook %s", s.moodle_url, s.outlook_url if outlook else "off")
        if new_moodle:
            self.force_full = True
        if new_moodle or new_outlook:
            self.on_login()
        elif outlook_off:
            self.wake.set()
        return {"ok": True, "moodle": s.moodle_url, "outlook": outlook, "sign_in": new_moodle or new_outlook,
                "outlook_off": outlook_off}

    def api_sound(self, body: dict) -> dict:
        squawk()   # "Play the squawk" in Settings
        return {"ok": True}

    def api_chirp(self, body: dict) -> dict:
        """The page asks for this when you tick off the last thing due today; it stays quiet if sounds are off."""
        if prefs.load(self.store).get("sound", True):
            squawk(CHIRP)
        return {"ok": True}

    def api_scan(self, body: dict) -> dict:
        """Scan now, or a full rescan of Moodle. "state" says what happened: "started"; "running" (a scan already is,
        so another isn't queued behind it); "queued" (a full rescan, once the running scan ends); while the sign-in
        window is open, "early" (what's signed in so far is being read) or "signing-in" (nothing is signed in yet)."""
        if body.get("full"):
            self.force_full = True
            self.wake.set()
            return {"ok": True, "state": "queued" if self.scanning else "started"}
        if self.scanning:
            return {"ok": True, "state": "running"}
        if self.signing_in.is_set():
            self.early_scan = False   # asked for: read whatever is signed in now, even if that was done once already
            return {"ok": True, "state": "early" if self._scan_signed_in() else "signing-in"}
        self.wake.set()
        return {"ok": True, "state": "started"}

    def api_scan_stop(self, body: dict) -> dict:
        """Stop the older-emails scan: a queued one never starts; a running one ends where it is, and what it has
        already added stays (emails it hadn't got to are read next time)."""
        if self.mail_since is not None and not self.inbox_scanning:
            self.mail_since = None
            self._set_status("Inbox scan cancelled.")
        self.stop_mail.set()
        return {"ok": True}

    def api_sites(self, body: dict) -> dict:
        """Settings > Scanning: whether to read Gradescope and McGraw Hill Connect too."""
        s = Settings.load()
        for key, name in (("gradescope", "scan_gradescope"), ("mcgraw", "scan_mcgraw"), ("mcgraw_auto_renew", "mcgraw_auto_renew")):
            if key in body:
                setattr(s, name, bool(body[key]))
        if body.get("mcgraw_via") in ("moodle", "direct"):
            s.mcgraw_via = body["mcgraw_via"]
        s.save()
        self.settings = s
        log.info("Other sites: Gradescope %s, McGraw Hill Connect %s", s.scan_gradescope, s.scan_mcgraw)
        return {"ok": True, "gradescope": s.scan_gradescope, "mcgraw": s.scan_mcgraw, "mcgraw_via": s.mcgraw_via,
                "mcgraw_auto_renew": s.mcgraw_auto_renew}

    def api_sign_in(self, body: dict) -> dict:
        self.on_login()
        return {"ok": True}

    def api_keywords(self, body: dict) -> dict:
        words = body.get("keywords")
        if not isinstance(words, list) or len(words) > 50:
            raise ValueError("Couldn't read the keyword list.")
        clean: list[str] = []
        for w in words:
            w = " ".join(str(w).split())[:80]
            if w and w.lower() not in (c.lower() for c in clean):
                clean.append(w)
        self.settings = Settings.load()
        self.settings.hidden_keywords = clean
        self.settings.save()
        log.info("Hidden keywords now %s", clean)
        self.store.touch()   # open list pages pick up the change
        self._refresh_view()
        return {"ok": True, "keywords": report.keyword_counts(report.build(self.store, self.settings), clean)}

    def api_open(self, body: dict) -> dict:
        path = {"settings": CONFIG_PATH, "log": LOG_PATH}.get(body.get("what"))
        if not path:
            raise ValueError("Nothing to open.")
        os.startfile(path)
        return {"ok": True}

    def api_quit(self, body: dict) -> dict:
        threading.Timer(0.5, self.on_quit).start()   # answer the page first
        return {"ok": True}

    def on_refresh(self, *_):
        self.wake.set()

    def on_full(self, *_):
        self.force_full = True
        self.wake.set()

    def on_login(self, *_):
        def run():
            self._sign_in()
            self.wake.set()
        threading.Thread(target=run, daemon=True).start()

    def _sign_in(self) -> None:
        """The sign-in window; then, if a site couldn't even be opened, say which, and where to change its address.
        The window failing outright is logged, and scanning carries on (it says what's wrong in its own words).
        Scans may run while it's open: it saves each sign-in as it happens, and a scan leaves that newer session be."""
        if self.signing_in.is_set():   # one window at a time: they share a browser profile
            return
        self.signing_in.set()
        self.signed, self.waiting, self.early_scan = [], [], False
        self._set_status(self._before_first_scan() + "Opening the sign-in window…")
        try:
            missed = interactive_login(self.settings, on_change=self._sign_in_changed)
        except Exception:
            log.exception("The sign-in window failed")
            missed = []
        finally:
            self.signing_in.clear()
            self.signed, self.waiting = [], []
        self.store.set_meta("login_done", "1")
        if missed:
            what = _and(missed)
            self._set_status(f"Couldn't reach {what}; check the address in Settings › Advanced.")
            self.notify("If the address is wrong, change it in Settings › Advanced.", f"Couldn't reach {what}")

    def _before_first_scan(self) -> str:
        """The start of the status line until the first scan is done (the page keeps its counts hidden until then)."""
        return "" if self.store.get_meta("first_scan_done") == "1" else "Not scanned yet. "

    def _sign_in_changed(self, signed: list[str], waiting: list[str]) -> None:
        """News from the sign-in window: the sites signed in so far and the ones it's still waiting on. Once Moodle and
        Outlook are in, they're read straight away, not when the window closes (it may wait on another site a while)."""
        self.signed, self.waiting = signed, waiting
        if waiting and not self.scanning:
            done = f"Signed in to {_and(signed)}. " if signed else ""
            self._set_status(f"{self._before_first_scan()}{done}Waiting for you to sign in to {_and(waiting)}.")
        if waiting and not self.early_scan and not any(core in waiting for core in ("Moodle", "Outlook")) and \
                any(core in signed for core in ("Moodle", "Outlook")):
            self._scan_signed_in()

    def _scan_signed_in(self) -> bool:
        """While the sign-in window is still open, read the sites already signed in to, in the background. False if
        there's nothing signed in yet, or a scan is already running."""
        ready = tuple(self.signed)
        if not ready or self.scanning or self.early_scan:
            return False
        self.early_scan = self.scanning = True

        def run():
            try:
                self.scan(only=ready)
            except Exception:
                log.exception("Scan crashed")
                self._set_status(states.DIDNT_FINISH)
            finally:
                self.scanning = False
        threading.Thread(target=run, daemon=True, name="early-scan").start()
        return True

    def on_quit(self, *_):
        self.stop.set()
        self.shortcut.keys.stop()
        self.wake.set()
        if self.server:
            self.server.stop()
        self.icon.stop()
        if self.window:
            self.window.quit()

    def notify(self, msg: str, title: str = "Birdbrain"):
        if self.settings.notify:
            try:
                self.icon.notify(msg, title)
            except Exception:
                log.exception("notify failed")

    # --- scanning -----------------------------------------------------------------
    def scan_inbox(self, since: date) -> None:
        """One-off: read the Outlook inbox back to `since` (asked for from the list page)."""
        self.settings = Settings.load()
        label = f"{since:%b} {since.day}"
        self._set_status(f"Scanning inbox back to {label}…")
        new, problem = [], ""

        mine = Progress([])   # there's no telling how many emails there are: a bar that shows it's working
        mine.at(f"your inbox back to {label}")

        def progress(n: int) -> None:
            self._set_status(f"Scanning inbox back to {label}… {n} emails read")
            mine.at(f"your inbox back to {label}", detail=f"{n} emails read")
        self.inbox_scanning = True
        try:
            with self.lock, open_context(self.settings) as ctx:
                self.progress = mine
                new = Outlook(self.settings, self.store).scan_mail_since(
                    ctx, since, progress=progress, stop=self.stop_mail.is_set)
        except NeedsLogin as e:
            log.warning("%s", e)
            problem = "Outlook needs sign-in"
        except Exception:
            log.exception("Inbox scan failed")
            problem = "The inbox scan didn't finish; try again, or use Report a problem in the menu"
        finally:
            self.inbox_scanning = False
            if self.progress is mine:
                self.progress = None
        new, _ = filters.split(new, self.settings.hidden_keywords,
                               pool=report.window(self.store, self.settings, datetime.now()))
        updated = datetime.now().strftime("%I:%M %p").lstrip("0")
        found = f"{len(new)} new item{'' if len(new) == 1 else 's'}"
        if problem:
            self.status = problem
        elif self.stop_mail.is_set():
            self.status = f"Inbox scan stopped at {updated}: {found}"
        else:
            self.status = f"Inbox scanned back to {label} at {updated}: {found}"
        self.stop_mail.clear()
        self._refresh_view()
        if problem and "sign-in" in problem:
            self.notify("Choose 'Sign in to your school sites…' from the tray menu.", problem)

    def scan(self, only: tuple[str, ...] | None = None) -> None:
        """Read every site the student uses, or just `only` these (the ones already signed in, while the sign-in window
        is still open for another). Says how far it has got as it goes, for the list page's progress bar."""
        self.settings = s = Settings.load()   # pick up edits made via "Settings…"
        full = self.force_full or self.store.get_meta("first_scan_done") != "1"
        sites = [(name, weight) for name, on, weight in (
            ("Moodle", bool(s.moodle_url), 4 if full else 1),   # a full scan reads every course: the longest part
            ("Outlook", s.scan_outlook_mail or s.scan_outlook_calendar, 1),
            ("Gradescope", s.scan_gradescope, 1),
            ("McGraw Hill Connect", s.scan_mcgraw, 1)) if on and (only is None or name in only)]
        full = full and any(name == "Moodle" for name, _ in sites)
        if full or only is None:
            self.force_full = False
        new, troubles = [], []
        step = lambda name: (lambda part=0.0, detail="": self.progress and self.progress.at(name, part, detail))
        address = {"Moodle": s.moodle_url, "Outlook": s.outlook_url}
        with self.lock:   # after any scan already running, which keeps its own progress until it ends
            self._set_status("Full Moodle scan in progress…" if full else "Scanning…")
            self.progress = Progress(sites)
            try:
                with open_context(s) as ctx:
                    for name, _ in sites:
                        self.progress.at(name)
                        try:
                            if name == "Moodle":
                                new += Moodle(s, self.store).scan(ctx, full=full, progress=step(name))
                                if full:
                                    self.store.set_meta("first_scan_done", "1")
                            elif name == "Outlook":
                                new += Outlook(s, self.store).scan(ctx, progress=step(name))
                            elif name == "Gradescope":
                                new += Gradescope(s, self.store).scan(ctx)
                            else:
                                new += McGraw(s, self.store).scan(ctx, progress=step(name))
                        except NeedsLogin as e:
                            log.warning("%s", e)
                            troubles.append(states.Problem(name, "sign-in"))
                        except Exception as e:
                            log.exception("%s scan failed", name)
                            troubles.append(states.problem(name, e, address.get(name, "")))
            finally:
                self.progress = None

        updated = datetime.now().strftime("%I:%M %p").lstrip("0")
        waiting = f" Waiting for you to sign in to {_and(self.waiting)}." if self.signing_in.is_set() and self.waiting else ""
        problems = [p.line for p in troubles]
        self.offline = states.offline(troubles, len(sites))   # the loop looks again sooner, and nothing is called a problem
        self.status = states.status(updated, troubles, len(sites)) + waiting
        self.problems = [] if self.offline else problems
        self._refresh_view()

        needs = [p for p in problems if "sign-in" in p]
        if needs and needs != self.last_sign_in_problems and not self.signing_in.is_set():  # tell once, not every scan
            self.notify("Choose 'Sign in to your school sites…' from the tray menu.", "; ".join(needs))
        self.last_sign_in_problems = needs
        # Don't announce duplicates or keyword-hidden entries.
        new, _ = filters.split(new, self.settings.hidden_keywords,
                               pool=report.window(self.store, self.settings, datetime.now()))
        # Nor anything already over: a meeting or exam that has happened isn't news (overdue work still is).
        new = [i for i in new if i.kind == "assignment" or i.due >= datetime.now()]
        if new:
            self.notices.settings = self.settings
            if self.store.get_meta("notice:first_scan") == "1":   # the very first scan finds everything: that isn't news
                self.toasts.tell(self.notices.new_work(new))
            if prefs.load(self.store).get("sound", True):
                squawk()
        self.store.set_meta("notice:first_scan", "1")

    def _refresh_view(self) -> int:
        """Rewrite the list page and the tray badge; returns the due-today count."""
        _, due_today = write_report(self.store, self.settings, self.status)
        self.icon.icon = make_icon(due_today)
        self.icon.title = f"Birdbrain: {due_today} due today" + (" (sign-in needed)" if self.problems else "")
        return due_today

    def _set_status(self, s: str):
        self.status = s
        self.icon.title = f"Birdbrain: {s}"[:127]

    def loop(self):
        if not self.set_up.is_set():
            self._set_status("Waiting for your Moodle and Outlook addresses")
            while not self.set_up.wait(1):
                if self.stop.is_set():
                    return
        if self.store.get_meta("login_done") != "1" or not STATE_PATH.exists():
            self.notify("Sign in to your school sites in the window that opens. "
                        "It closes by itself once you're signed in.")
            self._sign_in()
        while not self.stop.is_set():
            self.scanning = True
            since = self.mail_since
            self.inbox_scanning = since is not None   # before the queue empties, so the page never sees a gap
            self.mail_since = None
            try:
                with power.awake():   # the PC doesn't go to sleep partway through
                    self.scan_inbox(since) if since else self.scan()
            except Exception:
                log.exception("Scan crashed")
                self._set_status(states.DIDNT_FINISH)
            finally:
                self.scanning = False
            self._auto_check_update()
            if self.mail_since is None:   # nothing queued while we were busy
                # by the clock on the wall: a PC that slept through its scan time scans as soon as it's back
                # offline: look again in a few minutes rather than waiting out the whole interval
                wait = min(5, self.settings.interval_minutes) if self.offline else self.settings.interval_minutes
                why = power.wait(self.wake, wait * 60, self.stop)
                self.wake.clear()
                if why == "woke":
                    log.info("Back from sleep: scanning once the network is up")
                    self._set_status("Back from sleep. Scanning as soon as the network is up…")
                    power.online(self.settings.moodle_url)

    def run(self, show: bool = True) -> None:
        """The app window owns the main thread; the tray icon, scans and the list server run beside it."""
        self._start_server()
        if not self.set_up.is_set():
            if self.server:
                show = True   # the welcome page needs you, even when started with --background
            else:             # no list server: fall back to plain dialogs
                first_run_setup()
                self.settings = Settings.load()
                if self.settings.moodle_url:
                    self.set_up.set()
        self._listen_for_show()
        self._update_result()
        threading.Thread(target=self._start_hotkey, daemon=True, name="hotkey-start").start()
        threading.Thread(target=self.loop, daemon=True, name="scans").start()
        threading.Thread(target=self._notice_loop, daemon=True, name="notices").start()
        threading.Thread(target=self._chat_loop, daemon=True, name="telegram").start()
        if toast.hear_clicks(self.icon, self.toasts.clicked):
            log.info("Notifications: a click on one opens the list on its card")
        threading.Thread(target=self.icon.run, kwargs={"setup": lambda icon: setattr(icon, "visible", True)},
                         daemon=True, name="tray").start()
        if self.server:
            self.window_coming.set()
        if self.server and appwindow.available():
            try:
                self.window = appwindow.AppWindow(self.server.url, icon_path=_window_icon())
                self.window_coming.clear()
                self.window.run(show=show)   # returns once Birdbrain quits
            except Exception:
                log.exception("The app window failed; the list opens in the browser instead")
                self._notify_soon("Birdbrain's own window couldn't start, so your list opens in your browser. The log says why.")
            if self.stop.is_set():
                return
            self.window = None
        elif self.server:
            self._notify_soon(appwindow.problem)
        self.window_coming.clear()
        if show:
            self.on_show()
        self.stop.wait()

    def _listen_for_show(self) -> None:
        """Starting Birdbrain while it's already running (a pinned taskbar icon, say) brings the window up."""
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32")
        k.CreateEventW.restype = wintypes.HANDLE
        k.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = k.CreateEventW(None, False, False, SHOW_EVENT)

        def wait():
            while handle and not self.stop.is_set():
                if k.WaitForSingleObject(handle, 1000) == 0:   # WAIT_OBJECT_0: signalled
                    self.on_show()
        threading.Thread(target=wait, daemon=True, name="show-signal").start()


def _window_icon() -> str | None:
    """The packaged app's window takes Birdbrain.exe's icon; from source, give it the same one."""
    if getattr(sys, "frozen", False):
        return None
    path = DATA_DIR / "birdbrain-bird.ico"
    if not path.exists():
        save_icon(path, (16, 32, 48, 256))
    return str(path)


def save_icon(path: Path, sizes: tuple[int, ...]) -> None:
    """A Windows icon file with each size drawn at that size (so the small ones get their own detail rules)."""
    images = [make_icon(size=n) for n in sorted(sizes, reverse=True)]
    images[0].save(path, format="ICO", sizes=[(n, n) for n in sizes], append_images=images[1:])


def show_running_copy() -> bool:
    """Ask the Birdbrain that's already running to show its window. False if it can't be reached."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32")
    k.OpenEventW.restype = wintypes.HANDLE
    k.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k.SetEvent.argtypes = [wintypes.HANDLE]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    ctypes.windll.user32.AllowSetForegroundWindow(-1)   # ASFW_ANY: let its window come to the front
    handle = k.OpenEventW(0x0002, False, SHOW_EVENT)      # EVENT_MODIFY_STATE
    if not handle:
        return False
    k.SetEvent(handle)
    k.CloseHandle(handle)
    return True


def first_run_setup() -> None:
    """Plain dialogs for the addresses; only used if the list server can't start (the welcome page needs it)."""
    s = Settings.load()
    if s.moodle_url:
        return
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    url = simpledialog.askstring("Birdbrain setup", "Your Moodle address (e.g. https://moodle.myschool.edu):")
    outlook = simpledialog.askstring(
        "Birdbrain setup", "Outlook address (school accounts: https://outlook.office.com,\n"
        "personal: https://outlook.live.com):", initialvalue=s.outlook_url)
    root.destroy()
    try:
        if url:
            s.moodle_url = clean_moodle_url(url)
        if outlook:
            s.outlook_url = clean_outlook_url(outlook)
    except ValueError:
        pass
    s.save()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import selftest
        out = Path(sys.argv[sys.argv.index("--selftest") + 1]) if len(sys.argv) > sys.argv.index("--selftest") + 1 \
            else Path.cwd() / "birdbrain-selftest.txt"
        sys.exit(selftest.run(out))
    if "--install-update" in sys.argv:   # install a build from a zip on this PC, then start it with what follows
        at = sys.argv.index("--install-update")
        sys.exit(updater.install_from_zip(Path(sys.argv[at + 1]), sys.argv[at + 2:]))
    # (before --build-info: the arguments after the zip are for the new version, not this one)
    if "--build-info" in sys.argv:   # which build this is, written to the file named after the flag
        import json
        Path(sys.argv[sys.argv.index("--build-info") + 1]).write_text(json.dumps(buildinfo.current()), encoding="utf-8")
        sys.exit(0)
    todo = instance.start_or_hand_over(sys.argv, show=show_running_copy)
    if todo != "start":
        if todo == "tell":   # another copy is running but couldn't be asked to show its window
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showinfo("Birdbrain", "Birdbrain is already running. Use its icon in the system tray.")
        sys.exit(0)
    moved = migrate_old_data()   # before logging opens the log file
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if moved:
        log.info("%s", moved)
    app = App()
    import browser
    browser.on_browser_install = lambda: app.notify(
        "Setting up Birdbrain's background browser. This one-time download takes a minute or two.")
    app.run(show="--background" not in sys.argv)
