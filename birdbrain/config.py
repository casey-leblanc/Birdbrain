"""Settings, paths and every tunable constant in one place.

TypeSafe's guidance is to keep question thresholds and model names central so
they are easy to review; they live at the bottom of this file.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "Birdbrain"
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
PROFILE_DIR = DATA_DIR / "browser-profile"   # Edge profile for the sign-in window
STATE_PATH = DATA_DIR / "session.json"        # cookies handed to the background scanner
DB_PATH = DATA_DIR / "birdbrain.db"
REPORT_PATH = DATA_DIR / "today.html"
LOG_PATH = DATA_DIR / "birdbrain.log"
CONFIG_PATH = DATA_DIR / "config.json"

# Birdbrain used to be called StudyTray and kept its data in %APPDATA%\StudyTray.
_OLD_DIR = DATA_DIR.parent / "StudyTray"
_OLD_FILES = {"studytray.db": DB_PATH.name, "studytray.log": LOG_PATH.name}


def _sandboxed_copies() -> list[Path]:
    """Data left in an app sandbox's private AppData. When Birdbrain is started from
    inside a packaged (MSIX) Windows app, Windows redirects its AppData writes to
    %LOCALAPPDATA%\\Packages\\<app>\\LocalCache\\Roaming; started normally, it can't see them."""
    packages = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Packages"
    found = [p for name in (APP_NAME, "StudyTray") for p in packages.glob(f"*/LocalCache/Roaming/{name}")
             if (p / "config.json").exists()]
    newest = lambda p: max((f.stat().st_mtime for f in p.glob("*.db")), default=0)
    return sorted(found, key=newest, reverse=True)


def migrate_old_data() -> str:
    """Bring over sign-ins, items and settings saved under the old name (StudyTray)
    or left in a sandbox. Returns what happened ("" if there was nothing to do)."""
    if DATA_DIR.exists():
        return ""
    if _OLD_DIR.exists():
        try:
            _OLD_DIR.rename(DATA_DIR)
            how = f"Moved {_OLD_DIR} to {DATA_DIR}"
        except OSError:   # something still has a file open: copy instead, leave the old folder
            shutil.copytree(_OLD_DIR, DATA_DIR)
            how = f"Copied {_OLD_DIR} to {DATA_DIR} (the old folder was in use and was left in place)"
    elif copies := _sandboxed_copies():
        src = copies[0]
        try:   # copy, never move: the sandboxed copy stays as it was
            shutil.copytree(src, DATA_DIR, ignore=shutil.ignore_patterns("lockfile", "Singleton*", "*.tmp"))
        except shutil.Error:
            pass   # a few locked browser-cache files; everything that matters was copied
        how = f"Copied {src} to {DATA_DIR} (data saved while Birdbrain ran inside another app's sandbox)"
    else:
        return ""
    for old, new in _OLD_FILES.items():
        if (DATA_DIR / old).exists() and not (DATA_DIR / new).exists():
            (DATA_DIR / old).rename(DATA_DIR / new)
    return how


@dataclass
class Settings:
    moodle_url: str = ""                                   # e.g. https://moodle.myschool.edu
    outlook_url: str = "https://outlook.office.com"        # or https://outlook.live.com
    interval_minutes: int = 60
    headless: bool = True                                  # False shows scans in a visible browser (debugging)
    browser_channel: str = "msedge"                        # browser for the sign-in window: "msedge" or "chrome"
    lookahead_days: int = 30                               # how far ahead tests/events are listed
    overdue_days: int = 14                                 # how far back overdue work is shown
    email_scan_count: int = 50                             # newest inbox messages read per scan
    scan_outlook_mail: bool = True
    scan_outlook_calendar: bool = True
    typesafe_api_key: str = ""                             # falls back to TYPESAFE_API_KEY env var
    typesafe_model: str = "jev-latest"
    notify: bool = True
    # Entries whose title or course contains any of these (case-insensitive) are archived.
    hidden_keywords: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        return self.typesafe_api_key or os.environ.get("TYPESAFE_API_KEY", "")

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            s = cls()
            s.save()
            return s
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# --- TypeSafe / Jev tuning -------------------------------------------------
# An item is flagged "check this" in the report when Jev's confidence in any
# answer that shaped it falls below this value.
REVIEW_BELOW = 0.60
# Minimum Noul value for an email or course-page snippet to count as
# something the student must do or attend.
ACTIONABLE_MIN = 0.55
# Course pages are split into chunks of about this many characters before
# being shown to Jev on the first full scan.
CHUNK_CHARS = 900
