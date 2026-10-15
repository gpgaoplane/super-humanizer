






import json
import os
import re
import tempfile
from pathlib import Path

from scripts import scan, structure
from scripts.records import Document, Unit

HOME_ENV = "SUPERHUMANIZER_HOME"
PROFILE_NAME = "voice-profile.json"
NO_PROFILE = "Voice mine: no profile learned yet"
LEDGER_NAME = "ledger.jsonl"

KINDS = ("diction", "mark", "device", "structure", "avoid")

SLIP = "slip"

PROFILE_KINDS = KINDS + (SLIP,)
STATES = ("watch", "confirmed")

CONSUMERS = {"diction": "rewrite-prompt", "mark": "density-silence",
             "device": "rewrite-licence", "structure": "rewrite-prompt", "avoid": "self-check",
             "slip": "rewrite-normalise"}

SOURCES = ("judged", "stated", "sample")

TEACHING = ("voice", "slip")

RECENT_NAME = "learn/recent.json"
LEARN_HINT = ("Learn it from your own documents: /humanize learn <folder> "
              "[--recent NAME ...], which reads a folder of documents you wrote and writes the "
              "profile. Nothing runs until you name a folder.")
CLASSES = ("calibration", "scope or standard", "evidence selection", "voice", "slop",
           "artifact conflict")
WATCH_AT, CONFIRMED_AT, PROMOTE_AT = 1, 2, 2

CONFIRMED_TASKS = 2


HELD_BY = {"general": {"density": "design at density, where general counts marks and listed words"}}


TAKEN_FROM_C018 = ("C156", "C157")


TEMPLATE_FILES = ("references/register-prose.md", "references/judgment-checklist.md")
DEAD_LETTER = ("profile entry {entry!r} of kind {kind} names {enforced_at!r} as its consumer, "
               "which is {consumer!r} for that kind, so the entry is refused and layers nothing")
_REFUSED = ", so the entry is refused and layers nothing"
_LEDGER_ID = re.compile("L([0-9]+)")
_BOM = chr(0xFEFF).encode("utf-8")
_NEWLINE = chr(10).encode("ascii")


def home():




    raw = os.environ.get(HOME_ENV)
    return Path(raw).expanduser() if raw else Path.home() / ".claude" / "super-humanizer"


def _refusal(item, number):


    if not isinstance(item, dict):
        return f"profile entry number {number} is no mapping" + _REFUSED
    text = item.get("entry")
    if not isinstance(text, str) or not text.strip():
        return f"profile entry number {number} holds no entry text" + _REFUSED
    kind, state = item.get("kind"), item.get("state")
    if kind not in PROFILE_KINDS:
        return (f"profile entry {text!r} has kind {kind!r}, which is none of "
                f"{', '.join(PROFILE_KINDS)}" + _REFUSED)
    if state not in STATES:
        return (f"profile entry {text!r} has state {state!r}, which is neither watch nor "
                "confirmed" + _REFUSED)
    if item.get("enforced_at") != CONSUMERS[kind]:
        return DEAD_LETTER.format(entry=text, kind=kind, enforced_at=item.get("enforced_at"),
                                  consumer=CONSUMERS[kind])
    silences = item.get("silences", [])
    if not isinstance(silences, list) or not all(isinstance(rule, str) for rule in silences):
        return (f"profile entry {text!r} has silences {silences!r}, which is no list of "
                "rule ids" + _REFUSED)
    evidence = item.get("evidence", [])
    if not isinstance(evidence, list):
        return f"profile entry {text!r} has evidence {evidence!r}, which is no list" + _REFUSED
    recent = item.get("recent")
    if recent is not None and not isinstance(recent, bool):
        return (f"profile entry {text!r} has recent {recent!r}, which is none of true, false "
                "and null" + _REFUSED)
    return None


def load_profile(path=None):











    path = home() / PROFILE_NAME if path is None else Path(path)
    if not path.is_file():
        return None, []
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        return [], [f"the voice profile at {path} could not be read as JSON, {error}, so "
                    "every entry it holds is refused and layers nothing"]
    if not isinstance(raw, list):
        return [], [f"the voice profile at {path} holds no JSON list, so every entry it holds "
                    "is refused and layers nothing"]
    entries, warnings = [], []
    for number, item in enumerate(raw, 1):
        refusal = _refusal(item, number)
        if refusal is None:
            entries.append(item)
        else:
            warnings.append(refusal)
    return entries, warnings


def in_force(entries, rulebook_name):






    kinds = (PROFILE_KINDS if rulebook_name == "general"
             else ("diction", "structure", "avoid", SLIP))
    return [entry for entry in entries or []
            if entry["state"] == "confirmed" and entry["kind"] in kinds]


def avoid_lines(entries, rulebook_name):




    live = in_force(entries, rulebook_name)
    if not live:
        return None
    return {"avoid": [entry["entry"] for entry in live if entry["kind"] == "avoid"]}


def rewrite_block(entries, rulebook_name):











    live = sorted(in_force(entries, rulebook_name),
                  key=lambda entry: entry.get("recent") is not True)
    block = {
        "prefer": [{"entry": entry["entry"], "kind": entry["kind"]} for entry in live
                   if entry["kind"] in ("diction", "structure")
                   or (entry["kind"] == "mark" and not entry.get("silences"))],
        "licences": [entry["entry"] for entry in live if entry["kind"] == "device"],
        "avoid": [entry["entry"] for entry in live if entry["kind"] == "avoid"],
    }
    slips = [entry["entry"] for entry in live if entry["kind"] == SLIP]
    if slips:
        block["slips"] = slips
    return block if any(block.values()) else None


def silences_of(entries, rulebook_name):








    if rulebook_name != "general":
        return []
    return [(entry["entry"].strip().casefold(), set(entry["silences"]))
            for entry in in_force(entries, rulebook_name)
            if entry.get("silences") and entry["kind"] not in ("avoid", SLIP)]


def drop_silenced(findings, units, entries, rulebook_name):





    silences = silences_of(entries, rulebook_name)
    kept = []
    for f in findings:
        taken = f.rule in TAKEN_FROM_C018
        if silences and (f.tier == "density" or taken) and f.span is not None:
            start, end = f.span
            matched = units[f.unit].text[start:end].strip().casefold()
            if any(("C018" if taken else f.rule) in rules and matched == text
                   for text, rules in silences):
                continue
        kept.append(f)
    return kept


def _ledger_rows(data):


    if data.startswith(_BOM):
        data = data[len(_BOM):]
    lines = data.split(_NEWLINE)
    if lines[-1] == b"":
        lines.pop()
    rows, warnings = [], []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line.decode("utf-8"))
        except ValueError:
            row = None
        if isinstance(row, dict):
            rows.append(row)
        else:
            warnings.append(f"ledger line {number} is no JSON object, so it is left unread")
    return rows, warnings


def read_ledger(path=None):



    path = home() / LEDGER_NAME if path is None else Path(path)
    if not path.is_file():
        return [], []
    try:
        data = path.read_bytes()
    except OSError as error:
        return [], [f"the ledger at {path} could not be read, {error}"]
    return _ledger_rows(data)


def next_id(rows):

    numbers = [int(match.group(1)) for row in rows
               if isinstance(row.get("id"), str) and (match := _LEDGER_ID.fullmatch(row["id"]))]
    return f"L{max(numbers, default=0) + 1:04d}"


def _pair(row):

    pair = (row.get("retro_digest"), row.get("rid"))
    return pair if all(isinstance(half, str) for half in pair) else None


def pairs(rows):



    return {_pair(row) for row in rows} - {None}


def append_rows(rows, path=None):













    path = home() / LEDGER_NAME if path is None else Path(path)
    refusals = []
    try:
        data = path.read_bytes() if path.is_file() else b""
        taken = _ledger_rows(data)[0]
        held = pairs(taken)
        written, lines = [], []
        for number, row in enumerate(rows, 1):
            halves = (row.get("retro_digest"), row.get("rid"))
            if any(half is not None and not isinstance(half, str) for half in halves):
                refusals.append(f"row {number} of this append holds a retro_digest or rid "
                                "that is no string, so it is malformed and was left out")
                continue
            pair = _pair(row)
            if pair in held:
                source = "learn" if row.get("source") == "sample" else "retro"
                refusals.append(f"row {pair[1]} of {source} {pair[0][:12]} is already in the "
                                "ledger, so it was left out")
                continue
            if pair is not None:
                held.add(pair)
            stored = {"id": next_id(taken), **{key: value for key, value in row.items()
                                               if key != "id"}}
            taken.append(stored)
            written.append(stored["id"])
            lines.append(json.dumps(stored))
        if not lines:
            return [], refusals
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(line + chr(10) for line in lines).encode("utf-8")
        if data and not data.endswith(_NEWLINE):
            payload = _NEWLINE + payload
        with open(path, "ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        return [], refusals + [f"the ledger at {path} could not be written, {error}, so no "
                               "row was appended"]
    return written, refusals


def _entry_key(text):

    return text.strip().casefold()


def _side(text):


    return " ".join(text.split()) if isinstance(text, str) else ""


def _task(row):


    task = row.get("task")
    return (task.strip() or None) if isinstance(task, str) else None


def _measured(text, book):




    found = {f.rule for f in _scan_paragraph(text, book) if f.tier == "density"}
    if any(f.rule in TAKEN_FROM_C018 for f in _scan_paragraph(f"word {text} word", book)):
        found.add("C018")
    return sorted(found)


def _scan_paragraph(text, book):
    unit = Unit(id="u0001", kind="paragraph", surface="paragraph 1", text=text,
                locator={"start": 0, "end": len(text)})
    document = Document(path="", format="markdown", units=[unit], cannot_see=[],
                        encoding="utf-8", newline=chr(10))
    return scan.scan(document, book)


def recent_documents(path=None):




    path = home() / RECENT_NAME if path is None else Path(path)
    if not path.is_file():
        return set(), []
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        return set(), [f"the recent list at {path} could not be read, {error}, so no "
                       "document reads as recent"]
    except ValueError:
        raw = None
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return set(), [f"the recent list at {path} holds no JSON list of strings, so no "
                       "document reads as recent"]
    return set(raw), []


def harvest(rows, book, recent=None):













































    warnings, voiced = [], []
    if recent is None:
        recent, read = recent_documents()
        warnings.extend(read)
    for row in rows:
        cls = row.get("class")
        if cls not in TEACHING:
            continue
        text, kind = row.get("entry"), row.get("kind")
        kinds = (SLIP,) if cls == SLIP else KINDS
        if not isinstance(row.get("id"), str):
            warnings.append(f"a {cls} row of the ledger holds the id {row.get('id')!r}, which "
                            "is no text the evidence can cite, so the harvest passed it over")
        elif kind in PROFILE_KINDS and kind not in kinds:
            warnings.append(f"ledger row {row['id']} of class {cls} names kind {kind!r}, "
                            f"which is no kind of class {cls}, so the harvest passed it over")
        elif kind in kinds and isinstance(text, str) and text.strip():
            voiced.append(row)
            if _task(row) is None:
                warnings.append(f"ledger row {row['id']} of class {cls} names no task, so "
                                "the harvest counts it toward no task")
        else:
            warnings.append(f"ledger row {row.get('id')} of class {cls} names no kind of "
                            f"{', '.join(kinds)} with an entry text, so the harvest passed "
                            "it over")
    keys = [(row["kind"], _entry_key(row["entry"])) for row in voiced]
    edits = [(row["kind"], _side(row.get("before")), _side(row.get("after"))) for row in voiced]
    members, root, partner, first, told = {}, {}, {}, {}, set()
    for index, key in enumerate(keys):
        members.setdefault(key, []).append(index)
        root[key] = key

    def label(key):
        return voiced[members[key][0]]["entry"].strip()

    for index, edit in enumerate(edits):
        if not all(edit[1:]):
            continue
        at = first.setdefault(edit, index)
        target, source = keys[at], keys[index]
        if root[target] == root[source] or (source, edit) in told:
            continue
        told.add((source, edit))
        named = ", ".join(voiced[i]["id"] for i in members[source] if edits[i] == edit)
        head = (f"rows {named} named {label(source)!r} for the edit of {voiced[at]['id']}'s "
                f"{voiced[at]['entry'].strip()!r}")
        if target in partner:
            warnings.append(f"{head}, which already counts {label(partner[target])!r}, so "
                            f"{label(source)!r} stays apart")
        elif source in partner:
            warnings.append(f"{head}, and {label(source)!r} already counts with "
                            f"{label(partner[source])!r}, so {label(target)!r} stays apart")
        else:
            root[source] = target
            partner[target], partner[source] = source, target
            kept, left = sorted((target, source), key=lambda key: members[key][0])
            warnings.append(f"{head}, so {label(left)!r} is left out and the two count as "
                            f"{label(kept)!r}")
    groups = {}
    for index, key in enumerate(keys):
        groups.setdefault(root[key], []).append(index)
    ordered = sorted(groups.values(), key=lambda members: (
        all(voiced[index].get("change") != "deleted" for index in members),
        PROFILE_KINDS.index(voiced[members[0]]["kind"]), members[0]))
    entering = [[voiced[index] for index in members] for members in ordered]
    entering = [group for group in entering if len(group) >= WATCH_AT
                or any(row.get("source") == "stated" for row in group)]

    def confirmed(group):
        tasks = {_task(row) for row in group} - {None}
        return (any(row.get("source") == "stated" for row in group)
                or (len(group) >= CONFIRMED_AT and len(tasks) >= CONFIRMED_TASKS))

    avoided = {_entry_key(row["entry"]): group[0]["entry"].strip() for group in entering
               if group[0]["kind"] == "avoid" and confirmed(group) for row in group}
    entries = []
    for group in entering:
        kind, text = group[0]["kind"], group[0]["entry"].strip()
        evidence = [row["id"] for row in group]
        clash = next((avoided[key] for key in (_entry_key(row["entry"]) for row in group)
                      if key in avoided), None)
        if kind in ("device", "diction") and clash is not None:
            warnings.append(f"the {kind} entry {text!r} names the text of the avoid entry "
                            f"{clash!r}, and an avoid entry outranks it, so the harvest left "
                            f"it out, evidence {', '.join(evidence)}")
            continue
        samples = [row for row in group if row.get("source") == "sample"]
        entries.append({"entry": text, "kind": kind,
                        "state": "confirmed" if confirmed(group) else "watch",
                        "evidence": evidence, "enforced_at": CONSUMERS[kind],
                        "silences": [] if kind in ("avoid", SLIP) else _measured(text, book),
                        "recent": any(isinstance(row.get("document"), str)
                                      and row["document"] in recent for row in samples)
                        if samples else None})
    return entries, warnings


def _held_key(item):


    kind, text = item.get("kind"), item.get("entry")
    return (kind if isinstance(kind, str) else repr(kind),
            _entry_key(text) if isinstance(text, str) else repr(text))


def write_profile(entries, path=None):











    path = home() / PROFILE_NAME if path is None else Path(path)
    try:
        held = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else []
    except (OSError, ValueError):
        held = []
    kept = {_held_key(entry) for entry in entries}
    dropped = [(item.get("entry"), item.get("kind")) for item in
               (held if isinstance(held, list) else []) if isinstance(item, dict)
               and _held_key(item) not in kept]
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
                                    suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(json.dumps(entries, indent=1) + chr(10))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
    return path, dropped


def promotions(rows, book):











    named = {}
    for row in rows:
        rule = row.get("rule")
        if row.get("class") == "slop" and isinstance(rule, str):
            named.setdefault(rule, []).append(row.get("id"))
    order, argued = book.tier_order, []
    for rule_id, ids in named.items():
        if len(ids) < PROMOTE_AT:
            continue
        rule = book.rules.get(rule_id)
        if rule is None:
            argued.append((rule_id, f"absent from the {book.name} rulebook", ids))
            continue
        held = HELD_BY.get(book.name, {}).get(rule.tier)
        if held is not None:
            argued.append((rule_id, held, ids))
            continue
        tier = "warn" if rule.patterns else "self-check"
        if order.index(rule.tier) >= order.index(tier):
            tier = rule.tier
        argued.append((rule_id, tier, ids))
    return argued


def _blocks(text):


    blocks, lines = [], []
    for line in text.splitlines() + [""]:
        if line.strip():
            lines.append(line.strip())
        elif lines:
            blocks.append(" ".join(lines))
            lines = []
    return blocks


def _grams(text):

    words = structure.word_tokens(text)
    size = structure.SHARED_NGRAM
    return {tuple(words[index:index + size]) for index in range(len(words) - size + 1)}


def template_hits(rows, texts):







    held = {name: {gram for block in _blocks(text) for sentence in structure.sentence_texts(block)
                   for gram in _grams(sentence)} for name, text in texts.items()}
    hits = []
    for row in rows:
        before = row.get("before")
        if row.get("class") != "voice" or not isinstance(before, str):
            continue
        grams = _grams(before)
        hits.extend((row.get("id"), name) for name, sentences in held.items() if grams & sentences)
    return hits
