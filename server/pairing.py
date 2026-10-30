"""Pairing QR AgyBot: token sekali pakai untuk menghubungkan APK ke server.

Alur:
  1. Admin (installer / pair.py) bikin token: create_token(public_url).
     Token disimpan di data/pairing.json (kedaluwarsa 10 menit, used=False).
  2. QR = <public_url>/pair/<token> dicetak di terminal (pair.py, via segno).
  3. User scan QR pakai kamera HP -> buka halaman /pair/<token> -> tombol
     deep link agybot://pair?url=<public_url>&token=<token> (atau isi manual
     URL + token di layar setup APK).
  4. APK (best-effort) klaim token via POST /api/pair/claim -> token
     ditandai used (sekali pakai).

Token BUKAN kredensial permanen: ia hanya mengkonfigurasi URL server di APK.
Akses ke UI web tetap dijaga lapisan lain (mis. Cloudflare Access).
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
PAIR_FILE = os.path.join(BASE, "data", "pairing.json")
TOKEN_TTL_MINUTES = 10


def _now():
    return datetime.now(timezone.utc)


def _load():
    try:
        with open(PAIR_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    os.makedirs(os.path.dirname(PAIR_FILE), exist_ok=True)
    tmp = PAIR_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PAIR_FILE)


def create_token(public_url, minutes=TOKEN_TTL_MINUTES):
    """Buat token pairing baru. Return (token, entry)."""
    token = secrets.token_urlsafe(24)
    now = _now()
    entry = {
        "public_url": (public_url or "").rstrip("/"),
        "created": now.isoformat(),
        "expires": (now + timedelta(minutes=minutes)).isoformat(),
        "used": False,
        "device": None,
    }
    data = _load()
    data[token] = entry
    # Housekeeping: buang token kedaluwarsa yang sudah lama.
    cutoff = (now - timedelta(days=1)).isoformat()
    data = {k: v for k, v in data.items()
            if v.get("expires", "") >= cutoff or k == token}
    _save(data)
    return token, entry


def get_token(token):
    """Ambil entry token yang masih valid (belum used, belum expired)."""
    if not token:
        return None
    entry = _load().get(token)
    if not entry or entry.get("used"):
        return None
    try:
        exp = datetime.fromisoformat(entry["expires"])
    except (KeyError, ValueError):
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if _now() >= exp:
        return None
    return entry


def claim_token(token, device=None):
    """Tandai token sudah dipakai. Return entry atau None kalau tak valid."""
    entry = get_token(token)
    if entry is None:
        return None
    data = _load()
    data[token]["used"] = True
    data[token]["device"] = (device or "")[:200]
    _save(data)
    return entry
