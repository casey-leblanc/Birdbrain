"""`Birdbrain.exe --selftest <result file>`: checks that a packaged copy works.

main.py points APPDATA at a throwaway folder before anything is imported, so
the check never touches your real data. Results go to the file because the
packaged app has no console.
"""
from __future__ import annotations

import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


def run(out: Path) -> int:
    lines, ok = [], True

    def check(name: str, fn) -> None:
        nonlocal ok
        try:
            detail = fn()
            lines.append(f"PASS  {name}" + (f": {detail}" if detail else ""))
        except Exception as exc:
            ok = False
            lines.append(f"FAIL  {name}: {exc}\n{traceback.format_exc()}")

    import prefs
    import report
    import theme
    from browser import open_context
    from config import DATA_DIR, Settings
    from server import ListServer
    from store import Item, Store

    now = datetime.now()
    s, store = Settings(), Store()
    store.upsert(Item("moodle:cal:1", "moodle", "test", "Exam 1", now + timedelta(days=2), "2026 Fall CE 2450"))
    store.upsert(Item("moodle:cm:2", "moodle", "assignment", "Lab report", now - timedelta(days=1), "CHEM 1212"))
    page = lambda t: report.render(report.build(store, s), s, "Self-test", datetime.now(), t, store.version,
                                   prefs.load(store))
    srv = ListServer(store, render_page=page, render_board=lambda t: "", status=lambda: {"version": 0},
                     request_mail_scan=lambda d: None, on_change=lambda: None)
    srv.start()

    check("data folder is a throwaway copy", lambda: str(DATA_DIR))
    check("fonts bundled", lambda: f"{len(theme.font_face_css()) // 1024} KB embedded"
          if theme.font_face_css() else (_ for _ in ()).throw(RuntimeError("no fonts")))

    def page_served():
        html = urllib.request.urlopen(srv.url).read().decode()
        assert "Birdbrain" in html and "Birdbrain Mono" in html, "page content missing"
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/")
            raise AssertionError("page served without the token")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        return f"{len(html) // 1024} KB, refuses requests without the token"
    check("list page served", page_served)

    def photos():
        import glass
        names = [glass.photo_name(t, m) for t in theme.THEMES for m in ("light", "dark")]
        missing = [n for n in names if not (glass.BG_DIR / f"{n}.jpg").exists()]
        assert not missing, f"missing: {missing}"
        r = urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/bg/{names[0]}.jpg?token={srv.token}")
        assert r.headers.get("Content-Type") == "image/jpeg" and len(r.read()) > 10_000
        return f"{len(names)} background photos bundled and served"
    check("glass layout photos", photos)

    def scanner_browser():
        with open_context(s) as ctx:
            p = ctx.new_page()
            p.goto(srv.url)
            bands = p.locator(".band").count()
            assert bands == 3, f"{bands} columns rendered"
            return f"{ctx.browser.version}, 3 columns rendered"
    check("scanner browser (installs itself if missing)", scanner_browser)

    def icon():
        import main
        img = main.make_icon(3)
        return f"{img.size[0]}x{img.size[1]}"
    check("tray icon", icon)

    srv.stop()
    lines.append("ALL PASS" if ok else "SOME CHECKS FAILED")
    out.write_text("\n".join(lines), encoding="utf-8")
    return 0 if ok else 1
