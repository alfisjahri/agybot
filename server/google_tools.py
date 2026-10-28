"""AgyBot - Google helpers wrapper (Phase 2).

Thin wrappers around the existing helpers in /home/ubuntu/guru-tools/:
- gas_webapp.py: create a Form via the GAS Web App (POST JSON). Returns
  {formId, editUrl, publishedUrl, shortUrl} or {error}. This is the ONLY
  way bots create Forms (Forms API creation shows grades automatically).
- forms_api.py: READ a Form (get) or its responses (responses). NEVER create
  via forms_api.py (create is forbidden here on purpose).
- verify_form_live(url): check a Form's published URL answers (200/301).

These run as subprocesses with the system python3 (which has requests +
google-api-python-client). They read OAuth credentials from
/home/ubuntu/guru-tools/credentials.json (chmod 640, group muse — the agy
process runs as user ubuntu, which is in group muse, so it can read them).
"""
import json
import subprocess
import urllib.request

GURU_TOOLS = "/home/ubuntu/guru-tools"
GAS_WEBAPP = GURU_TOOLS + "/gas_webapp.py"
FORMS_API = GURU_TOOLS + "/forms_api.py"
PYTHON = "python3"


def _run(cmd, timeout=180):
    """Run a helper. Returns parsed JSON stdout, or {error, raw}."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout after %ss: %s" % (timeout, " ".join(cmd))}
    except FileNotFoundError as e:
        return {"error": "helper tidak ditemukan: %s" % e}
    out = (proc.stdout or "").strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {"error": "helper mengembalikan output bukan JSON",
                "raw": out[:1000], "stderr": (proc.stderr or "")[:500]}
    if proc.returncode != 0 and "error" not in data:
        data = {"error": "helper exit %s" % proc.returncode,
                "raw": out[:1000], "stderr": (proc.stderr or "")[:500]}
    return data


def create_form_via_gas(quiz_json_path):
    """Create a Form via the GAS Web App. quiz_json_path: file JSON kuis
    (format gas_webapp.py: {title, description?, materi?, kelas?,
    questions:[{text, choices[], correctIndex, points}]}, total poin = 100)."""
    return _run([PYTHON, GAS_WEBAPP, quiz_json_path], timeout=180)


def get_form(form_id):
    """Read a Form's definition (verification)."""
    return _run([PYTHON, FORMS_API, "get", form_id], timeout=120)


def get_responses(form_id):
    """Read a Form's responses (for CEK / rekap)."""
    return _run([PYTHON, FORMS_API, "responses", form_id], timeout=120)


def verify_form_live(url, timeout=15):
    """GET the Form's published/short URL. Returns (ok, status_code)."""
    if not url:
        return False, None
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "AgyBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception:
        return False, None
