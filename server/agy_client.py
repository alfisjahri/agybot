"""AgyBot - agy CLI client.

Calls /home/ubuntu/.local/bin/agy as user `ubuntu` (the OAuth token lives
under /home/ubuntu/.gemini/) via `sudo -n -u ubuntu`. Uses non-interactive
print mode with JSON output so the caller gets structured results.

Note: `agy` executes tools INTERNALLY and returns finished text. It does NOT
return tool_use blocks for the caller. AgyBot is therefore a thin wrapper:
routing + memory + routines + UI. Verification must be done by checking the
OUTPUT (link alive, numbers match), not by controlling tool calls.

Models: `agy models` (28 Okt 2026) lists model variants as
<base>-<effort> (e.g. gemini-3.8-flash-high). The CLI also accepts
--model <base> --effort <effort> separately — that is what AgyBot uses
(verified in Phase 1/2: gemini-3.8-flash + high/low both work).
BASE_MODELS is the picker list; MODEL_EFFORTS records which efforts each
base model actually offers according to `agy models`.
"""
import json
import subprocess
import time

AGY_BIN = "/home/ubuntu/.local/bin/agy"
SUDO_PREFIX = ["sudo", "-n", "-u", "ubuntu"]
DEFAULT_TIMEOUT = 600  # seconds; real tasks can take minutes

# Base models (picker list, as shown by `agy models` minus the effort suffix).
BASE_MODELS = [
    "gemini-4-argon",
    "gemini-3.8-flash",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "gpt-oss-120b",
]
# Backwards-compatible alias: validation uses base model names.
MODELS = BASE_MODELS

# Efforts each base model offers (from `agy models`, 28 Okt 2026).
# The --effort flag itself accepts low|medium|high|xhigh|max; the picker
# lists the full effort set, and agy reports an error if a combination
# does not exist (surfaced to the user by the chat).
MODEL_EFFORTS = {
    "gemini-4-argon": ["low", "medium", "high"],
    "gemini-3.8-flash": ["low", "medium", "high"],
    "claude-opus-5-5": ["low", "medium", "high"],
    "claude-sonnet-5-5": ["low", "medium", "high"],
    "gpt-oss-120b": ["medium"],
}
EFFORTS = ["low", "medium", "high", "xhigh", "max"]


def call_agy(prompt, model, effort, timeout=DEFAULT_TIMEOUT, cwd=None):
    """Run one agy print-mode call. Returns a dict:

    ok=True:  {ok, response, usage{input_tokens, output_tokens, total_tokens},
               duration_seconds, conversation_id}
    ok=False: {ok, error, duration_seconds, raw?}
    """
    cmd = SUDO_PREFIX + [
        AGY_BIN, "-p", prompt,
        "--model", model,
        "--effort", effort,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout after %ss" % timeout,
                "duration_seconds": round(time.time() - t0, 1)}
    except FileNotFoundError as e:
        return {"ok": False, "error": "agy binary not found: %s" % e,
                "duration_seconds": round(time.time() - t0, 1)}
    dur = round(time.time() - t0, 1)
    if proc.returncode != 0:
        return {"ok": False,
                "error": "agy exit %s: %s" % (proc.returncode,
                                              (proc.stderr or proc.stdout)[:800]),
                "duration_seconds": dur}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "agy returned non-JSON output",
                "raw": proc.stdout[:800], "duration_seconds": dur}
    if data.get("status") != "SUCCESS":
        return {"ok": False,
                "error": "agy status %s: %s" % (data.get("status"),
                                                str(data.get("error", ""))[:500]),
                "duration_seconds": dur}
    usage = data.get("usage") or {}
    return {
        "ok": True,
        "response": data.get("response", ""),
        "usage": {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        },
        "duration_seconds": data.get("duration_seconds", dur),
        "conversation_id": data.get("conversation_id"),
    }
