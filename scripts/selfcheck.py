






























import re
from dataclasses import dataclass

CAP = 5


NEEDS_VOICE = "voice"

_OWN_HITS = re.compile(r"^([A-Za-z0-9]+)'s own pattern hits\b")
_KINDS = re.compile(r"^unit kind:(.*)$")


@dataclass
class Slot:
    asked: list
    unasked: list


@dataclass
class Plan:
    per_unit: dict
    per_document: list


def _generator_rule(generator):


    m = _OWN_HITS.match(generator)
    return m.group(1) if m else None


def generator_kinds(generator):




    m = _KINDS.match(generator or "")
    return frozenset(name.strip() for name in m.group(1).split(",")) if m else None


def _items(generator):


    if generator is None:
        return ()
    if isinstance(generator, (str, dict)):
        return (generator,)
    return tuple(generator)


def _form(item):


    form = item.get("form") if isinstance(item, dict) else item
    return form if isinstance(form, str) else None


def _off(item):


    off = item.get("off") if isinstance(item, dict) else None
    if not isinstance(off, list):
        return frozenset()
    return frozenset(name for name in off if isinstance(name, str))


def alternatives(generator):



    return tuple(form for form in map(_form, _items(generator)) if form is not None)


def _live(generator, fmt, kind=None):


    return tuple(_form(item) for item in _items(generator)
                 if _form(item) is not None and not _off(item) & {fmt, kind})


def reads_hits(entry):


    return any(_generator_rule(g) is not None for g in alternatives(entry.get("generator")))


def _scope_warnings(where, item, known):



    warnings = [f"{where} names {key!r} in a generator alternative, which is neither form "
                "nor off, so that key is ignored"
                for key in sorted(set(item) - {"form", "off"}, key=str)]
    if _form(item) is None:
        warnings.append(f"{where} carries a generator alternative with no form string, so "
                        "that alternative matches nothing")
    off = item.get("off", [])
    if not isinstance(off, list):
        warnings.append(f"{where} carries a generator alternative whose off is no list, so "
                        "it is ignored")
        off = []
    for name in off:
        if not isinstance(name, str) or name not in known:
            warnings.append(f"{where} names {name!r} in a generator alternative's off list, "
                            "which is neither a document format nor a unit kind, so that "
                            "name is ignored")
    return warnings


def generator_warnings(self_check, known_kinds, known_formats=frozenset()):







    warnings = []
    for scope, entries in self_check.items():
        for entry in entries:
            where = f"self-check entry {entry.get('id')}"
            if "needs" in entry and scope != "per_document":
                warnings.append(f"{where} names {entry['needs']!r} in its needs key in the "
                                f"{scope} list, which only a per_document entry reads, so "
                                "that key is ignored")
            elif "needs" in entry and entry["needs"] != NEEDS_VOICE:
                warnings.append(f"{where} names {entry['needs']!r} in its needs key, which "
                                f"is not {NEEDS_VOICE!r}, so that key is ignored")
            for item in _items(entry.get("generator")):
                if isinstance(item, dict):
                    warnings.extend(_scope_warnings(where, item, known_kinds | known_formats))
                kinds = generator_kinds(_form(item))
                for name in sorted(kinds - known_kinds) if kinds is not None else ():
                    warnings.append(f"{where} names {name!r} in "
                                    "its unit kind generator, which is not a unit kind, so "
                                    "that name is ignored")
    return warnings


def _rule_on(entry, book, fmt, kind=None):


    rule = book.rules.get(entry.get("rule"))
    if rule is None:
        return True
    return "off" not in (rule.formats.get(fmt), rule.formats.get(kind) if kind else None)


def _generator_matches(generator, unit, unit_findings):
    kinds = generator_kinds(generator)
    if kinds is not None:
        return unit.kind in kinds
    rule_id = _generator_rule(generator)
    if rule_id is not None:
        return any(f.rule == rule_id for f in unit_findings)
    return re.search(generator, unit.text, re.IGNORECASE) is not None


def _entry_matches(entry, unit, unit_findings, fmt):
    generator = entry.get("generator")
    if alternatives(generator):
        return any(_generator_matches(g, unit, unit_findings)
                   for g in _live(generator, fmt, unit.kind))
    phrases = entry.get("phrases")
    if phrases:
        lowered = unit.text.lower()
        return any(p.lower() in lowered for p in phrases)
    return False


def eligible(document, findings, book, unit_id, units=None, by_unit=None):





    if units is None:
        unit = next((u for u in document.units if u.id == unit_id), None)
    else:
        unit = units.get(unit_id)
    if unit is None:
        return []
    if by_unit is None:
        unit_findings = [f for f in findings if f.unit == unit_id]
    else:
        unit_findings = by_unit.get(unit_id, [])
    return [entry for entry in book.self_check.get("per_unit", [])
            if _rule_on(entry, book, document.format, unit.kind)
            and _entry_matches(entry, unit, unit_findings, document.format)]


def _document_eligible(entry, book, document, weighing_units):



    if not _rule_on(entry, book, document.format):
        return False
    generator = entry.get("generator")
    if not alternatives(generator):
        return True
    named = [(generator_kinds(_form(item)), _off(item)) for item in _items(generator)
             if _form(item) is not None and document.format not in _off(item)]
    if any(kinds is None for kinds, _ in named):
        return True
    return any(unit.kind in kinds and unit.kind not in off
               for kinds, off in named for unit in weighing_units)


def _rotate(entries, index):

    n = len(entries)
    if n <= CAP:
        return list(entries), []
    start = index % n
    asked = [entries[(start + k) % n] for k in range(CAP)]
    asked_ids = {e["id"] for e in asked}
    unasked = [e["id"] for e in entries if e["id"] not in asked_ids]
    return asked, unasked


def plan_questions(document, findings, book, voice=None):
















    per_unit = {}
    weighing_units = [u for u in document.units if u.weighs]
    units, by_unit = {}, {}
    for unit in document.units:
        units.setdefault(unit.id, unit)
    for finding in findings:
        by_unit.setdefault(finding.unit, []).append(finding)
    for i, unit in enumerate(weighing_units):
        entries = eligible(document, findings, book, unit.id, units, by_unit)
        asked, unasked = _rotate(entries, i)
        per_unit[unit.id] = Slot(asked=asked, unasked=unasked)

    per_document = [entry for entry in book.self_check.get("per_document", [])
                    if (voice is not None or entry.get("needs") != NEEDS_VOICE)
                    and _document_eligible(entry, book, document, weighing_units)]
    if voice:
        for i, phrase in enumerate(voice.get("avoid", [])):
            per_document.append({
                "id": f"mine-avoid-{i}",
                "rule": "mine",
                "question": f'Does the text use "{phrase}", which the voice profile avoids?',
                "pass_line": "the phrase is absent",
                "fire_line": f'FIRE: "{phrase}" appears, which the voice profile avoids',
                "basis": "the voice profile's own avoid list",
            })

    return Plan(per_unit=per_unit, per_document=per_document)


def per_rewrite(book):















    return list(book.self_check.get("per_rewrite", []))
