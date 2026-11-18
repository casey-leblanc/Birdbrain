"""The one module that knows which computer this is, and its two halves. Everything here is the halves' pure logic,
which runs anywhere: where things are kept, the LaunchAgent, what the Mac's own tools are asked, the update script
(run for real, with ordinary tools standing in for the Mac's), one running copy."""
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401

import report
import system
import system_mac
import system_win

WANTED = ("NAME", "MOD", "PROGRAM", "TRAY", "HOTKEY", "NOTIFY_CLICKS", "ASSET", "UNPACKED", "SIGNIN_BROWSER", "data_dir",
          "update_dir", "browsers_dir", "app_root", "program_in", "another_copy_holds", "listen_for_show", "show_running_copy",
          "secrets_available", "secret_get", "secret_put", "autostart_available", "autostart_read", "autostart_write",
          "keep_awake", "on_main", "play", "open_file", "reveal", "notify", "hear_clicks", "signin_channel", "unpack", "update_blocked",
          "swap_script", "run_swap")


class TwoHalves(unittest.TestCase):
    def test_both_halves_have_everything_the_app_asks_for(self):
        for half in (system_win, system_mac):
            self.assertEqual([n for n in WANTED if not hasattr(half, n)], [], half.__name__)

    def test_the_module_is_the_half_that_fits_this_computer(self):
        self.assertEqual(system.NAME, "mac" if sys.platform == "darwin" else "windows")
        self.assertIs(system.half, system_mac if sys.platform == "darwin" else system_win)

    def test_what_each_system_calls_things(self):
        self.assertEqual((system_win.MOD, system_win.TRAY, system_win.PROGRAM, system_win.ASSET),
                         ("Ctrl", "system tray", "Birdbrain.exe", "-windows.zip"))
        self.assertEqual((system_mac.MOD, system_mac.TRAY, system_mac.PROGRAM), ("Cmd", "menu bar", "Birdbrain.app"))
        self.assertIn(system_mac.ASSET, ("-mac-arm64.zip", "-mac-x64.zip"))

    def test_what_the_mac_cant_do_yet_is_switched_off_not_left_to_break(self):
        self.assertFalse(system_mac.HOTKEY)
        self.assertFalse(system_mac.NOTIFY_CLICKS)
        self.assertFalse(system_mac.hear_clicks(object(), lambda: None))
        self.assertTrue(system_win.HOTKEY and system_win.NOTIFY_CLICKS)

    def test_nothing_in_the_rest_of_the_app_talks_to_the_system_directly(self):
        src = Path(report.__file__).parent
        allowed = {"system_win.py", "system_mac.py", "appwindow_win.py", "appwindow_mac.py", "hotkey.py", "theme.py"}
        found = []
        for f in sorted(src.glob("*.py")):
            if f.name in allowed:
                continue
            text = f.read_text(encoding="utf-8")
            for word in ("winreg", "winsound", "ctypes", "os.startfile", "osascript", "caffeinate", "/usr/bin/"):
                if word in text:
                    found.append(f"{f.name}: {word}")
        self.assertEqual(found, [])


class MacPlaces(unittest.TestCase):
    def test_the_data_folder_is_application_support(self):
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(Path, "home", lambda: Path("/Users/sam")):
            os.environ.pop("APPDATA", None)
            self.assertEqual(system_mac.data_dir(), Path("/Users/sam/Library/Application Support/Birdbrain"))
            self.assertEqual(system_mac.update_dir(), Path("/Users/sam/Library/Caches/Birdbrain-update"))
        with mock.patch.dict(os.environ, {"APPDATA": "/tmp/x"}):                # the tests and the self-test
            self.assertEqual(system_mac.data_dir(), Path("/tmp/x/Birdbrain"))

    def test_the_app_is_found_from_the_program_inside_it(self):
        program = "/Applications/Birdbrain.app/Contents/MacOS/Birdbrain"
        self.assertEqual(system_mac.app_root(program), Path("/Applications/Birdbrain.app"))
        self.assertEqual(system_mac.program_in(Path("/Applications/Birdbrain.app")), Path(program))

    def test_windows_keeps_its_data_where_it_always_has(self):
        with mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\sam\AppData\Roaming"}):
            self.assertEqual(str(system_win.data_dir()).replace("\\", "/").split("/")[-1], "Birdbrain")


class MacStartAtLogin(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        patch = mock.patch.object(Path, "home", lambda: self.home)
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_launch_agent_of_your_own_starts_it_in_the_background(self):
        program = "/Applications/Birdbrain.app/Contents/MacOS/Birdbrain"
        system_mac.autostart_write("Birdbrain", f'"{program}" --background')
        path = self.home / "Library" / "LaunchAgents" / "io.github.casey-leblanc.birdbrain.birdbrain.plist"
        agent = plistlib.loads(path.read_bytes())
        self.assertEqual(agent["ProgramArguments"], [program, "--background"])
        self.assertTrue(agent["RunAtLoad"])
        self.assertEqual(agent["Label"], "io.github.casey-leblanc.birdbrain.birdbrain")
        self.assertEqual(system_mac.autostart_read("Birdbrain"), f'"{program}" --background')

    def test_off_removes_it_and_nothing_there_reads_as_off(self):
        self.assertIsNone(system_mac.autostart_read("Birdbrain"))
        system_mac.autostart_write("Birdbrain", '"/x/Birdbrain" --background')
        system_mac.autostart_write("Birdbrain", None)
        self.assertIsNone(system_mac.autostart_read("Birdbrain"))
        system_mac.autostart_write("Birdbrain", None)                           # twice is fine

    def test_a_program_with_a_space_in_its_path_comes_back_whole(self):
        program = "/Users/sam/My Apps/Birdbrain.app/Contents/MacOS/Birdbrain"
        system_mac.autostart_write("Birdbrain", f'"{program}" --background')
        agent = plistlib.loads(system_mac.agent_path("Birdbrain").read_bytes())
        self.assertEqual(agent["ProgramArguments"][0], program)

    def test_the_feature_module_works_the_same_over_the_mac_half(self):
        import autostart
        program = "/Applications/Birdbrain.app/Contents/MacOS/Birdbrain"
        with mock.patch.object(autostart, "system", system_mac):
            self.assertTrue(autostart.turn(True, program=program))
            self.assertTrue(autostart.is_on(program=program))
            self.assertFalse(autostart.is_on(program="/elsewhere/Birdbrain"))
            self.assertTrue(autostart.turn(False, program=program))
            self.assertFalse(autostart.is_on(program=program))


class MacTools(unittest.TestCase):
    def test_a_notification_cant_run_anything_a_title_says(self):
        script = system_mac.notify_script('Due "tonight"', 'Essay \\ "draft"\n" & (do shell script "rm -rf ~") & "')
        self.assertTrue(script.startswith('display notification "'))
        self.assertEqual(script.count('\\"'), 8)                                 # every quote in the words is escaped
        self.assertNotIn("\n", script)
        inner = script.replace('\\\\', "").replace('\\"', "")
        self.assertEqual(inner.count('"'), 4)                                    # only the four that fence the two strings

    def test_the_notification_goes_through_osascript(self):
        with mock.patch.object(system_mac.subprocess, "run") as run:
            system_mac.notify(None, "Due tonight", "Chem Exp 15 Quiz")
        args = run.call_args[0][0]
        self.assertEqual(args[:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(args[2], 'display notification "Chem Exp 15 Quiz" with title "Due tonight"')

    def test_the_keychain_is_asked_through_security(self):
        calls = []

        def security(*args):
            calls.append(args)
            return (44, "") if args[0] == "find-generic-password" and len(calls) == 1 else (0, "tok")
        with mock.patch.object(system_mac, "_security", security):
            self.assertEqual(system_mac.secret_get("telegram_token", "Birdbrain/"), "")      # nothing kept yet
            self.assertTrue(system_mac.secret_put("telegram_token", "tok", "Birdbrain/"))
            self.assertEqual(system_mac.secret_get("telegram_token", "Birdbrain/"), "tok")
            self.assertTrue(system_mac.secret_put("telegram_token", "", "Birdbrain/"))
        self.assertEqual(calls[1][:5], ("add-generic-password", "-U", "-s", "Birdbrain", "-a"))
        self.assertEqual(calls[3][0], "delete-generic-password")

    def test_staying_awake_holds_caffeinate_for_as_long_as_the_scan(self):
        with mock.patch.object(system_mac.subprocess, "Popen") as popen:
            with system_mac.keep_awake():
                self.assertEqual(popen.call_args[0][0][:2], ["/usr/bin/caffeinate", "-i"])
                popen.return_value.terminate.assert_not_called()
            popen.return_value.terminate.assert_called_once()

    def test_sounds_and_files(self):
        with mock.patch.object(system_mac.subprocess, "Popen") as popen:
            system_mac.play(Path("/a/chirp.wav"))
            system_mac.reveal(Path("/a/b.zip"))
            system_mac.open_file(Path("/a/log.txt"))
        said = [c[0][0] for c in popen.call_args_list]
        self.assertEqual(said, [["/usr/bin/afplay", "/a/chirp.wav"], ["/usr/bin/open", "-R", "/a/b.zip"], ["/usr/bin/open", "/a/log.txt"]])


class SignInBrowser(unittest.TestCase):
    def test_on_a_mac_chrome_if_there_is_one_then_edge_then_birdbrains_own(self):
        has = lambda *names: (lambda p: p.name in names)
        self.assertEqual(system_mac.signin_channel("msedge", has("Google Chrome.app", "Microsoft Edge.app")), "chrome")
        self.assertEqual(system_mac.signin_channel("msedge", has("Microsoft Edge.app")), "msedge")
        self.assertIsNone(system_mac.signin_channel("msedge", has()))            # the Chromium Birdbrain downloads

    def test_on_windows_the_one_in_the_settings(self):
        self.assertEqual(system_win.signin_channel("msedge"), "msedge")
        self.assertIsNone(system_win.signin_channel(""))


@unittest.skipIf(sys.platform == "win32", "the Mac's lock and socket need a Unix")
class MacOneCopy(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="bb"))
        patch = mock.patch.object(system_mac, "data_dir", lambda: self.dir)
        patch.start()
        self.addCleanup(patch.stop)
        system_mac._locks.clear()

    def test_the_first_copy_holds_the_lock_and_a_second_finds_it_held(self):
        self.assertFalse(system_mac.another_copy_holds("a"))
        self.assertFalse(system_mac.another_copy_holds("a"))                    # asked again: still the first answer
        first = dict(system_mac._locks)
        system_mac._locks.clear()                                               # a second copy starting up
        self.assertTrue(system_mac.another_copy_holds("a"))
        os.close(first["a"][0])                                                 # the first one quits
        system_mac._locks.clear()
        self.assertFalse(system_mac.another_copy_holds("a"))

    def test_a_second_copy_asks_the_first_to_show_its_window(self):
        self.assertFalse(system_mac.show_running_copy())                        # nobody listening yet
        shown, stop = threading.Event(), threading.Event()
        system_mac.listen_for_show(shown.set, stop)
        self.assertTrue(system_mac.show_running_copy())
        self.assertTrue(shown.wait(3))
        stop.set()


@unittest.skipIf(sys.platform == "win32", "the Mac's update script is a shell script")
class MacUpdate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="bb"))
        self.app, self.new, self.backup = self.dir / "Apps" / "Birdbrain.app", self.dir / "upd" / "new" / "Birdbrain.app", self.dir / "upd" / "previous"
        for where, text in ((self.app, "old"), (self.new, "new")):
            (where / "Contents" / "MacOS").mkdir(parents=True)
            (where / "Contents" / "MacOS" / "Birdbrain").write_text(text)
        self.opened = self.dir / "opened.txt"
        opener = self.dir / "open.sh"
        opener.write_text(f'#!/bin/sh\necho "$@" > "{self.opened}"\n')
        opener.chmod(0o700)
        self.opener = f"/bin/sh {opener}"

    def script(self, pid: int, ditto: str = "cp -R") -> Path:
        text = system_mac.swap_script(self.app, self.new, self.backup, pid, "exp-2.0.0-abc1234", ["--background"],
                                      folder=self.dir / "upd", ditto=ditto, opener=self.opener)
        path = self.dir / "upd" / "update.sh"
        path.write_text(text)
        return path

    def result(self) -> dict:
        return json.loads((self.dir / "upd" / "result.json").read_text())

    def test_the_script_is_sound_shell(self):
        self.assertEqual(subprocess.run(["/bin/sh", "-n", str(self.script(1))], capture_output=True).returncode, 0)
        real = system_mac.swap_script(Path("/Applications/Bird's \"100%\" $HOME.app"), self.new, self.backup, 1, "exp-2.0.0-abc1234", [])
        check = self.dir / "odd.sh"
        check.write_text(real)
        self.assertEqual(subprocess.run(["/bin/sh", "-n", str(check)], capture_output=True).returncode, 0)
        self.assertIn("/usr/bin/ditto", real)
        self.assertIn("/usr/bin/open -n", real)
        self.assertIn("com.apple.quarantine", real)

    def test_it_waits_for_birdbrain_to_close_then_swaps_the_app_and_opens_it(self):
        running = subprocess.Popen(["sleep", "2"])
        threading.Thread(target=running.wait, daemon=True).start()              # so it is really gone when it ends
        started = time.time()
        subprocess.run(["/bin/sh", str(self.script(running.pid))], check=True, timeout=60)
        self.assertGreaterEqual(time.time() - started, 1.5)                     # it waited
        self.assertEqual((self.app / "Contents" / "MacOS" / "Birdbrain").read_text(), "new")
        self.assertEqual((self.backup / "Contents" / "MacOS" / "Birdbrain").read_text(), "old")   # the one in use is kept
        self.assertEqual(self.result(), {"ok": True, "tag": "exp-2.0.0-abc1234"})
        self.assertEqual(self.opened.read_text().strip(), f"{self.app} --args --background")
        self.assertFalse(self.new.parent.exists())                              # the unpacked update is cleared away

    def test_if_the_new_one_wont_go_in_the_old_one_is_put_back_and_opened(self):
        subprocess.run(["/bin/sh", str(self.script(999999, ditto="false"))], check=True, timeout=60)
        self.assertEqual((self.app / "Contents" / "MacOS" / "Birdbrain").read_text(), "old")
        self.assertEqual(self.result()["ok"], False)
        self.assertIn("couldn't be copied in", self.result()["why"])
        self.assertTrue(self.opened.exists())

    def test_where_it_cant_update_itself_it_says_what_to_do(self):
        self.assertIn("Applications folder", system_mac.update_blocked(Path("/private/var/folders/x/AppTranslocation/1/d/Birdbrain.app")))
        self.assertIn("Applications folder", system_mac.update_blocked(Path("/Volumes/Birdbrain/Birdbrain.app")))
        self.assertEqual(system_mac.update_blocked(self.app), "")


class MacWords(unittest.TestCase):
    def test_the_same_page_says_cmd_and_menu_bar_on_a_mac(self):
        page = ('<kbd>Ctrl</kbd><kbd>Enter</kbd> title="Undo (Ctrl+Z)" Start Birdbrain too, in the tray. One short line. '
                'Click it and Birdbrain opens on that card.')
        mac = report.for_system(page, "mac")
        self.assertEqual(mac, '<kbd>Cmd</kbd><kbd>Enter</kbd> title="Undo (Cmd+Z)" Start Birdbrain too, in the menu bar. One short line.')
        self.assertEqual(report.for_system(page, "windows"), page)

    def test_the_keys_sheet_has_no_ctrl_left_on_a_mac(self):
        from config import Settings
        from helpers import NOW, item, store
        s = store()
        s.upsert(item())
        with mock.patch.object(report.system, "NAME", "mac"):
            page = report.render(report.build(s, Settings(), NOW), Settings(), "", NOW, "tok")
        self.assertNotIn("<kbd>Ctrl</kbd>", page)
        self.assertNotIn("Ctrl+", page)
        self.assertIn("<kbd>Cmd</kbd>", page)
        self.assertIn("Cmd+K", page)


if __name__ == "__main__":
    unittest.main()
