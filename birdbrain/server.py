"""Serves the list page from inside Birdbrain so the page can save things:
ticking items off, adding and editing your own items, display preferences,
and starting an inbox scan.

Security: it listens on 127.0.0.1 only, and every request must carry a random
token that changes each time Birdbrain starts (in the URL for the page, in a
header for changes). Requests with any other Host header are refused, and
there are no CORS headers, so other websites can't call it.
"""
from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import threading
import uuid
from datetime import date, datetime, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

import glass
import prefs
from store import Item, Store

log = logging.getLogger(__name__)

KIND_LEVEL = {"assignment": ("assignment", ""), "exam": ("test", "exam"),
              "quiz": ("test", "quiz"), "event": ("event", "")}
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; font-src data:; "
       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
TOKEN_HEADER = "X-Birdbrain-Token"


class ListServer:
    def __init__(self, store: Store, render_page: Callable[[str], str], render_board: Callable[[str], str],
                 status: Callable[[], dict], request_mail_scan: Callable[[date], None],
                 on_change: Callable[[], None], port: int = 0):
        self.store = store
        self.token = secrets.token_urlsafe(24)
        self.render_page, self.render_board = render_page, render_board
        self.status, self.request_mail_scan, self.on_change = status, request_mail_scan, on_change
        try:  # keep the same port between runs when it's free
            self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        except OSError:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?token={self.token}"

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="list-server").start()
        log.info("List page served at http://127.0.0.1:%s/", self.port)

    def stop(self) -> None:
        self.httpd.shutdown()

    # --- API actions -------------------------------------------------------------
    def set_done(self, body: dict) -> dict:
        ok = self.store.set_done(str(body.get("id", "")), bool(body.get("done")))
        if not ok:
            raise ValueError("No such item")
        self.on_change()
        return {"ok": True}

    def _manual(self, body: dict, item_id: str) -> Item:
        """Build a validated item you're adding or editing."""
        title = " ".join(str(body.get("title", "")).split())
        if not 1 <= len(title) <= 200:
            raise ValueError("Give the item a title (up to 200 characters).")
        if body.get("kind") not in KIND_LEVEL:
            raise ValueError("Unknown item type.")
        try:
            day = date.fromisoformat(str(body.get("date", "")))
        except ValueError:
            raise ValueError("Pick a due date.")
        t = str(body.get("time") or "")
        if t and not re.fullmatch(r"\d{2}:\d{2}", t):
            raise ValueError("Time should look like 14:30.")
        kind, level = KIND_LEVEL[body["kind"]]
        return Item(id=item_id, source="manual", kind=kind, title=title,
                    due=datetime.combine(day, time.fromisoformat(t) if t else time(23, 59)),
                    course=" ".join(str(body.get("course", "")).split())[:40],
                    detail=" ".join(str(body.get("notes", "")).split())[:300], level=level)

    def add_item(self, body: dict) -> dict:
        item = self._manual(body, f"manual:{uuid.uuid4().hex[:12]}")
        self.store.upsert(item)
        self.on_change()
        return {"ok": True, "id": item.id}

    def update_item(self, body: dict) -> dict:
        old = self.store.get(str(body.get("id", "")))
        if not old or old.source != "manual":
            raise ValueError("Only items you added yourself can be edited.")
        self.store.upsert(self._manual(body, old.id))   # keeps its ticked-off state
        self.on_change()
        return {"ok": True, "id": old.id}

    def delete_item(self, body: dict) -> dict:
        item = self.store.get(str(body.get("id", "")))
        if not item or item.source != "manual":
            raise ValueError("Only items you added yourself can be deleted.")
        self.store.delete(item.id)
        self.on_change()
        return {"ok": True}

    def save_prefs(self, body: dict) -> dict:
        return {"ok": True, "prefs": prefs.update(self.store, body)}

    def scan_mail(self, body: dict) -> dict:
        try:
            since = date.fromisoformat(str(body.get("since", "")))
        except ValueError:
            raise ValueError("Pick a date to scan back to.")
        if since > date.today():
            raise ValueError("Pick a date in the past.")
        self.request_mail_scan(since)
        return {"ok": True}

    # --- HTTP plumbing ------------------------------------------------------------
    def _handler(self):
        srv = self
        routes = {"/api/done": srv.set_done, "/api/items": srv.add_item, "/api/items/update": srv.update_item,
                  "/api/items/delete": srv.delete_item, "/api/prefs": srv.save_prefs,
                  "/api/scan-mail": srv.scan_mail}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                log.debug("list server: " + fmt, *args)

            def _send(self, status: int, body: str, ctype: str) -> None:
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", CSP)
                self.end_headers()
                self.wfile.write(data)

            def _photo(self, name: str) -> None:
                """A background photo for the glass layout (assets/backgrounds)."""
                path = glass.BG_DIR / f"{name}.jpg"
                if not re.fullmatch(r"[a-z]+-(light|dark)(-thumb)?", name) or not path.is_file():
                    return self._send(404, "Not found", "text/plain")
                data = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, max-age=86400")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)

            def _json(self, status: int, obj: dict) -> None:
                self._send(status, json.dumps(obj), "application/json")

            def _host_ok(self) -> bool:
                return self.headers.get("Host", "") in (f"127.0.0.1:{srv.port}", f"localhost:{srv.port}")

            def _token_ok(self, given: str | None) -> bool:
                return bool(given) and hmac.compare_digest(given, srv.token)

            def do_GET(self):
                url = urlparse(self.path)
                token = parse_qs(url.query).get("token", [None])[0]
                if not self._host_ok() or not self._token_ok(token):
                    return self._send(403, "<p style='font:16px system-ui;margin:2em'>Open your list from the "
                                           "Birdbrain icon in the system tray.</p>", "text/html; charset=utf-8")
                try:
                    if url.path == "/":
                        return self._send(200, srv.render_page(srv.token), "text/html; charset=utf-8")
                    if url.path == "/board":
                        return self._send(200, srv.render_board(srv.token), "text/html; charset=utf-8")
                    if url.path == "/api/status":
                        return self._json(200, srv.status())
                    if url.path.startswith("/bg/") and url.path.endswith(".jpg"):
                        return self._photo(url.path[4:-4])
                except Exception:
                    log.exception("list server GET %s failed", url.path)
                    return self._send(500, "Birdbrain couldn't build the page; see the log.", "text/plain")
                self._send(404, "Not found", "text/plain")

            def do_POST(self):
                action = routes.get(urlparse(self.path).path)
                if not self._host_ok() or not self._token_ok(self.headers.get(TOKEN_HEADER)):
                    return self._json(403, {"error": "Forbidden"})
                if not action or not self.headers.get("Content-Type", "").startswith("application/json"):
                    return self._json(404, {"error": "Not found"})
                try:
                    length = min(int(self.headers.get("Content-Length", 0)), 32_768)
                    body = json.loads(self.rfile.read(length) or b"{}")
                    return self._json(200, action(body if isinstance(body, dict) else {}))
                except ValueError as e:
                    return self._json(400, {"error": str(e)})
                except Exception:
                    log.exception("list server POST %s failed", self.path)
                    return self._json(500, {"error": "Something went wrong; see the log."})

        return Handler
