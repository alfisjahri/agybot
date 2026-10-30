"""AgyBot - routines engine (Phase 2).

APScheduler-based scheduler that lives inside the Flask process. Routines
are stored in SQLite; the scheduler is reconciled with the DB on startup and
on every change (sync_scheduler). Each routine: bot + cron schedule + prompt
template + enabled flag.

On trigger (scheduled or manual "run now"), the routine calls the assigned
bot via agy (same path as /api/chat) and records the run + usage. A routine
run is attributed in the usage table via usage.routine_id so the Usage page
can show per-routine totals.

Schedule representation: a 5-field cron expression is canonical
("35 7 * * 1-6"). The UI also collects friendly days ("mon,tue,...") +
time ("07:35") and converts them to cron via days_time_to_cron().

Timezone is Asia/Makassar (WITA) for all schedules.
"""
import json
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

import store

TZ = ZoneInfo("Asia/Makassar")

# BUG HARI (diperbaiki 30 Okt 2026): APScheduler menghitung hari Senin=0 ..
# Minggu=6, sedangkan cron standar menghitung Minggu=0, Senin=1 .. Sabtu=6.
# Tanpa konversi ini semua routine bergeser +1 hari (routine Sel/Rab/Kam
# jalan Rab/Kam/Jum, PTMT Kamis jalan Jumat, Rekap Jumat jalan Sabtu).
# DB tetap menyimpan cron standar (mudah dibaca manusia); konversi hanya
# dilakukan saat membuat trigger APScheduler di sync_scheduler().
def _aps_dow_num(n):
    return (int(n) - 1) % 7

def _conv_dow_range(tok):
    if "-" in tok:
        a, b = tok.split("-", 1)
        return "%d-%d" % (_aps_dow_num(a), _aps_dow_num(b))
    return str(_aps_dow_num(tok))

def cron_to_apscheduler(cron_expr):
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return cron_expr
    dow = parts[4]
    out = []
    for tok in dow.split(","):
        if tok == "*":
            out.append(tok)
        elif "/" in tok:
            b, s = tok.split("/", 1)
            out.append((_conv_dow_range(b) + "/" + s) if b != "*" else tok)
        else:
            out.append(_conv_dow_range(tok))
    parts[4] = ",".join(out)
    return " ".join(parts)

WITA = TZ

ROUTINE_SCHEMA = """
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
    started_at INTEGER NOT NULL,
    finished_at INTEGER
);
"""

# cron day-of-week numbers: mon=1 .. sun=0 (0 and 7 both mean Sunday)
DOW = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}
DOW_REV = {v: k for k, v in DOW.items()}


def init_routines_db(db_path):
    conn = store.connect(db_path)
    conn.executescript(ROUTINE_SCHEMA)
    conn.commit()
    conn.close()


def days_time_to_cron(days, time_hhmm):
    """days: 'mon,tue,wed,thu,fri,sat' or '' (every day). time_hhmm: '07:35'."""
    hh, mm = time_hhmm.strip().split(":")
    minute, hour = int(mm), int(hh)
    if not days:
        dow = "*"
    else:
        nums = sorted({DOW[d.strip().lower()] for d in days.split(",") if d.strip()})
        dow = ",".join(str(n) for n in nums)
    return "%d %d * * %s" % (minute, hour, dow)


def validate_cron(cron_expr):
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError("cron harus 5 field (menit jam tanggal bulan hari)")
    minute, hour = parts[0], parts[1]
    if not re.fullmatch(r"(\*|\d+|\d+-\d+|\*/\d+|\d+(,\d+)*)", minute):
        raise ValueError("field menit cron tidak valid: %s" % minute)
    if not re.fullmatch(r"(\*|\d+|\d+-\d+|\*/\d+|\d+(,\d+)*)", hour):
        raise ValueError("field jam cron tidak valid: %s" % hour)
    return cron_expr.strip()


def friendly_schedule(routine):
    """'Sen-Sab 07:35' style label, or the raw cron if no friendly fields."""
    if routine.get("days") and routine.get("time_hhmm"):
        names = {"mon": "Sen", "tue": "Sel", "wed": "Rab", "thu": "Kam",
                 "fri": "Jum", "sat": "Sab", "sun": "Min"}
        ds = [names.get(d.strip().lower(), d) for d in routine["days"].split(",")]
        return "%s %s" % ("-".join(ds), routine["time_hhmm"])
    return routine.get("cron_expr", "")


# ---------------------------------------------------------------- CRUD
def list_routines(db_path):
    conn = store.connect(db_path)
    rows = conn.execute(
        "SELECT r.*, b.name AS bot_name FROM routines r"
        " LEFT JOIN bots b ON b.id = r.bot_id ORDER BY r.id").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["schedule_label"] = friendly_schedule(d)
        out.append(d)
    return out


def get_routine(db_path, routine_id):
    conn = store.connect(db_path)
    row = conn.execute(
        "SELECT r.*, b.name AS bot_name FROM routines r"
        " LEFT JOIN bots b ON b.id = r.bot_id WHERE r.id = ?",
        (routine_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["schedule_label"] = friendly_schedule(d)
    return d


def create_routine(db_path, fields):
    name = (fields.get("name") or "").strip()
    prompt = (fields.get("prompt") or "").strip()
    if not name or not prompt:
        raise ValueError("name dan prompt wajib diisi")
    bot_id = int(fields.get("bot_id"))
    if not store.get_bot(db_path, bot_id):
        raise ValueError("bot tidak ditemukan: %s" % bot_id)
    cron = fields.get("cron_expr", "").strip()
    days = (fields.get("days") or "").strip()
    time_hhmm = (fields.get("time_hhmm") or "").strip()
    if not cron and days and time_hhmm:
        cron = days_time_to_cron(days, time_hhmm)
    cron = validate_cron(cron)
    enabled = 1 if fields.get("enabled") in (1, True, "1", "true", "on") else 0
    now = int(time.time())
    conn = store.connect(db_path)
    cur = conn.execute(
        "INSERT INTO routines (name, bot_id, cron_expr, days, time_hhmm,"
        " prompt, enabled, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (name, bot_id, cron, days, time_hhmm, prompt, enabled, now, now))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return get_routine(db_path, rid)


def update_routine(db_path, routine_id, fields):
    routine = get_routine(db_path, routine_id)
    if not routine:
        return None
    sets = {}
    if "name" in fields and (fields["name"] or "").strip():
        sets["name"] = fields["name"].strip()
    if "prompt" in fields and (fields["prompt"] or "").strip():
        sets["prompt"] = fields["prompt"].strip()
    if "bot_id" in fields:
        bot_id = int(fields["bot_id"])
        if not store.get_bot(db_path, bot_id):
            raise ValueError("bot tidak ditemukan: %s" % bot_id)
        sets["bot_id"] = bot_id
    # schedule: cron wins if given; otherwise rebuild from days+time
    if fields.get("cron_expr"):
        sets["cron_expr"] = validate_cron(fields["cron_expr"])
    elif "days" in fields or "time_hhmm" in fields:
        days = (fields.get("days") if "days" in fields
                else routine.get("days") or "").strip()
        time_hhmm = (fields.get("time_hhmm") if "time_hhmm" in fields
                     else routine.get("time_hhmm") or "").strip()
        if days and time_hhmm:
            sets["cron_expr"] = days_time_to_cron(days, time_hhmm)
            sets["days"] = days
            sets["time_hhmm"] = time_hhmm
    if "enabled" in fields:
        sets["enabled"] = 1 if fields["enabled"] in (1, True, "1", "true", "on") else 0
    if not sets:
        return routine
    sets["updated_at"] = int(time.time())
    conn = store.connect(db_path)
    conn.execute(
        "UPDATE routines SET %s WHERE id = ?" % ", ".join("%s = ?" % k for k in sets),
        list(sets.values()) + [routine_id])
    conn.commit()
    conn.close()
    return get_routine(db_path, routine_id)


def delete_routine(db_path, routine_id):
    conn = store.connect(db_path)
    conn.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------- runs
def create_run(db_path, routine_id, bot_id, trigger="schedule"):
    conn = store.connect(db_path)
    cur = conn.execute(
        "INSERT INTO routine_runs (routine_id, bot_id, trigger, status,"
        " started_at) VALUES (?,?,?,?,?)",
        (routine_id, bot_id, trigger, "running", int(time.time())))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def get_run(db_path, run_id):
    conn = store.connect(db_path)
    row = conn.execute(
        "SELECT rr.*, r.name AS routine_name FROM routine_runs rr"
        " LEFT JOIN routines r ON r.id = rr.routine_id WHERE rr.id = ?",
        (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_runs(db_path, routine_id=None, limit=20):
    conn = store.connect(db_path)
    if routine_id:
        rows = conn.execute(
            "SELECT rr.*, r.name AS routine_name FROM routine_runs rr"
            " LEFT JOIN routines r ON r.id = rr.routine_id"
            " WHERE rr.routine_id = ? ORDER BY rr.id DESC LIMIT ?",
            (routine_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT rr.*, r.name AS routine_name FROM routine_runs rr"
            " LEFT JOIN routines r ON r.id = rr.routine_id"
            " ORDER BY rr.id DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def last_run(db_path, routine_id):
    runs = get_runs(db_path, routine_id, limit=1)
    return runs[0] if runs else None


# ---------------------------------------------------------------- forms registry
def registry_path(db_path):
    return os.path.join(os.path.dirname(os.path.abspath(db_path)),
                        "data", "latest_forms.json")


def record_form(db_path, routine_id, routine_name, short_url=None, form_id=None):
    """Remember a Form a routine just created, so CEK routines can find it.

    Phase 3 fix: the registry file can be owned by user `ubuntu` (agy writes
    it too, following its instructions) with mode 644, which makes the
    Flask process (user `muse`) unable to write it. That used to raise
    PermissionError and kill the executor thread, leaving the run stuck at
    "running" forever. Now a write failure is logged and swallowed — the
    run must still finish and be verified.
    """
    if not short_url and not form_id:
        return None
    path = registry_path(db_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, encoding="utf-8") as f:
                reg = json.load(f)
        except Exception:
            reg = {}
        today = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        reg[str(routine_id)] = {
            "routine_id": routine_id,
            "routine_name": routine_name,
            "date": today,
            "short_url": short_url,
            "form_id": form_id,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(path, 0o664)  # group muse (ubuntu is in it) can write too
        except Exception:
            pass
        return reg[str(routine_id)]
    except OSError as e:
        print("WARNING: record_form gagal menulis %s: %s" % (path, e),
              flush=True)
        return None


SHORT_URL_RE = re.compile(r"https?://forms\.gle/[A-Za-z0-9_-]+")
FORM_ID_RE = re.compile(
    r"formId[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_-]{20,})[\"']?")


def extract_forms(text):
    """Best-effort: pull a forms.gle short URL and/or a formId from a reply."""
    m = SHORT_URL_RE.search(text or "")
    short_url = m.group(0) if m else None
    m2 = FORM_ID_RE.search(text or "")
    form_id = m2.group(1) if m2 else None
    return short_url, form_id


# ---------------------------------------------------------------- executor
def build_routine_prompt(bot, routine):
    today = time.strftime("%A, %d %B %Y", time.localtime(time.time()))
    parts = [
        bot["instructions"].strip(),
        "",
        "---",
        "TUGAS ROUTINE: %s" % routine["name"],
        "Hari ini: %s (WITA)." % today,
        routine["prompt"].strip(),
        "",
        "Kerjakan tugas di atas sampai selesai lewat tool bash/file kamu, "
        "lalu laporkan hasilnya dengan ringkas. Kalau tugas butuh Form, "
        "sertakan formId DAN shortUrl (forms.gle) di laporanmu.",
    ]
    return "\n".join(parts)


def execute_run(db_path, run_id):
    """Run one routine run (blocking; call from a worker thread)."""
    import agy_client

    run = get_run(db_path, run_id)
    if not run:
        return None
    routine = get_routine(db_path, run["routine_id"])
    bot = store.get_bot(db_path, run["bot_id"])
    if not routine or not bot:
        _finish_run(db_path, run_id, "failed",
                    "routine atau bot tidak ditemukan", {}, 0)
        return get_run(db_path, run_id)
    base = os.path.dirname(os.path.abspath(db_path))
    workdir = os.path.join(base, "work")
    os.makedirs(workdir, exist_ok=True)
    prompt = build_routine_prompt(bot, routine)
    result = agy_client.call_agy(prompt, bot["model"], bot["effort"], cwd=workdir)
    is_skip = (result.get("response") or "").strip() == "SKIP_NO_CLASS"
    if not result["ok"]:
        _finish_run(db_path, run_id, "failed",
                    "agy gagal: %s" % result.get("error", "unknown error"),
                    {}, result.get("duration_seconds", 0))
        return get_run(db_path, run_id)
    usage = result.get("usage") or {}
    # Phase 3: semua langkah pasca-agy dibungkus — kegagalan di satu langkah
    # (mis. registry tidak bisa ditulis) TIDAK boleh membuat run nyangkut
    # di status "running" selamanya; _finish_run harus selalu jalan.
    verification = None
    try:
        store.record_usage(db_path, bot["id"], bot["model"], usage,
                           result.get("duration_seconds", 0),
                           routine_id=routine["id"])
        if is_skip:
            verification = {"status": "skipped", "checks": [{"type": "skip_no_class", "ok": True, "note": "Tidak ada kelas 30 menit lagi, pesan tidak dikirim"}]}
        else:
            store.add_message(db_path, bot["id"], "assistant",
                              "[Routine: %s]\n%s" % (routine["name"], result["response"]))
            short_url, form_id = extract_forms(result["response"])
            if short_url or form_id:
                record_form(db_path, routine["id"], routine["name"], short_url, form_id)
        # Phase 3: verifikasi ringan (BUKAN Chief) — cek output terhadap API.
        try:
            import verify as verify_mod
            verification = verify_mod.verify_run(db_path, routine, result["response"])
        except Exception as e:  # verifikasi tidak boleh menggagalkan run
            verification = {"status": "unverified",
                            "checks": [{"type": "verify_error", "ok": None,
                                        "note": "verifikasi gagal dijalankan: %s" % e}]}
    except Exception as e:
        print("WARNING: execute_run post-processing gagal (run %s): %s"
              % (run_id, e), flush=True)
        if verification is None:
            verification = {"status": "unverified",
                            "checks": [{"type": "postprocess_error", "ok": None,
                                        "note": "post-processing gagal: %s" % e}]}
    _finish_run(db_path, run_id, "done", result["response"], usage,
                result.get("duration_seconds", 0), verification=verification, skip_notify=is_skip)
    return get_run(db_path, run_id)


def _finish_run(db_path, run_id, status, result_text, usage, duration,
                verification=None, skip_notify=False):
    conn = store.connect(db_path)
    conn.execute(
        "UPDATE routine_runs SET status=?, result=?, input_tokens=?,"
        " output_tokens=?, total_tokens=?, duration_seconds=?, finished_at=?,"
        " verification=? WHERE id = ?",
        (status, result_text,
         int(usage.get("input_tokens", 0)),
         int(usage.get("output_tokens", 0)),
         int(usage.get("total_tokens", 0)),
         float(duration), int(time.time()),
         json.dumps(verification, ensure_ascii=False) if verification else None,
         run_id))
    conn.commit()
    conn.close()

    # Phase 11 (notifikasi): catat event selesai + kirim push (best-effort).
    # SKIP_NO_CLASS: tidak ada chat, tidak ada notifikasi sama sekali.
    if skip_notify:
        return
    # TIDAK BOLEH mengganggu penyelesaian run — semua error ditelan + log.
    try:
        import notifications as _notif
        _run = get_run(db_path, run_id)
        _routine = get_routine(db_path, _run["routine_id"]) if _run else None
        _bot = store.get_bot(db_path, _run["bot_id"]) if _run else None
        _notif.record_routine_finished(
            db_path,
            _run["routine_id"] if _run else 0,
            (_routine or {}).get("name") or "Routine",
            (_bot or {}).get("name") or "",
            status, result_text,
            finished_at=_run.get("finished_at") if _run else None)
    except Exception as _e:
        print("WARNING: notifikasi gagal (run %s): %s" % (run_id, _e), flush=True)


def run_routine_now(db_path, routine_id):
    """Create a manual run and execute it in a background thread."""
    routine = get_routine(db_path, routine_id)
    if not routine:
        return None
    run_id = create_run(db_path, routine_id, routine["bot_id"], trigger="manual")
    t = threading.Thread(target=execute_run, args=(db_path, run_id), daemon=True)
    t.start()
    return run_id


# ---------------------------------------------------------------- scheduler
def scheduled_job(db_path, routine_id):
    routine = get_routine(db_path, routine_id)
    if not routine or not routine["enabled"]:
        return None
    run_id = create_run(db_path, routine_id, routine["bot_id"], trigger="schedule")
    return execute_run(db_path, run_id)


def job_id(routine_id):
    return "routine_%s" % routine_id


def sync_scheduler(scheduler, db_path):
    """Reconcile APScheduler jobs with the routines table (enabled only)."""
    from apscheduler.triggers.cron import CronTrigger

    wanted = {}
    for r in list_routines(db_path):
        if r["enabled"]:
            wanted[job_id(r["id"])] = r
    existing = {j.id for j in scheduler.get_jobs()}
    for jid, r in wanted.items():
        trigger = CronTrigger.from_crontab(cron_to_apscheduler(r["cron_expr"]), timezone=TZ)
        if jid in existing:
            job = scheduler.get_job(jid)
            if str(job.trigger) != str(trigger):
                scheduler.reschedule_job(jid, trigger=trigger)
        else:
            scheduler.add_job(scheduled_job, trigger=trigger, args=[db_path, r["id"]],
                              id=jid, name=r["name"], coalesce=True,
                              misfire_grace_time=3600, max_instances=1)
    for jid in existing - set(wanted):
        scheduler.remove_job(jid)


def start_scheduler(db_path):
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone=TZ)
    sync_scheduler(scheduler, db_path)
    scheduler.start()
    return scheduler
