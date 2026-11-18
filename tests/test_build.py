"""Which build this is: what a packaged app reports, and what a copy run from source reports."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (sets the data folder and the import path)

import buildinfo
from version import VERSION


class BuildInfo(unittest.TestCase):
    def test_from_source_there_is_no_commit_or_tag(self):
        self.assertEqual(buildinfo.current(), {"version": VERSION, "commit": "", "tag": ""})
        self.assertEqual(buildinfo.name(), f"{VERSION} (from source)")

    def test_a_packaged_build_reads_its_stamp(self):
        stamp = {"version": "2.0.0", "commit": "abc1234", "tag": buildinfo.tag_for("2.0.0", "abc1234def")}
        with mock.patch.object(Path, "read_text", return_value=json.dumps(stamp)):
            self.assertEqual(buildinfo.current(), stamp)
            self.assertEqual(buildinfo.name(), "2.0.0 (abc1234)")

    def test_experimental_tags_can_never_be_mistaken_for_a_normal_release(self):
        self.assertEqual(buildinfo.tag_for("2.0.0", "abc1234def5678"), "exp-2.0.0-abc1234")
        self.assertTrue(buildinfo.tag_for(VERSION, "0" * 40).startswith(buildinfo.TAG_PREFIX))

    def test_version_is_plain_numbers(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")   # build.py turns it into the exe's version numbers


if __name__ == "__main__":
    unittest.main()
