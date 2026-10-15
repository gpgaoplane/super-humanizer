













































import re

from scripts.records import Finding
from scripts.units import sentences

OPENING_STEM_WORDS = 4
CLOSING_STEM_WORDS = 3
SHARED_NGRAM = 5
PATTERN_ROW_IDS = frozenset({"C072", "C085"})


_WORD = re.compile(r"[A-Za-z0-9']+")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_BOLD_LEAD = re.compile(r"^\*\*([^*\n]+)\*\*")
_CHECKMARK_LEAD = re.compile(r"^[✓✔]")
_HEADING_MARKER = re.compile(r"^#{1,6}\s+")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def word_tokens(text):


    return [w.lower() for w in _WORD.findall(text)]


def sentence_texts(text):



    return [piece for piece in _SENTENCE_END.split(text.strip()) if _WORD.search(piece)]


def _item_text(unit):

    return _BULLET.sub("", unit.text, count=1)


def _is_delimiter_row(line):



    stripped = line.strip()
    return bool(stripped) and "|" in stripped and "-" in stripped and set(stripped) <= set("|-: ")


def _list_runs(document):









    run = []
    for unit in document.units:
        if unit.kind == "list_item":
            if _BULLET.match(unit.text):
                run.append(unit)
            continue
        if run:
            yield run
        run = []
    if run:
        yield run


def _structural_c073(document, book):















    if "C073" not in book.rules:
        return
    if book.rules["C073"].formats.get(document.format) == "off":
        return
    for run in _list_runs(document):
        if len(run) < 5:
            continue
        words = [word_tokens(_item_text(u)) for u in run]
        if any(not w for w in words):
            continue
        first = words[0][0]
        if not first.endswith("ing") or any(w[0] != first for w in words[1:]):
            continue
        lengths = [len(_item_text(u).strip()) for u in run]
        band = max(lengths) - min(lengths)
        if band > 0.3 * (sum(lengths) / len(lengths)):
            continue
        yield Finding(rule="C073", rulebook=book.name, unit=run[0].id, span=None,
                      tier=book.rules["C073"].tier, source="cross-unit",
                      verdict="candidate", fix=None, category=book.rules["C073"].category)


def _structural_c075(document, book):













    if "C075" not in book.rules:
        return
    if book.rules["C075"].formats.get(document.format) == "off":
        return
    for run in _list_runs(document):
        if len(run) < 3:
            continue
        leads = [_BOLD_LEAD.match(_item_text(u)) for u in run]
        if any(m is None for m in leads):
            continue
        if any(m.group(1).rstrip().endswith(".") for m in leads):
            continue
        yield Finding(rule="C075", rulebook=book.name, unit=run[0].id, span=None,
                      tier=book.rules["C075"].tier, source="cross-unit",
                      verdict="candidate", fix=None, category=book.rules["C075"].category)


def _structural_c076(document, book):
























    if "C076" not in book.rules:
        return
    units = document.units
    for i, unit in enumerate(units):
        if unit.kind != "heading":
            continue
        if i + 1 >= len(units) or units[i + 1].kind != "paragraph":
            continue
        para = units[i + 1]
        heading_text = _HEADING_MARKER.sub("", unit.text).strip().lower()
        if not heading_text:
            continue
        spans = sentences(para.text)
        if not spans:
            continue
        start, end = spans[0]
        first_sentence = para.text[start:end].lower()
        if heading_text in first_sentence:
            yield Finding(rule="C076", rulebook=book.name, unit=para.id, span=None,
                          tier=book.rules["C076"].tier, source="cross-unit",
                          verdict="candidate", fix=None, category=book.rules["C076"].category)


def _structural_c077(document, book):













    if "C077" not in book.rules:
        return
    if book.rules["C077"].formats.get(document.format) == "off":
        return
    for unit in document.units:
        if unit.kind != "paragraph":
            continue
        lines = [line for line in unit.text.split("\n") if line.strip()]
        if len(lines) < 3:
            continue
        if not (_TABLE_ROW.match(lines[0]) and _is_delimiter_row(lines[1])):
            continue
        data_rows = [line for line in lines[2:] if _TABLE_ROW.match(line)]
        if not data_rows or len(data_rows) > 2:
            continue
        yield Finding(rule="C077", rulebook=book.name, unit=unit.id, span=None,
                      tier=book.rules["C077"].tier, source="cross-unit",
                      verdict="candidate", fix=None, category=book.rules["C077"].category)


def _structural_c155(document, book):








    if "C155" not in book.rules:
        return
    if book.rules["C155"].formats.get(document.format) == "off":
        return
    for run in _list_runs(document):
        if len(run) < 2:
            continue
        if all(_CHECKMARK_LEAD.match(_item_text(u)) for u in run):
            yield Finding(rule="C155", rulebook=book.name, unit=run[0].id, span=None,
                          tier=book.rules["C155"].tier, source="cross-unit",
                          verdict="candidate", fix=None, category=book.rules["C155"].category)


def structural(document, book):







    findings = []
    findings.extend(_structural_c073(document, book))
    findings.extend(_structural_c075(document, book))
    findings.extend(_structural_c076(document, book))
    findings.extend(_structural_c077(document, book))
    findings.extend(_structural_c155(document, book))
    return findings




_WORD_BEFORE = "(?<![A-Za-z0-9_])"
_WORD_AFTER = "(?![A-Za-z0-9_])"


def _qualifier(word):




    source = " *".join(re.escape(piece) for piece in word.split())
    if word[:1].isalnum():
        source = _WORD_BEFORE + source
    if word[-1:].isalnum():
        source += _WORD_AFTER
    return re.compile(source, re.IGNORECASE)


def notes_caveat(document, book):











    rule = book.rules.get("C080")
    if rule is None or document.format != "pptx":
        return []
    if rule.formats.get(document.format) == "off":
        return []
    patterns = [_qualifier(word) for word in rule.signal]
    presented = {}
    for unit in document.units:
        if unit.kind != "notes":
            presented.setdefault(unit.locator.get("slide"), []).append(unit.text)
    findings = []
    for unit in document.units:
        if unit.kind != "notes" or not unit.weighs or rule.formats.get(unit.kind) == "off":
            continue
        body = presented.get(unit.locator.get("slide"), [])
        missing = []
        for pattern in patterns:
            match = pattern.search(unit.text)
            if match and not any(pattern.search(text) for text in body):
                missing.append(match)
        if not missing:
            continue
        first = min(missing, key=lambda match: match.start())
        findings.append(Finding(rule="C080", rulebook=book.name, unit=unit.id,
                                span=first.span(), tier=rule.tier, source="cross-unit",
                                verdict="candidate", fix=None, category=rule.category))
    return findings


def _opening_stem_count(document):






    groups = {}
    for unit in document.units:
        if not unit.weighs:
            continue
        words = word_tokens(unit.text)
        if not words:
            continue
        groups.setdefault(tuple(words[:OPENING_STEM_WORDS]), []).append(unit.id)
    return sum(len(ids) for ids in groups.values() if len(ids) > 1)


def _closing_stem_count(document):






    groups = {}
    for unit in document.units:
        if not unit.weighs:
            continue
        words = word_tokens(unit.text)
        if not words:
            continue
        groups.setdefault(tuple(words[-CLOSING_STEM_WORDS:]), []).append(unit.id)
    return sum(len(ids) for ids in groups.values() if len(ids) > 1)


def _shared_ngram_count(document):




    owner = {}
    shared = set()
    for unit in document.units:
        if not unit.weighs:
            continue
        words = word_tokens(unit.text)
        grams = {tuple(words[i:i + SHARED_NGRAM])
                 for i in range(len(words) - SHARED_NGRAM + 1)}
        for gram in grams:
            seen_in = owner.get(gram)
            if seen_in is None:
                owner[gram] = unit.id
            elif seen_in != unit.id:
                shared.add(gram)
    return len(shared)


def pattern_rows(document, book):











    opening = _opening_stem_count(document)
    closing = _closing_stem_count(document)
    shared = _shared_ngram_count(document)
    return [
        Finding(rule="C072", rulebook="general", unit="document", span=None,
                tier="metric", source="cross-unit", verdict="n-a",
                category=book.rules["C072"].category,
                fix={"kind": "none", "text": f"opening-stem repeats: {opening}"}),
        Finding(rule="C085", rulebook="general", unit="document", span=None,
                tier="metric", source="cross-unit", verdict="n-a",
                category=book.rules["C085"].category,
                fix={"kind": "none", "text": f"closing-stem repeats: {closing}"}),
        Finding(rule="C072", rulebook="general", unit="document", span=None,
                tier="metric", source="cross-unit", verdict="n-a",
                category=book.rules["C072"].category,
                fix={"kind": "none", "text": f"shared 5-grams: {shared}"}),
    ]


GUIDE_HEADING_DEPTH = 3
GUIDE_PARAGRAPH_WORDS = 150
CAP_PARAGRAPH_WORDS = 250
LONG_LIST = 4


def _is_table(unit):


    lines = [line for line in unit.text.split("\n") if line.strip()]
    return len(lines) >= 2 and bool(_TABLE_ROW.match(lines[0])) and _is_delimiter_row(lines[1])


def _prose_paragraphs(document):
    return [u for u in document.units
            if u.kind == "paragraph" and u.weighs and not _is_table(u)]


def _c081(document):
    levels = []
    for unit in document.units:
        if unit.kind == "heading" and unit.weighs:
            match = _HEADING_MARKER.match(unit.text)
            if match:
                levels.append(len(match.group(0).strip()))
    deeper = sum(1 for level in levels if level > GUIDE_HEADING_DEPTH)
    return f"deepest heading level: {max(levels, default=0)}, headings deeper than three: {deeper}"


def _c082(document):
    lengths = [len(word_tokens(u.text)) for u in _prose_paragraphs(document)]
    over_target = sum(1 for n in lengths if n > GUIDE_PARAGRAPH_WORDS)
    over_cap = sum(1 for n in lengths if n > CAP_PARAGRAPH_WORDS)
    return (f"paragraphs over {GUIDE_PARAGRAPH_WORDS} words: {over_target}, "
            f"over {CAP_PARAGRAPH_WORDS} words: {over_cap}, "
            f"longest: {max(lengths, default=0)} words")


def _list_sections(document):


    section = 0
    placed = {}
    for unit in document.units:
        if unit.kind == "heading":
            section += 1
        placed[unit.id] = section
    return placed


def _c087(document):
    counts = [len(sentence_texts(u.text)) for u in _prose_paragraphs(document)]
    counts = [n for n in counts if n]
    mean = sum(counts) / len(counts) if counts else 0.0
    runs = list(_list_runs(document))
    long_runs = sum(1 for run in runs if len(run) >= LONG_LIST)
    bold = sum(1 for u in _prose_paragraphs(document) if _BOLD_LEAD.match(u.text))
    bold += sum(1 for run in runs for u in run if _BOLD_LEAD.match(_item_text(u)))
    placed = _list_sections(document)
    per_section = {}
    for run in runs:
        per_section[placed[run[0].id]] = per_section.get(placed[run[0].id], 0) + 1
    sizes = {}
    for run in runs:
        sizes[len(run)] = sizes.get(len(run), 0) + 1
    sharing = sum(n for n in sizes.values() if n > 1)
    return (f"sentences per paragraph: mean {mean:.2f}, most {max(counts, default=0)}, "
            f"bullet runs of four or more: {long_runs}, "
            f"bold blocks: {bold}, lists per section: most {max(per_section.values(), default=0)}, "
            f"lists sharing a length: {sharing}")


_COUNTS = (("C081", _c081), ("C082", _c082), ("C087", _c087))


def count_rows(document, book):








    return [Finding(rule=rule, rulebook=book.name, unit="document", span=None,
                    tier="metric", source="cross-unit", verdict="n-a",
                    category=book.rules[rule].category,
                    fix={"kind": "none", "text": count(document)})
            for rule, count in _COUNTS
            if rule in book.rules and book.rules[rule].formats.get(document.format) != "off"]
