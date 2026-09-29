"""Browsers used by the app.

- Sign-in window: your real Edge (persistent profile in PROFILE_DIR, so it
  remembers your Microsoft account). Only opened when you need to sign in.
- Background scans: Playwright's windowless Chromium "headless shell". Unlike
  headless Edge, it creates no Edge window, so nothing appears in Alt+Tab.

Cookies move between the two through STATE_PATH. Scans save it back when they
finish, so Moodle's session cookie (which a browser normally drops on exit)
survives from one scan to the next.

Scans send a normal desktop user-agent: LSU Moodle answers "403 Forbidden" to
browsers that announce themselves as HeadlessChrome.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import time
from typing import Callable
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

from config import PROFILE_DIR, STATE_PATH, Settings

log = logging.getLogger(__name__)

MS_LOGIN_HOSTS = ("login.microsoftonline.com", "login.live.com", "login.microsoft.com")

# "Log in with ..." buttons on a Moodle login page (OAuth2 such as LSU's
# "LSU Office 365 Authentication", SAML, Shibboleth).
IDP_BUTTONS = ('a[href*="/auth/oauth2/login.php"]', 'a.login-identityprovider-btn',
               'a[href*="/auth/saml2/"]', 'a[href*="/auth/shibboleth/"]')


class NeedsLogin(Exception):
    """Raised when a site wants a person to sign in (password, MFA, ...)."""


def on_ms_login(url: str) -> bool:
    return urlparse(url).netloc in MS_LOGIN_HOSTS


def _desktop_ua(version: str) -> str:
    major = version.split(".")[0]
    return (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")


def save_state(ctx: BrowserContext) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    ctx.storage_state(path=str(tmp))
    os.replace(tmp, STATE_PATH)


def save_state_quietly(ctx: BrowserContext) -> None:
    """save_state for the visible sign-in window. Playwright's storage_state() opens a
    temporary tab for every site visited but not open right now, to read its storage;
    in a visible window that makes Outlook and Microsoft tabs flash open and shut and
    steal focus from the sign-in form. This reads the cookies and the storage of the
    tabs already open instead, and keeps what the last save had for the other sites."""
    origins = {}
    with contextlib.suppress(Exception):
        origins = {o["origin"]: o for o in json.loads(STATE_PATH.read_text(encoding="utf-8")).get("origins", [])}
    for page in ctx.pages:
        with contextlib.suppress(Exception):   # a tab mid-navigation: its storage waits for the next save
            origin, items = page.evaluate("""() => [location.origin,
              Object.keys(localStorage).map(k => ({name: k, value: localStorage.getItem(k)}))]""")
            if origin.startswith("http"):
                origins[origin] = {"origin": origin, "localStorage": items}
    state = {"cookies": ctx.cookies(), "origins": list(origins.values())}
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


on_browser_install: Callable[[], None] | None = None   # set by the app to tell the user


def install_browser() -> None:
    """One-time download of the scanner's windowless browser into Playwright's
    shared cache (%LOCALAPPDATA%\\ms-playwright), using the driver bundled with
    Birdbrain. Runs without a console window."""
    from playwright._impl._driver import compute_driver_executable, get_driver_env
    log.info("Installing the scanner's browser (one-time download)")
    if on_browser_install:
        with contextlib.suppress(Exception):
            on_browser_install()
    node, cli = compute_driver_executable()
    done = subprocess.run([node, cli, "install", "chromium-headless-shell"], env=get_driver_env(),
                          capture_output=True, text=True, timeout=1800,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise RuntimeError(f"Browser install failed: {(done.stderr or done.stdout)[-500:]}")
    log.info("Scanner's browser installed")


def _launch_scanner(pw):
    try:
        return pw.chromium.launch(headless=True)                 # windowless headless shell
    except Exception as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        install_browser()                                        # first run of a packaged copy
        return pw.chromium.launch(headless=True)


@contextlib.contextmanager
def open_context(settings: Settings):
    """Browser context for a background scan."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved_at = STATE_PATH.stat().st_mtime if STATE_PATH.exists() else 0.0
    with sync_playwright() as pw:
        if settings.headless:
            browser = _launch_scanner(pw)
        else:                                                    # visible, for debugging
            browser = pw.chromium.launch(headless=False, channel=settings.browser_channel or None)
        ctx = browser.new_context(
            storage_state=str(STATE_PATH) if STATE_PATH.exists() else None,
            user_agent=_desktop_ua(browser.version),
            viewport={"width": 1400, "height": 1000},
        )
        ctx.set_default_timeout(30_000)
        try:
            yield ctx
        finally:
            # The sign-in window can be open while a scan runs, saving each sign-in as it happens. If it saved while this
            # scan ran, its session is the newer one, and this scan's copy would undo a sign-in.
            if (STATE_PATH.stat().st_mtime if STATE_PATH.exists() else 0.0) == saved_at:
                with contextlib.suppress(Exception):
                    save_state(ctx)
            else:
                log.info("Kept the session the sign-in window saved during this scan")
            with contextlib.suppress(Exception):
                browser.close()


def complete_sign_in(page: Page, done: Callable[[str], bool], timeout_s: float = 45) -> bool:
    """Let a single-sign-on redirect finish without typing anything.

    Clicks through Microsoft's "Stay signed in?" prompt and a one-account
    "Pick an account" list. Gives up (returns False) as soon as a password,
    code, or email address would have to be entered; that needs a person.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        if done(page.url):
            return True
        if on_ms_login(page.url):
            try:
                if page.locator('input[type="password"]:visible, input[name="otc"]:visible, '
                                'input[name="loginfmt"]:visible').count():
                    log.info("Microsoft sign-in needs a password/code/email; stopping")
                    return False
                if page.locator("#KmsiCheckboxField, #KmsiDescription").count():
                    page.locator("#idSIButton9").click()          # "Stay signed in?" -> Yes
                else:
                    tiles = page.locator('#tilesHolder [data-test-id]:not(#otherTile)')
                    if tiles.count() == 1:
                        tiles.first.click()                       # the one remembered account
                    elif tiles.count() > 1:
                        log.info("Several Microsoft accounts to pick from; stopping")
                        return False
            except Exception:
                pass  # page navigated mid-check; look again
        page.wait_for_timeout(1_000)
    return done(page.url)


def moodle_sso(page: Page, base: str) -> bool:
    """On Moodle's login page, press the single-sign-on button and follow it."""
    host = urlparse(base).netloc
    if "/login/" not in page.url:
        page.goto(base + "/login/index.php", wait_until="domcontentloaded")
    for sel in IDP_BUTTONS:
        btn = page.locator(sel)
        if btn.count():
            log.info("Pressing Moodle sign-in button %r", btn.first.inner_text().strip())
            btn.first.click()
            return complete_sign_in(page, lambda u: _moodle_home(u, host))
    log.info("No single-sign-on button on Moodle's login page")
    return False


def _moodle_home(url: str, host: str) -> bool:
    u = urlparse(url)
    return u.netloc == host and not re.match(r"/(login|auth)/", u.path)


def _go(page: Page, url: str) -> bool:
    """Open a site in the sign-in window. False if it can't be reached (a mistyped address, usually): its tab keeps the
    browser's own error page, and the window stops waiting on that site instead of failing."""
    try:
        page.goto(url, wait_until="domcontentloaded")
        return True
    except Exception as e:
        log.warning("The sign-in window couldn't open %s: %s", url, str(e).splitlines()[0][:200])
        return False


def interactive_login(settings: Settings,
                      on_change: Callable[[list[str], list[str]], None] | None = None) -> list[str]:
    """Visible Edge window for signing in. Presses Moodle's sign-in button for
    you, closes itself once every site is signed in (or when you close it),
    and hands the cookies to the background scanner. `on_change(signed,
    waiting)` hears which sites are signed in and which the window is still
    waiting on, whenever that changes (the session is saved first, so a scan
    can start on the signed-in ones at once). Returns the sites it couldn't
    even open ("Moodle", "Outlook", ...), so Birdbrain can say which address
    to check."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    missed: list[str] = []
    base = settings.moodle_url.rstrip("/")
    want_outlook = settings.scan_outlook_mail or settings.scan_outlook_calendar
    with sync_playwright() as pw:
        kwargs = dict(user_data_dir=str(PROFILE_DIR), headless=False, no_viewport=True)
        if settings.browser_channel:
            kwargs["channel"] = settings.browser_channel
        ctx = pw.chromium.launch_persistent_context(**kwargs)
        if STATE_PATH.exists():  # bring back the scanner's latest session cookies
            with contextlib.suppress(Exception):
                ctx.add_cookies(json.loads(STATE_PATH.read_text(encoding="utf-8"))["cookies"])

        moodle_page = outlook_page = None
        if base:
            moodle_page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if not _go(moodle_page, base + "/my/"):
                missed.append("Moodle")
                moodle_page = None
            elif "/login/" in moodle_page.url:
                with contextlib.suppress(Exception):
                    moodle_sso(moodle_page, base)
        if want_outlook:
            outlook_page = ctx.new_page()
            if not _go(outlook_page, settings.outlook_url.rstrip("/") + "/mail/"):
                missed.append("Outlook")
                outlook_page = None
            else:
                outlook_page.wait_for_timeout(1_500)
            if outlook_page and on_ms_login(outlook_page.url):
                with contextlib.suppress(Exception):
                    complete_sign_in(outlook_page, lambda u: not on_ms_login(u), timeout_s=20)

        # the other course sites the student uses, each in its own tab
        site_pages = []
        if settings.scan_gradescope:
            p = ctx.new_page()
            if _go(p, settings.gradescope_url.rstrip("/") + "/login"):
                site_pages.append(("Gradescope", p, _signed_in_gradescope))
            else:
                missed.append("Gradescope")
        connect = None
        if settings.scan_mcgraw and settings.mcgraw_via == "moodle" and base:
            # Connect through Moodle: the student's course, a note saying what to do, and a watch for Connect opening
            connect = ConnectWatch(ctx, base)
            p = ctx.new_page()
            p.add_init_script(_note_js(urlparse(base).netloc))
            if _go(p, settings.mcgraw_course or base + "/my/courses.php"):
                site_pages.append(("McGraw Hill Connect", p, lambda _p: connect.done()))
            elif "Moodle" not in missed:   # it's a Moodle page, so Moodle's address is the one to check
                missed.append("McGraw Hill Connect")
        elif settings.scan_mcgraw:
            p = ctx.new_page()
            if _go(p, settings.mcgraw_url.rstrip("/")):
                site_pages.append(("McGraw Hill Connect", p, _signed_in_mcgraw))
            else:
                missed.append("McGraw Hill Connect")

        host = urlparse(base).netloc
        # every site the window waits on: its name, its tab, and when it counts as signed in (a closed tab isn't waited on)
        watch = ([("Moodle", moodle_page, lambda p: _signed_in_moodle(p, host))] if moodle_page else []) \
            + ([("Outlook", outlook_page, _signed_in_outlook)] if outlook_page else []) + site_pages
        told = None
        while ctx.pages:
            open_ = [(name, p, ok) for name, p, ok in watch if not p.is_closed()]
            signed = [name for name, p, ok in open_ if ok(p)]
            waiting = [name for name, p, ok in open_ if name not in signed]
            with contextlib.suppress(Exception):
                save_state_quietly(ctx)
            if on_change and (signed, waiting) != told:
                told = (signed, waiting)
                with contextlib.suppress(Exception):
                    on_change(signed, waiting)
            if not waiting:
                log.info("Signed in to everything; closing the sign-in window")
                break
            if connect:
                connect.look(ctx)
            time.sleep(2)
        with contextlib.suppress(Exception):
            save_state_quietly(ctx)
        if connect and connect.link:
            connect.remember()
        with contextlib.suppress(Exception):
            ctx.close()
    return missed


# --- McGraw Hill Connect through Moodle ------------------------------------------------------------------------
# A Connect class (a "section") has its own page listing every assignment. Some courses link Moodle to that page; others
# link each Moodle activity to a single assignment. Either way Connect's addresses name the class, in the path
# (/section/123456789) or as sectionId=, so any of them leads to the class page.
SECTION_URL = "https://newconnect.mheducation.com/student/class/section/{}"
_SECTION_ID = re.compile(r"/class/section/(\d+)|/sections?/(\d{6,})|[?&]section_?id=(\d{6,})", re.I)


def section_page(url: str) -> str | None:
    """The class page for a Connect address that names a class, if it does."""
    if not urlparse(url).netloc.endswith("mheducation.com"):
        return None
    m = _SECTION_ID.search(url)
    return SECTION_URL.format(next(g for g in m.groups() if g)) if m else None


def _shape(url: str) -> str:
    """An address without its numbers or query, for the log: where Connect opened, without anything personal."""
    u = urlparse(url)
    return u.netloc + re.sub(r"\d+", "N", u.path)


class ConnectWatch:
    """Watches a sign-in window while the student clicks a McGraw Hill link in their Moodle course: which Moodle link
    it was (an external-tool activity, mod/lti), the course page it was on, and when Connect opened from it. Moodle
    hands the browser to McGraw Hill itself (an LTI launch), so Connect's own sign-in page is never needed."""

    def __init__(self, ctx: BrowserContext, moodle_base: str):
        self.base = moodle_base.rstrip("/")
        self.link = self.course = self.name = ""
        self.sections: list[str] = []   # Connect class pages named on the way in (each lists every assignment)
        self.opened_at = 0.0
        self.told = False
        ctx.on("request", self._request)

    def _request(self, req) -> None:
        url = req.url
        if url.startswith(self.base):
            if m := re.search(r"/mod/lti/(?:view|launch)\.php\?id=(\d+)", url):
                self.link = f"{self.base}/mod/lti/launch.php?id={m.group(1)}"
            elif m := re.search(r"/course/view\.php\?id=(\d+)", url):
                self.course = f"{self.base}/course/view.php?id={m.group(1)}"
        elif urlparse(url).netloc.endswith("mheducation.com") and not re.search(r"login|signin|sign-in", url, re.I):
            if req.is_navigation_request() and not self.opened_at:
                self.opened_at = time.time()
                log.info("McGraw Hill Connect opened from Moodle, on %s", _shape(url))
            # the class page itself, or a single assignment (or Connect's own requests) naming its class
            if (page := section_page(url)) and page not in self.sections:
                self.sections.append(page)
                log.info("Connect class found on the way in: %s", _shape(page))

    def look(self, ctx: BrowserContext) -> None:
        """The activity's name, from the Moodle tab it was opened on (Moodle titles pages "Course: Activity"); and once
        Connect is in, say so on the Moodle pages, since the window may still be waiting on another site."""
        for p in ctx.pages:
            with contextlib.suppress(Exception):
                if "/mod/lti/" in p.url and p.url.startswith(self.base):
                    self.name = re.sub(r"\s*\|.*$", "", p.title()).split(": ", 1)[-1].strip()[:120]
        if self.done() and not self.told:
            for p in ctx.pages:
                with contextlib.suppress(Exception):
                    if p.url.startswith(self.base):
                        p.evaluate("""() => { const d = document.getElementById('birdbrain-note');
                          if (d) d.textContent = 'Birdbrain: McGraw Hill Connect is signed in. This window closes by itself once every site is.'; }""")
            self.told = True

    def done(self) -> bool:
        return bool(self.opened_at) and time.time() - self.opened_at > 4   # a moment for Connect to set its sign-in

    def remember(self) -> None:
        s = Settings.load()
        s.mcgraw_launch, s.mcgraw_course = self.link, self.course or s.mcgraw_course
        s.mcgraw_launch_name = self.name or s.mcgraw_launch_name
        s.mcgraw_sections = (self.sections + [u for u in s.mcgraw_sections if u not in self.sections])[:6]
        s.save()
        log.info("McGraw Hill Connect is reached through Moodle link %s (%s)", self.link, s.mcgraw_launch_name or "unnamed")


def _note_js(moodle_host: str) -> str:
    """A note on the Moodle pages of the sign-in window saying what to click."""
    return """(() => { if (location.host !== %s) return;
  const show = () => { if (document.getElementById('birdbrain-note')) return;
    const d = document.createElement('div'); d.id = 'birdbrain-note'; d.setAttribute('role', 'status');
    d.textContent = 'Birdbrain: open the course that uses McGraw Hill Connect and click any McGraw Hill link in it once. ' +
      'If each link opens a single assignment, pick one you have already finished, never a timed quiz or exam. ' +
      'This window closes by itself when Connect opens.';
    d.style.cssText = 'position:fixed;z-index:2147483647;left:50%%;bottom:16px;transform:translateX(-50%%);max-width:min(640px,calc(100vw - 32px));' +
      'padding:12px 18px;border-radius:10px;background:#1C2230;color:#fff;font:600 15px/1.45 "Segoe UI",system-ui,sans-serif;' +
      'box-shadow:0 8px 24px -8px rgba(0,0,0,.45)';
    document.body.appendChild(d); };
  if (document.body) show(); else addEventListener('DOMContentLoaded', show); })()""" % json.dumps(moodle_host)


def relaunch_connect(ctx: BrowserContext, settings: Settings) -> bool:
    """Re-open the McGraw Hill link the student last clicked in Moodle, in the background, so Moodle signs this browser
    in to Connect again. Only when they turned this on in Settings. True once Moodle has handed over to McGraw Hill;
    whether that signed Connect in is for the caller to check, on Connect's own page."""
    if not (settings.mcgraw_via == "moodle" and settings.mcgraw_auto_renew and settings.mcgraw_launch):
        return False
    page = ctx.new_page()
    handed = []   # McGraw Hill pages the launch reached
    page.on("request", lambda r: handed.append(r.url) if r.is_navigation_request()
            and urlparse(r.url).netloc.endswith("mheducation.com") else None)
    try:
        # Moodle's launch page hands straight over to McGraw Hill (a form it submits as it loads), so don't wait for
        # it to finish loading: only for Moodle to answer, then for McGraw Hill's own page to settle
        with contextlib.suppress(Exception):
            page.goto(settings.mcgraw_launch, wait_until="commit")
        for _ in range(40):
            if handed or "/login" in page.url:
                break
            page.wait_for_timeout(500)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        log.info("Renewing McGraw Hill Connect through Moodle (%s): %s", settings.mcgraw_launch_name or settings.mcgraw_launch,
                 "handed over" if handed else f"stopped at {page.url.split('?')[0]}")
        return bool(handed)
    finally:
        page.close()


def _signed_in_moodle(page: Page, host: str) -> bool:
    try:
        return _moodle_home(page.url, host) and bool(
            page.evaluate("() => (window.M && M.cfg && M.cfg.sesskey) || ''"))
    except Exception:
        return False


def _signed_in_gradescope(page: Page) -> bool:
    """In once Gradescope shows your courses: at /account or a course, or at its main address, which becomes your
    course list ("Your Courses") after signing in."""
    try:
        path = urlparse(page.url).path
        if re.match(r"/(account|courses)\b", path):
            return True
        return path in ("", "/") and page.locator("a.courseBox, .courseList, a[href='/logout']").count() > 0
    except Exception:
        return False


def _signed_in_mcgraw(page: Page) -> bool:
    """Connect: off its sign-in pages, with no password box, on a page that offers to sign out or shows the To Do list."""
    try:
        if re.search(r"login|signin|sign-in", page.url, re.I) or page.locator("input[type=password]").count():
            return False
        return bool(page.get_by_text(re.compile(r"(sign|log)\s*out|\bto\s*do\b", re.I)).count())
    except Exception:
        return False


def _signed_in_outlook(page: Page) -> bool:
    try:
        return not on_ms_login(page.url) and page.locator('[role="listbox"] [role="option"]').count() > 0
    except Exception:
        return False
