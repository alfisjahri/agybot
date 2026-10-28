"""AgyBot - FCM sender (Phase 11).

Server-side Firebase Cloud Messaging, PLUGGABLE credentials:

  * Preferred: service-account JSON at data/firebase-service-account.json
    (Alfi downloads it from Firebase Console). Uses the FCM HTTP v1 API:
    JWT (RS256, signed with the `openssl` CLI — no extra Python deps)
    -> OAuth2 access token -> POST /v1/projects/{id}/messages:send.
  * Fallback: legacy server key in data/fcm-server-key.txt (one line).
    Uses the legacy https://fcm.googleapis.com/fcm/send endpoint.

If NEITHER credential file exists, every send returns
{"ok": False, "reason": "not_configured"} and logs that honestly —
no credentials are ever invented. If no device tokens are registered,
sends return {"ok": False, "reason": "no_tokens_registered"}.

Device tokens live in data/fcm-tokens.json (registered by the APK via
POST /api/notifications/register once the APK has an FCM client).
Every send attempt is appended to data/fcm-send.log (no secrets logged).
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
SA_PATH = os.environ.get("AGYBOT_FCM_SA", os.path.join(DATA, "firebase-service-account.json"))
SERVER_KEY_PATH = os.environ.get("AGYBOT_FCM_SERVER_KEY", os.path.join(DATA, "fcm-server-key.txt"))
TOKENS_PATH = os.path.join(DATA, "fcm-tokens.json")
SEND_LOG = os.path.join(DATA, "fcm-send.log")

FCM_V1_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _log(msg):
    try:
        with open(SEND_LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S %Z",
                                               time.localtime()), msg))
    except OSError:
        pass
    print("FCM: %s" % msg, flush=True)


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _load_sa():
    try:
        with open(SA_PATH, encoding="utf-8") as f:
            sa = json.load(f)
        if sa.get("type") != "service_account" or not sa.get("private_key"):
            return None, "service-account JSON bukan tipe service_account"
        return sa, None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, "gagal baca service-account JSON: %s" % e


def _load_server_key():
    try:
        with open(SERVER_KEY_PATH, encoding="utf-8") as f:
            key = f.read().strip()
        return key or None
    except OSError:
        return None


def _access_token(sa):
    """Exchange the service-account JWT for an OAuth2 access token."""
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": sa["client_email"],
        "scope": FCM_V1_SCOPE,
        "aud": OAUTH_TOKEN_URL,
        "exp": now + 3600,
        "iat": now,
    }
    unsigned = "%s.%s" % (_b64url(json.dumps(header, separators=(",", ":")).encode()),
                          _b64url(json.dumps(claims, separators=(",", ":")).encode()))
    # RS256 sign via openssl (stdlib-only: no PyJWT/cryptography in venv).
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as kf:
        kf.write(sa["private_key"])
        keyfile = kf.name
    os.chmod(keyfile, 0o600)
    try:
        sig = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", keyfile],
            input=unsigned.encode(), capture_output=True, timeout=30)
        if sig.returncode != 0:
            raise RuntimeError("openssl sign gagal: %s" % sig.stderr.decode()[:200])
        jwt = "%s.%s" % (unsigned, _b64url(sig.stdout))
    finally:
        try:
            os.unlink(keyfile)
        except OSError:
            pass
    body = json.dumps({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(OAUTH_TOKEN_URL, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError("token exchange HTTP %s: %s" % (e.code, e.read()[:200]))
    return data["access_token"], sa.get("project_id")


def _post_json(url, payload, headers):
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:500]
        except Exception:
            detail = ""
        return e.code, {"error": detail}


def _send_v1(sa, token, title, body, data):
    access, project_id = _access_token(sa)
    if not project_id:
        return {"ok": False, "reason": "service-account tanpa project_id"}
    url = ("https://fcm.googleapis.com/v1/projects/%s/messages:send"
           % project_id)
    payload = {"message": {
        "token": token,
        "notification": {"title": title, "body": body},
        "data": {k: str(v) for k, v in (data or {}).items()},
        "android": {"priority": "high"},
    }}
    status, resp = _post_json(url, payload, {
        "Authorization": "Bearer " + access,
        "Content-Type": "application/json",
    })
    if status == 200:
        return {"ok": True, "method": "v1", "message_id": resp.get("name")}
    return {"ok": False, "method": "v1", "reason": "http_%s" % status,
            "detail": str(resp)[:300]}


def _send_legacy(server_key, token, title, body, data):
    payload = {"to": token,
               "notification": {"title": title, "body": body},
               "data": {k: str(v) for k, v in (data or {}).items()},
               "priority": "high"}
    status, resp = _post_json("https://fcm.googleapis.com/fcm/send", payload, {
        "Authorization": "key=" + server_key,
        "Content-Type": "application/json",
    })
    if status == 200 and resp.get("success") == 1:
        return {"ok": True, "method": "legacy",
                "message_id": str(resp.get("results", [{}])[0].get("message_id"))}
    return {"ok": False, "method": "legacy", "reason": "http_%s" % status,
            "detail": str(resp)[:300]}


def load_tokens():
    try:
        with open(TOKENS_PATH, encoding="utf-8") as f:
            tokens = json.load(f)
        return tokens if isinstance(tokens, list) else []
    except (OSError, ValueError):
        return []


def register_token(token):
    """Register an FCM device token (deduplicated). Returns token count."""
    token = (token or "").strip()
    if not token:
        raise ValueError("token kosong")
    tokens = load_tokens()
    if token not in tokens:
        tokens.append(token)
        with open(TOKENS_PATH, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        os.chmod(TOKENS_PATH, 0o600)
    return len(tokens)


def status():
    """Honest FCM readiness report (no secrets)."""
    sa, sa_err = _load_sa()
    server_key = _load_server_key()
    tokens = load_tokens()
    if sa:
        method = "service_account_v1"
        project_id = sa.get("project_id")
    elif server_key:
        method = "legacy_server_key"
        project_id = None
    else:
        method = "none"
        project_id = None
    return {
        "configured": method != "none",
        "method": method,
        "project_id": project_id,
        "sa_error": sa_err,
        "tokens_registered": len(tokens),
        "ready": method != "none" and len(tokens) > 0,
    }


def send_push(title, body, data=None):
    """Send a push to all registered tokens. Never raises.

    Returns {"ok": bool, "reason": ...} — "not_configured" /
    "no_tokens_registered" are honest states, not crashes.
    """
    st = status()
    if not st["configured"]:
        _log("SKIP send_push: FCM belum terkonfigurasi "
             "(tidak ada firebase-service-account.json / fcm-server-key.txt)")
        return {"ok": False, "reason": "not_configured",
                "detail": "FCM belum terkonfigurasi — lihat panduan Fase 11"}
    tokens = load_tokens()
    if not tokens:
        _log("SKIP send_push: FCM terkonfigurasi tapi belum ada token perangkat "
             "terdaftar (APK belum kirim token / FCM client belum ada)")
        return {"ok": False, "reason": "no_tokens_registered"}
    results = []
    if st["method"] == "service_account_v1":
        sa, _ = _load_sa()
        for tok in tokens:
            try:
                results.append(_send_v1(sa, tok, title, body, data))
            except Exception as e:
                results.append({"ok": False, "method": "v1",
                                "reason": "exception: %s" % e})
    else:
        key = _load_server_key()
        for tok in tokens:
            try:
                results.append(_send_legacy(key, tok, title, body, data))
            except Exception as e:
                results.append({"ok": False, "method": "legacy",
                                "reason": "exception: %s" % e})
    ok = sum(1 for r in results if r.get("ok"))
    _log("send_push '%s': %d/%d terkirim (%s)"
         % (title, ok, len(results), st["method"]))
    return {"ok": ok > 0, "sent": ok, "total": len(results),
            "method": st["method"], "results": results}
