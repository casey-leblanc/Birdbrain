"""Your phone, through a Telegram bot of your own (telegram.py). Off unless you turn it on: Settings › Advanced.

What it does, with no AI anywhere:

- The same short lines as the PC's notifications (notices.py), at the same moments: "Due tonight: Chem Exp 15 Quiz,
  Pre-lab". Under each, a button per card: tap it and the card is ticked off on the PC at once.
- Anything you text the bot is read the way quick write reads it: "dentist tue 3pm #appointment" adds that to your
  list and says how it was understood, with Undo.
- /list sends what's due today and tonight; /scan scans now.

Linking: Settings shows a six-digit code; you send the bot "/start <code>". The code works once. Five wrong tries
and it changes, so it can't be guessed by trying them all. Only the linked chat is ever listened to.

The bot's token is kept by the system (vault.py), never in the settings file.
"""
from __future__ import annotations

import json
import logging
import secrets
import threading
from datetime import datetime

import notices
import vault
from config import Settings
from notices import Notice
from store import Item, Store
from telegram import Telegram, esc

log = logging.getLogger(__name__)

TOKEN = "telegram_token"
BUTTONS = 4          # at most this many "✓ name" buttons under one message
HELP = ("Text me something to add it to your list, like “dentist tue 3pm #appointment”.\n"
        "/list: what's due today and tonight\n/scan: scan your sites now")


def new_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


class Phone:
    def __init__(self, store: Store, settings: Settings, add=None, tg: Telegram | None = None):
        """`add(text)` puts a line of quick write on the list and returns how it was read (server.quick)."""
        self.store, self.settings, self.add = store, settings, add
        self.tg = tg or Telegram(self.token(), settings.telegram_chat)
        self.actions: dict = {}     # what /scan does, set by the app: {"scan": fn}
        self.lock = threading.RLock()

    # --- the token, the code, the link ------------------------------------------------------------------------------
    @staticmethod
    def token() -> str:
        return (vault.get(TOKEN) or "") if vault.available() else ""

    @property
    def on(self) -> bool:
        return bool(self.settings.telegram_on and self.tg.ready)

    def _meta(self, key: str, default=None):
        raw = self.store.get_meta("phone:" + key)
        return json.loads(raw) if raw else default

    def _set(self, key: str, value) -> None:
        self.store.set_meta("phone:" + key, json.dumps(value))

    def _save(self, **changes) -> None:
        s = Settings.load()
        for k, v in changes.items():
            setattr(s, k, v)
            setattr(self.settings, k, v)
        s.save()

    def view(self) -> dict:
        """For Settings: where the setup has got to."""
        linked = bool(self.settings.telegram_chat)
        return {"available": vault.available(), "on": bool(self.settings.telegram_on), "bot": self.settings.telegram_bot,
                "has_token": bool(self.tg.token), "linked": linked, "code": "" if linked else (self._meta("code") or "")}

    def use_token(self, token: str) -> dict:
        """Step 2: check the token with Telegram, keep it with the system, and make the code for step 3."""
        token = token.strip()
        if not vault.available():
            raise ValueError("This computer has nowhere safe to keep the bot's token, so Telegram can't be turned on here.")
        if not token or ":" not in token or len(token) > 100:
            raise ValueError("That doesn't look like a bot token. BotFather's message has it on a line of its own, "
                             "like 1234567890:AAH…")
        bot = Telegram(token).me()
        if not bot:
            raise ValueError("Telegram didn't accept that token. Copy it again from BotFather's message, all of it.")
        if not vault.put(TOKEN, token):
            raise ValueError("The token couldn't be kept safely on this computer, so nothing was changed.")
        with self.lock:
            self.tg = Telegram(token, "")
            self._save(telegram_on=True, telegram_bot=str(bot.get("username", "")), telegram_chat="")
            self._set("code", new_code())
            self._set("wrong_codes", 0)
        log.info("Telegram bot set: @%s", self.settings.telegram_bot)
        return self.view()

    def unlink(self) -> dict:
        """Forget the linked chat and make a new code, to link another."""
        with self.lock:
            self._save(telegram_chat="")
            self.tg.chat_id = ""
            self._set("code", new_code())
        return self.view()

    def turn_off(self) -> dict:
        """Off, and everything forgotten: the token, the chat, the code."""
        with self.lock:
            if vault.available():
                vault.put(TOKEN, "")
            self.tg = Telegram("", "")
            self._save(telegram_on=False, telegram_bot="", telegram_chat="")
            self._set("code", "")
        log.info("Telegram turned off; the bot's token was removed from this computer")
        return self.view()

    def _link(self, chat: str, code: str) -> None:
        want = self._meta("code") or ""
        if not want or code != want:
            wrong = self._meta("wrong_codes", 0) + 1
            if wrong >= 5:
                wrong = 0
                self._set("code", new_code())
                log.warning("Five wrong link codes: the code has changed (Settings shows the new one)")
            self._set("wrong_codes", wrong)
            self.tg.send("Send /start followed by the code in Birdbrain's Settings, under Advanced › Telegram.", chat_id=chat)
            return
        self._save(telegram_chat=chat)
        self.tg.chat_id = chat
        self._set("code", "")          # it worked once; it won't again
        self._set("wrong_codes", 0)
        log.info("Telegram chat linked")
        self.tg.send("<b>Linked.</b> What Birdbrain says on your PC it now says here too.\n" + esc(HELP))

    # --- saying things ------------------------------------------------------------------------------------------------
    def _nicks(self) -> dict:
        import prefs
        return prefs.load(self.store).get("courses", {})

    def _buttons(self, ids: list[str]) -> list[list[dict]]:
        items = [i for i in (self.store.get(x) for x in ids) if i and not i.done_at][:BUTTONS]
        if len(items) == 1:
            row = [Telegram.done(items[0].id)]
            if items[0].url:
                row.insert(0, Telegram.link("Open", items[0].url))
            return [row]
        nicks = self._nicks()
        return [[{"text": ("✓ " + notices.short(i, nicks))[:40], "callback_data": ("d:" + i.id)[:64]}] for i in items]

    def tell(self, notice: Notice | None) -> bool:
        """The same line the PC shows, with a button per card. True if it went."""
        if not notice or not self.on:
            return False
        with self.lock:
            return self.tg.send(f"<b>{esc(notice.title)}:</b> {esc(notice.text)}", self._buttons(notice.ids)) is not None

    def listing(self, now: datetime | None = None) -> None:
        """/list: this morning's line and tonight's, or that nothing is due."""
        now = now or datetime.now()
        n = notices.Notices(self.store, self.settings)
        said = [x for x in (n.morning(now), n.evening(now)) if x]
        if not said:
            self.tg.send("Nothing due today or tonight.", silent=True)
            return
        seen: list[str] = []
        for x in said:
            if x.ids != seen:
                self.tg.send(f"<b>{esc(x.title)}:</b> {esc(x.text)}", self._buttons(x.ids), silent=True)
                seen = x.ids

    # --- hearing things -----------------------------------------------------------------------------------------------
    def chat(self, wait: int = 25, now: datetime | None = None) -> bool | None:
        """Wait up to `wait` seconds for something from the chat and act on it. True if the list changed; None if
        Telegram couldn't be asked (off, no token, or offline), so the caller waits a little before trying again."""
        if not self.settings.telegram_on or not self.tg.token:
            return None
        offset = self._meta("offset", 0)
        updates = self.tg.updates(offset, wait)   # not under the lock: this is the wait
        if updates is None:
            return None
        if not updates:
            return False
        with self.lock:
            return self._read(updates, offset, now or datetime.now())

    def _find(self, key: str) -> Item | None:
        """The card a button names. A long id is cut to fit a button, so the start of one is enough."""
        return self.store.get(key) or next((i for i in self.store.open_items() if i.id.startswith(key)), None)

    def _read(self, updates: list[dict], offset: int, now: datetime) -> bool:
        changed = False
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
            if cq := u.get("callback_query"):
                msg, data = cq.get("message") or {}, cq.get("data") or ""
                if not self.settings.telegram_chat or str((msg.get("chat") or {}).get("id", "")) != self.settings.telegram_chat:
                    continue
                changed |= self._tapped(cq["id"], data, msg)
            elif m := u.get("message"):
                chat, text = str((m.get("chat") or {}).get("id", "")), (m.get("text") or "").strip()
                if text.startswith("/start") and not self.settings.telegram_chat:
                    self._link(chat, text[6:].strip())
                elif not self.settings.telegram_chat or chat != self.settings.telegram_chat:
                    continue   # not your chat: ignored, whatever it says
                elif text.startswith("/list"):
                    self.listing(now)
                elif text.startswith("/scan"):
                    self.tg.send("Scanning now. Anything new will show up here.", silent=True)
                    if fn := self.actions.get("scan"):
                        threading.Thread(target=fn, daemon=True, name="phone-scan").start()
                elif text.startswith("/"):
                    self.tg.send(esc(HELP), silent=True)
                elif text:
                    changed |= self._typed(text)
        self._set("offset", offset)
        return changed

    def _tapped(self, callback_id: str, data: str, msg: dict) -> bool:
        if data.startswith("x:"):      # Undo on something just added from the phone
            item = self._find(data[2:])
            if item and item.source == "manual":
                self.store.delete(item.id)
                self.tg.answer(callback_id, "Removed")
                if msg.get("message_id"):
                    self.tg.edit(msg["message_id"], f"<s>{esc(msg.get('text') or item.title)}</s>\nRemoved.")
                return True
            self.tg.answer(callback_id, "Already gone")
            return False
        item = self._find(data[2:]) if data.startswith("d:") else None
        if not item or item.done_at:
            self.tg.answer(callback_id, "Already done")
            return False
        self.store.set_done(item.id, True)
        log.info("Ticked off from the phone: %s", item.source)
        self.tg.answer(callback_id, "Ticked off ✓")
        if msg.get("message_id") and msg.get("text"):
            left = [row for row in ((msg.get("reply_markup") or {}).get("inline_keyboard") or [])
                    if not any(b.get("callback_data") == data for b in row)]
            self.tg.edit(msg["message_id"], esc(msg["text"]) + f"\n✓ {esc(notices.short(item, self._nicks()))}", left)
        return True

    def _typed(self, text: str) -> bool:
        """A plain message: quick write reads it, and it goes on the list."""
        if not self.add:
            self.tg.send("Birdbrain's list isn't open on the PC right now, so I couldn't add that.", silent=True)
            return False
        try:
            got = self.add(text[:300])
        except ValueError as e:
            self.tg.send(esc(str(e)), silent=True)
            return False
        when = got["day"] + (f", {notices.clock(datetime.fromisoformat(got['date'] + 'T' + got['time']))}" if got.get("time") else "")
        tags = "".join(f" · {esc(c['says'])}" for c in got.get("chips", []) if c.get("what") in ("label", "course", "kind"))
        self.tg.send(f"<b>Added:</b> {esc(got['title'])}\n{esc(when)}{tags}",
                     [[{"text": "Undo", "callback_data": ("x:" + got["id"])[:64]}]], silent=True)
        return True
