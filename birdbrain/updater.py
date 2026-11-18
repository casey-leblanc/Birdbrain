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

import system
from buildinfo import TAG_PREFIX, current

log = logging.getLogger(__name__)

API = "https://api.github.com"
REPO = "casey-leblanc/Birdbrain"
UPDATE_DIR = system.update_dir()
RESULT = UPDATE_DIR / "result.json"   # what the last update did, read (once) by the next start
EXE = system.PROGRAM   # Birdbrain.exe, or Birdbrain.app


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
            zips = [a for a in data.get("assets", []) if a.get("name", "").endswith(system.ASSET)]   # this system's file
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

    def stage(self, zip_path: Path, rel: Release | None) -> tuple[Path, dict]:
        """Unpack the zip and check the new Birdbrain starts here and (given a release) is the build it names.
        Returns the unpacked app and what it says of itself."""
        new = UPDATE_DIR / "new"
        shutil.rmtree(new, ignore_errors=True)
        try:
            system.unpack(zip_path, new)
        except (zipfile.BadZipFile, OSError, subprocess.SubprocessError) as e:
            raise UpdateError("The downloaded update couldn't be unpacked. Try again.") from e
        app = new / system.UNPACKED
        program = system.program_in(app)
        if not program.exists():
            raise UpdateError("The downloaded update isn't a Birdbrain build.")
        out = UPDATE_DIR / "build-info.json"
        out.unlink(missing_ok=True)
        try:
            subprocess.run([str(program), "--build-info", str(out)], timeout=120, check=True)
            info = json.loads(out.read_text(encoding="utf-8"))
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            raise UpdateError("The new version didn't start on this computer, so Birdbrain is staying as it is.") from e
        if rel is not None and info.get("tag") != rel.tag:
            raise UpdateError("The downloaded build isn't the one the release names. Birdbrain is staying as it is.")
        return app, info

    def install(self, new_app: Path, rel: Release, args: list[str]) -> None:
        """Start the script that swaps the new version in once this process has gone. The caller quits right after."""
        if not getattr(sys, "frozen", False):
            raise UpdateError("Birdbrain is running from source here. Pull the repository to update it.")
        app = system.app_root()
        if why := system.update_blocked(app):
            raise UpdateError(why)
        RESULT.unlink(missing_ok=True)
        script = system.run_swap(UPDATE_DIR, system.swap_script(app, new_app, UPDATE_DIR / "previous", os.getpid(), rel.tag,
                                                                args, folder=UPDATE_DIR))
        log.info("Update to %s handed to %s", rel.tag, script)


def install_from_zip(zip_path: Path, args: list[str]) -> int:
    """Birdbrain --install-update <zip> [arguments for the new version]: install a build from a zip already on this
    computer (one downloaded by hand, say), the same way an update goes in: it must be an experimental build that
    starts here, the version in use is kept in Birdbrain-update/previous, and the new one is started afterwards.
    Returns 0 once the swap is handed over; the caller exits straight away so it can happen."""
    try:
        if not zipfile.is_zipfile(zip_path):
            raise UpdateError("That file isn't a Birdbrain build.")
        with zipfile.ZipFile(zip_path) as z:   # a Windows build says which it is without being started
            if "Birdbrain/_internal/assets/build.json" in z.namelist() and \
                    not json.loads(z.read("Birdbrain/_internal/assets/build.json")).get("tag", "").startswith(TAG_PREFIX):
                raise UpdateError("That zip isn't an experimental Birdbrain build.")
        up = Updater()
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        app, info = up.stage(zip_path, None)
        tag = str(info.get("tag") or "")
        if not tag.startswith(TAG_PREFIX):
            raise UpdateError("That zip isn't an experimental Birdbrain build.")
        up.install(app, Release(tag=tag, version=_version_of(tag), notes="", asset_id=0, size=0, sha256=""), args)
        return 0
    except (UpdateError, OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        why = str(e) if isinstance(e, UpdateError) else "That file isn't a Birdbrain build."
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps({"ok": False, "tag": "", "why": why}), encoding="utf-8")
        return 1


swap_script = system.swap_script   # the script that does the swap is the system's own (system_win.py, system_mac.py)


def last_result() -> dict | None:
    """What the update that restarted Birdbrain did ({"ok": bool, "tag": ..., "why": ...}); read once."""
    try:
        got = json.loads(RESULT.read_text(encoding="utf-8"))
        RESULT.unlink(missing_ok=True)
        return got
    except (OSError, ValueError):
        return None
