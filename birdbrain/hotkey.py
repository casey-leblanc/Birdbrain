"""A system-wide shortcut for quick write: press it anywhere on the PC, even with Birdbrain's window closed.

Windows gives a shortcut to one program at a time. If another program already has the one asked for, Windows says
so, and Birdbrain passes that on in words with a few others to try.

A shortcut is written "ctrl+alt+space": one or more of ctrl, alt, shift and win, then one key (space, a letter, a
digit, or f1 to f12). Windows only for now.
"""
from __future__ import annotations

import logging
import sys
import threading

log = logging.getLogger(__name__)

DEFAULT = "ctrl+alt+space"
CHOICES = ("ctrl+alt+space", "ctrl+shift+space", "ctrl+alt+q", "alt+shift+q", "ctrl+alt+n")   # offered when one is taken
MODS = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
_NOREPEAT = 0x4000
_KEYS = {"space": 0x20, **{chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)},
         **{str(n): 0x30 + n for n in range(10)}, **{f"f{n}": 0x6F + n for n in range(1, 13)}}
_WM_HOTKEY, _WM_APP, _WM_QUIT = 0x0312, 0x8000, 0x0012
_TAKEN = 1409   # ERROR_HOTKEY_ALREADY_REGISTERED


def available() -> bool:
    return sys.platform == "win32"


def tidy(combo: str) -> str:
    """"Ctrl + Alt+SPACE" -> "ctrl+alt+space", modifiers first in a fixed order. ValueError says what's wrong."""
    parts = [p.strip().lower() for p in str(combo).replace(" ", "").split("+") if p.strip()]
    parts = ["ctrl" if p in ("control", "ctl") else "win" if p in ("meta", "cmd", "super") else p for p in parts]
    mods = [m for m in MODS if m in parts]
    keys = [p for p in parts if p not in MODS]
    if len(keys) != 1 or keys[0] not in _KEYS:
        raise ValueError("A shortcut needs one key: Space, a letter, a digit or F1 to F12.")
    if not mods or mods == ["shift"]:
        raise ValueError("A shortcut needs Ctrl, Alt or the Windows key, so it can't be typed by accident.")
    return "+".join([*mods, keys[0]])


def parse(combo: str) -> tuple[int, int]:
    """(modifier flags, virtual-key code) for Windows."""
    *mods, key = tidy(combo).split("+")
    flags = 0
    for m in mods:
        flags |= MODS[m]
    return flags, _KEYS[key]


def say(combo: str) -> str:
    """"ctrl+alt+space" -> "Ctrl+Alt+Space"."""
    return "+".join("Win" if p == "win" else p.upper() if p.startswith("f") and p[1:].isdigit() else p.capitalize()
                    for p in combo.split("+")) if combo else ""


def others(combo: str) -> list[str]:
    """Shortcuts to offer in place of one that's taken."""
    return [c for c in CHOICES if c != combo][:3]


class Hotkey:
    """One system-wide shortcut. `on_press` is called on its own thread each time it's pressed."""

    def __init__(self, on_press):
        self.on_press = on_press
        self.combo = ""       # the shortcut in force; "" when off, or when the one asked for couldn't be had
        self._want = ""
        self._answer = ""
        self._asked, self._ready = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._tid = 0

    def set(self, combo: str) -> str:
        """Use this shortcut ("" turns it off). Returns "" if that worked, else why not, in words."""
        if not available():
            return "" if not combo else "The system-wide shortcut works on Windows only for now."
        try:
            combo = tidy(combo) if combo else ""
        except ValueError as e:
            return str(e)
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey")
            self._thread.start()
        if not self._ready.wait(5):
            return "Windows didn't answer. Try again."
        import ctypes
        self._want = combo
        self._asked.clear()
        ctypes.WinDLL("user32").PostThreadMessageW(self._tid, _WM_APP, 0, 0)
        if not self._asked.wait(5):
            return "Windows didn't answer. Try again."
        return self._answer

    def stop(self) -> None:
        if self._thread is not None and self._ready.is_set():
            import ctypes
            ctypes.WinDLL("user32").PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)   # gives this thread a message queue
        self._tid = ctypes.WinDLL("kernel32").GetCurrentThreadId()
        self._ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY:
                threading.Thread(target=self._pressed, daemon=True, name="hotkey-press").start()
            elif msg.message == _WM_APP:
                had, self._answer = self.combo, ""
                if had:
                    user32.UnregisterHotKey(None, 1)
                    self.combo = ""
                if self._want:
                    flags, key = parse(self._want)
                    if user32.RegisterHotKey(None, 1, flags | _NOREPEAT, key):
                        self.combo = self._want
                        log.info("Quick write shortcut: %s", say(self.combo))
                    else:
                        error = ctypes.get_last_error()
                        self._answer = (f"Another program is already using {say(self._want)}." if error == _TAKEN else
                                        f"Windows wouldn't give Birdbrain {say(self._want)} (error {error}).")
                        log.info("Quick write shortcut not set: %s", self._answer)
                        if had and user32.RegisterHotKey(None, 1, parse(had)[0] | _NOREPEAT, parse(had)[1]):
                            self.combo = had   # the one that was working keeps working
                self._asked.set()
        if self.combo:
            user32.UnregisterHotKey(None, 1)

    def _pressed(self) -> None:
        try:
            self.on_press()
        except Exception:
            log.exception("The quick write shortcut's action failed")


class Shortcut:
    """The quick write shortcut as the app and Settings see it: the one in force, the one asked for, what went wrong,
    and what to offer instead. `keys` is a Hotkey (or a stand-in); `save` keeps the choice ("" for off)."""

    def __init__(self, keys, save=lambda combo: None):
        self.keys, self.save = keys, save
        self.want = self.problem = ""

    def start(self, combo: str) -> str:
        """Put the saved shortcut in force as the app starts. Returns what went wrong, if anything."""
        self.want = combo
        self.problem = self.keys.set(combo) if combo else ""
        return self.problem

    def view(self) -> dict:
        return {"available": available(), "combo": self.keys.combo, "label": say(self.keys.combo), "want": self.want,
                "problem": self.problem,
                "suggest": [{"combo": c, "label": say(c)} for c in others(self.want) if c != self.keys.combo]
                if self.problem else []}

    def use(self, body: dict) -> dict:
        """Settings asks for a shortcut ({"combo": "ctrl+alt+q"}), for none ({"combo": ""}), or for it back on
        ({"on": true}). Says how that went. A shortcut that can't be had leaves the one that was working in force."""
        combo = DEFAULT if body.get("on") else str(body.get("combo", ""))
        try:
            combo = tidy(combo) if combo else ""
        except ValueError as e:
            self.problem = str(e)
            return {"ok": True, "message": self.problem, **self.view()}
        self.want = combo
        self.problem = self.keys.set(combo)
        if self.problem:
            still = f" {say(self.keys.combo)} still works." if self.keys.combo else ""
            return {"ok": True, "message": f"{self.problem}{still} Try one of these, or press Change for another:", **self.view()}
        self.save(combo)
        message = (f"{say(combo)} is ready: press it anywhere on your PC and type." if combo else
                   "The shortcut is off. In Birdbrain's window, Space still opens quick write.")
        return {"ok": True, "message": message, **self.view()}
