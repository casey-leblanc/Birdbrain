"""Updating Birdbrain from its builds on GitHub, with one button.

Every push to the experimental branch builds the app and attaches it to a pre-release tagged exp-<version>-<commit>
(.github/workflows/build.yml), and only if the packaged app passed its own self-test and started properly. Birdbrain
asks GitHub for the newest of those (a few times a day, and when you press Check for updates) and, when it's a
different build from the one running:

1. downloads the zip to %LOCALAPPDATA%\\Birdbrain-update and checks it against the size and SHA-256 GitHub gives;
2. unpacks it and starts the new Birdbrain.exe once with --build-info, to see that it runs on this PC and is the
   build it says it is;
3. waits for any scan to finish, then quits. A small script (update.cmd) waits for Birdbrain to close, keeps a copy
   of the version you had (in Birdbrain-update\\previous), copies the new one over it, and starts it again. If the
   copy fails, it puts the old version back. What it did is in Birdbrain-update\\update.log.

Your data (%APPDATA%\\Birdbrain) isn't touched. The repository is public, so no account or token is needed, and
nothing about you is sent: only the request for the list of builds and for the zip.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from buildinfo import TAG_PREFIX, current

log = logging.getLogger(__name__)

API = "https://api.github.com"
REPO = "casey-leblanc/Birdbrain"
UPDATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Birdbrain-update"
RESULT = UPDATE_DIR / "result.json"   # what the last update did, read (once) by the next start
EXE = "Birdbrain.exe"


@dataclass
class Release:
    tag: str            # "exp-2.0.0-73d77c1"
    version: str        # "2.0.0"
    notes: str          # what changed, as the release says
    asset_id: int
    size: int
    sha256: str         # "" if GitHub gave none

    @property
    def label(self) -> str:
        """'2.0.0 (73d77c1)'."""
        commit = self.tag.rsplit("-", 1)[-1]
        return f"{self.version} ({commit})" if commit != self.version else self.version


class UpdateError(Exception):
    """Something the person can act on, in plain words."""


def _version_of(tag: str) -> str:
    """'exp-2.0.0-73d77c1' -> '2.0.0'."""
    return tag[len(TAG_PREFIX):].split("-")[0]


class Updater:
    def __init__(self, repo: str = REPO, fetch=None):
        self.repo = repo
        self._fetch = fetch or self._http   # (url, headers) -> response with .read(n); tests replace it

    # --- GitHub -----------------------------------------------------------------------------------------------------
    @staticmethod
    def _http(url: str, headers: dict):
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Birdbrain", **headers}),
                                      timeout=60)

    def _api(self, path: str, accept: str = "application/vnd.github+json"):
        try:
            return self._fetch(f"{API}/repos/{self.repo}{path}", {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"})
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):   # GitHub allows 60 questions an hour from one address without an account
                raise UpdateError("GitHub is taking a break from this network's questions. Try again in an hour.") from e
            if e.code == 404:
                raise UpdateError("GitHub couldn't find Birdbrain's builds. Try again later.") from e
            raise UpdateError(f"GitHub had an error ({e.code}). Try again in a while.") from e
        except (urllib.error.URLError, OSError) as e:
            raise UpdateError("Couldn't reach GitHub. Check this PC is online.") from e

    def latest(self) -> Release:
        """The newest experimental build that has a Windows zip. Normal releases and drafts are passed over."""
        try:
            releases = json.loads(self._api("/releases?per_page=30").read())
        except ValueError as e:
            raise UpdateError("GitHub's answer couldn't be read. Try again in a while.") from e
        for data in releases if isinstance(releases, list) else []:
            tag = data.get("tag_name") or ""
            zips = [a for a in data.get("assets", []) if a.get("name", "").endswith("-windows.zip")]
            if not tag.startswith(TAG_PREFIX) or data.get("draft") or not zips:
                continue
            a = zips[0]
            digest = a.get("digest") or ""
            return Release(tag=tag, version=_version_of(tag), notes=(data.get("body") or "").strip(),
                           asset_id=a["id"], size=int(a.get("size") or 0),
                           sha256=digest[7:] if digest.startswith("sha256:") else "")
        raise UpdateError("There is no experimental build to update to yet. Try again in a few minutes.")

    def available(self) -> Release | None:
        """The newest build, if it isn't the one that's running. None when up to date."""
        rel, mine = self.latest(), current()
        return None if rel.tag == mine["tag"] else rel

    # --- download, check, hand over -------------------------------------------------------------------------------
    def download(self, rel: Release, progress=None) -> Path:
        """The release's zip, checked against the size and SHA-256 GitHub lists for it."""
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        for old in UPDATE_DIR.glob("*.zip"):
            old.unlink(missing_ok=True)
        path = UPDATE_DIR / f"Birdbrain-{rel.tag}.zip"
        resp = self._api(f"/releases/assets/{rel.asset_id}", accept="application/octet-stream")
        digest, got = hashlib.sha256(), 0
        try:
            with open(path, "wb") as f:
                while chunk := resp.read(1 << 18):
                    f.write(chunk)
                    digest.update(chunk)
                    got += len(chunk)
                    if progress and rel.size:
                        progress(min(got / rel.size, 1.0))
        except (urllib.error.URLError, OSError) as e:
            raise UpdateError("The download stopped partway. Try again.") from e
        if (rel.size and got != rel.size) or (rel.sha256 and digest.hexdigest() != rel.sha256):
            path.unlink(missing_ok=True)
            raise UpdateError("The download didn't match what GitHub lists for this release. Try again.")
        return path

    def stage(self, zip_path: Path, rel: Release) -> Path:
        """Unpack the zip and check the new Birdbrain.exe starts here and is the build the release says."""
        new = UPDATE_DIR / "new"
        shutil.rmtree(new, ignore_errors=True)
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(new)
        except (zipfile.BadZipFile, OSError) as e:
            raise UpdateError("The downloaded update couldn't be unpacked. Try again.") from e
        app = new / "Birdbrain"
        if not (app / EXE).exists():
            raise UpdateError("The downloaded update isn't a Birdbrain build.")
        out = UPDATE_DIR / "build-info.json"
        out.unlink(missing_ok=True)
        try:
            subprocess.run([str(app / EXE), "--build-info", str(out)], timeout=120, check=True)
            info = json.loads(out.read_text(encoding="utf-8"))
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            raise UpdateError("The new version didn't start on this PC, so Birdbrain is staying as it is.") from e
        if info.get("tag") != rel.tag:
            raise UpdateError("The downloaded build isn't the one the release names. Birdbrain is staying as it is.")
        return app

    def install(self, new_app: Path, rel: Release, args: list[str]) -> None:
        """Start the script that swaps the new version in once this process has gone. The caller quits right after."""
        app = Path(sys.executable).resolve().parent
        if not getattr(sys, "frozen", False):
            raise UpdateError("Birdbrain is running from source here. Pull the repository to update it.")
        if not os.access(app, os.W_OK):
            raise UpdateError(f"Birdbrain can't write to its own folder ({app}). Move it somewhere you can, such as "
                              "%LOCALAPPDATA%\\Programs, and update again.")
        script = UPDATE_DIR / "update.cmd"
        script.write_text(swap_script(app, new_app, UPDATE_DIR / "previous", os.getpid(), rel.tag, args),
                          encoding="utf-8", newline="\r\n")
        RESULT.unlink(missing_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:   # outside any job object this process is in, where that's allowed, so it outlives us
            subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(UPDATE_DIR), close_fds=True,
                             creationflags=flags | 0x01000000)
        except OSError:
            subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(UPDATE_DIR), close_fds=True, creationflags=flags)
        log.info("Update to %s handed to %s", rel.tag, script)


def install_from_zip(zip_path: Path, args: list[str]) -> int:
    """Birdbrain.exe --install-update <zip> [arguments for the new version]: install a build from a zip already on
    this PC (one downloaded by hand, say), the same way an update goes in: it must be an experimental build that
    starts here, the version in use is kept in Birdbrain-update\\previous, and the new one is started afterwards.
    Returns 0 once the swap is handed over; the caller exits straight away so it can happen."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            tag = json.loads(z.read("Birdbrain/_internal/assets/build.json"))["tag"]
        if not tag.startswith(TAG_PREFIX):
            raise UpdateError("That zip isn't an experimental Birdbrain build.")
        rel = Release(tag=tag, version=_version_of(tag), notes="", asset_id=0, size=0, sha256="")
        up = Updater()
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        up.install(up.stage(zip_path, rel), rel, args)
        return 0
    except (UpdateError, OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        why = str(e) if isinstance(e, UpdateError) else "That file isn't a Birdbrain build."
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps({"ok": False, "tag": "", "why": why}), encoding="utf-8")
        return 1


def swap_script(app: Path, new: Path, backup: Path, pid: int, tag: str, args: list[str], exe: str = EXE,
                image: str = EXE) -> str:
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


def last_result() -> dict | None:
    """What the update that restarted Birdbrain did ({"ok": bool, "tag": ..., "why": ...}); read once."""
    try:
        got = json.loads(RESULT.read_text(encoding="utf-8"))
        RESULT.unlink(missing_ok=True)
        return got
    except (OSError, ValueError):
        return None
