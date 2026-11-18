"""The phone, through a Telegram bot: linking with a one-time code, the same short lines, Done, and texting to add.
No AI, and the bot's token never in the settings file. Telegram itself is played by a stand-in."""
from __future__ import annotations

import json
import unittest
from datetime import timedelta
from unittest import mock

from helpers import NOW, item, store

import notices
import phone
import vault
from config import CONFIG_PATH, Settings
from server import ListServer

CHEM = "2026 Fall CHEM 1212 for A. Teacher"
ME, STRANGER = "4242", "9999"


class FakeTelegram:
    """Records what Birdbrain sends, and hands over what "came in"."""

    def __init__(self, token="1234567890:AAH-test", chat_id=""):
        self.token, self.chat_id, self.problem = token, chat_id, ""
        self.sent, self.edits, self.answers, self.incoming, self._n, self._u = [], [], [], [], 100, 1000

    @property
    def ready(self):
        return bool(self.token and self.chat_id)

    def send(self, text, buttons=None, silent=False, chat_id=""):
        self._n += 1
        self.sent.append({"id": self._n, "text": text, "buttons": buttons or [], "chat": chat_id or self.chat_id})
        return self._n

    def edit(self, message_id, text, buttons=None):
        self.edits.append({"id": message_id, "text": text, "buttons": buttons or []})
        return True

    def answer(self, callback_id, text):
        self.answers.append(text)

    def updates(self, offset, wait=0):
        got, self.incoming = [u for u in self.incoming if u["update_id"] >= offset], []
        return got

    # what the student does on their phone
    def types(self, text, chat=ME):
        self._u += 1
        self.incoming.append({"update_id": self._u, "message": {"chat": {"id": int(chat)}, "text": text}})

    def taps(self, message, button, chat=ME):
        self._u += 1
        self.incoming.append({"update_id": self._u,
                              "callback_query": {"id": "cb", "data": button["callback_data"],
                                                 "message": {"message_id": message["id"], "chat": {"id": int(chat)},
                                                             "text": "Due tonight: Chem Exp 15 Quiz, Chem Pre-lab",
                                                             "reply_markup": {"inline_keyboard": message["buttons"]}}}})


class Base(unittest.TestCase):
    def setUp(self):
        self.kept: dict[str, str] = {}
        for name, fake in (("available", lambda: True), ("get", lambda n, p="": self.kept.get(n, "")),
                           ("put", lambda n, v, p="": (self.kept.__setitem__(n, v) if v else self.kept.pop(n, None)) is None or True)):
            patch = mock.patch.object(vault, name, fake)
            patch.start()
            self.addCleanup(patch.stop)
        Settings().save()
        self.s, self.settings, self.tg = store(), Settings.load(), FakeTelegram()
        srv = ListServer(self.s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                         request_mail_scan=lambda d: None, on_change=lambda: None)
        self.p = phone.Phone(self.s, self.settings, add=lambda text: srv.quick({"text": text, "save": True}, NOW), tg=self.tg)

    def link(self):
        """Go through the setup as a student would: token, then /start with the code."""
        with mock.patch.object(phone, "Telegram", lambda token, chat="": self.tg):
            self.tg.me = lambda: {"username": "my_birdbrain_bot"}
            view = self.p.use_token("1234567890:AAH-test")
        self.tg.types(f"/start {view['code']}")
        self.p.chat(0, NOW)
        self.tg.sent.clear()
        return view


class Linking(Base):
    def test_it_is_off_until_turned_on(self):
        self.assertFalse(Settings().telegram_on)
        self.assertFalse(self.p.on)
        self.assertIsNone(self.p.chat(0, NOW))                                  # nothing is even asked of Telegram
        self.assertFalse(self.p.tell(notices.Notice("evening", "Due tonight", "Chem Pre-lab", [])))
        self.assertEqual(self.tg.sent, [])

    def test_the_token_goes_to_the_system_and_never_into_the_settings_file(self):
        view = self.link()
        self.assertEqual(self.kept, {"telegram_token": "1234567890:AAH-test"})
        on_disk = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertNotIn("AAH-test", on_disk)
        self.assertNotIn("token", on_disk)
        self.assertEqual(json.loads(on_disk)["telegram_bot"], "my_birdbrain_bot")
        self.assertRegex(view["code"], r"^\d{6}$")

    def test_a_token_telegram_refuses_changes_nothing(self):
        with mock.patch.object(phone, "Telegram", lambda token, chat="": self.tg):
            self.tg.me = lambda: None
            with self.assertRaisesRegex(ValueError, "didn't accept that token"):
                self.p.use_token("1234567890:wrong")
        with self.assertRaisesRegex(ValueError, "doesn't look like a bot token"):
            self.p.use_token("hello")
        self.assertEqual(self.kept, {})
        self.assertFalse(Settings.load().telegram_on)

    def test_without_a_safe_place_for_the_token_it_cant_be_turned_on(self):
        with mock.patch.object(vault, "available", lambda: False):
            with self.assertRaisesRegex(ValueError, "nowhere safe"):
                self.p.use_token("1234567890:AAH-test")
        self.assertNotIn("AAH", CONFIG_PATH.read_text(encoding="utf-8"))

    def test_the_code_links_the_chat_once(self):
        with mock.patch.object(phone, "Telegram", lambda token, chat="": self.tg):
            self.tg.me = lambda: {"username": "my_birdbrain_bot"}
            code = self.p.use_token("1234567890:AAH-test")["code"]
        self.tg.types(f"/start {code}")
        self.p.chat(0, NOW)
        self.assertEqual(Settings.load().telegram_chat, ME)
        self.assertTrue(self.p.on)
        self.assertIn("Linked.", self.tg.sent[-1]["text"])
        self.assertEqual(self.p.view()["code"], "")                             # used up
        self.assertTrue(self.p.view()["linked"])
        self.tg.types(f"/start {code}", chat=STRANGER)                          # someone else, same code, later
        self.p.chat(0, NOW)
        self.assertEqual(Settings.load().telegram_chat, ME)

    def test_five_wrong_codes_and_the_code_changes(self):
        with mock.patch.object(phone, "Telegram", lambda token, chat="": self.tg):
            self.tg.me = lambda: {"username": "my_birdbrain_bot"}
            code = self.p.use_token("1234567890:AAH-test")["code"]
        for _ in range(5):
            self.tg.types("/start 000000", chat=STRANGER)
            self.p.chat(0, NOW)
        self.assertNotEqual(self.p.view()["code"], code)
        self.assertEqual(Settings.load().telegram_chat, "")
        self.tg.types(f"/start {code}", chat=STRANGER)                          # the old one is dead
        self.p.chat(0, NOW)
        self.assertEqual(Settings.load().telegram_chat, "")

    def test_unlink_makes_a_new_code_and_off_forgets_everything(self):
        self.link()
        view = self.p.unlink()
        self.assertFalse(view["linked"])
        self.assertRegex(view["code"], r"^\d{6}$")
        view = self.p.turn_off()
        self.assertEqual((view["on"], view["bot"], view["code"], view["has_token"]), (False, "", "", False))
        self.assertEqual(self.kept, {})
        self.assertFalse(Settings.load().telegram_on)


class Saying(Base):
    def setUp(self):
        super().setUp()
        self.s.upsert(item("moodle:cm:1", "Exp 15 Quiz", NOW.replace(hour=23, minute=59), course=CHEM, url="https://example.edu/1"))
        self.s.upsert(item("moodle:cm:2", "Pre-lab", NOW.replace(hour=23, minute=59), course=CHEM))
        self.link()

    def test_the_same_line_as_the_pc_with_a_button_per_card(self):
        said = notices.Notices(self.s, self.settings).evening(NOW.replace(hour=19))
        self.assertTrue(self.p.tell(said))
        msg = self.tg.sent[-1]
        self.assertEqual(msg["text"], "<b>Due tonight:</b> Chem Exp 15 Quiz, Chem Pre-lab")
        self.assertEqual([row[0]["text"] for row in msg["buttons"]], ["✓ Chem Exp 15 Quiz", "✓ Chem Pre-lab"])
        self.assertEqual(msg["chat"], ME)

    def test_one_card_gets_open_and_done(self):
        self.p.tell(notices.Notice("new", "New", "Chem Exp 15 Quiz (Nov 18)", ["moodle:cm:1"]))
        self.assertEqual([b["text"] for b in self.tg.sent[-1]["buttons"][0]], ["Open", "✓ Done"])
        self.assertEqual(self.tg.sent[-1]["buttons"][0][0]["url"], "https://example.edu/1")

    def test_tapping_done_ticks_the_card_off_on_the_pc(self):
        self.p.tell(notices.Notices(self.s, self.settings).evening(NOW.replace(hour=19)))
        msg = self.tg.sent[-1]
        self.tg.taps(msg, msg["buttons"][0][0])
        self.assertTrue(self.p.chat(0, NOW))
        self.assertIsNotNone(self.s.get("moodle:cm:1").done_at)
        self.assertIsNone(self.s.get("moodle:cm:2").done_at)
        self.assertEqual(self.tg.answers, ["Ticked off ✓"])
        edit = self.tg.edits[-1]
        self.assertIn("✓ Chem Exp 15 Quiz", edit["text"])
        self.assertEqual([row[0]["text"] for row in edit["buttons"]], ["✓ Chem Pre-lab"])   # the other button stays
        self.tg.taps(msg, msg["buttons"][0][0])                                 # tapped twice
        self.assertFalse(self.p.chat(0, NOW))
        self.assertEqual(self.tg.answers[-1], "Already done")

    def test_a_tap_from_another_chat_is_ignored(self):
        self.p.tell(notices.Notices(self.s, self.settings).evening(NOW.replace(hour=19)))
        msg = self.tg.sent[-1]
        self.tg.taps(msg, msg["buttons"][0][0], chat=STRANGER)
        self.assertFalse(self.p.chat(0, NOW))
        self.assertIsNone(self.s.get("moodle:cm:1").done_at)

    def test_list_sends_what_is_due_or_says_nothing_is(self):
        self.tg.types("/list")
        self.p.chat(0, NOW.replace(hour=12))
        self.assertTrue(self.tg.sent[0]["text"].startswith("<b>Today:</b> Chem Exp 15 Quiz, Chem Pre-lab"))
        self.s.set_done("moodle:cm:1", True)
        self.s.set_done("moodle:cm:2", True)
        self.tg.sent.clear()
        self.tg.types("/list")
        self.p.chat(0, NOW.replace(hour=12))
        self.assertEqual([m["text"] for m in self.tg.sent], ["Nothing due today or tonight."])

    def test_scan_asks_the_app_to_scan(self):
        import threading
        asked = threading.Event()
        self.p.actions["scan"] = asked.set
        self.tg.types("/scan")
        self.p.chat(0, NOW)
        self.assertTrue(asked.wait(2))


class Texting(Base):
    def setUp(self):
        super().setUp()
        self.link()

    def manual(self):
        return [i for i in self.s.open_items() if i.source == "manual"]

    def test_a_text_goes_through_quick_write_and_onto_the_list(self):
        self.tg.types("dentist tue 3pm #appointment")
        self.assertTrue(self.p.chat(0, NOW))
        (added,) = self.manual()
        tuesday = NOW + timedelta(days=6)
        self.assertEqual((added.title, added.due, added.label), ("Dentist", tuesday.replace(hour=15, minute=0), "appointment"))
        reply = self.tg.sent[-1]
        self.assertEqual(reply["text"], f"<b>Added:</b> Dentist\nTuesday, Nov {tuesday.day}, 3 PM · Appointment")
        self.assertEqual(reply["buttons"][0][0]["text"], "Undo")

    def test_undo_takes_it_off_again(self):
        self.tg.types("call mom")
        self.p.chat(0, NOW)
        reply = self.tg.sent[-1]
        self.tg.taps(reply, reply["buttons"][0][0])
        self.assertTrue(self.p.chat(0, NOW))
        self.assertEqual(self.manual(), [])
        self.assertEqual(self.tg.answers[-1], "Removed")

    def test_a_stranger_can_add_nothing(self):
        self.tg.types("free pizza friday", chat=STRANGER)
        self.assertFalse(self.p.chat(0, NOW))
        self.assertEqual(self.manual(), [])
        self.assertEqual(self.tg.sent, [])

    def test_an_unknown_command_gets_the_short_help(self):
        self.tg.types("/what")
        self.p.chat(0, NOW)
        self.assertIn("/list", self.tg.sent[-1]["text"])
        self.assertEqual(self.manual(), [])

    def test_nothing_in_the_module_talks_to_an_ai(self):
        import inspect
        import telegram
        for module in (phone, telegram, notices):
            code = inspect.getsource(module).lower()
            for word in ("api_key", "brain.", "/v1/", "completion", "prompt"):
                self.assertNotIn(word, code)


if __name__ == "__main__":
    unittest.main()
