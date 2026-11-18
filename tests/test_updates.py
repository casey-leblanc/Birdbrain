"""Updating from Birdbrain's experimental builds on GitHub. GitHub is stood in for; update.cmd, the script that swaps
a new version in, is run for real on Windows."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import zipfile
from pathlib import Path, PureWindowsPath
from unittest import mock

from helpers import NOW, item, store

import report
import updater
from config import Settings

TAG = "exp-9.9.9-abc1234"


def build_zip(tag: str = TAG) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Birdbrain/Birdbrain.exe", b"MZ fake")
        z.writestr("Birdbrain/_internal/assets/build.json", json.dumps({"tag": tag}))
    return buf.getvalue()


class FakeGitHub:
    """Stands in for api.github.com: a normal release, a draft, and experimental builds with Windows zips."""

    def __init__(self, tag=TAG, body=None, digest=True, status=None, releases=None):
        self.zip = build_zip(tag) if body is None else body
        self.tag, self.status, self.calls, self.releases = tag, status, [], releases
        self.digest = "sha256:" + hashlib.sha256(build_zip(tag)).hexdigest() if digest else None

    def asset(self, n):
        return {"id": n, "name": "Birdbrain-9.9.9-windows.zip", "size": len(build_zip(self.tag)), "digest": self.digest}

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        if self.status:
            raise urllib.error.HTTPError(url, self.status, "no", {}, io.BytesIO(b"{}"))
        if "/releases?" in url:
            listed = self.releases if self.releases is not None else [
                {"tag_name": "v3.0.0", "prerelease": False, "assets": [self.asset(1)]},            # a normal release
                {"tag_name": "exp-9.9.9-ddddddd", "draft": True, "assets": [self.asset(2)]},        # not published
                {"tag_name": "exp-9.9.9-eeeeeee", "prerelease": True,
                 "assets": [{"id": 3, "name": "selftest-result.txt", "size": 10}]},                 # no zip yet
                {"tag_name": self.tag, "prerelease": True, "body": "- Quick write\n- Fixes",
                 "assets": [{"id": 7, "name": "selftest-result.txt", "size": 10}, self.asset(8)]},
                {"tag_name": "exp-9.9.8-0000000", "prerelease": True, "assets": [self.asset(9)]},  # older
            ]
            return io.BytesIO(json.dumps(listed).encode())
        assert url.endswith("/releases/assets/8") and headers["Accept"] == "application/octet-stream", url
        return io.BytesIO(self.zip)


class Updates(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        for name, value in (("UPDATE_DIR", self.dir), ("RESULT", self.dir / "result.json")):
            p = mock.patch.object(updater, name, value)
            p.start()
            self.addCleanup(p.stop)

    def running(self, tag):
        return mock.patch.object(updater, "current", lambda: {"version": "9.9.8", "commit": "0000000", "tag": tag})

    def test_the_newest_experimental_build_is_found_with_no_token(self):
        gh = FakeGitHub()
        up = updater.Updater(fetch=gh)
        with self.running("exp-9.9.8-0000000"):
            rel = up.available()
        self.assertEqual((rel.tag, rel.version, rel.label, rel.asset_id), (TAG, "9.9.9", "9.9.9 (abc1234)", 8))
        self.assertEqual(rel.notes, "- Quick write\n- Fixes")
        url, headers = gh.calls[0]
        self.assertEqual(url, "https://api.github.com/repos/casey-leblanc/Birdbrain/releases?per_page=30")
        self.assertNotIn("Authorization", headers)
        with self.running(TAG):
            self.assertIsNone(up.available())   # already running it

    def test_a_normal_release_is_never_taken_for_an_update(self):
        only_normal = FakeGitHub(releases=[{"tag_name": "v3.0.0", "assets": [{"id": 1, "name": "Birdbrain-3.0.0-windows.zip"}]}])
        with self.assertRaisesRegex(updater.UpdateError, "no experimental build"):
            updater.Updater(fetch=only_normal).latest()

    def test_errors_say_what_to_do(self):
        for status, words in ((403, "Try again in an hour"), (404, "couldn't find"), (500, r"error \(500\)")):
            with self.subTest(status=status), self.assertRaisesRegex(updater.UpdateError, words):
                updater.Updater(fetch=FakeGitHub(status=status)).latest()

        def offline(url, headers):
            raise urllib.error.URLError("no route")
        with self.assertRaisesRegex(updater.UpdateError, "Check this PC is online"):
            updater.Updater(fetch=offline).latest()

    def test_download_is_checked_and_staged(self):
        up = updater.Updater(fetch=FakeGitHub())
        rel = up.latest()
        seen = []
        path = up.download(rel, seen.append)
        self.assertEqual(path.read_bytes(), build_zip())
        self.assertEqual(seen[-1], 1.0)

        def run_new_build(cmd, **kw):   # stands in for starting the new Birdbrain.exe --build-info <file>
            self.assertEqual(cmd[1], "--build-info")
            Path(cmd[2]).write_text(json.dumps({"tag": TAG}))
        with mock.patch.object(updater.subprocess, "run", run_new_build):
            app = up.stage(path, rel)
        self.assertTrue((app / "Birdbrain.exe").exists())
        # a build that says it's a different one isn't installed
        with mock.patch.object(updater.subprocess, "run", lambda cmd, **kw: Path(cmd[2]).write_text('{"tag": "exp-0-x"}')):
            with self.assertRaisesRegex(updater.UpdateError, "isn't the one the release names"):
                up.stage(path, rel)

        def broken(cmd, **kw):   # nor one that doesn't start
            raise subprocess.CalledProcessError(1, cmd)
        with mock.patch.object(updater.subprocess, "run", broken):
            with self.assertRaisesRegex(updater.UpdateError, "didn't start on this PC"):
                up.stage(path, rel)

    def test_a_download_that_does_not_match_its_sha256_is_thrown_away(self):
        bad = updater.Updater(fetch=FakeGitHub(body=build_zip()[:-1] + b"x"))
        with self.assertRaisesRegex(updater.UpdateError, "didn't match"):
            bad.download(bad.latest())
        self.assertEqual(list(self.dir.glob("*.zip")), [])
        short = updater.Updater(fetch=FakeGitHub(body=build_zip()[:-10], digest=False))
        with self.assertRaisesRegex(updater.UpdateError, "didn't match"):   # the size alone gives it away
            short.download(short.latest())

    def test_install_refuses_from_source(self):
        up = updater.Updater(fetch=FakeGitHub())
        with self.assertRaisesRegex(updater.UpdateError, "from source"):
            up.install(self.dir / "new" / "Birdbrain", up.latest(), [])

    def test_result_is_read_once(self):
        (self.dir / "result.json").write_text('{"ok": true, "tag": "exp-9.9.9-abc1234"} \n')
        self.assertEqual(updater.last_result(), {"ok": True, "tag": TAG})
        self.assertIsNone(updater.last_result())

    def test_script_text(self):
        win = PureWindowsPath   # so the paths split the same wherever the test runs
        text = updater.swap_script(win(r"C:\Apps\Bird's 100%\Birdbrain"), win(r"C:\U\new\Birdbrain"),
                                   win(r"C:\U\previous"), 4321, TAG, ["--background"])
        self.assertIn('tasklist /FI "PID eq 4321" /FI "IMAGENAME eq Birdbrain.exe"', text)
        self.assertIn(r'''start "" "C:\Apps\Bird's 100%%\Birdbrain\Birdbrain.exe" --background''', text)
        self.assertIn(r"-like 'C:\Apps\Bird''s 100%\Birdbrain\*'", text)
        self.assertIn('rmdir /s /q "C:\\U\\new"', text)

    @unittest.skipUnless(os.name == "nt", "update.cmd is a Windows script")
    def test_script_swaps_the_new_version_in(self):
        app, new, backup = self.dir / "app", self.dir / "new" / "Birdbrain", self.dir / "previous"
        for path, text in ((app / "old-only.txt", "old"), (app / "README.md", "old readme"),
                           (app / "_internal" / "stale.dll", "old"), (app / "_internal" / "lib.dll", "old"),
                           (new / "README.md", "new readme"), (new / "_internal" / "lib.dll", "new"),
                           (new / "hello.cmd", '@echo %1> "%~dp0started.txt"\r\n@exit\r\n')):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        running = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(4)"])   # "Birdbrain", still closing
        script = self.dir / "update.cmd"
        script.write_text(updater.swap_script(app, new, backup, running.pid, TAG, ["--background"], exe="hello.cmd",
                                              image=Path(sys.executable).name), encoding="utf-8", newline="\r\n")
        began = time.monotonic()
        subprocess.run(["cmd.exe", "/c", str(script)], cwd=self.dir, timeout=180, check=False)
        self.assertGreater(time.monotonic() - began, 2)   # it waited for the old process
        log = (self.dir / "update.log").read_text(errors="replace")
        self.assertEqual(updater.last_result(), {"ok": True, "tag": TAG}, log)
        # (these pairs are the same size and written in the same instant: copied all the same)
        self.assertEqual((app / "_internal" / "lib.dll").read_text(), "new", log)
        self.assertEqual((app / "README.md").read_text(), "new readme", log)
        self.assertFalse((app / "_internal" / "stale.dll").exists())   # the new version's files only
        self.assertTrue((app / "old-only.txt").exists())               # but nothing else of yours in the folder goes
        self.assertEqual((backup / "_internal" / "lib.dll").read_text(), "old")   # the version you had, kept
        self.assertFalse(new.parent.exists())
        for _ in range(50):   # the new version was started, with its arguments
            if (app / "started.txt").exists():
                break
            time.sleep(0.2)
        self.assertEqual((app / "started.txt").read_text().strip(), "--background")


class StartingUp(unittest.TestCase):
    def test_the_arguments_after_the_zip_belong_to_the_new_version(self):
        """Birdbrain.exe --install-update <zip> --build-info <file> must install, not answer --build-info itself."""
        main = (Path(__file__).resolve().parent.parent / "birdbrain" / "main.py").read_text(encoding="utf-8")
        start = main[main.index('if __name__ == "__main__":'):]
        self.assertLess(start.index('"--install-update" in sys.argv'), start.index('"--build-info" in sys.argv'))

    def test_a_zip_that_is_not_a_build_is_refused_and_says_why(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(updater, "UPDATE_DIR", tmp), mock.patch.object(updater, "RESULT", tmp / "result.json"):
            bad = tmp / "notes.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("readme.txt", "hello")
            self.assertEqual(updater.install_from_zip(bad, []), 1)
            self.assertEqual(updater.last_result()["ok"], False)
            normal = tmp / "normal.zip"
            normal.write_bytes(build_zip("v3.0.0"))
            self.assertEqual(updater.install_from_zip(normal, []), 1)
            self.assertIn("isn't an experimental", updater.last_result()["why"])


class InSettings(unittest.TestCase):
    def page(self, update):
        s = store()
        s.upsert(item())
        return report.render(report.build(s, Settings(), NOW), Settings(), "", NOW, "tok", update=update)

    def test_settings_says_which_build_this_is_and_offers_a_check(self):
        page = self.page({"current": "2.0.0 (abc1234)", "available": "", "notes": "", "packaged": True})
        self.assertIn('<b id="update-current">2.0.0 (abc1234)</b>', page)
        self.assertIn('id="update-check">Check for updates</button>', page)
        self.assertIn('id="update-go" hidden>', page)
        self.assertNotIn("token", page.split('id="updates-sec"')[1].split("</div></div>")[0].lower())

    def test_a_waiting_build_shows_the_update_button(self):
        page = self.page({"current": "2.0.0 (abc1234)", "available": "2.0.1 (def5678)", "notes": "", "packaged": True})
        self.assertIn('id="update-go">Update to 2.0.1 (def5678) and restart</button>', page)

    def test_from_source_there_is_nothing_to_install(self):
        page = self.page({"current": "2.0.0 (from source)", "available": "2.0.1 (def5678)", "notes": "", "packaged": False})
        self.assertIn('id="update-go" hidden>', page)
        self.assertIn("pulling the repository", page)


if __name__ == "__main__":
    unittest.main()
