#!/usr/bin/env python3
"""AgyBot — fetch REAL Antigravity Pro quota via `agy` interactive /usage.

How it works (proven 28 Okt 2026, agy 1.4.9):
  * `agy` has NO non-interactive usage flag/subcommand and NO quota cache
    file on disk (checked: quota_manager.go fetches it in-memory only).
  * The ONLY way to see the real quota is the interactive slash command
    `/usage` ("View model quota usage"), which opens a "Models & Quota"
    view with 38 lines:
      - GEMINI MODELS (Gemini Flash, Gemini Pro): Weekly Limit Remaining
        % + "Refreshes in …", Five Hour Limit Remaining % + refresh.
      - CLAUDE AND GPT MODELS (Claude Opus, Claude Sonnet, GPT-OSS):
        Weekly % + refresh, Five Hour % + refresh.
      - GEMINI 4 ARGON: Gemini 4 Argon Weekly Limit % + refresh only.
      - Footer note: within each group, models share a weekly limit and
        a 5-hour limit; quota is consumed proportionally to token cost.
  * So this script drives `agy` in a PTY (120 cols x 50 rows so the whole
    38-line view fits on one screen, no scrolling needed), types `/usage`,
    captures the view, parses it into structured JSON and writes it to
    data/quota.json (read by the AgyBot Usage page).

Limitations (honest):
  * Each fetch spawns a full interactive agy session (~40-60 s: startup +
    sign-in + quota refresh). It is a quota-READ, not an LLM call, so it
    does not consume model tokens — but it does trigger agy's internal
    quota refresh (a lightweight API call).
  * The numbers are a snapshot: they tick down as Alfi uses the account
    (other agy/OpenBot calls consume the same shared pool). The page
    shows the fetch timestamp so Alfi knows how fresh the numbers are.
  * If agy changes the /usage layout, parsing fails and the script writes
    an error state (the page falls back to the honest "belum bisa dibaca"
    note and keeps the last good snapshot if one exists).

Run as:  sudo -n -u ubuntu python3 /home/ubuntu/agybot/quota.py
(agy's OAuth token lives under /home/ubuntu/.gemini/, so it must run as
user `ubuntu`; the AgyBot Flask app runs as `muse` and calls it via sudo.)
"""
import fcntl
import json
import os
import pty
import re
import select
import struct
import sys
import termios
import time
from datetime import datetime, timezone, timedelta

AGY_BIN = "/home/ubuntu/.local/bin/agy"
HERE = os.path.dirname(os.path.abspath(__file__))
QUOTA_FILE = os.path.join(HERE, "data", "quota.json")
WITA = timezone(timedelta(hours=8))
START_TIMEOUT = 45     # seconds to reach the main prompt

# Indonesian translation of agy's standard /usage footer note. The raw
# English note is parsed from the view (kept as note_en for debugging),
# but Alfi always sees this Indonesian version -- the whole AgyBot UI is
# in Indonesian, and the raw English footer looked like a bug.
NOTE_ID = (
    "Dalam tiap grup, model berbagi limit mingguan dan limit 5 jam. "
    "Kuota terpakai sebanding dengan biaya tokennya. Jadi, limit akan "
    "lebih awet kalau tugasnya pendek atau memakai model yang lebih hemat. "
    "Limit 5 jam meratakan permintaan secara global agar kapasitas terbagi "
    "adil ke semua pengguna, sementara limit mingguan terikat langsung ke "
    "pemakaianmu sendiri."
)
USAGE_TIMEOUT = 30     # seconds for the /usage view to render


def _clean(raw: bytes) -> str:
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", raw.decode("utf-8", "replace"))
    text = re.sub(r"\x1b\][^\x07]*\x07", "", text)
    text = re.sub(r"\x1b[()][0-9A-B]", "", text)
    text = re.sub(r"\x1b[=>]", "", text)
    return text


def _drain(master, seconds, buf):
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.3)
        if r:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
    return buf


def fetch_quota_text() -> str:
    """Drive agy interactively and return the raw cleaned terminal text."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 120, 0, 0))
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.chdir("/home/ubuntu")
        os.execv(AGY_BIN, [AGY_BIN])
        os._exit(1)
    os.close(slave)
    buf = b""

    def write(b):
        try:
            os.write(master, b)
        except OSError:
            pass

    try:
        # --- wait for the main prompt -------------------------------------
        deadline = time.time() + START_TIMEOUT
        prompt_seen = False
        while time.time() < deadline:
            buf = _drain(master, 3, buf)
            text = _clean(buf)
            # Main prompt marker: the "? for shortcuts" footer plus a model
            # name. (Do NOT require "Gemini 4 Argon": the startup screen only
            # shows the CURRENT model, which changes -- e.g. it is now
            # "Gemini 3.8 Flash (Low)", so the old check never fired and
            # every fetch timed out after 45s.)
            if "? for shortcuts" in text and re.search(r"Gemini|Claude|GPT", text):
                prompt_seen = True
                break
            # trust prompt (new workspace) — default option is "Yes, I trust"
            if "Do you trust the contents of this project?" in text:
                write(b"\r")
                buf = _drain(master, 3, buf)
            # login-method picker — default is "1. Google OAuth"
            elif "Select login method" in text and "Google OAuth" in text:
                write(b"\r")
                buf = _drain(master, 3, buf)
        if not prompt_seen:
            raise RuntimeError("agy main prompt not reached in %ss" % START_TIMEOUT)

        # --- open /usage ---------------------------------------------------
        write(b"/usage")
        _drain(master, 3, buf)
        write(b"\r")
        deadline = time.time() + USAGE_TIMEOUT
        view_seen = False
        while time.time() < deadline:
            buf = _drain(master, 3, buf)
            if "Models & Quota" in _clean(buf):
                view_seen = True
                break
        if not view_seen:
            raise RuntimeError("/usage view did not appear in %ss" % USAGE_TIMEOUT)
        _drain(master, 6, buf)  # let the quota numbers finish rendering
        return _clean(buf)
    finally:
        # --- exit cleanly --------------------------------------------------
        try:
            write(b"\x1b")          # close the quota view / palette
            _drain(master, 1, buf)
            write(b"/exit\r")
            _drain(master, 2, buf)
            write(b"\x03")          # Ctrl+C as a backstop
            _drain(master, 1, buf)
        except Exception:
            pass
        try:
            os.close(master)
        except OSError:
            pass
        try:
            _, status = os.waitpid(pid, os.WNOHANG)
            if not os.WIFEXITED(status) and not os.WIFSIGNALED(status):
                os.kill(pid, 9)
                os.waitpid(pid, 0)
        except (ChildProcessError, ProcessLookupError, OSError):
            pass


def _last(pattern, text):
    matches = list(re.finditer(pattern, text, re.DOTALL))
    return matches[-1] if matches else None


def parse_quota(text: str) -> dict:
    """Parse the /usage view into structured quota data."""
    idx = text.rfind("Models & Quota")
    if idx < 0:
        raise RuntimeError("no 'Models & Quota' view in captured output")
    view = text[idx:]

    account_m = re.search(r"Account:\s*(\S+)", view)
    account = account_m.group(1) if account_m else None

    def _limits(header_pat, with_five_hour=True):
        m = _last(header_pat, view)
        if not m:
            return None
        weekly_pct = float(m.group(2))
        weekly_refresh = m.group(3).strip() if m.group(3) else "Quota available"
        five = None
        if with_five_hour:
            five = {
                "remaining_pct": float(m.group(4)),
                "refresh": m.group(5).strip() if m.group(5) else "Quota available",
            }
        return {
            "models": m.group(1).strip(),
            "weekly": {"remaining_pct": weekly_pct, "refresh": weekly_refresh},
            "five_hour": five,
        }

    # Bar diikuti "Refreshes in ..." atau, saat limit penuh (100%),
    # "Quota available". Pola lama hanya terima "Refreshes in", sehingga
    # limit 5-jam yang penuh membuat SELURUH grup gagal parse (hanya Argon
    # yang lolos karena ia tak punya limit 5-jam).
    bar = r"\[[^\]]*\]\s*([\d.]+)%\s*\n\s*(?:Refreshes in\s+([^\n]+)|Quota available)"
    gemini = _limits(
        r"GEMINI MODELS\s+Models within this group:\s*([^\n]+?)\s+"
        r"Weekly Limit Remaining\s*\n\s*" + bar +
        r"\s+Five Hour Limit Remaining\s*\n\s*" + bar)
    # _limits expects groups (models, weekly_pct, weekly_refresh,
    # five_pct, five_refresh); the combined pattern above yields exactly
    # those 5 groups.
    claude_gpt = _limits(
        r"CLAUDE AND GPT MODELS\s+Models within this group:\s*([^\n]+?)\s+"
        r"Weekly Limit Remaining\s*\n\s*" + bar +
        r"\s+Five Hour Limit Remaining\s*\n\s*" + bar)
    argon_m = _last(
        r"GEMINI 4 ARGON\s+.*?Gemini 4 Argon Weekly Limit\s*\n\s*" + bar, view)
    argon = None
    if argon_m:
        argon = {
            "models": "Gemini 4 Argon",
            "weekly": {"remaining_pct": float(argon_m.group(1)),
                       "refresh": argon_m.group(2).strip() if argon_m.group(2) else "Quota available"},
            "five_hour": None,
        }

    if not (gemini or claude_gpt or argon):
        raise RuntimeError("no quota group parsed from /usage view")

    # Raw English footer (parsed for debugging); Alfi sees NOTE_ID.
    note_lines = re.findall(r"\u2502([^\n]*)", view)
    note_en = " ".join(l.strip() for l in note_lines).strip() or None
    note = NOTE_ID

    groups = []
    if gemini:
        groups.append({"id": "gemini", "name": "Gemini",
                       "subtitle": gemini["models"],
                       "weekly": gemini["weekly"],
                       "five_hour": gemini["five_hour"]})
    if claude_gpt:
        groups.append({"id": "claude_gpt", "name": "Claude & GPT",
                       "subtitle": claude_gpt["models"],
                       "weekly": claude_gpt["weekly"],
                       "five_hour": claude_gpt["five_hour"]})
    if argon:
        groups.append({"id": "argon", "name": "Gemini 4 Argon",
                       "subtitle": "Kuota Argon terpisah (Pro)",
                       "weekly": argon["weekly"],
                       "five_hour": None})

    now = datetime.now(WITA)
    return {
        "ok": True,
        "source": "agy /usage (mode interaktif via PTY)",
        "account": account,
        "fetched_at": now.isoformat(timespec="seconds"),
        "fetched_at_human": now.strftime("%d %b %Y %H:%M WITA"),
        "groups": groups,
        "note": note,
        "note_en": note_en,
    }


def main():
    try:
        text = fetch_quota_text()
        # Keep the raw view so a future parse failure can be diagnosed
        # from the actual captured output (the 17:29 Gemini miss could
        # not be diagnosed because the raw text was never saved).
        try:
            with open(os.path.join(HERE, "data", "quota-raw.txt"), "w") as f:
                f.write(text)
        except OSError:
            pass
        data = parse_quota(text)
    except Exception as e:
        # Keep the last good snapshot; record the failure separately.
        err = {
            "ok": False,
            "source": "agy /usage (mode interaktif via PTY)",
            "error": str(e),
            "fetched_at": datetime.now(WITA).isoformat(timespec="seconds"),
        }
        os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
        err_file = os.path.join(HERE, "data", "quota-error.json")
        with open(err_file, "w") as f:
            json.dump(err, f, indent=2, ensure_ascii=False)
        print(json.dumps(err, indent=2, ensure_ascii=False))
        return 1
    os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
    tmp = QUOTA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, QUOTA_FILE)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
