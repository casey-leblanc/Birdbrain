"""The Windows half of system.py: everything Birdbrain asks of the computer it runs on, as Windows does it.

Nothing here is imported at the top that only Windows has, so the pure parts (paths, commands, the update script)
can be tested anywhere.
"""
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)

NAME = "windows"
MOD = "Ctrl"                      # the key shortcuts are said with
PROGRAM = "Birdbrain.exe"         # what a student starts
TRAY = "system tray"
HOTKEY = True                     # a shortcut that works anywhere on the computer (hotkey.py)
NOTIFY_CLICKS = True              # a click on a notification can be heard
ASSET = "-windows.zip"            # the end of this system's file in a release
SIGNIN_BROWSER = "Microsoft Edge"
MUTEX = "Local\\BirdbrainTrayApp"
SHOW_EVENT = "Local\\BirdbrainShowWindow"   # a second launch sets this to bring the window up
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_GENERIC, _LOCAL_MACHINE, _NOT_FOUND = 1, 2, 1168
_held: dict[str, tuple[int, bool]] = {}
_cred = None


# --- where things are kept ----------------------------------------------------------------------------------------
def data_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "Birdbrain"


def update_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Birdbrain-update"


def browsers_dir() -> Path:
    """Playwright's usual shared folder for the scanner's browser."""
    return Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "ms-playwright"


def app_root() -> Path:
    """The folder a packaged Birdbrain lives in: what an update replaces."""
    return Path(sys.executable).resolve().parent


def program_in(app: Path) -> Path:
    return app / PROGRAM


UNPACKED = "Birdbrain"            # what a release zip unpacks to


# --- one running copy -----------------------------------------------------------------------------------------------
def another_copy_holds(name: str = MUTEX) -> bool:
    """True if another copy of Birdbrain holds the lock. Asked again, the answer is the first one."""
    if name not in _held and sys.platform != "win32":
        _held[name] = (0, False)
    if name not in _held:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel.CreateMutexW(None, False, name)
        _held[name] = (handle, ctypes.get_last_error() == 183)   # ERROR_ALREADY_EXISTS
    return _held[name][1]


def listen_for_show(on_show, stop: threading.Event) -> None:
    """Starting Birdbrain while it's already running (a pinned taskbar icon, say) brings the window up."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32")
    k.CreateEventW.restype = wintypes.HANDLE
    k.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = k.CreateEventW(None, False, False, SHOW_EVENT)

    def wait():
        while handle and not stop.is_set():
            if k.WaitForSingleObject(handle, 1000) == 0:   # WAIT_OBJECT_0: signalled
                on_show()
    threading.Thread(target=wait, daemon=True, name="show-signal").start()


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


# --- the credential store: Windows Credential Manager ----------------------------------------------------------------
def secrets_available() -> bool:
    return sys.platform == "win32"


def _credentials():
    global _cred
    if _cred is None:
        import ctypes
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                        ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

        lib = ctypes.WinDLL("advapi32", use_last_error=True)
        lib.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        lib.CredWriteW.restype = wintypes.BOOL
        lib.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(ctypes.POINTER(Credential))]
        lib.CredReadW.restype = wintypes.BOOL
        lib.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        lib.CredDeleteW.restype = wintypes.BOOL
        lib.CredFree.argtypes = [ctypes.c_void_p]
        lib.CredFree.restype = None
        _cred = (ctypes, lib, Credential)
    return _cred


def secret_get(name: str, prefix: str) -> str | None:
    """The stored value, "" if there's none, or None if Credential Manager couldn't be read."""
    try:
        ctypes, lib, Credential = _credentials()
        p = ctypes.POINTER(Credential)()
        if not lib.CredReadW(prefix + name, _GENERIC, 0, ctypes.byref(p)):
            return "" if ctypes.get_last_error() == _NOT_FOUND else None
        try:
            c = p.contents
            return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-8")
        finally:
            lib.CredFree(p)
    except Exception:
        log.exception("Couldn't read %s from Credential Manager", name)
        return None


def secret_put(name: str, value: str, prefix: str) -> bool:
    """Store the value (or remove it, for ""). False if it didn't take."""
    try:
        ctypes, lib, Credential = _credentials()
        if not value:
            return bool(lib.CredDeleteW(prefix + name, _GENERIC, 0) or ctypes.get_last_error() == _NOT_FOUND)
        blob = value.encode("utf-8")
        buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = Credential(Type=_GENERIC, TargetName=prefix + name, Comment="Kept by Birdbrain",
                          CredentialBlobSize=len(blob), CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                          Persist=_LOCAL_MACHINE, UserName="Birdbrain")
        if not lib.CredWriteW(ctypes.byref(cred), 0):
            log.warning("Credential Manager wouldn't take %s (error %s)", name, ctypes.get_last_error())
            return False
        return True
    except Exception:
        log.exception("Couldn't write %s to Credential Manager", name)
        return False


# --- start when you sign in: one value under your own Run key --------------------------------------------------------
def autostart_available() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def autostart_read(name: str) -> str | None:
    """The command registered under this name, or None."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return str(winreg.QueryValueEx(key, name)[0])
    except FileNotFoundError:
        return None


def autostart_write(name: str, command: str | None) -> None:
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if command is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)


# --- staying awake, sounds, files, notifications ----------------------------------------------------------------------
@contextlib.contextmanager
def keep_awake():
    """Keep Windows from going to sleep until the block ends (the display can still turn off)."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    kernel = None
    try:
        if sys.platform != "win32":
            raise OSError("not Windows")
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        if sys.platform == "win32":
            log.exception("Couldn't ask Windows to stay awake")
        kernel = None
    try:
        yield
    finally:
        if kernel is not None:
            kernel.SetThreadExecutionState(ES_CONTINUOUS)


def on_main(fn) -> None:
    """Do something that touches the tray icon. On Windows any thread may."""
    fn()


def play(sound: Path) -> None:
    import winsound
    winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


def open_file(path: Path) -> None:
    os.startfile(path)   # noqa: S606 (the student's own log or settings file)


def reveal(path: Path) -> None:
    """Show a file in its folder, selected."""
    subprocess.Popen(["explorer", "/select,", str(path)])


def notify(icon, title: str, text: str) -> None:
    """A notification by the clock, from the tray icon."""
    icon.notify(text, title)


BALLOON_CLICK = 0x0405   # NIN_BALLOONUSERCLICK, sent to the tray icon when its notification is clicked


def hear_clicks(icon, on_click) -> bool:
    """Have `on_click()` called when a notification from this tray icon is clicked. pystray shows the notification
    but doesn't report the click, so the icon's own message handler is wrapped. Returns whether it could be."""
    handlers, own = getattr(icon, "_message_handlers", None), getattr(icon, "_on_notify", None)
    if not isinstance(handlers, dict) or own is None:
        return False
    for message, handler in list(handlers.items()):
        if handler == own:
            def heard(wparam, lparam, _handler=handler):
                if lparam & 0xFFFF == BALLOON_CLICK:
                    threading.Thread(target=on_click, daemon=True, name="notice-click").start()
                    return 0
                return _handler(wparam, lparam)
            handlers[message] = heard
            return True
    return False


# --- signing in, and updating ------------------------------------------------------------------------------------------
def signin_channel(saved: str) -> str | None:
    """The browser the sign-in window uses: the one in the settings (Edge, which every Windows PC has)."""
    return saved or None


def unpack(zip_path: Path, into: Path) -> None:
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(into)


def update_blocked(app: Path) -> str:
    """Why this copy can't update itself where it is; "" if it can."""
    if not os.access(app, os.W_OK):
        return (f"Birdbrain can't write to its own folder ({app}). Move it somewhere you can, such as "
                "%LOCALAPPDATA%\\Programs, and update again.")
    return ""


def swap_script(app: Path, new: Path, backup: Path, pid: int, tag: str, args: list[str], exe: str = PROGRAM,
                image: str = PROGRAM, folder: Path | None = None) -> str:
    """update.cmd: wait for process `pid` to end (up to two minutes), stop anything still running from the app's
    folder (a scan's browser, say), keep a copy of the app as it is, copy the new one over it, and start it. If the
    copy fails, put the old one back and start that. Each step is logged, and result.json says how it went.
    `image` is the name the waited-for process runs under and `exe` the file to start afterwards (both Birdbrain.exe;
    the tests use others). The unpacked update (`new`'s folder) is removed at the end."""
    q = lambda p: str(p).replace("%", "%%")
    ps = str(app).replace("'", "''")
    robo = "/R:5 /W:1 /NFL /NDL /NJH /NJS /NP"
    every = "/IS /IT"   # copy every file, even one whose size and time match what's there (robocopy would skip it)
    start_args = " ".join(args)
    return f"""@echo off
chcp 65001 >nul
setlocal
set "LOG=%~dp0update.log"
set "RESULT=%~dp0result.json"
set /a N=0
echo %date% %time% update to {tag}: waiting for Birdbrain to close > "%LOG%"
:wait
tasklist /FI "PID eq {pid}" /FI "IMAGENAME eq {image}" /NH 2>nul | find "{pid}" >nul
if errorlevel 1 goto closed
set /a N+=1
if %N% GEQ 120 goto stuck
ping -n 2 127.0.0.1 >nul
goto wait
:stuck
echo %date% %time% Birdbrain did not close; nothing was changed >> "%LOG%"
echo {{"ok": false, "tag": "{tag}", "why": "Birdbrain didn't close"}} > "%RESULT%"
goto :eof
:closed
powershell -NoProfile -Command "Get-Process | Where-Object {{ $_.Path -like '{ps}\\*' }} | Stop-Process -Force" >nul 2>&1
echo %date% %time% keeping a copy of the version in use >> "%LOG%"
robocopy "{q(app)}" "{q(backup)}" /MIR {every} {robo} >> "%LOG%" 2>&1
if errorlevel 8 goto failed_before
echo %date% %time% copying the new version >> "%LOG%"
robocopy "{q(new)}\\_internal" "{q(app)}\\_internal" /MIR {every} {robo} >> "%LOG%" 2>&1
if errorlevel 8 goto restore
robocopy "{q(new)}" "{q(app)}" /E /XD _internal {every} {robo} >> "%LOG%" 2>&1
if errorlevel 8 goto restore
echo %date% %time% updated to {tag} >> "%LOG%"
echo {{"ok": true, "tag": "{tag}"}} > "%RESULT%"
goto start
:restore
echo %date% %time% the copy failed; putting the previous version back >> "%LOG%"
robocopy "{q(backup)}" "{q(app)}" /MIR {every} {robo} >> "%LOG%" 2>&1
:failed_before
echo {{"ok": false, "tag": "{tag}", "why": "the new version couldn't be copied in"}} > "%RESULT%"
:start
start "" "{q(app)}\\{exe}" {start_args}
rmdir /s /q "{q(new.parent)}" >nul 2>&1
"""


def run_swap(folder: Path, text: str) -> Path:
    """Write the update script and start it so that it outlives this process."""
    script = folder / "update.cmd"
    script.write_text(text, encoding="utf-8", newline="\r\n")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:   # outside any job object this process is in, where that's allowed
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(folder), close_fds=True, creationflags=flags | 0x01000000)
    except OSError:
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(folder), close_fds=True, creationflags=flags)
    return script
