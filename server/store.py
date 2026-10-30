"""AgyBot - SQLite store: bots, chat messages, usage, routines, routine runs.

Kept separate from the web app so routines / CLI tools can reuse it later.
Phase 2 adds: routines + routine_runs tables, usage.routine_id (attribution),
and per-routine totals in usage_summary().
Phase 3 adds: bots.avatar_image (foto upload), routine_runs.verification
(JSON hasil langkah verifikasi), and per-model totals in usage_summary().
Phase 4 adds: bots.tagline (karakter bot, tampil di daftar chat + header),
and "today" totals in usage_summary() (hari ini, zona WITA).
"""
import sqlite3
import json
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    instructions TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'gemini-3.8-flash',
    effort TEXT NOT NULL DEFAULT 'medium',
    avatar_template INTEGER NOT NULL DEFAULT 1,
    avatar_color TEXT NOT NULL DEFAULT '#2FA08C',
    avatar_shape TEXT NOT NULL DEFAULT '',
    avatar_image TEXT,
    tagline TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0,
    routine_id INTEGER,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    bot_id INTEGER NOT NULL,
    cron_expr TEXT NOT NULL,
    days TEXT NOT NULL DEFAULT '',
    time_hhmm TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS routine_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id INTEGER NOT NULL,
    bot_id INTEGER NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'schedule',
    status TEXT NOT NULL DEFAULT 'running',
    result TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0,
    verification TEXT,
    started_at INTEGER NOT NULL,
    finished_at INTEGER
);
CREATE TABLE IF NOT EXISTS chat_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reply TEXT NOT NULL DEFAULT '',
    ok INTEGER,
    error TEXT,
    duration_seconds REAL,
    usage_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
"""


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path):
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    migrate(db_path)


def migrate(db_path):
    """Bring an older Phase 1/2 DB up to the current schema."""
    conn = connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usage)").fetchall()}
    if "routine_id" not in cols:
        conn.execute("ALTER TABLE usage ADD COLUMN routine_id INTEGER")
    bcols = {r[1] for r in conn.execute("PRAGMA table_info(bots)").fetchall()}
    if "avatar_image" not in bcols:
        conn.execute("ALTER TABLE bots ADD COLUMN avatar_image TEXT")
    if "avatar_shape" not in bcols:
        conn.execute("ALTER TABLE bots ADD COLUMN avatar_shape TEXT NOT NULL DEFAULT ''")
    if "tagline" not in bcols:
        conn.execute("ALTER TABLE bots ADD COLUMN tagline TEXT NOT NULL DEFAULT ''")
    rcols = {r[1] for r in conn.execute("PRAGMA table_info(routine_runs)").fetchall()}
    if "verification" not in rcols:
        conn.execute("ALTER TABLE routine_runs ADD COLUMN verification TEXT")
    conn.commit()
    conn.close()


def get_bots(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM bots ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bot(db_path, bot_id):
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_bot(db_path, bot_id, fields):
    allowed = {"name", "role", "tagline", "instructions", "model", "effort",
               "avatar_template", "avatar_color", "avatar_shape", "avatar_image"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    sets["updated_at"] = int(time.time())
    conn = connect(db_path)
    conn.execute(
        "UPDATE bots SET %s WHERE id = ?" % ", ".join("%s = ?" % k for k in sets),
        list(sets.values()) + [bot_id],
    )
    conn.commit()
    conn.close()
    return True


def create_bot(db_path, fields):
    now = int(time.time())
    name = (fields.get("name") or "Bot baru").strip() or "Bot baru"
    role = (fields.get("role") or "Bot baru").strip() or "Bot baru"
    instructions = fields.get("instructions") or "Kamu bot baru AgyBot. Jawab ringkas dan to-the-point."
    conn = connect(db_path)
    cur = conn.execute(
        "INSERT INTO bots (name, role, instructions, model, effort, avatar_template, avatar_color, avatar_shape, tagline, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (name, role, instructions, fields.get("model") or "gemini-3.8-flash",
         fields.get("effort") or "medium", int(fields.get("avatar_template") or 1),
         fields.get("avatar_color") or "#2FA08C", fields.get("avatar_shape") or "",
         fields.get("tagline") or "", now, now))
    bot_id = cur.lastrowid
    conn.commit()
    conn.close()
    return get_bot(db_path, bot_id)


def delete_bot(db_path, bot_id):
    """Return (True, 0) if deleted, (False, n_routines) if blocked by routines."""
    conn = connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM routines WHERE bot_id = ?", (bot_id,)).fetchone()[0]
    conn.close()
    if n:
        return False, n
    conn = connect(db_path)
    conn.execute("DELETE FROM messages WHERE bot_id = ?", (bot_id,))
    conn.execute("DELETE FROM chat_jobs WHERE bot_id = ?", (bot_id,))
    conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()
    return True, 0


def add_message(db_path, bot_id, role, content):
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO messages (bot_id, role, content, created_at) VALUES (?,?,?,?)",
        (bot_id, role, content, int(time.time())),
    )
    conn.commit()
    conn.close()


def get_messages(db_path, bot_id, limit=20):
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM messages WHERE bot_id = ? ORDER BY id DESC LIMIT ?",
        (bot_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def record_usage(db_path, bot_id, model, usage, duration_seconds, routine_id=None):
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO usage (bot_id, model, input_tokens, output_tokens,"
        " total_tokens, duration_seconds, routine_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (bot_id, model,
         int(usage.get("input_tokens", 0)),
         int(usage.get("output_tokens", 0)),
         int(usage.get("total_tokens", 0)),
         float(duration_seconds), routine_id, int(time.time())),
    )
    conn.commit()
    conn.close()


def usage_summary(db_path):
    """Per-bot totals + per-day totals + per-routine totals + per-model
    totals + grand total."""
    conn = connect(db_path)
    per_bot = conn.execute(
        "SELECT b.id AS bot_id, b.name AS name, COUNT(u.id) AS calls,"
        " COALESCE(SUM(u.input_tokens),0) AS input_tokens,"
        " COALESCE(SUM(u.output_tokens),0) AS output_tokens,"
        " COALESCE(SUM(u.total_tokens),0) AS total_tokens,"
        " COALESCE(ROUND(AVG(u.duration_seconds),1),0) AS avg_seconds"
        " FROM bots b LEFT JOIN usage u ON u.bot_id = b.id"
        " GROUP BY b.id ORDER BY b.id"
    ).fetchall()
    per_day = conn.execute(
        "SELECT date(created_at, 'unixepoch', 'localtime') AS day,"
        " COUNT(*) AS calls, SUM(total_tokens) AS total_tokens"
        " FROM usage GROUP BY day ORDER BY day DESC LIMIT 30"
    ).fetchall()
    per_routine = conn.execute(
        "SELECT r.id AS routine_id, r.name AS name, COUNT(u.id) AS calls,"
        " COALESCE(SUM(u.input_tokens),0) AS input_tokens,"
        " COALESCE(SUM(u.output_tokens),0) AS output_tokens,"
        " COALESCE(SUM(u.total_tokens),0) AS total_tokens"
        " FROM routines r LEFT JOIN usage u ON u.routine_id = r.id"
        " GROUP BY r.id ORDER BY total_tokens DESC"
    ).fetchall()
    per_model = conn.execute(
        "SELECT model, COUNT(*) AS calls,"
        " COALESCE(SUM(input_tokens),0) AS input_tokens,"
        " COALESCE(SUM(output_tokens),0) AS output_tokens,"
        " COALESCE(SUM(total_tokens),0) AS total_tokens"
        " FROM usage GROUP BY model ORDER BY total_tokens DESC"
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(total_tokens),0) AS total_tokens"
        " FROM usage"
    ).fetchone()
    today = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(total_tokens),0) AS total_tokens"
        " FROM usage WHERE date(created_at, 'unixepoch', 'localtime')"
        " = date('now', 'localtime')"
    ).fetchone()
    conn.close()
    return {
        "per_bot": [dict(r) for r in per_bot],
        "per_day": [dict(r) for r in per_day],
        "per_routine": [dict(r) for r in per_routine if r["calls"] > 0],
        "per_model": [dict(r) for r in per_model],
        "total": dict(total),
        "today": dict(today),
    }


def create_chat_job(db_path, bot_id):
    conn = connect(db_path)
    cur = conn.execute(
        "INSERT INTO chat_jobs (bot_id, status, created_at, updated_at)"
        " VALUES (?,?,?,?)",
        (bot_id, "pending", int(time.time()), int(time.time())),
    )
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_chat_job(db_path, job_id):
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM chat_jobs WHERE id = ?",
                       (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    job = dict(row)
    try:
        job["usage"] = json.loads(job.pop("usage_json")) if job.get("usage_json") else None
    except Exception:
        job["usage"] = None
    return job


def pending_chat_job(db_path, bot_id):
    conn = connect(db_path)
    row = conn.execute(
        "SELECT * FROM chat_jobs WHERE bot_id = ? AND status = 'pending'"
        " ORDER BY id DESC LIMIT 1",
        (bot_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_chat_job(db_path, job_id, status, reply=None, ok=None,
                    error=None, duration_seconds=None, usage=None):
    sets = {"status": status, "updated_at": int(time.time())}
    if reply is not None:
        sets["reply"] = reply
    if ok is not None:
        sets["ok"] = 1 if ok else 0
    if error is not None:
        sets["error"] = error
    if duration_seconds is not None:
        sets["duration_seconds"] = float(duration_seconds)
    if usage is not None:
        sets["usage_json"] = json.dumps(usage)
    conn = connect(db_path)
    conn.execute(
        "UPDATE chat_jobs SET %s WHERE id = ?"
        % ", ".join("%s = ?" % k for k in sets),
        list(sets.values()) + [job_id],
    )
    conn.commit()
    conn.close()
