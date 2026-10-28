"""AgyBot - notification events (Phase 11).

Every routine finish is recorded here (own SQLite DB, separate from
agybot.db so the OpenBot->AgyBot migration never collides with it):

  data/notifications.db, table notification_events:
    id, routine_id, routine_name, bot_name, status (done/failed),
    title, summary, finished_at (ISO 8601 WITA), created_at (epoch)

The APK (v2, polling) reads events via GET /api/notifications?since=...
When FCM is configured, record_routine_finished() also fires a push
via fcm.send_push() — best-effort, never allowed to break the run.
"""
import json
import os
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Makassar")

SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id INTEGER NOT NULL DEFAULT 0,
    routine_name TEXT NOT NULL DEFAULT '',
    bot_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'done',
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_finished ON notification_events(finished_at);
"""


def notifications_db_path(db_path):
    """data/notifications.db next to the given (agybot) db path."""
    base = os.path.dirname(os.path.abspath(db_path))
    return os.path.join(base, "data", "notifications.db")


def _connect(db_path):
    path = notifications_db_path(db_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _clean_summary(text, limit=300):
    cleaned = " ".join((text or "").split())
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip() + "..."
    return cleaned


def _iso_now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def _iso_from_epoch(epoch):
    if not epoch:
        return _iso_now()
    return datetime.fromtimestamp(int(epoch), TZ).isoformat(timespec="seconds")


def record_event(db_path, routine_id=0, routine_name="", bot_name="",
                status="done", title="", summary="", finished_at=None):
    """Insert one event; fire FCM best-effort; return the event dict."""
    if not finished_at:
        finished_at = _iso_now()
    elif isinstance(finished_at, (int, float)):
        finished_at = _iso_from_epoch(finished_at)
    conn = _connect(db_path)
    cur = conn.execute(
        "INSERT INTO notification_events (routine_id, routine_name, bot_name,"
        " status, title, summary, finished_at, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (int(routine_id or 0), routine_name or "", bot_name or "",
         status or "done", title or "", summary or "",
         finished_at, int(time.time())))
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    event = {"id": event_id, "routine_id": int(routine_id or 0),
             "routine_name": routine_name or "", "bot_name": bot_name or "",
             "status": status or "done", "title": title or "",
             "summary": summary or "", "finished_at": finished_at}
    # FCM push (best-effort — failures are logged, never raised).
    try:
        import fcm as fcm_mod
        event["fcm"] = fcm_mod.send_push(
            title, summary or routine_name or "Routine selesai",
            {"event_id": str(event_id),
             "routine_id": str(routine_id or 0),
             "routine_name": routine_name or ""})
    except Exception as e:
        print("WARNING: FCM send gagal (event %s): %s" % (event_id, e),
              flush=True)
        event["fcm"] = {"ok": False, "reason": "exception: %s" % e}
    return event


def record_routine_finished(db_path, routine_id, routine_name, bot_name,
                            status, result_text, finished_at=None):
    """Called from routines._finish_run (additive hook, Phase 11)."""
    if status == "done":
        title = "Routine selesai: %s" % (routine_name or "tanpa nama")
    else:
        title = "Routine gagal: %s" % (routine_name or "tanpa nama")
    return record_event(db_path, routine_id=routine_id,
                        routine_name=routine_name, bot_name=bot_name,
                        status=status, title=title,
                        summary=_clean_summary(result_text),
                        finished_at=finished_at)


def list_events(db_path, since=None, limit=50):
    """Events finished after `since` (ISO 8601, or None = latest).

    ISO strings with the same +07:00 offset compare correctly as text.
    """
    conn = _connect(db_path)
    if since:
        rows = conn.execute(
            "SELECT * FROM notification_events WHERE finished_at > ?"
            " ORDER BY finished_at ASC LIMIT ?",
            (str(since), int(limit))).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notification_events ORDER BY finished_at DESC"
            " LIMIT ?", (int(limit),)).fetchall()
        rows = list(reversed(rows))
    conn.close()
    return [dict(r) for r in rows]


def count_events(db_path):
    conn = _connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM notification_events").fetchone()[0]
    conn.close()
    return n


def latest_events(db_path, limit=5):
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM notification_events ORDER BY id DESC LIMIT ?",
        (int(limit),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
