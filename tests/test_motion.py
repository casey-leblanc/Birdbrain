"""Motion: one vocabulary in one place, three levels, and only transform and opacity ever animated."""
from __future__ import annotations

import re
import unittest

from helpers import NOW, item, store

import motion
import prefs
import report
from config import Settings
from server import ListServer

AMBIENT = {"flap", "pulse", "scan-busy", "dot-breathe", "landed"}   # loops and marks that keep their own time


def pages():
    s = store()
    s.upsert(item())
    board = report.build(s, Settings(), NOW)
    out = {}
    for layout in ("glass", "focus"):
        out[layout] = report.render(board, Settings(), "", NOW, "tok", prefs={**prefs.DEFAULTS, "layout": layout})
    out["welcome"] = report.render_setup("tok", prefs.DEFAULTS)
    out["small window"] = report.render_quick("tok", prefs.DEFAULTS)
    return out


def styles(page: str) -> str:
    return "".join(re.findall(r"<style[^>]*>(.*?)</style>", page, re.S))


class Vocabulary(unittest.TestCase):
    def test_every_page_carries_the_timings_and_sets_the_level_before_it_paints(self):
        for name, page in pages().items():
            with self.subTest(page=name):
                self.assertIn("--m-fast:120ms", page)
                self.assertIn("--m-spring:", page)
                self.assertIn('data-motion-pref=""', page)
                self.assertLess(page.index(motion.HEAD_JS), page.index("<style"))

    def test_transitions_move_only_transform_and_opacity_at_the_shared_pace(self):
        for name, page in pages().items():
            for value in re.findall(r"transition:([^;}]+)", styles(page)):
                if value.startswith("none"):
                    continue
                for part in re.split(r",(?![^(]*\))", value):
                    with self.subTest(page=name, transition=part):
                        self.assertRegex(part.strip(), r"^(transform|opacity) var\(--m-(fast|base|slow|long|spring-time)\) var\(--m-(out|in|move|spring)\)$")

    def test_animations_keep_the_shared_pace_too(self):
        for name, page in pages().items():
            for value in re.findall(r"animation:([^;}]+)", styles(page)):
                if value.startswith("none"):
                    continue
                with self.subTest(page=name, animation=value):
                    if value.split()[0] not in AMBIENT:
                        self.assertIn("var(--m-", value)
                        self.assertNotRegex(value.replace(".04s", "").replace(".06s", ""), r"(?<![\w-])\.?\d+m?s\b")

    def test_keyframes_change_only_transform_and_opacity(self):
        for name, page in pages().items():
            for frames in re.findall(r"@keyframes [\w-]+\{((?:[^{}]*\{[^{}]*\})+)\}", styles(page)):
                props = set(re.findall(r"[{;]\s*([a-z-]+)\s*:", frames))
                with self.subTest(page=name, keyframes=frames[:40]):
                    self.assertLessEqual(props, {"transform", "opacity", "offset-distance"})

    def test_the_system_setting_no_longer_decides_alone(self):
        for name, page in pages().items():
            with self.subTest(page=name):
                self.assertNotIn("prefers-reduced-motion", styles(page))            # the level in force decides
                self.assertEqual(page.count("prefers-reduced-motion"), 1)           # asked once, to start with
                self.assertIn(":root[data-motion=off] *", page)

    def test_script_takes_its_timings_from_the_same_place(self):
        script = report.JS
        self.assertIn("readMotion();", script)
        self.assertEqual(re.findall(r"duration:\d{2,}", script), [])
        self.assertEqual(re.findall(r"easing:'(?:ease-out|ease-in)'", script), [])
        self.assertNotIn("matchMedia('(prefers-reduced-motion", script)


class Spring(unittest.TestCase):
    def test_it_goes_a_little_past_and_comes_to_rest(self):
        values = [float(v) for v in re.findall(r"-?\d*\.?\d+", motion.spring())]
        self.assertEqual((values[0], values[-1]), (0, 1))
        self.assertTrue(1.02 < max(values) < 1.1, max(values))
        self.assertGreater(values.index(max(values)), 3)                 # it rises before it overshoots
        self.assertLess(abs(values[-2] - 1), 0.01)                       # and has settled by the end

    def test_browsers_that_cannot_draw_it_get_a_stand_in(self):
        self.assertIn("--m-spring:cubic-bezier(", motion.TOKENS_CSS)
        self.assertIn("@supports (transition-timing-function:linear(0,1))", motion.TOKENS_CSS)
        self.assertLess(motion.TOKENS_CSS.index("--m-spring:cubic-bezier("), motion.TOKENS_CSS.index("@supports"))


class Levels(unittest.TestCase):
    def test_the_three_levels_are_offered_in_settings(self):
        page = pages()["glass"]
        for level, name in (("full", "Full"), ("subtle", "Subtle"), ("off", "Off")):
            self.assertIn(f'name="motion" value="{level}"><span>{name}</span>', page)

    def test_a_chosen_level_is_kept_and_put_on_the_page(self):
        s = store()
        s.upsert(item())
        srv = ListServer(s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                         request_mail_scan=lambda d: None, on_change=lambda: None)
        srv.save_prefs({"motion": "subtle"})
        self.assertEqual(prefs.load(s)["motion"], "subtle")
        page = report.render(report.build(s, Settings(), NOW), Settings(), "", NOW, "tok", prefs=prefs.load(s))
        self.assertIn('data-motion-pref="subtle"', page)
        with self.assertRaisesRegex(ValueError, "Unknown motion level"):
            srv.save_prefs({"motion": "frantic"})

    def test_off_stops_everything_and_zeroes_the_timings(self):
        css = motion.TOKENS_CSS
        off = css[css.index(":root[data-motion=off]{"):]
        self.assertIn("--m-fast:0ms", off)
        self.assertIn("transition:none!important;animation:none!important", off)

    def test_a_saved_level_that_makes_no_sense_is_forgotten(self):
        s = store()
        s.set_meta(prefs.KEY, '{"motion": "warp"}')
        self.assertEqual(prefs.load(s)["motion"], "")


if __name__ == "__main__":
    unittest.main()
