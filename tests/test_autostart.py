"""Starting with the computer: one value under the student's own Run key, pointing at this copy."""
from __future__ import annotations

import sys
import unittest
from unittest import mock

import helpers  # noqa: F401

import autostart


class Rules(unittest.TestCase):
    def setUp(self):
        self.reg: dict[str, str] = {}
        for name, fake in (("_read", lambda n: self.reg.get(n)),
                           ("_write", lambda n, v: self.reg.pop(n, None) if v is None else self.reg.__setitem__(n, v))):
            p = mock.patch.object(autostart, name, fake)
            p.start()
            self.addCleanup(p.stop)

    def test_on_writes_this_copy_started_in_the_background_and_off_removes_it(self):
        exe = r"C:\Users\x\Documents\Birdbrain\Birdbrain.exe"
        self.assertFalse(autostart.is_on(program=exe))
        self.assertTrue(autostart.turn(True, program=exe))
        self.assertEqual(self.reg, {"Birdbrain": f'"{exe}" --background'})
        self.assertTrue(autostart.is_on(program=exe))
        self.assertTrue(autostart.turn(False, program=exe))
        self.assertEqual(self.reg, {})

    def test_a_value_left_by_a_copy_somewhere_else_isnt_this_one_being_on(self):
        self.reg["Birdbrain"] = '"D:\\Old\\Birdbrain.exe" --background'
        self.assertFalse(autostart.is_on(program=r"C:\New\Birdbrain.exe"))
        autostart.turn(True, program=r"C:\New\Birdbrain.exe")                    # turning it on moves it here
        self.assertEqual(self.reg["Birdbrain"], '"C:\\New\\Birdbrain.exe" --background')

    def test_a_registry_that_wont_be_written_says_so_instead_of_crashing(self):
        def refuse(name, value):
            raise PermissionError("no")
        with mock.patch.object(autostart, "_write", refuse):
            self.assertFalse(autostart.turn(True, program="x.exe"))

    def test_only_a_packaged_copy_on_windows_offers_it(self):
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(sys, "frozen", True, create=True):
            self.assertTrue(autostart.available())
        with mock.patch.object(sys, "platform", "win32"):
            self.assertFalse(autostart.available() and not getattr(sys, "frozen", False))
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(sys, "frozen", True, create=True):
            self.assertFalse(autostart.available())


@unittest.skipUnless(sys.platform == "win32", "the real registry is only on Windows")
class OnRealWindows(unittest.TestCase):
    NAME = "Birdbrain-selftest"

    def tearDown(self):
        autostart.turn(False, self.NAME, "C:\\nowhere\\Birdbrain.exe")

    def test_the_real_run_key_takes_it_and_gives_it_back(self):
        exe = "C:\\nowhere\\Birdbrain.exe"
        self.assertTrue(autostart.turn(True, self.NAME, exe))
        self.assertTrue(autostart.is_on(self.NAME, exe))
        self.assertEqual(autostart._read(self.NAME), f'"{exe}" --background')
        self.assertTrue(autostart.turn(False, self.NAME, exe))
        self.assertIsNone(autostart._read(self.NAME))


if __name__ == "__main__":
    unittest.main()
