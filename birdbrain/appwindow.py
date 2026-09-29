"""Birdbrain's own app window.

The list page opens in a native window (Microsoft Edge WebView2, through pywebview)
with Birdbrain's title, icon and taskbar button, instead of a browser tab. Closing
the window only hides it: Birdbrain keeps scanning from the tray, and a left-click
on the tray icon, or starting Birdbrain again, brings the window back. Quitting
(from the tray menu or Settings) closes it for good. Links to Moodle and Outlook
open in your usual browser.

The window has no Windows title bar. CustomFrame removes it the way Windows
Terminal does, keeping the resizable frame, rounded corners, shadow and snapping,
and the page draws its own see-through bar (report.py) that blends into the theme.
The page's bar calls back through Bridge: a press on the bar starts Windows' own
move loop (so dragging to a screen edge still snaps), the top edge resizes, and
the buttons minimise, maximise and close.

The window's event loop has to own the main thread, so main.py runs the tray icon
on another thread. If the window can't be made (no WebView2 runtime, say), main.py
falls back to opening the list in the default browser.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)
problem = ""   # why the window can't be made here, in plain words, once check() has failed


def unblock_own_files() -> int:
    """A zip downloaded from the internet marks every file in it as downloaded (the Mark of the Web), and .NET then
    refuses to load the window's libraries (Python.Runtime.dll), so the list would open in the browser instead. The
    student already chose to run Birdbrain, so take the mark off its own files, as Windows' "Unblock" would. Only the
    packaged app does this, and only in its own folder. Returns how many files it cleared."""
    if not getattr(sys, "frozen", False):
        return 0
    base = Path(sys.executable).parent
    marked = lambda p: os.path.exists(f"{p}:Zone.Identifier")
    if not (marked(sys.executable) or marked(base / "_internal" / "pythonnet" / "runtime" / "Python.Runtime.dll")):
        return 0
    cleared = 0
    for p in (Path(sys.executable), *base.rglob("*")):
        try:
            if p.is_file() and marked(p):
                os.remove(f"{p}:Zone.Identifier")
                cleared += 1
        except OSError:
            pass
    log.info("Cleared the downloaded-file mark from %d of Birdbrain's own files", cleared)
    return cleared

# --- Win32 --------------------------------------------------------------------------
_u32 = ctypes.WinDLL("user32")
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_u32.CallWindowProcW.restype = LRESULT
_u32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.SetWindowLongPtrW.restype = ctypes.c_void_p
_u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_u32.SendMessageW.restype = LRESULT
_u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.IsZoomed.argtypes = [wintypes.HWND]
_u32.GetDpiForWindow.argtypes = [wintypes.HWND]
_u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT]

WM_NCCALCSIZE, WM_NCLBUTTONDOWN = 0x0083, 0x00A1
WM_BEGIN_DRAG = 0x8000 + 0x2A              # our own: start a native move or resize from the UI thread
HIT = {"move": 2, "top": 12, "topleft": 13, "topright": 14}   # HTCAPTION, HTTOP, HTTOPLEFT, HTTOPRIGHT


def _own_window(title: str, timeout: float = 15) -> int | None:
    """This process's top-level window with this title, once Windows Forms has made it."""
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found: list[int] = []

    def check(hwnd, _):
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        text = ctypes.create_unicode_buffer(64)
        _u32.GetWindowTextW(hwnd, text, 64)
        if pid.value == os.getpid() and text.value == title:
            found.append(hwnd)
        return True
    callback = enum_proc(check)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _u32.EnumWindows(callback, 0)
        if found:
            return found[0]
        time.sleep(0.05)
    return None


class _NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class CustomFrame:
    """Removes the title bar but keeps everything else about a normal window."""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._proc = WNDPROC(self._wndproc)   # kept alive for as long as the window
        self._prev = _u32.SetWindowLongPtrW(hwnd, -4, ctypes.cast(self._proc, ctypes.c_void_p))   # GWLP_WNDPROC
        _u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)   # FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE

    def _frame_y(self) -> int:
        dpi = _u32.GetDpiForWindow(self.hwnd) or 96
        return _u32.GetSystemMetricsForDpi(33, dpi) + _u32.GetSystemMetricsForDpi(92, dpi)   # SM_CYFRAME + padding

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if msg == WM_NCCALCSIZE and wp:
                # Let Windows work out the frame, then give the title bar's strip back to the page.
                # A maximised window hangs its frame off the screen, so keep that much at the top.
                params = _NCCALCSIZE_PARAMS.from_address(lp)
                top = params.rgrc[0].top
                result = _u32.CallWindowProcW(self._prev, hwnd, msg, wp, lp)
                params.rgrc[0].top = top + (self._frame_y() if _u32.IsZoomed(hwnd) else 0)
                return result
            if msg == WM_BEGIN_DRAG:
                _u32.ReleaseCapture()
                return _u32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, wp, 0)
        except Exception:
            log.exception("window frame")
        return _u32.CallWindowProcW(self._prev, hwnd, msg, wp, lp)

    def begin(self, what: str) -> None:
        """Start moving ("move") or resizing ("top", "topleft", "topright") with the mouse that's down now."""
        _u32.PostMessageW(self.hwnd, WM_BEGIN_DRAG, HIT[what], 0)

    @property
    def maximized(self) -> bool:
        return bool(_u32.IsZoomed(self.hwnd))


class Bridge:
    """What the page's own title bar can ask for (window.pywebview.api.<name>)."""

    def __init__(self, owner: "AppWindow"):
        self._owner = owner

    def drag(self, what: str = "move") -> None:
        if self._owner.frame and what in HIT:
            self._owner.frame.begin(what)

    def minimize(self) -> None:
        self._owner.window.minimize()

    def toggle_maximize(self) -> None:
        frame = self._owner.frame
        if frame and frame.maximized:
            self._owner.window.restore()
        else:
            self._owner.window.maximize()

    def close(self) -> None:
        self._owner.window.hide()   # same as the close button of a normal window: keep running in the tray

    def is_maximized(self) -> bool:
        return bool(self._owner.frame and self._owner.frame.maximized)

    def framed(self) -> bool:
        """False if Windows' own title bar is still there (then the page drops its own)."""
        return self._owner.frame is not None


# --- the window -------------------------------------------------------------------------
def check() -> str:
    """Raises if the window can't be made here; otherwise says what it will use."""
    unblock_own_files()   # before .NET loads anything
    import webview   # noqa: F401  (the library)
    from webview.platforms import winforms   # loads the .NET bridge and Windows Forms
    if not winforms._is_chromium():
        raise RuntimeError("Microsoft Edge WebView2 Runtime is not installed")
    return "WebView2 runtime found"


def available() -> bool:
    global problem
    try:
        check()
        return True
    except Exception as e:
        log.exception("No app window available; the list will open in the browser")
        problem = ("Birdbrain's own window needs the Microsoft Edge WebView2 Runtime, which isn't installed. It's free "
                   "from Microsoft; until then your list opens in your browser." if "WebView2" in str(e) else
                   "Birdbrain's own window couldn't start, so your list opens in your browser. The log says why.")
        return False


class AppWindow:
    def __init__(self, url: str, icon_path: str | None = None):
        import webview
        self.icon_path = icon_path
        self.quitting = False
        self.minimized = False
        self.frame: CustomFrame | None = None
        self.ready = threading.Event()
        # "app=1" asks the list server for the page with Birdbrain's own title bar.
        self.window = webview.create_window("Birdbrain", url + "&app=1", width=1320, height=900, min_size=(420, 560),
                                            hidden=True, background_color="#20242C", text_select=True,
                                            easy_drag=False, js_api=Bridge(self))
        ev = self.window.events
        ev.closing += self._on_closing
        ev.minimized += lambda: setattr(self, "minimized", True)
        ev.restored += self._on_restored
        ev.maximized += self._on_maximized
        ev.loaded += self._tell_page

    def _on_closing(self) -> bool:
        if self.quitting:
            return True
        self.window.hide()   # keep running in the tray
        return False         # cancels the close

    def _on_restored(self) -> None:
        self.minimized = False
        self._tell_page()

    def _on_maximized(self) -> None:
        self.minimized = False
        self._tell_page()

    def _tell_page(self) -> None:
        """The page swaps its maximise/restore button and hides its resize edge when maximised."""
        maximized = "true" if self.frame and self.frame.maximized else "false"
        try:
            self.window.evaluate_js(f"window.birdbrainWindow && birdbrainWindow.maximized({maximized})")
        except Exception:
            pass

    def run(self, show: bool) -> None:
        """Run the window's event loop on this (the main) thread until quit()."""
        import webview

        def started():
            try:
                hwnd = _own_window("Birdbrain")
                if hwnd:
                    self.frame = CustomFrame(hwnd)
            except Exception:
                log.exception("Couldn't replace the title bar; keeping Windows' own")
            self.ready.set()
            if show:
                self.show()
        webview.start(started, gui="edgechromium", private_mode=True, icon=self.icon_path)

    def show(self) -> None:
        """Bring the window up (from any thread)."""
        if not self.ready.wait(20):
            return
        self.window.show()
        if self.minimized:
            self.window.restore()

    def quit(self) -> None:
        self.quitting = True
        if self.ready.is_set():
            self.window.destroy()
