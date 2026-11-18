"""Report a problem: a small zip a student can send to whoever is helping them. Nothing is uploaded, ever.

What goes in, each as plain text you can read first (the window shows every line before anything is saved):

- about.txt: the version and build, the system, how many cards there are (numbers only), and the last status line;
- settings.txt: the settings file, with every address and anything personal blanked;
- log.txt: the end of the log;
- what-happened.txt: your own words, if you wrote any.

Before any of it is shown or saved it is scrubbed: email addresses, web addresses, tokens and long keys, your
computer's user name, and every course name, teacher's name and card title Birdbrain knows of are replaced by a
word in square brackets ([email], [address], [token], [you], [course], [title], [name]). An @name goes too. Course codes like
"CHEM 1212" go too. A scrub by rules can miss something written in an unusual way, which is why you are shown the
whole thing and asked to look before sending.

The zip is saved to your Downloads folder (or Birdbrain's own folder, if there isn't one).
"""
from __future__ import annotations

import getpass
import json
import platform
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import buildinfo
from config import CONFIG_PATH, DATA_DIR, LOG_PATH
from store import COURSE_CODE, Store

LOG_TAIL = 400          # lines of the log that go in
MAX_NOTE = 2000
# Settings that say where the student studies or what they hide; their values never go in.
BLANKED = ("moodle_url", "outlook_url", "gradescope_url", "mcgraw_url", "mcgraw_launch", "mcgraw_launch_name",
           "mcgraw_course", "mcgraw_sections", "hidden_keywords", "telegram_bot", "telegram_chat", "extra")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"\b(?:https?|file)://[^\s\"'<>)\]]+", re.I)
_HOST = re.compile(r"\b(?:[\w-]+\.)+(?:edu|com|org|net|gov|io|ca|uk|au|us|live|microsoft|cloud)\b(?:/[^\s\"'<>)\]]*)?", re.I)
_BOT_TOKEN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}")
_LONG_KEY = re.compile(r"(?<![\w/\\.-])(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{24,}(?![\w-])")
_HANDLE = re.compile(r"(?<![\w.])@[A-Za-z]\w{4,}")                   # a bot's or a person's @name
_TEACHER = re.compile(r"\bfor (?:[A-Z]\. ?)+[A-Z][\w'-]+")           # Moodle's "… for A. Teacher"


def known(store: Store | None) -> dict[str, str]:
    """Every personal string Birdbrain knows of, with what replaces it: titles, course names, notes."""
    out: dict[str, str] = {}
    if store is None:
        return out
    with store._lock:
        rows = store._db.execute("SELECT title, course, detail FROM items").fetchall()
    for title, course, detail in rows:
        for text, word in ((course, "[course]"), (title, "[title]"), (detail, "[note]")):
            text = " ".join((text or "").split())
            if len(text) >= 4:
                out[text] = word
    return out


def scrub(text: str, names: dict[str, str] | None = None) -> str:
    """Take out everything that says who the student is or where they study. `names` are known strings to replace
    (see known()); the rest goes by shape."""
    user, home = getpass.getuser(), str(Path.home())
    text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    for found, word in sorted((names or {}).items(), key=lambda kv: -len(kv[0])):     # longest first
        text = re.sub(re.escape(found), word, text, flags=re.I)
    text = _EMAIL.sub("[email]", text)
    text = _URL.sub("[address]", text)
    text = _BOT_TOKEN.sub("[token]", text)
    text = _HOST.sub("[address]", text)
    text = _LONG_KEY.sub("[token]", text)
    text = _HANDLE.sub("@[name]", text)
    text = _TEACHER.sub("for [name]", text)
    text = COURSE_CODE.sub("[course]", text)
    if len(user) >= 3:
        text = re.sub(rf"(?<![\w]){re.escape(user)}(?![\w])", "[you]", text, flags=re.I)
    return text


def settings_text(path: Path = CONFIG_PATH) -> str:
    """The settings file with the values that could say who or where blanked, and the rest as they are."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "(no settings file, or it couldn't be read)"
    for key in list(data):
        if key in BLANKED or "token" in key or "secret" in key or "key" in key or "password" in key:
            value = data[key]
            data[key] = "[removed]" if value not in ("", [], {}, None) else value
    return json.dumps(data, indent=2)


def about_text(store: Store | None, status: str = "") -> str:
    b = buildinfo.current()
    lines = [f"Birdbrain {buildinfo.name()}",
             f"Build: {b.get('tag') or 'not a packaged build'}",
             f"System: {platform.system()} {platform.release()} ({platform.machine()})",
             f"Python {sys.version.split()[0]}, {'packaged' if getattr(sys, 'frozen', False) else 'from source'}",
             f"Made: {datetime.now():%Y-%m-%d %H:%M}"]
    if store is not None:
        with store._lock:
            rows = store._db.execute("SELECT source, kind, COUNT(*), SUM(done_at IS NOT NULL) FROM items GROUP BY source, kind").fetchall()
        lines.append("Cards (how many, not what): " + (", ".join(f"{n} {source} {kind} ({done or 0} done)" for source, kind, n, done in rows) or "none"))
    if status:
        lines.append(f"Last status: {status}")
    return "\n".join(lines)


def log_text(path: Path = LOG_PATH) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no log yet)"
    return "\n".join(lines[-LOG_TAIL:])


def gather(store: Store | None, status: str = "", note: str = "", log: Path = LOG_PATH, settings: Path = CONFIG_PATH) -> list[dict]:
    """The files that would go in the zip, already scrubbed: [{"name", "text"}]."""
    names = known(store)
    files = [{"name": "about.txt", "text": scrub(about_text(store, status), names)},
             {"name": "settings.txt", "text": scrub(settings_text(settings), names)},
             {"name": "log.txt", "text": scrub(log_text(log), names)}]
    note = note.strip()[:MAX_NOTE]
    if note:
        files.insert(0, {"name": "what-happened.txt", "text": scrub(note, names)})
    return files


def save(files: list[dict], folder: Path | None = None, now: datetime | None = None) -> Path:
    """Write the zip and say where it is."""
    now = now or datetime.now()
    folder = folder or (Path.home() / "Downloads")
    if not folder.is_dir():
        folder = DATA_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"Birdbrain-report-{now:%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.writestr(f["name"], f["text"])
    return path


def action(store: Store | None, body: dict, status: str = "", folder: Path | None = None, reveal=None) -> dict:
    """What the Report a problem window asks for: the files to look through, or (with "save") the zip made from
    exactly those. `reveal(path)` shows the saved file in its folder."""
    files = gather(store, status, str(body.get("note") or ""))
    if not body.get("save"):
        return {"ok": True, "files": files}
    path = save(files, folder)
    if reveal:
        try:
            reveal(path)
        except Exception:
            pass
    return {"ok": True, "files": files, "saved": path.name, "folder": scrub(str(path.parent)),
            "message": f"Saved {path.name} in your {path.parent.name} folder. Nothing was sent anywhere: attach it to a "
                       "message to whoever is helping you."}
