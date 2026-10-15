












import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import extract_code, extract_prompt, hookio, marker, protect, voice
from scripts.density import density
from scripts.extract_markdown import extract_text
from scripts.rulebook import load
from scripts.scan import scan
from scripts.voice import NO_PROFILE

MARK_RULES = frozenset({"C018"})
HOOK_TIERS = frozenset({"block", "warn", "warn-with-company", "density"})
WARN_TIERS = frozenset({"warn"})
BOM = "\ufeff"








RULEBOOK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

REFUSAL_LIMIT = 3
STATE_MAX_AGE_DAYS = 1
SESSION_ID = re.compile(r"[A-Za-z0-9_-]+")

GUARD_REASON = ("super-humanizer: this write of {path} was refused. The marker is changed "
                "through /humanize, which runs scripts/marker.py. The user edits a rulebook "
                "overlay by hand. A .git file or folder below the repository root would hide "
                "files from the gate. The installed plugin's files are not edited from a "
                "session.")
SKIP_NOTES = {
    "exclude": "this file matches an exclude glob, so this write was not scanned",
    "no-include": "this file matches no include glob, so this write was not scanned",
}



ROUTE_NOTES = {
    "other": "no handler exists for this file type in this version, "
             "so this write was not scanned",
    "office": "this file is read by the post-hoc run alone, so this write was not scanned",
    "pdf": "this file is read by the post-hoc run alone, so this write was not scanned",
}
PROMPT_SCANNED_NOTE = "this file routes to the prompt handler, and this write was scanned"
CODE_SCANNED_NOTE = "this file routes to the code handler, and this write was scanned"


CODE_UNREAD_NOTE = "nothing in this file was read: {line}"


_NOTHING_READ = re.compile(r", so nothing in (?:the file|it) was read$")


CODE_DECODE_FAILED = "the file's encoding could not be decoded: {error}"


PRINT_MODULES = "SUPERHUMANIZER_PRINT_MODULES"


def _comparable(path):


    path = os.path.normcase(path).replace("\\", "/")
    return path.casefold() if marker.CASE_FOLD_PLATFORMS else path


def _is_overlay(target):

    folder = _comparable(hookio.normalize_path(str(hookio.plugin_data()))).rstrip("/") + "/"
    path = _comparable(target)
    return path.startswith(folder) and path.endswith(".overlay.json")


def _plugin_cache_root():


    raw = os.environ.get("SUPERHUMANIZER_PLUGIN_CACHE")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "plugins" / "cache"


def _is_installed_plugin_copy(target):




    root = _comparable(hookio.normalize_path(str(hookio.plugin_root()))).rstrip("/") + "/"
    cache = _comparable(hookio.normalize_path(str(_plugin_cache_root()))).rstrip("/") + "/"
    if not root.startswith(cache):
        return False
    return _comparable(target).startswith(root)


def _is_marker(target):
    return _comparable(Path(target).name) == marker.MARKER_NAME


def _git_below_marker(target, marker_dir):





    prefix = _comparable(marker_dir.as_posix() + "/")
    path = _comparable(target)
    if not path.startswith(prefix):
        return False
    components = path[len(prefix):].split("/")
    return ".git" in components[1:]


def _replace(text, old, new, replace_all):


    if not old:
        return None
    starts, pos = [], text.find(old)
    while pos != -1:
        starts.append(pos)
        pos = text.find(old, pos + len(old))
    if not starts or (len(starts) > 1 and not replace_all):
        return None
    shift = len(new) - len(old)
    regions = [(s + i * shift, s + i * shift + len(new)) for i, s in enumerate(starts)]
    return text.replace(old, new), regions


def _utf8(data):
    return data.decode("utf-8")


def decode_code(data):


    return data.decode(extract_code.encoding_of(data))


def _applied(event, path, decode=_utf8):
    tool_input = event["tool_input"]
    if event["tool_name"] != "Edit":
        return tool_input["content"], None
    old, new = tool_input["old_string"], tool_input["new_string"]
    if not path.is_file():
        return (new, None) if old == "" else None
    text = decode(path.read_bytes())
    if old == "" and text == "":
        return new, None
    replace_all = tool_input.get("replace_all", False)
    applied = _replace(text, old, new, replace_all)
    if applied is not None or "\r\n" not in text:
        return applied
    applied = _replace(text.replace("\r\n", "\n"), old.replace("\r\n", "\n"),
                       new.replace("\r\n", "\n"), replace_all)
    if applied is None:
        return None
    result, regions = applied

    def rebuilt(pos):
        return pos + result.count("\n", 0, pos)

    return result.replace("\n", "\r\n"), [(rebuilt(a), rebuilt(b)) for a, b in regions]


def resulting_text(event, path, decode=_utf8):





















    applied = _applied(event, path, decode)
    if applied is None or not applied[0].startswith(BOM):
        return applied
    text, regions = applied
    if regions is not None:
        regions = [(max(a - 1, 0), max(b - 1, 0)) for a, b in regions]
    return text[1:], regions


def touched_units(document, regions):


    touched = []
    for unit in document.units:
        if not unit.weighs:
            continue
        start, end = unit.locator["start"], unit.locator["end"]
        for a, b in regions:
            if (a < end and start < b) or (a == b and start <= a <= end):
                touched.append(unit)
                break
    return touched


def line_of(text, unit, span):





    if unit.frame is not None:
        return (text.count("\n", 0, unit.locator["start"])
                + unit.text.count("\n", 0, span[0]) + 1)
    return text.count("\n", 0, unit.locator["start"] + span[0]) + 1


def finding_line(text, unit, finding, rulebook, verb):






    start, end = finding.span
    rule = rulebook.rules[finding.rule]
    matched = unit.text[start:end].replace("\r", " ").replace("\n", " ")
    where = f"Line {line_of(text, unit, finding.span)}"
    if unit.frame is None:
        where += f" of {unit.surface}"
    return (f"{rule.id} {rule.name}. {where} carries \"{matched}\". "
            f"Rulebook {rulebook.name} {verb}.")


def density_record(document, findings, rulebook, touched=None, what="write"):







    vocab_rules = {rid for rid, rule in rulebook.rules.items()
                   if rule.tier == "density" and rid not in MARK_RULES}
    records, band = density(document, findings, MARK_RULES, vocab_rules)
    if touched is not None:
        ids = {unit.id for unit in touched}


        records = [r for r in records if r.unit in ids]
    marks = sum(r.marks for r in records)
    vocab = sum(r.vocab for r in records)
    state = "dense" if any(r.dense for r in records) else "not dense"
    return (f"Rulebook {rulebook.name}. Unit density for the units this {what} touched: "
            f"marks {marks}, vocab {vocab}, {state}. Document band: {band}."), band


def _prints_record(findings, rulebook):


    return rulebook.name == "general" or any(f.tier == "density" for f in findings)


def family_order(rulebook):





    ordered = []
    seen = set()
    for key in ("per_unit", "per_document", "per_rewrite"):
        for item in rulebook.self_check.get(key, []):
            rule_id = item["rule"]
            if rule_id not in seen:
                seen.add(rule_id)
                ordered.append(rule_id)
    ordered += sorted(rid for rid in rulebook.rules if rid not in seen)
    return ordered


def warn_context(text, document, findings, rulebook, touched=None, reserved=0):











    units = {unit.id: unit for unit in document.units}
    lines = []
    if _prints_record(findings, rulebook):
        lines.append(density_record(document, findings, rulebook, touched)[0])
    total = len(lines[0]) if lines else 0

    grouped = {}
    for f in findings:
        if f.tier in WARN_TIERS:
            grouped.setdefault(f.rule, []).append(f)
    order = [rid for rid in family_order(rulebook) if rid in grouped]

    limit = hookio.BUDGET - reserved
    left_out = []
    cut = False
    for index, rule_id in enumerate(order):
        family = grouped[rule_id]
        written = 0
        for f in family:
            line = finding_line(text, units[f.unit], f, rulebook, "warns on it")
            addition = len(line) + (1 if lines else 0)
            if total + addition > limit:
                cut = True
                break
            lines.append(line)
            total += addition
            written += 1
        if written < len(family):
            left_out.append((rule_id, len(family) - written))
        if cut:
            left_out += [(rid, len(grouped[rid])) for rid in order[index + 1:]]
            break

    if left_out:
        lines.append("Findings left out for length: " +
                     ", ".join(f"{rid} {count}" for rid, count in left_out) + ".")

    return "\n".join(lines)


def budgeted(lines, grouped, order, limit):








    lines = list(lines)
    total = len("\n".join(lines))
    left_out = []
    for rule_id in order:
        family = grouped[rule_id]
        written = 0
        if not left_out:
            for line in family:
                addition = len(line) + (1 if lines else 0)
                if total + addition > limit:
                    break
                lines.append(line)
                total += addition
                written += 1
        if written < len(family):
            left_out.append((rule_id, len(family) - written))
    if left_out:
        lines.append("Findings left out for length: " +
                     ", ".join(f"{rid} {count}" for rid, count in left_out) + ".")
    return "\n".join(lines)


def block_reason(text, document, blocks, rulebook, warnings):








    units = {unit.id: unit for unit in document.units}
    grouped = {}
    for f in blocks:
        grouped.setdefault(f.rule, []).append(
            finding_line(text, units[f.unit], f, rulebook, "blocks it"))
    lines = [f"super-humanizer: rulebook {rulebook.name} refused this write."]
    lines += [f"{warning}." for warning in warnings]
    order = [rid for rid in family_order(rulebook) if rid in grouped]
    return budgeted(lines, grouped, order, hookio.BUDGET)


def protect_spans(document, entries):


    protected = {}
    for unit_id, start, end, _ in protect.apply(document, entries):
        protected.setdefault(unit_id, []).append((start, end))
    return protected


def protect_warnings(entries):

    _, skips = protect.compile_patterns(entries)
    return [f"Marker warning: protect entry {entry!r} is skipped, {reason}"
            for entry, reason in skips]


def scan_text(text, path, rulebook, profile, protect_entries=(), extract=extract_text):






    newline = "\r\n" if "\r\n" in text else "\n"
    document = extract(text, path, newline)
    protected = protect_spans(document, protect_entries)
    units = {unit.id: unit for unit in document.units}
    return document, hook_findings(scan(document, rulebook, protected), units, rulebook,
                                   profile)


def hook_findings(findings, units, rulebook, profile):




    return voice.drop_silenced([f for f in findings if f.tier in HOOK_TIERS], units,
                               profile, rulebook.name)


def voice_profile(settings):



    if settings["voice"] != "mine":
        return [], []
    profile, warnings = voice.load_profile()
    if profile is None:
        return [], [NO_PROFILE]
    return profile, [f"Voice profile warning: {w}" for w in warnings]


def _code_extractor(target, root):








    relative = Path(target).relative_to(root).as_posix()
    return lambda text, _path, newline: extract_code.extract_text(text, relative, newline)


def _file_lines(document, target):


    python = extract_code.language_of(target) == "python"
    constant = extract_code.CANNOT_SEE if python else extract_code.SCRIPT_CANNOT_SEE
    return document.cannot_see[len(constant):]


def _message(head, sentences):
    return ". ".join([f"super-humanizer: {head}", *sentences]) + ("." if sentences else "")


def _state_path(session_id):



    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        return None
    return hookio.plugin_data() / "state" / f"{session_id}.json"


def _write_state(path, state):



    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(state))
        os.replace(tmp_name, path)
    except OSError:
        os.unlink(tmp_name)
        raise


def refusal_count(session_id, normalized_path):



    path = _state_path(session_id)
    if path is None or not path.is_file():
        return 0
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    if not isinstance(state, dict):
        return 0
    count = state.get(os.path.normcase(normalized_path), 0)
    return count if isinstance(count, int) else 0


def record_refusal(session_id, normalized_path):





    path = _state_path(session_id)
    if path is None:
        return 0
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(state, dict):
            state = {}
        key = os.path.normcase(normalized_path)
        count = state.get(key, 0)
        count = (count if isinstance(count, int) else 0) + 1
        state[key] = count
        _write_state(path, state)
        return count
    except (OSError, ValueError):
        return 0


def sweep_state(now):



    try:
        entries = list((hookio.plugin_data() / "state").iterdir())
    except OSError:
        return 0
    cutoff = now - STATE_MAX_AGE_DAYS * 24 * 60 * 60
    removed = 0
    for entry in entries:
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def handle(event):

    target = hookio.normalize_path(event["tool_input"]["file_path"])


    if _is_overlay(target):
        cwd = event.get("cwd")
        if cwd and marker.find_marker(Path(hookio.normalize_path(cwd))) is not None:
            hookio.emit_block(GUARD_REASON.format(path=target))
        return


    if _is_installed_plugin_copy(target):
        cwd = event.get("cwd")
        if cwd and marker.find_marker(Path(hookio.normalize_path(cwd))) is not None:
            hookio.emit_block(GUARD_REASON.format(path=target))
        return

    marker_path = marker.find_marker(Path(target).parent)
    if marker_path is None:
        return
    if _is_marker(target):
        hookio.emit_block(GUARD_REASON.format(path=target))
    if _git_below_marker(target, marker_path.parent):
        hookio.emit_block(GUARD_REASON.format(path=target))

    settings, marker_warnings = marker.load_marker(marker_path)
    warnings = [f"Marker warning: {w}" for w in marker_warnings]
    warnings += protect_warnings(settings["protect"])
    outcome = marker.route(settings, marker_path.parent, target)
    if outcome in SKIP_NOTES:
        if warnings:
            hookio.emit_note(_message(SKIP_NOTES[outcome], warnings))
        return
    if outcome in ROUTE_NOTES:
        hookio.emit_note(_message(ROUTE_NOTES[outcome], warnings))

    try:
        edited = resulting_text(event, Path(target),
                                decode_code if outcome == "code" else _utf8)
    except extract_code.ExtractError as error:
        hookio.emit_note(_message(CODE_DECODE_FAILED.format(error=error)
                                  + ", so this write was not scanned", warnings))
    if edited is None:
        return
    text, regions = edited

    name = settings["rulebook"]
    if not isinstance(name, str) or not RULEBOOK_NAME.fullmatch(name):
        raise ValueError(f"marker rulebook {name!r} is not a rulebook name")
    book = load(hookio.plugin_root() / "references" / "rulebooks" / f"{name}.json",
                hookio.plugin_data() / f"{name}.overlay.json")
    warnings += [f"Rulebook warning: {w}" for w in book.warnings]
    notes = []
    if outcome == "prompt":
        notes.append(PROMPT_SCANNED_NOTE)
    elif outcome == "code":
        notes.append(CODE_SCANNED_NOTE)
    profile, voice_notes = voice_profile(settings)
    notes += voice_notes

    if outcome == "prompt":
        extractor = extract_prompt.extract_text
    elif outcome == "code":
        extractor = _code_extractor(target, marker_path.parent)
    else:
        extractor = extract_text
    document, findings = scan_text(text, target, book, profile, settings["protect"],
                                    extract=extractor)


    unread = _file_lines(document, target) if outcome == "code" else []
    if unread and not document.units:
        hookio.emit_note(_message(CODE_UNREAD_NOTE.format(line=_NOTHING_READ.sub("", unread[0])),
                                  unread[1:] + voice_notes + warnings))
        return

    blocks = [f for f in findings if f.tier == "block"]
    if blocks:
        reason = block_reason(text, document, blocks, book, warnings)
        session_id = event.get("session_id")
        state_path = _state_path(session_id)
        if state_path is not None and not state_path.is_file():
            sweep_state(time.time())
        count = record_refusal(session_id, target)
        if count > REFUSAL_LIMIT:
            hookio.emit_ask(reason)
        hookio.emit_block(reason)

    touched = None if regions is None else touched_units(document, regions)
    warns = sum(1 for f in findings if f.tier in WARN_TIERS)
    if warns:
        head = f"{warns} warn{'' if warns == 1 else 's'}, {book.name}"
    elif _prints_record(findings, book):
        head = f"density {density_record(document, findings, book)[1]}, {book.name}"
    else:
        head = f"clean, {book.name}"
    message = _message(head, notes + unread + warnings)
    context = warn_context(text, document, findings, book, touched, reserved=len(message))
    if context:
        hookio.emit_context(context, message)
    hookio.emit_note(message)


if __name__ == "__main__":
    try:
        hookio.run_guarded(lambda: handle(hookio.read_event()))
    finally:
        if os.environ.get(PRINT_MODULES) == "1":
            sys.stderr.write(" ".join(sorted(name for name in sys.modules
                                             if name.startswith("scripts."))) + "\n")
