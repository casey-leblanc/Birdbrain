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
import webbrowser
from datetime import date, datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

import appwindow
import filters
import prefs
import report
import theme
from browser import NeedsLogin, interactive_login, open_context
from config import CONFIG_PATH, DATA_DIR, LOG_PATH, STATE_PATH, Settings, migrate_old_data
from jev import Jev
from keyword_dialog import edit_keywords
from moodle import Moodle
from outlook import Outlook
from report import write as write_report
from server import ListServer
from store import Store

log = logging.getLogger("birdbrain")
SQUAWK = Path(__file__).parent / "assets" / "sounds" / "squawk.wav"


def squawk() -> None:
    """The little squawk for something new that's due (Settings can turn it off)."""
    try:
        import winsound
        winsound.PlaySound(str(SQUAWK), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        log.exception("Couldn't play the squawk")
SHOW_EVENT = "Local\\BirdbrainShowWindow"   # a second launch sets this to bring the window up


def make_icon(badge: int | None = None, size: int = 64) -> Image.Image:
    """Tray/app icon: a bold "B" in the Birdbrain structure colour, with the
    due-today count in the accent colour."""
    t = theme.THEMES["birdbrain"]["modes"]["light"]
    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2 * s, 2 * s, 62 * s, 62 * s), 12 * s, fill=t["struct"])
    bold = theme.FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"
    d.text((32 * s, 33 * s), "B", fill="#FFFFFF", anchor="mm", font=ImageFont.truetype(str(bold), int(46 * s)))
    if badge:
        d.ellipse((33 * s, 0, 64 * s, 31 * s), fill=t["accent"])
        d.text((48.5 * s, 15.5 * s), str(min(badge, 9)), fill="#FFFFFF", anchor="mm",
               font=ImageFont.truetype(str(bold), int(22 * s)))
    return img


class App:
    def __init__(self):
        self.settings = Settings.load()
        self.store = Store()
        self.jev = Jev(self.settings)
        self.lock = threading.Lock()          # one browser session at a time
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.force_full = False
        self.status = "Not scanned yet"
        self.last_sign_in_problems: list[str] = []
        self.problems: list[str] = []
        self.dialog_open = threading.Lock()   # one keyword window at a time
        self.scanning = False
        self.mail_since: date | None = None   # inbox scan requested from the list page
        self.server: ListServer | None = None
        self.window: appwindow.AppWindow | None = None
        # Left-click runs the default item: open the app window.
        self.icon = pystray.Icon("Birdbrain", make_icon(), "Birdbrain", menu=pystray.Menu(
            pystray.MenuItem("Open Birdbrain", self.on_show, default=True),
            pystray.MenuItem("Refresh now", self.on_refresh),
            pystray.MenuItem("Full rescan of Moodle", self.on_full),
            pystray.MenuItem("Hide entries by keyword…", self.on_keywords),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sign in to Moodle / Outlook…", self.on_login),
            pystray.MenuItem("Settings…", lambda: os.startfile(CONFIG_PATH)),
            pystray.MenuItem("Open log", lambda: os.startfile(LOG_PATH)),
            pystray.MenuItem("Quit", self.on_quit),
        ))

    # --- menu actions -----------------------------------------------------------
    def on_show(self, *_):
        if self.window:
            threading.Thread(target=self.window.show, daemon=True).start()   # waits for the window if it's starting
        elif self.server:
            webbrowser.open(self.server.url)
        else:  # server didn't start: fall back to the read-only copy
            path, _ = write_report(self.store, self.settings, self.status)
            webbrowser.open(f"file:///{path}")

    # --- list page (served by server.ListServer) ---------------------------------
    def _render(self, token: str, board: bool = False, app_window: bool = False) -> str:
        now = datetime.now()
        b = report.build(self.store, self.settings, now)
        saved = prefs.load(self.store)
        if board:
            return report.render_board(b, self.settings, self.status, now, self.store.version, saved)
        return report.render(b, self.settings, self.status, now, token, self.store.version, saved, app_window)

    def _page_status(self) -> dict:
        return {"version": self.store.version, "status": self.status,
                "scanning": self.scanning or self.mail_since is not None}

    def request_mail_scan(self, since: date) -> None:
        self.mail_since = since
        self._set_status(f"Inbox scan back to {since:%b} {since.day} is queued…")
        self.wake.set()

    def _start_server(self) -> None:
        try:
            self.server = ListServer(self.store, render_page=self._render,
                                     render_board=lambda token: self._render(token, board=True),
                                     status=self._page_status, request_mail_scan=self.request_mail_scan,
                                     on_change=self._refresh_view, port=self._last_port(),
                                     actions=self._page_actions())
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
        return {"scan": self.api_scan, "sign-in": self.api_sign_in, "keywords": self.api_keywords,
                "open": self.api_open, "quit": self.api_quit, "sound": self.api_sound}

    def api_sound(self, body: dict) -> dict:
        squawk()   # "Play the squawk" in Settings
        return {"ok": True}

    def api_scan(self, body: dict) -> dict:
        if body.get("full"):
            self.force_full = True
        self.wake.set()
        return {"ok": True}

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
            with self.lock:
                interactive_login(self.settings)
            self.store.set_meta("login_done", "1")
            self.wake.set()
        threading.Thread(target=run, daemon=True).start()

    def on_keywords(self, *_):
        if self.dialog_open.locked():
            return
        def run():
            with self.dialog_open:
                items = report.window(self.store, self.settings, datetime.now())
                count = lambda k: sum(1 for i in items if filters.keyword_hit(i, [k]))
                result = edit_keywords(self.settings.hidden_keywords, count, icon=make_icon())
            if result is not None and result != self.settings.hidden_keywords:
                self.settings = Settings.load()
                self.settings.hidden_keywords = result
                self.settings.save()
                log.info("Hidden keywords now %s", result)
                self.store.touch()   # lets an open list page pick up the change
                self._refresh_view()
        threading.Thread(target=run, daemon=True).start()

    def on_quit(self, *_):
        self.stop.set()
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
        try:
            with self.lock, open_context(self.settings) as ctx:
                new = Outlook(self.settings, self.store, self.jev).scan_mail_since(
                    ctx, since, progress=lambda n: self._set_status(f"Scanning inbox back to {label}… {n} emails read"))
        except NeedsLogin as e:
            log.warning("%s", e)
            problem = "Outlook needs sign-in"
        except Exception:
            log.exception("Inbox scan failed")
            problem = "Inbox scan failed (see log)"
        new, _ = filters.split(new, self.settings.hidden_keywords,
                               pool=report.window(self.store, self.settings, datetime.now()))
        updated = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.status = (f"Inbox scanned back to {label} at {updated}: "
                       f"{len(new)} new item{'' if len(new) == 1 else 's'}") if not problem else problem
        self._refresh_view()
        if problem and "sign-in" in problem:
            self.notify("Choose 'Sign in to Moodle / Outlook…' from the tray menu.", problem)

    def scan(self) -> None:
        self.settings = Settings.load()   # pick up edits made via "Settings…"
        full = self.force_full or self.store.get_meta("first_scan_done") != "1"
        self.force_full = False
        new, problems = [], []
        self._set_status("Full Moodle scan in progress…" if full else "Scanning…")
        with self.lock, open_context(self.settings) as ctx:
            if self.settings.moodle_url:
                try:
                    new += Moodle(self.settings, self.store, self.jev).scan(ctx, full=full)
                    if full:
                        self.store.set_meta("first_scan_done", "1")
                except NeedsLogin as e:
                    log.warning("%s", e)
                    problems.append("Moodle needs sign-in")
                except Exception:
                    log.exception("Moodle scan failed")
                    problems.append("Moodle scan failed (see log)")
            if self.settings.scan_outlook_mail or self.settings.scan_outlook_calendar:
                try:
                    new += Outlook(self.settings, self.store, self.jev).scan(ctx)
                except NeedsLogin as e:
                    log.warning("%s", e)
                    problems.append("Outlook needs sign-in")
                except Exception:
                    log.exception("Outlook scan failed")
                    problems.append("Outlook scan failed (see log)")

        jev = "Read by Jev" if self.jev.online else "Keyword matching (no TypeSafe key)"
        updated = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.status = f"Updated {updated}. {jev}." + (f" {'; '.join(problems)}." if problems else "")
        self.problems = problems
        due_today = self._refresh_view()

        needs = [p for p in problems if "sign-in" in p]
        if needs and needs != self.last_sign_in_problems:  # tell once, not every scan
            self.notify("Choose 'Sign in to Moodle / Outlook…' from the tray menu.", "; ".join(needs))
        self.last_sign_in_problems = needs
        # Don't announce duplicates or keyword-hidden entries.
        new, _ = filters.split(new, self.settings.hidden_keywords,
                               pool=report.window(self.store, self.settings, datetime.now()))
        if new:
            soon = sorted(new, key=lambda i: i.due)[:3]
            lines = "\n".join(f"{i.title[:50]} ({i.due:%a %b %d})" for i in soon)
            self.notify(lines, f"{len(new)} new item{'s' if len(new) > 1 else ''}")
            if prefs.load(self.store).get("sound", True):
                squawk()
        self._daily_digest(due_today)

    def _refresh_view(self) -> int:
        """Rewrite the list page and the tray badge; returns the due-today count."""
        _, due_today = write_report(self.store, self.settings, self.status)
        self.icon.icon = make_icon(due_today)
        self.icon.title = f"Birdbrain: {due_today} due today" + (" (sign-in needed)" if self.problems else "")
        return due_today

    def _daily_digest(self, due_today: int):
        today = datetime.now().date().isoformat()
        if self.store.get_meta("digest_day") != today:
            self.store.set_meta("digest_day", today)
            self.notify(f"{due_today} item(s) due today. Click the tray icon for the full list.", "Today")

    def _set_status(self, s: str):
        self.status = s
        self.icon.title = f"Birdbrain: {s}"[:127]

    def loop(self):
        if self.store.get_meta("login_done") != "1" or not STATE_PATH.exists():
            self.notify("Sign in to Moodle and Outlook in the window that opens. "
                        "It closes by itself once you're signed in.")
            with self.lock:
                interactive_login(self.settings)
            self.store.set_meta("login_done", "1")
        while not self.stop.is_set():
            self.scanning = True
            since, self.mail_since = self.mail_since, None
            try:
                self.scan_inbox(since) if since else self.scan()
            except Exception:
                log.exception("Scan crashed")
                self._set_status("Last scan failed (see log)")
            finally:
                self.scanning = False
            if self.mail_since is None:   # nothing queued while we were busy
                self.wake.wait(self.settings.interval_minutes * 60)
                self.wake.clear()

    def run(self, show: bool = True) -> None:
        """The app window owns the main thread; the tray icon, scans and the list server run beside it."""
        self._start_server()
        self._listen_for_show()
        threading.Thread(target=self.loop, daemon=True, name="scans").start()
        threading.Thread(target=self.icon.run, kwargs={"setup": lambda icon: setattr(icon, "visible", True)},
                         daemon=True, name="tray").start()
        if self.server and appwindow.available():
            try:
                self.window = appwindow.AppWindow(self.server.url, icon_path=_window_icon())
                self.window.run(show=show)   # returns once Birdbrain quits
            except Exception:
                log.exception("The app window failed; the list opens in the browser instead")
            if self.stop.is_set():
                return
            self.window = None
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
    path = DATA_DIR / "birdbrain.ico"
    if not path.exists():
        make_icon(size=256).save(path, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return str(path)


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
    if url:
        s.moodle_url = url.strip().rstrip("/")
    if outlook:
        s.outlook_url = outlook.strip().rstrip("/")
    s.save()


def already_running() -> bool:
    """True if another copy of Birdbrain is open (two would fight over the browser profile)."""
    import ctypes
    global _instance_lock
    _instance_lock = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\BirdbrainTrayApp")
    return ctypes.windll.kernel32.GetLastError() == 183   # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import selftest
        out = Path(sys.argv[sys.argv.index("--selftest") + 1]) if len(sys.argv) > sys.argv.index("--selftest") + 1 \
            else Path.cwd() / "birdbrain-selftest.txt"
        sys.exit(selftest.run(out))
    if already_running():
        if not show_running_copy():   # an older copy without the signal
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
    first_run_setup()
    app = App()
    import browser
    browser.on_browser_install = lambda: app.notify(
        "Setting up Birdbrain's background browser. This one-time download takes a minute or two.")
    app.run(show="--background" not in sys.argv)
