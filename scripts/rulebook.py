





import json
import re
from dataclasses import dataclass, field

from scripts import selfcheck

SCHEMA_VERSION = 1
_FLAG_MAP = {"ignore_case": re.IGNORECASE, "multiline": re.MULTILINE}




UNIT_KINDS = frozenset({
    "heading", "paragraph", "list_item", "table_cell", "caption", "title", "label", "notes",
    "comment", "docstring", "prose_string", "commit_subject", "commit_body", "front_matter",
    "code"})
DOCUMENT_FORMATS = frozenset({"markdown", "txt", "prompt", "code prose", "pptx", "docx",
                              "xlsx", "pdf"})


class RulebookError(Exception):
    pass


@dataclass
class PatternEntry:
    id: str
    match: str
    type: str = "literal"
    flags: list = field(default_factory=list)
    fix: dict | None = None
    exceptions: list = field(default_factory=list)
    basis: str = ""
    entry_class: str | None = None
    qualifier: str | None = None
    compiled: object = None


@dataclass
class Rule:
    id: str
    name: str
    rule_class: str
    tier: str
    per: str


    home: str
    category: str = ""
    formats: dict = field(default_factory=dict)
    patterns: list = field(default_factory=list)
    question: str | None = None
    examples: dict = field(default_factory=dict)
    limits: str = ""
    signal: list = field(default_factory=list)



@dataclass
class Rulebook:
    name: str
    version: int
    tier_order: list
    self_check: dict
    exceptions: dict
    rules: dict
    warnings: list = field(default_factory=list)
    overlay_changes: list = field(default_factory=list)


def _entry(raw):
    e = PatternEntry(
        id=raw["id"], match=raw["match"], type=raw.get("type", "literal"),
        flags=raw.get("flags", []), fix=raw.get("fix"),
        exceptions=raw.get("exceptions", []), basis=raw.get("basis", ""),
        entry_class=raw.get("class"), qualifier=raw.get("qualifier"),
    )
    source = e.match if e.type == "regex" else re.escape(e.match)
    if "word_boundary" in e.flags:
        source = r"\b" + source + r"\b"
    if "line_initial" in e.flags:
        source = r"^\s*" + source
    if "standalone" in e.flags:
        source = r"^\s*" + source + r"\s*$"
    bits = 0
    for name in e.flags:
        bits |= _FLAG_MAP.get(name, 0)
    if "line_initial" in e.flags or "standalone" in e.flags:
        bits |= re.MULTILINE
    e.compiled = re.compile(source, bits)
    return e


def _rule(rule_id, raw):
    return Rule(
        id=rule_id, name=raw["name"], rule_class=raw["class"], tier=raw["tier"],
        per=raw.get("per", "unit"), home=raw.get("home", ""),
        category=raw.get("category", ""), formats=raw.get("formats", {}),
        patterns=[_entry(p) for p in raw.get("patterns", [])],
        question=raw.get("question"), examples=raw.get("examples", {}),
        limits=raw.get("limits", ""), signal=raw.get("signal", []),
    )


def _check_formats(rule, warnings):



    if not isinstance(rule.formats, dict):
        return
    known = DOCUMENT_FORMATS | UNIT_KINDS
    for name in rule.formats:
        if name not in known:
            warnings.append(f"rule {rule.id} names {name!r} in formats, which is neither a "
                            "document format nor a unit kind, so that key is ignored")
    rule.formats = {name: value for name, value in rule.formats.items() if name in known}


def _check_signal(rule, warnings):



    signal = rule.signal
    if isinstance(signal, list) and all(isinstance(word, str) and word.strip()
                                        for word in signal):
        return
    warnings.append(f"rule {rule.id} carries a signal that is not a list of words, so it is "
                    "ignored")
    rule.signal = []


def _apply_list_ops(current, ops, warnings, where):

    by_id = {e.id: e for e in current}
    for raw in ops.get("add", []):
        by_id[raw["id"]] = _entry(raw)
    for dead in ops.get("remove", []):
        if dead in by_id:
            del by_id[dead]
        else:
            warnings.append(f"{where}: overlay removes pattern id {dead!r}, which is not present")
    return list(by_id.values())


def load(shipped_path, overlay_path=None):
    raw = json.loads(shipped_path.read_text(encoding="utf-8-sig"))
    if raw.get("version") != SCHEMA_VERSION:
        raise RulebookError(
            f"{shipped_path}: version {raw.get('version')!r}, expected {SCHEMA_VERSION}")
    rb = Rulebook(
        name=raw["rulebook"], version=raw["version"], tier_order=raw["tier_order"],
        self_check=raw.get("self_check", {}), exceptions=raw.get("exceptions", {}),
        rules={rid: _rule(rid, r) for rid, r in raw.get("rules", {}).items()},
    )
    for rule in rb.rules.values():
        _check_formats(rule, rb.warnings)
        _check_signal(rule, rb.warnings)
    rb.warnings.extend(selfcheck.generator_warnings(rb.self_check, UNIT_KINDS, DOCUMENT_FORMATS))
    if overlay_path is None or not overlay_path.exists():
        return rb







    try:
        over = json.loads(overlay_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        rb.warnings.append(
            f"the overlay at {overlay_path} could not be read, so the shipped rulebook runs "
            f"unchanged: {exc}")
        return rb
    if not isinstance(over, dict):
        rb.warnings.append(
            f"the overlay at {overlay_path} has a top level that is a "
            f"{type(over).__name__} and not an object, so the shipped rulebook runs unchanged")
        return rb
    over_rules = over.get("rules", {})
    if not isinstance(over_rules, dict):
        rb.warnings.append(
            f"the overlay at {overlay_path} has a 'rules' key holding a "
            f"{type(over_rules).__name__} and not an object, so the shipped rulebook runs unchanged")
        return rb
    for rid, changes in over_rules.items():
        if not isinstance(changes, dict):
            rb.warnings.append(
                f"overlay rule {rid} holds a {type(changes).__name__} and not an object, so it is "
                f"ignored")
            continue
        if rid not in rb.rules:
            rb.warnings.append(f"overlay names rule {rid}, which the shipped rulebook lacks")
            continue
        rule = rb.rules[rid]
        for key, value in changes.items():
            if key == "patterns" and isinstance(value, dict):
                rule.patterns = _apply_list_ops(rule.patterns, value, rb.warnings, rid)
                rb.overlay_changes.append((rid, "patterns", "shipped", "changed"))
            elif hasattr(rule, key):
                rb.overlay_changes.append((rid, key, getattr(rule, key), value))
                setattr(rule, key, value)
                if key == "formats":
                    _check_formats(rule, rb.warnings)
                elif key == "signal":
                    _check_signal(rule, rb.warnings)
            else:
                rb.warnings.append(f"overlay names unknown field {key!r} on {rid}")
    return rb
