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
            with contextlib.suppress(Exception):
                save_state(ctx)
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


def interactive_login(settings: Settings) -> None:
    """Visible Edge window for signing in. Presses Moodle's sign-in button for
    you, closes itself once both sites are signed in (or when you close it),
    and hands the cookies to the background scanner."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
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
            moodle_page.goto(base + "/my/", wait_until="domcontentloaded")
            if "/login/" in moodle_page.url:
                with contextlib.suppress(Exception):
                    moodle_sso(moodle_page, base)
        if want_outlook:
            outlook_page = ctx.new_page()
            outlook_page.goto(settings.outlook_url.rstrip("/") + "/mail/", wait_until="domcontentloaded")
            outlook_page.wait_for_timeout(1_500)
            if on_ms_login(outlook_page.url):
                with contextlib.suppress(Exception):
                    complete_sign_in(outlook_page, lambda u: not on_ms_login(u), timeout_s=20)

        host = urlparse(base).netloc
        while ctx.pages:
            with contextlib.suppress(Exception):
                save_state_quietly(ctx)
            moodle_ok = moodle_page is None or moodle_page.is_closed() or _signed_in_moodle(moodle_page, host)
            outlook_ok = outlook_page is None or outlook_page.is_closed() or _signed_in_outlook(outlook_page)
            if moodle_ok and outlook_ok:
                log.info("Signed in to everything; closing the sign-in window")
                break
            time.sleep(2)
        with contextlib.suppress(Exception):
            save_state_quietly(ctx)
        with contextlib.suppress(Exception):
            ctx.close()


def _signed_in_moodle(page: Page, host: str) -> bool:
    try:
        return _moodle_home(page.url, host) and bool(
            page.evaluate("() => (window.M && M.cfg && M.cfg.sesskey) || ''"))
    except Exception:
        return False


def _signed_in_outlook(page: Page) -> bool:
    try:
        return not on_ms_login(page.url) and page.locator('[role="listbox"] [role="option"]').count() > 0
    except Exception:
        return False
