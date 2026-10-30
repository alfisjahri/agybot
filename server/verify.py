"""AgyBot - verifikasi ringan untuk routine runs (Phase 3).

BUKAN Chief: tidak ada bot kedua yang menilai. Langkah ini memeriksa OUTPUT
routine secara mekanis terhadap sumber kebenaran (API Google Forms / wali):
- Form baru (BUAT SOAL): cek shortUrl hidup (HTTP) — link mati = gagal.
- CEK: bandingkan jumlah submit menurut API Forms dengan angka yang
  dilaporkan bot. 0 submit = mencurigakan (aturan CEK) -> cek manual.
  Angka tidak cocok -> cek manual. Data tidak bisa dibaca -> gagal.
- Rekap absensi: hadir + alpa + sakit + izin harus = 18.

Hasil: {"status": "ok" | "needs_manual_check" | "failed" | "unverified" |
"none", "checks": [...]}. Disimpan sebagai JSON di routine_runs.verification
dan ditampilkan sebagai badge di UI Routines.
"""
import json
import os
import re
import time

import google_tools
import routines

# Entri tes yang TIDAK dihitung sebagai submit murid.
TEST_NAMES = {"tes siswa", "tes muse", "muse alias jolly", "tes", "test"}


def _is_test_entry(first_answer):
    name = (first_answer or "").strip().lower()
    if name in TEST_NAMES:
        return True
    if name.startswith("tes ") or name.startswith("test "):
        return True
    return False


def _count_real(responses_data):
    """Jumlah respons murid asli (tanpa entri tes) dari output forms_api.py."""
    if not isinstance(responses_data, dict):
        return None
    responses = responses_data.get("responses") or []
    return sum(1 for r in responses
               if not _is_test_entry(r.get("firstAnswer")))


_CLAIMED_SUBMIT_RE = re.compile(
    r"\*{0,2}(\d+)\*{0,2}\s*(siswa\s+)?(sudah\s+)?(submit|mengumpulkan|mengirim|"
    r"mengerjakan|respons|respon|menjawab)", re.IGNORECASE)
_CLAIMED_MISSING_RE = re.compile(
    r"\*{0,2}(\d+)\*{0,2}\s*(siswa\s+)?belum(\s+mengerjakan|\s+mengumpulkan|\s+submit)?",
    re.IGNORECASE)


def _parse_claimed(reply):
    """Ambil angka yang diklaim bot: {'submitted': int|None, 'missing': int|None}."""
    m = _CLAIMED_SUBMIT_RE.search(reply or "")
    submitted = int(m.group(1)) if m else None
    m2 = _CLAIMED_MISSING_RE.search(reply or "")
    missing = int(m2.group(1)) if m2 else None
    return {"submitted": submitted, "missing": missing}


def _find_form_for_cek(db_path, routine):
    """Cari formId kuis hari ini untuk routine CEK: dari registry, entri
    BUAT SOAL di tanggal yang sama dan kelas yang sama."""
    path = routines.registry_path(db_path)
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except Exception:
        return None
    today = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    m = re.search(r"(\d+[A-Z])\s*(Koding|Matematika|Mat)", routine.get("name", ""),
                  re.IGNORECASE)
    kelas = m.group(0) if m else ""
    for entry in reg.values():
        if entry.get("date") != today:
            continue
        if kelas and kelas.lower() not in (entry.get("routine_name") or "").lower():
            continue
        if entry.get("form_id"):
            return entry["form_id"]
    return None


def _check_form_live(short_url, form_id):
    ok, status = google_tools.verify_form_live(short_url) if short_url else (None, None)
    return {
        "type": "form_live",
        "url": short_url,
        "form_id": form_id,
        "ok": bool(ok),
        "http_status": status,
        "note": ("Link Form hidup (HTTP %s)" % status) if ok
                else ("Link Form TIDAK hidup (HTTP %s) — cek manual" % status),
    }


def _check_cek(db_path, routine, reply, form_id):
    if not form_id:
        form_id = _find_form_for_cek(db_path, routine)
    if not form_id:
        return {
            "type": "cek_crosscheck",
            "ok": False,
            "note": "formId kuis hari ini tidak ditemukan (registry kosong) — cek manual",
        }
    data = google_tools.get_responses(form_id)
    if isinstance(data, dict) and "error" in data:
        return {
            "type": "cek_crosscheck",
            "form_id": form_id,
            "ok": False,
            "note": "Data Form tidak bisa dibaca (%s) — cek manual" % data["error"],
        }
    submitted_api = _count_real(data)
    if submitted_api is None:
        return {
            "type": "cek_crosscheck",
            "form_id": form_id,
            "ok": False,
            "note": "Respons Form tidak bisa diparse — cek manual",
        }
    claimed = _parse_claimed(reply)
    check = {
        "type": "cek_crosscheck",
        "form_id": form_id,
        "submitted_api": submitted_api,
        "submitted_claimed": claimed["submitted"],
        "missing_claimed": claimed["missing"],
    }
    if submitted_api == 0:
        check["ok"] = False
        check["note"] = ("0 respons di Form (API) — hasil 0 mencurigakan, "
                         "perlu dicek manual (aturan CEK)")
        return check
    if claimed["submitted"] is None:
        check["ok"] = None
        check["note"] = ("Angka submit di balasan bot tidak bisa diparse; "
                         "API mencatat %d submit — verifikasi manual disarankan"
                         % submitted_api)
        return check
    if claimed["submitted"] != submitted_api:
        check["ok"] = False
        check["note"] = ("Bot melapor %d submit, API mencatat %d submit — "
                         "ANGKA TIDAK COCOK, cek manual" % (claimed["submitted"], submitted_api))
        return check
    check["ok"] = True
    check["note"] = "Jumlah submit bot (%d) cocok dengan API" % submitted_api
    return check


_HADIR_RE = re.compile(r"hadir\s*\*{0,2}(\d+)", re.IGNORECASE)
_ALPA_RE = re.compile(r"alpa\s*\*{0,2}(\d+)", re.IGNORECASE)
_SAKIT_RE = re.compile(r"sakit\s*\*{0,2}(\d+)", re.IGNORECASE)
_IZIN_RE = re.compile(r"izin\s*\*{0,2}(\d+)", re.IGNORECASE)


def _check_rekap_absensi(reply):
    def _n(rx):
        m = rx.search(reply or "")
        return int(m.group(1)) if m else 0
    hadir, alpa = _n(_HADIR_RE), _n(_ALPA_RE)
    sakit, izin = _n(_SAKIT_RE), _n(_IZIN_RE)
    total = hadir + alpa + sakit + izin
    found = any(rx.search(reply or "") for rx in
                (_HADIR_RE, _ALPA_RE, _SAKIT_RE, _IZIN_RE))
    check = {
        "type": "rekap_absensi",
        "hadir": hadir, "alpa": alpa, "sakit": sakit, "izin": izin,
        "total": total,
    }
    if not found:
        check["ok"] = None
        check["note"] = "Angka absensi di balasan tidak bisa diparse"
        return check
    if total == 18:
        check["ok"] = True
        check["note"] = "Total %d = 18 (roster 8A) — cocok" % total
    else:
        check["ok"] = False
        check["note"] = "Total %d != 18 (roster 8A) — cek manual" % total
    return check


def verify_run(db_path, routine, reply):
    """Jalankan semua langkah verifikasi yang berlaku untuk routine ini."""
    checks = []
    short_url, form_id = routines.extract_forms(reply or "")
    if short_url or form_id:
        checks.append(_check_form_live(short_url, form_id))
    if "CEK" in (routine.get("name") or "").upper():
        checks.append(_check_cek(db_path, routine, reply, form_id))
    if "rekap absensi" in (routine.get("name") or "").lower():
        checks.append(_check_rekap_absensi(reply))
    if not checks:
        return {"status": "none", "checks": []}
    if any(c.get("ok") is False for c in checks):
        # Bedakan "gagal baca data" (failed) dari "angka tidak cocok / 0"
        # (needs_manual_check): keduanya butuh cek manual, tapi pesannya beda.
        status = "needs_manual_check"
        for c in checks:
            if c.get("ok") is False and c.get("type") == "form_live":
                status = "failed"
            if c.get("ok") is False and c.get("type") == "cek_crosscheck" \
                    and "tidak bisa dibaca" in (c.get("note") or ""):
                status = "failed"
        return {"status": status, "checks": checks}
    if any(c.get("ok") is None for c in checks):
        return {"status": "unverified", "checks": checks}
    return {"status": "ok", "checks": checks}


def status_label(status):
    return {
        "ok": "✅ Terverifikasi",
        "needs_manual_check": "⚠️ Cek manual",
        "failed": "❌ Gagal",
        "unverified": "❓ Belum terverifikasi",
        "none": "—",
    }.get(status, status)
