"""AgyBot - Flask server (Phase 3: + avatar, quota per model, verifikasi,
image input).

Routes (Phase 1):
  GET  /                 chat UI
  GET  /usage            usage page (server-rendered)
  GET  /api/bots         list bots
  GET  /api/bots/<id>    one bot
  POST /api/bots/<id>    update bot (model, effort, name, instructions, avatar)
  GET  /api/bots/<id>/messages
  POST /api/chat         {bot_id, message} -> agy round-trip
                         (also accepts multipart: message + image file)
  GET  /api/usage        usage summary JSON
  GET  /api/models       model + effort lists

Routes (Phase 2):
  GET  /routines         routines UI
  GET  /api/routines     list routines
  POST /api/routines     create routine
  GET  /api/routines/<id>
  POST /api/routines/<id>  update routine (incl. enabled toggle)
  DELETE /api/routines/<id>
  POST /api/routines/<id>/run   run now (background thread)
  GET  /api/routines/<id>/runs  recent runs for a routine
  GET  /api/routine-runs        recent runs (all)
  GET  /api/routine-runs/<id>   one run

Routes (Phase 3):
  GET  /api/avatars             5 avatar templates
  POST /api/bots/<id>/avatar    upload foto avatar (multipart, field "avatar")
  POST /api/bots/<id>           {"avatar_image": null} = hapus foto, balik ke template

Routes (Phase 5 — real Antigravity Pro quota, from `agy /usage`):
  GET  /api/quota               real quota snapshot (data/quota.json)
  POST /api/quota/refresh       trigger a background quota fetch
  The quota is fetched by quota.py (PTY drive of interactive `agy /usage`),
  refreshed automatically every 30 min by a background thread.
"""
import json
import os
import subprocess
import threading
import time

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

import agy_client
import avatars
import fcm
import notifications
import routines
import store

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("AGYBOT_DB", os.path.join(BASE, "agybot.db"))
WORKDIR = os.path.join(BASE, "work")
AVATAR_DIR = os.path.join(BASE, "static", "avatars")
UPLOAD_DIR = os.path.join(BASE, "static", "uploads")
QUOTA_FILE = os.path.join(BASE, "data", "quota.json")
QUOTA_SCRIPT = os.path.join(BASE, "quota.py")
os.makedirs(WORKDIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(BASE, "templates"),
            static_folder=os.path.join(BASE, "static"))

SCHEDULER = None
_QUOTA_LOCK = threading.Lock()
_QUOTA_FETCHING = False
_QUOTA_THREAD_STARTED = False


def read_quota():
    """Read the last real-quota snapshot (data/quota.json), or None."""
    try:
        with open(QUOTA_FILE) as f:
            data = json.load(f)
        return data if data.get("ok") else None
    except (OSError, ValueError):
        return None


def _run_quota_fetch():
    """Run quota.py as user ubuntu (agy OAuth lives under /home/ubuntu)."""
    global _QUOTA_FETCHING
    if not _QUOTA_LOCK.acquire(blocking=False):
        return False
    _QUOTA_FETCHING = True
    try:
        subprocess.run(
            ["sudo", "-n", "-u", "ubuntu", "python3", QUOTA_SCRIPT],
            capture_output=True, timeout=180)
    except (subprocess.SubprocessError, OSError):
        pass
    finally:
        _QUOTA_FETCHING = False
        _QUOTA_LOCK.release()
    return True


def refresh_quota_async():
    """Trigger a background quota fetch (non-blocking)."""
    t = threading.Thread(target=_run_quota_fetch, daemon=True)
    t.start()
    return True


def _quota_auto_refresh_loop():
    """Background loop: fetch quota shortly after startup, then every 30 min."""
    time.sleep(60)
    while True:
        _run_quota_fetch()
        time.sleep(1800)


def start_quota_auto_refresh():
    global _QUOTA_THREAD_STARTED
    if _QUOTA_THREAD_STARTED:
        return
    _QUOTA_THREAD_STARTED = True
    t = threading.Thread(target=_quota_auto_refresh_loop, daemon=True)
    t.start()


def get_scheduler():
    global SCHEDULER
    if SCHEDULER is None:
        SCHEDULER = routines.start_scheduler(DB)
    return SCHEDULER


def resync_scheduler():
    if SCHEDULER is not None:
        routines.sync_scheduler(SCHEDULER, DB)


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/usage")
def usage_page():
    return render_template("usage.html", summary=store.usage_summary(DB),
                           quota=read_quota(), quota_fetching=_QUOTA_FETCHING)


@app.route("/routines")
def routines_page():
    return render_template("routines.html")


@app.route("/api/bots", methods=["GET"])
def api_bots():
    return jsonify(store.get_bots(DB))


@app.route("/api/bots/<int:bot_id>", methods=["GET", "POST"])
def api_bot(bot_id):
    if request.method == "GET":
        bot = store.get_bot(DB, bot_id)
        return jsonify(bot) if bot else (jsonify({"error": "bot not found"}), 404)
    bot = store.get_bot(DB, bot_id)
    if not bot:
        return jsonify({"error": "bot not found"}), 404
    data = request.get_json(silent=True) or {}
    if "model" in data and data["model"] not in agy_client.MODELS:
        return jsonify({"error": "unknown model: %s" % data["model"]}), 400
    if "effort" in data and data["effort"] not in agy_client.EFFORTS:
        return jsonify({"error": "unknown effort: %s" % data["effort"]}), 400
    if "avatar_template" in data:
        try:
            tpl = int(data["avatar_template"])
        except (TypeError, ValueError):
            return jsonify({"error": "avatar_template harus angka 1-5"}), 400
        if tpl not in [t["id"] for t in avatars.TEMPLATES]:
            return jsonify({"error": "avatar_template tidak dikenal: %s" % tpl}), 400
        data["avatar_template"] = tpl
    if "avatar_shape" in data:
        shape = str(data["avatar_shape"]).strip()
        if shape and shape not in avatars.SHAPE_IDS:
            return jsonify({"error": "avatar_shape tidak dikenal: %s" % shape}), 400
        data["avatar_shape"] = shape
    if "avatar_color" in data:
        color = str(data["avatar_color"]).strip()
        # Fase 8: warna boleh nama warna DS-Bot (cth. "blue", "aurora")
        # atau hex custom (cth. "#2FA08C").
        if color not in avatars.COLOR_IDS and not (
                color.startswith("#") and len(color) in (4, 7)):
            return jsonify({"error": "avatar_color harus nama warna DS-Bot atau "
                                     "hex, cth. blue / #2FA08C"}), 400
    # Hapus foto avatar lama kalau avatar_image di-set null.
    if "avatar_image" in data and data["avatar_image"] is None and bot.get("avatar_image"):
        _delete_avatar_file(bot["avatar_image"])
    store.update_bot(DB, bot_id, data)
    return jsonify(store.get_bot(DB, bot_id))


def _delete_avatar_file(filename):
    try:
        path = os.path.join(AVATAR_DIR, secure_filename(filename))
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


@app.route("/api/avatars", methods=["GET"])
def api_avatars():
    return jsonify({
        "templates": avatars.list_templates(),  # lama (kompatibilitas)
        "shapes": avatars.list_shapes(),        # Fase 8: karakter ala DS-Bot
        "colors": avatars.list_colors(),
    })


@app.route("/api/bots/<int:bot_id>/avatar", methods=["POST"])
def api_bot_avatar(bot_id):
    """Upload foto avatar bot (multipart, field 'avatar').
    Disimpan sebagai static/avatars/bot_<id>.<ext>, max 2 MB."""
    bot = store.get_bot(DB, bot_id)
    if not bot:
        return jsonify({"error": "bot not found"}), 404
    if "avatar" not in request.files:
        return jsonify({"error": "field file 'avatar' wajib"}), 400
    f = request.files["avatar"]
    if not f.filename:
        return jsonify({"error": "file kosong"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in avatars.ALLOWED_EXTS:
        return jsonify({"error": "format gambar harus: %s"
                        % ", ".join(sorted(avatars.ALLOWED_EXTS))}), 400
    data = f.read()
    if len(data) > avatars.MAX_AVATAR_BYTES:
        return jsonify({"error": "file terlalu besar (max 2 MB)"}), 400
    filename = "bot_%d.%s" % (bot_id, ext)
    if bot.get("avatar_image") and bot["avatar_image"] != filename:
        _delete_avatar_file(bot["avatar_image"])
    path = os.path.join(AVATAR_DIR, filename)
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o644)
    store.update_bot(DB, bot_id, {"avatar_image": filename})
    return jsonify(store.get_bot(DB, bot_id))


@app.route("/api/bots/<int:bot_id>/messages", methods=["GET"])
def api_messages(bot_id):
    return jsonify(store.get_messages(DB, bot_id, limit=30))


@app.route("/api/models", methods=["GET"])
def api_models():
    return jsonify({
        "models": agy_client.BASE_MODELS,
        "efforts": agy_client.EFFORTS,
        "model_efforts": agy_client.MODEL_EFFORTS,
        "avatar_templates": avatars.list_templates(),
    })


def build_prompt(bot, history, message, image_path=None):
    parts = [bot["instructions"].strip(), "", "Percakapan sejauh ini:"]
    for m in history[-8:]:
        who = "User" if m["role"] == "user" else bot["name"]
        parts.append("%s: %s" % (who, m["content"]))
    if image_path:
        parts.append("")
        parts.append("GAMBAR TERLAMPIR dari user (file di server): %s" % image_path)
        parts.append("Baca file gambar itu dengan tool file kamu — cek keberadaan, "
                     "ukuran (lebar x tinggi piksel), dan isi visualnya — lalu "
                     "jawab pertanyaan user berdasarkan gambar itu. Kalau kamu "
                     "tidak bisa membaca isi visual gambar, katakan jujur dan "
                     "laporkan saja apa yang bisa kamu baca dari file-nya "
                     "(nama, ukuran, dimensi).")
    parts.append("User: %s" % message)
    parts.append("")
    parts.append("Jawablah sebagai %s dalam Bahasa Indonesia yang santai dan ringkas. "
                 "Kalau tugas butuh file/script/API, kerjakan lewat tool bash/file kamu "
                 "lalu laporkan hasilnya." % bot["name"])
    return "\n".join(parts)


def _save_chat_image(bot_id):
    """Simpan file gambar dari multipart chat. Return (web_path, abs_path)
    atau (None, None) kalau tidak ada file."""
    if "image" not in request.files:
        return None, None
    f = request.files["image"]
    if not f.filename:
        return None, None
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in avatars.ALLOWED_EXTS:
        return None, "FORMAT_TIDAK_DIDUKUNG"
    data = f.read()
    if len(data) > avatars.MAX_UPLOAD_BYTES:
        return None, "TERLALU_BESAR"
    safe = secure_filename(f.filename)
    filename = "%d_%d_%s" % (bot_id, int(time.time()), safe or ("gambar.%s" % ext))
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o644)  # agy jalan sebagai user ubuntu, harus bisa baca
    return "/static/uploads/" + filename, path


@app.route("/api/chat", methods=["POST"])
def api_chat():
    # Dua bentuk: JSON biasa, atau multipart (message + file gambar).
    if request.content_type and "multipart/form-data" in request.content_type:
        bot_id = request.form.get("bot_id")
        message = (request.form.get("message") or "").strip()
        try:
            bot_id = int(bot_id) if bot_id else None
        except ValueError:
            bot_id = None
    else:
        data = request.get_json(silent=True) or {}
        bot_id = data.get("bot_id")
        message = (data.get("message") or "").strip()
    if not bot_id or not message:
        return jsonify({"error": "bot_id and message required"}), 400
    bot = store.get_bot(DB, bot_id)
    if not bot:
        return jsonify({"error": "bot not found"}), 404
    image_web_path, image_abs_path = (None, None)
    if request.content_type and "multipart/form-data" in request.content_type:
        image_web_path, image_abs_path = _save_chat_image(bot_id)
        if image_abs_path in ("FORMAT_TIDAK_DIDUKUNG", "TERLALU_BESAR"):
            return jsonify({"error": "gambar harus %s, max 5 MB"
                            % ", ".join(sorted(avatars.ALLOWED_EXTS))}), 400
    stored_message = message
    if image_web_path:
        stored_message = "[gambar: %s]\n%s" % (image_web_path, message)
    store.add_message(DB, bot_id, "user", stored_message)
    history = store.get_messages(DB, bot_id, limit=8)
    prompt = build_prompt(bot, history, message, image_path=image_abs_path)
    result = agy_client.call_agy(prompt, bot["model"], bot["effort"], cwd=WORKDIR)
    if not result["ok"]:
        reply = "Maaf, agy gagal: %s" % result.get("error", "unknown error")
        store.add_message(DB, bot_id, "assistant", reply)
        return jsonify({"reply": reply, "ok": False,
                        "error": result.get("error"),
                        "duration_seconds": result.get("duration_seconds")})
    store.add_message(DB, bot_id, "assistant", result["response"])
    store.record_usage(DB, bot_id, bot["model"], result["usage"],
                       result.get("duration_seconds", 0))
    return jsonify({"reply": result["response"], "ok": True,
                    "usage": result["usage"],
                    "duration_seconds": result.get("duration_seconds"),
                    "conversation_id": result.get("conversation_id"),
                    "image": image_web_path})


@app.route("/api/usage", methods=["GET"])
def api_usage():
    return jsonify(store.usage_summary(DB))


# ---------------------------------------------------------------- real quota
@app.route("/api/quota", methods=["GET"])
def api_quota():
    quota = read_quota()
    if quota is None:
        return jsonify({"ok": False, "error": "kuota belum pernah diambil",
                        "fetching": _QUOTA_FETCHING})
    quota = dict(quota)
    quota["fetching"] = _QUOTA_FETCHING
    return jsonify(quota)


@app.route("/api/quota/refresh", methods=["POST"])
def api_quota_refresh():
    refresh_quota_async()
    return jsonify({"ok": True, "status": "fetching",
                    "note": "pengambilan kuota ~30-60 detik, refresh halaman nanti"})


# ---------------------------------------------------------------- routines
@app.route("/api/routines", methods=["GET", "POST"])
def api_routines():
    if request.method == "GET":
        out = routines.list_routines(DB)
        for r in out:
            r["last_run"] = routines.last_run(DB, r["id"])
        return jsonify(out)
    data = request.get_json(silent=True) or {}
    try:
        created = routines.create_routine(DB, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    resync_scheduler()
    return jsonify(created), 201


@app.route("/api/routines/<int:rid>", methods=["GET", "POST", "DELETE"])
def api_routine(rid):
    routine = routines.get_routine(DB, rid)
    if not routine:
        return jsonify({"error": "routine not found"}), 404
    if request.method == "GET":
        routine["last_run"] = routines.last_run(DB, rid)
        return jsonify(routine)
    if request.method == "DELETE":
        routines.delete_routine(DB, rid)
        resync_scheduler()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    try:
        updated = routines.update_routine(DB, rid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    resync_scheduler()
    return jsonify(updated)


@app.route("/api/routines/<int:rid>/run", methods=["POST"])
def api_routine_run(rid):
    routine = routines.get_routine(DB, rid)
    if not routine:
        return jsonify({"error": "routine not found"}), 404
    run_id = routines.create_run(DB, rid, routine["bot_id"], trigger="manual")
    t = threading.Thread(target=routines.execute_run, args=(DB, run_id), daemon=True)
    t.start()
    return jsonify({"run_id": run_id, "status": "running"})


@app.route("/api/routines/<int:rid>/runs", methods=["GET"])
def api_routine_runs(rid):
    limit = int(request.args.get("limit", 20))
    return jsonify(routines.get_runs(DB, rid, limit=limit))


@app.route("/api/routine-runs", methods=["GET"])
def api_all_runs():
    limit = int(request.args.get("limit", 20))
    return jsonify(routines.get_runs(DB, None, limit=limit))


@app.route("/api/routine-runs/<int:run_id>", methods=["GET"])
def api_one_run(run_id):
    run = routines.get_run(DB, run_id)
    return jsonify(run) if run else (jsonify({"error": "run not found"}), 404)


@app.route("/logo.svg")
def logo():
    return send_from_directory(os.path.join(BASE, "static"), "logo.svg",
                               mimetype="image/svg+xml")

# ---------------------------------------------------------------- notifications (Phase 11)
@app.route("/api/notifications", methods=["GET"])
def api_notifications():
    """Event routine selesai sejak `since` (ISO 8601 WITA).

    Dipakai APK v2 (polling). Contoh:
    GET /api/notifications?since=2026-10-28T19:00:00+08:00&limit=20
    """
    since = request.args.get("since") or None
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    events = notifications.list_events(DB, since=since, limit=max(1, min(limit, 100)))
    return jsonify({"events": events, "count": len(events),
                    "server_time": notifications._iso_now(),
                    "fcm_configured": fcm.status()["configured"]})


@app.route("/api/notifications/status", methods=["GET"])
def api_notifications_status():
    return jsonify({"fcm": fcm.status(),
                    "events_total": notifications.count_events(DB),
                    "recent": notifications.latest_events(DB, limit=5)})


@app.route("/api/notifications/register", methods=["POST"])
def api_notifications_register():
    """Daftarkan token perangkat FCM (dipakai APK saat FCM client ada)."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"error": "token wajib"}), 400
    try:
        n = fcm.register_token(token)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "tokens_registered": n})


@app.route("/api/notifications/test", methods=["POST"])
def api_notifications_test():
    """Buat satu event tes (untuk uji polling malam ini tanpa jalanin routine)."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Tes Notifikasi AgyBot").strip()
    summary = (data.get("summary") or "Event tes - routine selesai (simulasi).").strip()
    event = notifications.record_event(
        DB, routine_id=int(data.get("routine_id") or 0),
        routine_name=(data.get("routine_name") or "Tes Notifikasi"),
        bot_name="", status="done", title=title, summary=summary)
    return jsonify(event), 201


if __name__ == "__main__":
    store.init_db(DB)
    routines.init_routines_db(DB)
    get_scheduler()
    start_quota_auto_refresh()
    port = int(os.environ.get("AGYBOT_PORT", "8898"))
    # Bind to the Docker bridge (172.17.0.1) only: reachable from NPM container
    # (forward_host 172.17.0.1) but NOT from the public internet (129.225.15.95).
    # 127.0.0.1 would break NPM (container cannot reach host loopback).
    host = os.environ.get("AGYBOT_HOST", "172.17.0.1")
    app.run(host=host, port=port, threaded=True)
