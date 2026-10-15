






import json
import os
import sys
from pathlib import Path

CAP = 10000
BUDGET = 9500


def read_event(stream=None):







    if stream is None:
        stream = sys.stdin.buffer
    return json.loads(stream.read().decode("utf-8"))


def normalize_path(raw):









    path = os.path.normpath(raw).replace("\\", "/")
    if os.name == "nt":
        drive, rest = os.path.splitdrive(path)
        colon = rest.find(":")
        if colon != -1:
            rest = rest[:colon]
        parts = [part.rstrip(". ") or part for part in rest.split("/")]
        path = drive + "/".join(parts)
    return path


def plugin_root():
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[1]


def plugin_data():
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "plugins" / "data" / "super-humanizer"


def _write(payload, code, out):
    if out is None:
        out = sys.stdout.buffer
    out.write(json.dumps(payload).encode("utf-8"))
    out.flush()
    raise SystemExit(code)


def emit_note(message, out=None):

    _write({"systemMessage": message}, 0, out)


def emit_context(context, message, out=None):

    _write({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        },
        "systemMessage": message,
    }, 0, out)


def emit_ask(reason, out=None):

    _write({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        },
    }, 0, out)


def emit_block(reason, err=None):

    if err is None:
        err = sys.stderr.buffer
    err.write(reason.encode("utf-8"))
    err.flush()
    raise SystemExit(2)


def emit_fail_open(exc, out=None):

    first_line = str(exc).splitlines()[0] if str(exc) else ""
    message = (f"super-humanizer: gate failed open ({type(exc).__name__}: {first_line}).\n"
               "The write was allowed unscanned.")
    emit_note(message, out=out)


def run_guarded(handler):




    try:
        handler()
    except Exception as exc:
        emit_fail_open(exc)
