"""Telegram: the same short notifications on your phone, from a bot of your own (free; Telegram on iOS or Android).

Off unless you turn it on in Settings › Advanced › Telegram. You make the bot in Telegram (message @BotFather, send
/newbot, pick a name) and paste its token into Settings. Then you send the bot "/start <code>" from your phone, with
the code Settings shows; Birdbrain links to that chat and ignores every other. It talks to Telegram's Bot API over
HTTPS: messages go out, and Birdbrain keeps one request open that Telegram answers the moment something comes in (a
tap on Done, or something you typed), so nothing has to reach your PC from outside.

There is no AI here: what you type to the bot is read by the same plain rules as quick write (phone.py).
"""
from __future__ import annotations

import html
import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

API = "https://api.telegram.org"
MAX_CHARS = 4000   # Telegram allows 4096 per message


class Telegram:
    def __init__(self, token: str, chat_id: str = "", opener=None):
        self.token, self.chat_id = token.strip(), str(chat_id or "").strip()
        self._open = opener or urllib.request.urlopen
        self.problem = ""

    @property
    def ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def call(self, method: str, _timeout: float = 30, **params):
        """One Bot API call; its result, or None (with the reason in `problem`)."""
        if not self.token:
            self.problem = "no bot token"
            return None
        req = urllib.request.Request(f"{API}/bot{self.token}/{method}", data=json.dumps(params).encode("utf-8"),
                                     method="POST", headers={"Content-Type": "application/json"})
        try:
            with self._open(req, timeout=_timeout) as r:
                body = json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read() or b"{}")
            except ValueError:
                body = {}
            desc = body.get("description", f"HTTP {e.code}")
            if "message is not modified" in desc:
                return True
            self.problem = "Telegram refused the bot token" if e.code in (401, 404) else f"Telegram said: {desc}"
            log.warning("Telegram %s: %s", method, desc)
            return None
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.problem = "couldn't reach Telegram"
            log.warning("Telegram %s failed: %s", method, e)
            return None
        if not body.get("ok"):
            self.problem = f"Telegram said: {body.get('description', 'no')}"
            return None
        self.problem = ""
        return body.get("result")

    def me(self) -> dict | None:
        return self.call("getMe")

    def send(self, text: str, buttons: list[list[dict]] | None = None, silent: bool = False,
             chat_id: str = "") -> int | None:
        """Send a message (HTML: build it with esc()); its message id, or None."""
        params = {"chat_id": chat_id or self.chat_id, "text": _fit(text), "parse_mode": "HTML",
                  "link_preview_options": {"is_disabled": True}, "disable_notification": silent}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        r = self.call("sendMessage", **params)
        return r.get("message_id") if isinstance(r, dict) else None

    def edit(self, message_id: int, text: str, buttons: list[list[dict]] | None = None) -> bool:
        params = {"chat_id": self.chat_id, "message_id": message_id, "text": _fit(text), "parse_mode": "HTML",
                  "link_preview_options": {"is_disabled": True}, "reply_markup": {"inline_keyboard": buttons or []}}
        return self.call("editMessageText", **params) is not None

    def updates(self, offset: int, wait: int = 0) -> list[dict] | None:
        """What's come in since `offset` (taps on buttons and messages to the bot), waiting up to `wait` seconds for
        something to (Telegram holds the request open and answers the moment there is)."""
        return self.call("getUpdates", _timeout=wait + 15, offset=offset, timeout=wait,
                         allowed_updates=["message", "callback_query"])

    def answer(self, callback_id: str, text: str) -> None:
        self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    # --- buttons ------------------------------------------------------------------------------------------------
    @staticmethod
    def link(label: str, url: str) -> dict:
        return {"text": label[:40], "url": url}

    @staticmethod
    def done(item_id: str) -> dict:
        return {"text": "✓ Done", "callback_data": ("d:" + item_id)[:64]}


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def _fit(text: str) -> str:
    """Under Telegram's length limit, cut at a line (the text is HTML, so never inside a tag)."""
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    return cut[:cut.rfind("\n")] + "\n…"
