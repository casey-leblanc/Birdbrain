"""Backup: what is yours, in one file. Export it here, import it on another computer.

What is yours is what no scan can bring back: the items you added yourself (open and done, with their labels, notes,
times and how often they repeat), your labels, and the colours and nicknames you gave your classes. Everything from
Moodle and your email comes back by itself when you sign in on the other computer, so it isn't in the file.

The file is plain JSON, "Birdbrain-backup-20261118.json", saved to your Downloads folder. Importing adds what
isn't there yet: an item with the same title, time and label as one already on the list is left alone, so importing
the same file twice changes nothing. Nothing is uploaded; you carry the file yourself.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path

import prefs
import repeats
from config import DATA_DIR
from store import LABEL_ID, Item, Store

FORMAT = 1
MAX_ITEMS = 5000


def export(store: Store, now: datetime | None = None) -> dict:
    with store._lock:
        ids = [r[0] for r in store._db.execute("SELECT id FROM items WHERE source='manual' ORDER BY due").fetchall()]
    items = []
    for i in (store.get(x) for x in ids):
        items.append({"title": i.title, "kind": i.kind, "level": i.level, "due": i.due.isoformat(timespec="minutes"),
                      "timed": i.timed, "course": i.course, "notes": i.detail, "label": i.label, "repeat": i.repeat,
                      "done_at": i.done_at.isoformat(timespec="seconds") if i.done_at else None,
                      "planned": i.planned.isoformat() if i.planned else None})
    p = prefs.load(store)
    return {"birdbrain_backup": FORMAT, "made": (now or datetime.now()).isoformat(timespec="minutes"),
            "labels": p.get("labels", []), "courses": p.get("courses", {}), "items": items}


def save(data: dict, folder: Path | None = None, now: datetime | None = None) -> Path:
    folder = folder or (Path.home() / "Downloads")
    if not folder.is_dir():
        folder = DATA_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"Birdbrain-backup-{(now or datetime.now()):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def _item(raw: dict, labels: set[str]) -> Item | None:
    """One item from a backup file, checked; None if it isn't one."""
    try:
        title = " ".join(str(raw["title"]).split())[:200]
        due = datetime.fromisoformat(str(raw["due"]))
        kind = raw.get("kind") if raw.get("kind") in ("assignment", "test", "event") else "assignment"
        level = raw.get("level") if raw.get("level") in ("exam", "quiz") else ""
        label = str(raw.get("label") or "")
        done = datetime.fromisoformat(raw["done_at"]) if raw.get("done_at") else None
        planned = date.fromisoformat(raw["planned"]) if raw.get("planned") else None
    except (KeyError, TypeError, ValueError):
        return None
    if not title:
        return None
    return Item(id=f"manual:{uuid.uuid4().hex[:12]}", source="manual", kind=kind, title=title, due=due, level=level,
                course=" ".join(str(raw.get("course") or "").split())[:40], detail=" ".join(str(raw.get("notes") or "").split())[:300],
                label=label if label in labels else "", timed=raw.get("timed") if isinstance(raw.get("timed"), bool) else None,
                repeat=raw.get("repeat") if repeats.valid(str(raw.get("repeat") or "")) else "", done_at=done, planned=planned)


def restore(store: Store, data) -> dict:
    """Add what a backup holds and isn't here yet. Says how much was added and how much was already here."""
    if not isinstance(data, dict) or data.get("birdbrain_backup") != FORMAT or not isinstance(data.get("items"), list):
        raise ValueError("That isn't a Birdbrain backup file. Choose the Birdbrain-backup-….json you exported.")
    p = prefs.load(store)
    have = {x["id"] for x in p.get("labels", [])}
    new_labels = [x for x in data.get("labels") or [] if isinstance(x, dict) and LABEL_ID.fullmatch(str(x.get("id", "")))
                  and x["id"] not in have and str(x.get("name", "")).strip()]
    patch = {}
    if new_labels:
        patch["labels"] = p.get("labels", []) + [{"id": x["id"], "name": str(x["name"])[:24], "color": str(x.get("color", "#7c9a5e"))[:9]}
                                                 for x in new_labels]
    courses = {k: v for k, v in (data.get("courses") or {}).items() if isinstance(v, dict) and k not in p.get("courses", {})}
    if courses:
        patch["courses"] = courses
    if patch:
        prefs.update(store, patch)
    labels = {x["id"] for x in prefs.load(store).get("labels", [])}
    with store._lock:
        rows = store._db.execute("SELECT title, due, label FROM items WHERE source='manual'").fetchall()
    here = {(t, d, lab or "") for t, d, lab in rows}
    added = skipped = 0
    for raw in data["items"][:MAX_ITEMS]:
        item = _item(raw, labels) if isinstance(raw, dict) else None
        if item is None:
            continue
        key = (item.title, item.due.isoformat(timespec="minutes"), item.label)
        if key in here:
            skipped += 1
            continue
        here.add(key)
        store.upsert(item)
        if item.done_at:
            with store._lock, store._db:
                store._db.execute("UPDATE items SET done_at=? WHERE id=?", (item.done_at.isoformat(timespec="seconds"), item.id))
        if item.planned:
            store.plan(item.id, item.planned)
        added += 1
    store.touch()
    return {"added": added, "skipped": skipped, "labels": len(new_labels)}


def _n(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def action(store: Store, body: dict, folder: Path | None = None, reveal=None) -> dict:
    """Settings > Advanced > Backup: {"export": true} saves the file and says where; {"import": {...}} adds what the
    chosen file holds."""
    if body.get("export"):
        data = export(store)
        path = save(data, folder)
        if reveal:
            try:
                reveal(path)
            except Exception:
                pass
        return {"ok": True, "saved": path.name,
                "message": f"Saved {path.name} in your {path.parent.name} folder: {_n(len(data['items']), 'item')} of yours and "
                           f"{_n(len(data['labels']), 'label')}. Copy it to the other computer and import it there."}
    if "import" in body:
        got = restore(store, body["import"])
        if not got["added"] and not got["labels"]:
            return {"ok": True, **got, "message": "Everything in that file is already here. Nothing was changed."}
        also = f" {_n(got['skipped'], 'item')} were already here." if got["skipped"] else ""
        labels = f" and {_n(got['labels'], 'label')}" if got["labels"] else ""
        return {"ok": True, **got, "prefs": prefs.load(store), "message": f"Added {_n(got['added'], 'item')}{labels}.{also}"}
    raise ValueError("Export, or choose a file to import.")
