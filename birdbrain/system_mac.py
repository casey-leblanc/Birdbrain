"""The Mac half of system.py: everything Birdbrain asks of the computer it runs on, as macOS does it.

Nothing here is imported at the top that only a Mac has, and what talks to the Mac goes through its own command-line
tools (security, caffeinate, afplay, osascript, open, ditto), so the pure parts (paths, the LaunchAgent, the update
script, what is said to those tools) can be tested anywhere.

Two things the Mac doesn't have yet, and says so here rather than half-working: a shortcut that works anywhere on
the computer (HOTKEY), and going to a card by clicking its notification (NOTIFY_CLICKS).
"""
from __future__ import annotations

import contextlib
import logging
import os
import platform
import plistlib
import shlex
import subprocess
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)

NAME = "mac"
MOD = "Cmd"
PROGRAM = "Birdbrain.app"
TRAY = "menu bar"
HOTKEY = False
NOTIFY_CLICKS = False
ASSET = f"-mac-{'arm64' if platform.machine() == 'arm64' else 'x64'}.zip"
SIGNIN_BROWSER = "Chrome"
BUNDLE_ID = "io.github.casey-leblanc.birdbrain"
UNPACKED = "Birdbrain.app"
_locks: dict[str, tuple[int, bool]] = {}


# --- where things are kept ----------------------------------------------------------------------------------------
def data_dir() -> Path:
    """~/Library/Application Support/Birdbrain (APPDATA, if set, is for the tests and the self-test)."""
    if os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Birdbrain"
    return Path.home() / "Library" / "Application Support" / "Birdbrain"


def update_dir() -> Path:
    return Path.home() / "Library" / "Caches" / "Birdbrain-update"


def browsers_dir() -> Path:
    return Path.home() / "Library" / "Caches" / "ms-playwright"


def app_root(program: str | None = None) -> Path:
    """Birdbrain.app, from the program inside it (…/Birdbrain.app/Contents/MacOS/Birdbrain): what an update replaces."""
    return Path(program or sys.executable).resolve().parents[2]


def program_in(app: Path) -> Path:
    return app / "Contents" / "MacOS" / "Birdbrain"


# --- one running copy: a lock on a file, and a socket beside it to ask for the window ---------------------------------
def another_copy_holds(name: str = "birdbrain") -> bool:
    """True if another copy of Birdbrain holds the lock. Asked again, the answer is the first one."""
    if name not in _locks:
        import fcntl
        folder = data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        fd = os.open(folder / f"{name}.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _locks[name] = (fd, False)
        except OSError:
            os.close(fd)
            _locks[name] = (-1, True)
    return _locks[name][1]


def _show_socket() -> Path:
    return data_dir() / "show.sock"


def listen_for_show(on_show, stop: threading.Event) -> None:
    """Starting Birdbrain while it's already running brings the window up: the second copy says so on this socket."""
    import socket
    path = _show_socket()
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(4)
    server.settimeout(1)

    def wait():
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                continue
            with conn:
                on_show()
        server.close()
    threading.Thread(target=wait, daemon=True, name="show-signal").start()


def show_running_copy() -> bool:
    """Ask the Birdbrain that's already running to show its window. False if it can't be reached."""
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect(str(_show_socket()))
            s.sendall(b"show")
        return True
    except OSError:
        return False


# --- the credential store: your login keychain ----------------------------------------------------------------------
def secrets_available() -> bool:
    return sys.platform == "darwin"


def _security(*args: str) -> tuple[int, str]:
    done = subprocess.run(["/usr/bin/security", *args], capture_output=True, text=True, timeout=20)
    return done.returncode, done.stdout.strip()


def secret_get(name: str, prefix: str) -> str | None:
    """The stored value, "" if there's none, or None if the keychain couldn't be read."""
    try:
        code, out = _security("find-generic-password", "-s", prefix.rstrip("/"), "-a", name, "-w")
        return out if code == 0 else "" if code == 44 else None   # 44: no such item
    except Exception:
        log.exception("Couldn't read %s from the keychain", name)
        return None


def secret_put(name: str, value: str, prefix: str) -> bool:
    try:
        if not value:
            return _security("delete-generic-password", "-s", prefix.rstrip("/"), "-a", name)[0] in (0, 44)
        return _security("add-generic-password", "-U", "-s", prefix.rstrip("/"), "-a", name, "-w", value,
                         "-j", "Kept by Birdbrain")[0] == 0
    except Exception:
        log.exception("Couldn't write %s to the keychain", name)
        return False


# --- start when you log in: a LaunchAgent of your own ------------------------------------------------------------------
def autostart_available() -> bool:
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def agent_path(name: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.{name.lower()}.plist"


def launch_agent(name: str, command: str) -> bytes:
    """The LaunchAgent that runs `command` (a program and its arguments) each time you log in."""
    return plistlib.dumps({"Label": f"{BUNDLE_ID}.{name.lower()}", "ProgramArguments": shlex.split(command),
                           "RunAtLoad": True, "ProcessType": "Interactive"})


def autostart_read(name: str) -> str | None:
    """The command registered under this name, or None."""
    try:
        args = plistlib.loads(agent_path(name).read_bytes()).get("ProgramArguments") or []
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None
    return " ".join(f'"{a}"' if n == 0 else a for n, a in enumerate(args)) if args else None


def autostart_write(name: str, command: str | None) -> None:
    path = agent_path(name)
    if command is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(launch_agent(name, command))


# --- staying awake, sounds, files, notifications ----------------------------------------------------------------------
@contextlib.contextmanager
def keep_awake():
    """Keep the Mac from going to sleep until the block ends (the display can still turn off)."""
    holder = None
    try:
        holder = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
    except OSError:
        log.exception("Couldn't ask the Mac to stay awake")
    try:
        yield
    finally:
        if holder is not None:
            holder.terminate()


def on_main(fn) -> None:
    """Do something that touches the menu bar icon: on a Mac that has to happen on the main thread."""
    try:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(fn)
    except Exception:
        log.exception("Couldn't reach the Mac's main thread")


def play(sound: Path) -> None:
    subprocess.Popen(["/usr/bin/afplay", str(sound)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_file(path: Path) -> None:
    subprocess.Popen(["/usr/bin/open", str(path)])


def reveal(path: Path) -> None:
    """Show a file in its folder, selected."""
    subprocess.Popen(["/usr/bin/open", "-R", str(path)])


def notify_script(title: str, text: str) -> str:
    """What osascript is asked to do. The words are quoted so that nothing in a card's title can be run."""
    quote = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'
    return f"display notification {quote(text)} with title {quote(title)}"


def notify(icon, title: str, text: str) -> None:
    """A notification in the corner of the screen. (macOS shows it as coming from its own script runner.)"""
    subprocess.run(["/usr/bin/osascript", "-e", notify_script(title, text)], capture_output=True, timeout=15, check=True)


def hear_clicks(icon, on_click) -> bool:
    return False   # not on the Mac yet: NOTIFY_CLICKS


# --- signing in, and updating ------------------------------------------------------------------------------------------
BROWSERS = (("chrome", "Google Chrome.app"), ("msedge", "Microsoft Edge.app"))


def signin_channel(saved: str, exists=lambda p: p.exists()) -> str | None:
    """The browser the sign-in window uses: Chrome if it's installed, else Edge if that is, else the Chromium that
    Birdbrain downloads for scanning (None). A Mac has no Edge by default, so the saved "msedge" isn't taken as read."""
    for channel, app in BROWSERS:
        if any(exists(folder / app) for folder in (Path("/Applications"), Path.home() / "Applications")):
            return channel
    return None


def unpack(zip_path: Path, into: Path) -> None:
    """ditto keeps what a Mac app is made of (links, and which files may be run); a plain unzip doesn't."""
    into.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(zip_path), str(into)], check=True, timeout=600)


def update_blocked(app: Path) -> str:
    """Why this copy can't update itself where it is; "" if it can."""
    if "/AppTranslocation/" in str(app) or str(app).startswith("/Volumes/"):
        return "Move Birdbrain into your Applications folder and open it from there. Then it can update itself."
    if not os.access(app.parent, os.W_OK):
        return (f"Birdbrain can't replace itself in {app.parent}. Move it into your Applications folder and update "
                "again.")
    return ""


def swap_script(app: Path, new: Path, backup: Path, pid: int, tag: str, args: list[str], folder: Path | None = None,
                ditto: str = "/usr/bin/ditto", opener: str = "/usr/bin/open -n") -> str:
    """update.sh: wait for process `pid` to end (up to two minutes), stop anything still running from inside the
    app (a scan's browser, say), move the app aside, move the new one into its place, and open it. If the move
    fails, put the old one back and open that. Each step is logged, and result.json says how it went. The unpacked
    update (`new`'s folder) is removed at the end. (`ditto` and `opener` are the Mac's own tools; the tests, which
    don't run on a Mac, put ordinary ones in their place.)"""
    q = shlex.quote
    here = folder or update_dir()
    run_args = (" --args " + " ".join(q(a) for a in args)) if args else ""
    return f"""#!/bin/sh
LOG={q(str(here / "update.log"))}
RESULT={q(str(here / "result.json"))}
APP={q(str(app))}
NEW={q(str(new))}
BACKUP={q(str(backup))}
echo "$(date) update to {tag}: waiting for Birdbrain to close" > "$LOG"
n=0
while kill -0 {pid} 2>/dev/null; do
  n=$((n+1))
  if [ "$n" -ge 120 ]; then
    echo "$(date) Birdbrain did not close; nothing was changed" >> "$LOG"
    echo '{{"ok": false, "tag": "{tag}", "why": "Birdbrain didn'"'"'t close"}}' > "$RESULT"
    exit 0
  fi
  sleep 1
done
pkill -f "$APP/Contents/" >/dev/null 2>&1
echo "$(date) keeping the version in use" >> "$LOG"
rm -rf "$BACKUP"
if ! mv "$APP" "$BACKUP" >> "$LOG" 2>&1; then
  echo '{{"ok": false, "tag": "{tag}", "why": "the new version couldn'"'"'t be copied in"}}' > "$RESULT"
else
  echo "$(date) putting the new version in its place" >> "$LOG"
  if {ditto} "$NEW" "$APP" >> "$LOG" 2>&1; then
    /usr/bin/xattr -dr com.apple.quarantine "$APP" >/dev/null 2>&1
    echo "$(date) updated to {tag}" >> "$LOG"
    echo '{{"ok": true, "tag": "{tag}"}}' > "$RESULT"
  else
    echo "$(date) that failed; putting the previous version back" >> "$LOG"
    rm -rf "$APP"
    mv "$BACKUP" "$APP" >> "$LOG" 2>&1
    echo '{{"ok": false, "tag": "{tag}", "why": "the new version couldn'"'"'t be copied in"}}' > "$RESULT"
  fi
fi
{opener} "$APP"{run_args} >> "$LOG" 2>&1
rm -rf {q(str(new.parent))}
"""


def run_swap(folder: Path, text: str) -> Path:
    """Write the update script and start it so that it outlives this process."""
    script = folder / "update.sh"
    script.write_text(text, encoding="utf-8")
    script.chmod(0o700)
    subprocess.Popen(["/bin/sh", str(script)], cwd=str(folder), start_new_session=True, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return script
