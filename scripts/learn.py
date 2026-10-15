










import dataclasses
import difflib
import hashlib
import io
import itertools
import json
import os
import re
import statistics
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

from scripts import (density, extract_docx, extract_markdown, extract_pdf, office, report,
                     retro, scan, structure, units, voice)
from scripts.gate_write import MARK_RULES
from scripts.records import Document



GROUP_AT = 0.35


LAYOUT_AT = 10

RECUR_IN = 3

RECUR_CAP = 40

CITED_MAX = 10

LOCK_PREFIX = "~$"
QUESTIONS_NAME = "questions.json"
VERDICTS_NAME = "verdicts.json"
APPLIED_STEM = "verdicts.applied-"
REPORT_NAME = "learn-report.md"

FOLDER = "learn"

FORMATS = {".md": "markdown", ".markdown": "markdown", ".txt": "txt", ".docx": "docx",
           ".pdf": "pdf"}
SECTIONS = ("What ran", "Documents", "Tasks", "Recency", "Candidates", "Ledger", "Profile",
            "Older only", "Cannot see", "Limits")


STOP = frozenset("""
the be to of and a in that have i it for not on with he as you do at this but his by
from they we say her she or an will my one all would there their what so up out if about
who get which go me when make can like time no just him know take people into year your
good some could them see other than then now look only come its over think also back after
use two how our work first well way even new want because any these give day most us is
are was were been has had does did said made got went more many much very such own same
each every both few those here where why while through before between under again off
down against until since still too never always often ever should may might must shall
being let put need find tell ask seem feel try leave call three last long great little old
right big high small next thing part place case week point number world life hand man
woman child around another something nothing however without within though whether yes
upon per among during
""".split())

AT_OR_ABOVE, AT_OR_UNDER = "at or above", "at or under"



KIND_LINES = {
    "diction": "A word or a phrase the writer reaches for, which a rewrite keeps.",
    "mark": ("A punctuation mark the writer uses at a rate of their own, its glyph as the "
             "entry, which a rewrite keeps."),
    "device": ("A move the writer makes on purpose, such as a one-word fragment after a full "
               "sentence, which a rewrite may use."),
    "structure": ("A shape the writer gives a sentence, a paragraph or a list, which a rewrite "
                  "keeps."),
    "slip": ("A form the writer makes by mistake, such as a lowercase i, which a rewrite "
             "corrects to the full form."),
}

CLASS_OF = {"slip": "slip"}




SLIP_PATTERNS = {
    "lowercase i": re.compile(r"(?<![\w'\u2019.-])i(?![\w-]|\.\w)"),
    "chat shorthand": re.compile(r"\b(?:tbh|imo|imho|btw|idk|lol|afaik|iirc|ngl|smh|thx|pls"
                                 r"|plz|fwiw|lmk|omg|ofc)\b", re.IGNORECASE),
    "a space before a sentence mark": re.compile(r"(?<=\w)[ \t]+[.,;:!?](?=\s|$)"),
    "no space after a sentence mark": re.compile(r"(?<=[a-z])[.!?;:](?=[A-Z][a-z])"
                                                 r"|(?<=[a-z]),(?=[A-Za-z])"),
    **{f"{full} as {slip}": re.compile(rf"\b{re.escape(slip)}\b", re.IGNORECASE)
       for full, slip in retro.SLIP_FORMS},
}


CUT_APPLIED = "applied"
CUT_MISSED = "no heading unit, the cut was not applied"


EMPTIED = "holds no weighing unit after the until cut"

_TOKEN = re.compile(r"[a-z0-9']+")


_RAW_TOKEN = re.compile(r"[A-Za-z0-9']+")

_CURLY_APOSTROPHE = chr(0x2019)

_CORE = "docProps/core.xml"
_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"


_CONJUNCTIONS = frozenset({"and", "but", "or", "so", "yet", "nor"})
_FIRST_PERSON = frozenset({"i", "me", "my", "mine", "myself", "we", "us", "our", "ours",
                           "ourselves"})



_CONTRACTION = re.compile(r"\b(?:it|that|there|here|what|who|where|how|he|she|let)'s\b"
                          r"|[A-Za-z]'(?:t|d|m|re|ve|ll)\b", re.IGNORECASE)

_CLOSERS = "\"')]\u201d\u2019"


_COUNT_ROW = re.compile(r"c[0-9]{2}")

_EXTRACTORS = {"markdown": extract_markdown, "txt": extract_markdown, "docx": extract_docx,
               "pdf": extract_pdf}


@dataclass
class Sample:

    path: Path
    digest: str
    format: str
    document: Document
    text: str
    words: frozenset
    task: str = ""
    twin_of: str | None = None
    cut: str = ""
    creator: str = ""


class LearnError(Exception):
    pass


def _apostrophes_folded(text):



    return text.replace(_CURLY_APOSTROPHE, "'")


def normalised(document):


    return "\n".join(" ".join(_apostrophes_folded(unit.text).split())
                     for unit in document.units if unit.weighs).casefold()


def tokens(text):


    return _TOKEN.findall(_apostrophes_folded(text))


def word_set(text):

    return frozenset(tokens(text))


def jaccard(a, b):

    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _refused_suffix(path):

    what = f"a {path.suffix} file" if path.suffix else "a file with no suffix"
    return (f"{path.name}: {what}, and learn reads markdown, txt, docx and pdf files alone, "
            "so it was skipped")


def _cut(document, until_text):



    if not until_text:
        return document, ""
    if document.format != extract_pdf.FORMAT:
        document, dropped = retro.until(document, until_text)
        return document, CUT_APPLIED if dropped else CUT_MISSED
    wanted = until_text.casefold()
    for index, unit in enumerate(document.units):
        if unit.text.lstrip().casefold().startswith(wanted):
            return dataclasses.replace(document, units=document.units[:index]), CUT_APPLIED
    return document, CUT_MISSED


def _unweighed(path, document, module, cut):


    own = [line for line in document.cannot_see if line not in module.CANNOT_SEE]
    said = "".join(f". Its reader says {line}" for line in own)
    held = EMPTIED if cut == CUT_APPLIED else "holds no weighing unit"
    return f"{path.name}: {held}, so it was skipped{said}"


def _creator(data):



    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            root = ElementTree.fromstring(package.read(_CORE))
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError):
        return ""
    node = root.find(_CREATOR)
    return (node.text or "").strip() if node is not None else ""


def _mark_twins(samples, skipped):



    read = {}
    for sample in sorted(samples, key=lambda sample: (sample.digest, sample.path.name)):
        read.setdefault(sample.text, sample)
    for sample in samples:
        member = read[sample.text]
        if member is not sample:
            sample.twin_of = member.digest
            skipped.append(f"{sample.path.name}: read once, since its text equals "
                           f"{member.path.name}'s, so it writes no questions file")


def read_folder(folder, until_text=None):









    samples, skipped = [], []
    for path in sorted(Path(folder).iterdir(), key=lambda path: path.name):
        if not path.is_file() or path.name.startswith(LOCK_PREFIX):
            continue
        name = FORMATS.get(path.suffix.lower())
        if name is None:
            skipped.append(_refused_suffix(path))
            continue
        module = _EXTRACTORS[name]
        try:
            data = path.read_bytes()
            document = module.extract(path)
        except (OSError, ValueError, office.OfficeError) as error:
            skipped.append(f"{path.name}: could not be read, {type(error).__name__}: {error}, "
                           "so it was skipped")
            continue
        document, cut = _cut(document, until_text)
        if not any(unit.weighs for unit in document.units):
            skipped.append(_unweighed(path, document, module, cut))
            continue
        text = normalised(document)
        samples.append(Sample(path, hashlib.sha256(data).hexdigest(), name, document, text,
                              word_set(text), cut=cut,
                              creator=_creator(data) if name == "docx" else ""))
    _mark_twins(samples, skipped)
    return samples, skipped


def group(samples, at=GROUP_AT, absent=()):
















    read = [sample for sample in samples if sample.twin_of is None]
    absent = list(absent)
    nodes = read + absent
    root = list(range(len(nodes)))

    def find(index):
        while root[index] != index:
            index = root[index]
        return index

    pairs = [(first, second, jaccard(nodes[first].words, nodes[second].words))
             for first, second in itertools.combinations(range(len(nodes)), 2)]
    for first, second, value in pairs:
        if value >= at or nodes[first].text == nodes[second].text:
            root[find(first)] = find(second)
    families = {}
    for index, sample in enumerate(read):
        families.setdefault(find(index), []).append(sample)
    family_of = {sample.digest: find(index) for index, sample in enumerate(read)}
    for sample in samples:
        if sample.twin_of is not None:
            families[family_of[sample.twin_of]].append(sample)
    held = {}
    for index, record in enumerate(absent, len(read)):
        held.setdefault(find(index), set()).update(record.tasks)
    tasks = {}
    for key, members in families.items():
        digests = sorted(member.digest for member in members)
        ids = held.get(key, set())
        if len(ids) == 1:
            task, = ids
        else:
            task = hashlib.sha256("\n".join(sorted(set(digests))).encode("utf-8")).hexdigest()
        for member in members:
            member.task = task
        tasks[task] = sorted(tasks.get(task, []) + digests)
    for index, record in enumerate(absent, len(read)):
        if find(index) in families:
            record.task = families[find(index)][0].task
    nearest = max((value for first, second, value in pairs
                   if second < len(read) and read[first].task != read[second].task),
                  default=0.0)
    return dict(sorted(tasks.items())), nearest


def spans(unit):



    return [(index, unit.text[start:end])
            for index, (start, end) in enumerate(units.sentences(unit.text), 1)]


def layout(unit):



    return unit.text.count("\n") / (len(units.sentences(unit.text)) or 1) >= LAYOUT_AT


def recurring(samples, creators):






    tasks, counts, lower = {}, Counter(), set()
    for sample in _read(samples):
        found = tokens(sample.text)
        counts.update(found)
        for word in set(found):
            tasks.setdefault(word, set()).add(sample.task)
        lower.update(token for unit in sample.document.units if unit.weighs
                     for token in _RAW_TOKEN.findall(_apostrophes_folded(unit.text))
                     if token == token.lower())
    names = {token for value in creators for part in value.split(",")
             for token in tokens(part.casefold())}
    kept = [(word, len(held), counts[word]) for word, held in tasks.items()
            if len(held) >= RECUR_IN and word not in STOP and len(word) > 2
            and word in lower and word not in names]
    return sorted(kept, key=lambda row: (-row[1], -row[2], row[0]))[:RECUR_CAP]


def _meets(value, direction, floor):

    if value is None:
        return False
    return value >= floor if direction == AT_OR_ABOVE else value <= floor


def _words(text):

    return len(structure.word_tokens(text))


def _sentences_of(unit):


    return [text for _, text in spans(unit)] if unit.kind == "paragraph" else []


def _sentence_words(unit):
    return [_words(text) for text in _sentences_of(unit)]


def _paragraph_words(unit):
    return [_words(unit.text)] if unit.kind == "paragraph" else []


def _over_30(text):
    return _words(text) > 30


def _under_8(text):
    return _words(text) < 8


def _opens_on_conjunction(text):
    found = structure.word_tokens(text)
    return bool(found) and found[0] in _CONJUNCTIONS


def _asks(text):
    return text.rstrip().rstrip(_CLOSERS).endswith("?")


def _list_lines(unit):


    if unit.kind == "list_item":
        return 1
    return sum(bool(retro.LIST_MARKER.match(line)) for line in unit.text.splitlines())


def _contractions(unit):
    return len(_CONTRACTION.findall(_apostrophes_folded(unit.text)))


def _first_person(unit):
    return sum(token.split("'")[0] in _FIRST_PERSON
               for token in structure.word_tokens(unit.text))


def _glyph(glyph):

    return lambda unit: unit.text.count(glyph)


def _median(items):


    def measure(read, direction, floor):
        values = [value for unit in read for value in items(unit)]
        shown = [unit.id for unit in read
                 if any(_meets(value, direction, floor) for value in items(unit))]
        return (statistics.median(values) if values else None), shown
    return measure


def _share(test):


    def measure(read, direction, floor):
        held = [(unit.id, test(text)) for unit in read for text in _sentences_of(unit)]
        shown = list(dict.fromkeys(unit_id for unit_id, hit in held if hit))
        hits = sum(hit for _, hit in held)
        return (hits / len(held) if held else None), shown
    return measure


def _total(count):

    def measure(read, direction, floor):
        counted = [(unit.id, count(unit)) for unit in read]
        return sum(n for _, n in counted), [unit_id for unit_id, n in counted if n]
    return measure


def _per_100(count):


    def measure(read, direction, floor):
        words = sum(_words(unit.text) for unit in read)
        counted = [(unit.id, count(unit)) for unit in read]
        value = 100 * sum(n for _, n in counted) / words if words else None
        return value, [unit_id for unit_id, n in counted if n]
    return measure





COUNTS = (("short sentences, median words", _median(_sentence_words), AT_OR_UNDER, 16),
          ("long sentences, median words", _median(_sentence_words), AT_OR_ABOVE, 20),
          ("sentences over 30 words, share", _share(_over_30), AT_OR_ABOVE, 0.2),
          ("sentences under 8 words, share", _share(_under_8), AT_OR_ABOVE, 0.3),
          ("short paragraphs, median words", _median(_paragraph_words), AT_OR_UNDER, 20),
          ("list lines", _total(_list_lines), AT_OR_ABOVE, 5),
          ("contractions per 100 words", _per_100(_contractions), AT_OR_ABOVE, 1.0),
          ("first person per 100 words", _per_100(_first_person), AT_OR_ABOVE, 1.0),
          ("sentences opening on a conjunction, share", _share(_opens_on_conjunction),
           AT_OR_ABOVE, 0.02),
          ("questions, share", _share(_asks), AT_OR_ABOVE, 0.02))


MARKS = (("colon", ":", 1.0), ("open parenthesis", "(", 1.0), ("semicolon", ";", 0.2),
         ("em dash", "\u2014", 0.2), ("en dash", "\u2013", 0.2), ("exclamation", "!", 0.2),
         ("question mark", "?", 0.2), ("straight apostrophe", "'", 1.0),
         ("curly apostrophe", "\u2019", 1.0))


def _rounded(value):
    return round(value, 3) if isinstance(value, float) else value


def _measured(document):




    read = [unit for unit in document.units if unit.weighs and not layout(unit)]
    rows = list(COUNTS) + [(name, _per_100(_glyph(glyph)), AT_OR_ABOVE, floor)
                           for name, glyph, floor in MARKS]
    measured = []
    for index, (name, measure, direction, floor) in enumerate(rows, 1):
        value, shown = measure(read, direction, floor)
        measured.append((f"c{index:02d}", name, _rounded(value), direction, floor, shown))
    return measured


def corpus_view(samples):




    values = {}
    for sample in _read(samples):
        for _, name, value, _, _, _ in _measured(sample.document):
            values.setdefault(sample.task, {}).setdefault(name, []).append(value)
    view = {}
    for task in sorted(values):
        view[task] = {}
        for name, found in values[task].items():
            held = [value for value in found if value is not None]
            view[task][name] = _rounded(statistics.median(held)) if held else None
    return view


def _rule_rows(document, book):


    findings = scan.scan(document, book)
    vocab_rules = {rule_id for rule_id, rule in book.rules.items()
                   if rule.tier == "density" and rule_id not in MARK_RULES}
    fired = {}
    for finding in findings:
        fired.setdefault(finding.rule, []).append(finding)
    rows = []
    for rule_id in sorted(fired):
        records, _ = density.density(document, fired[rule_id], MARK_RULES, vocab_rules)
        rows.append({"id": rule_id, "name": book.rules[rule_id].name,
                     "value": len(fired[rule_id]),
                     "marks": sum(record.marks for record in records),
                     "vocab": sum(record.vocab for record in records),
                     "direction": None, "floor": None, "corpus": None,
                     "units": list(dict.fromkeys(f.unit for f in fired[rule_id]))[:CITED_MAX]})
    return rows


def slip_candidates(sample):




    weighing = [unit for unit in sample.document.units if unit.weighs]
    rows = []
    for index, (form, pattern) in enumerate(SLIP_PATTERNS.items(), 1):
        counted = [(unit.id, sum(1 for _ in pattern.finditer(unit.text))) for unit in weighing]
        count = sum(n for _, n in counted)
        if count:
            rows.append({"id": f"p{index:02d}", "form": form, "count": count,
                         "units": [unit_id for unit_id, n in counted if n][:CITED_MAX]})
    return rows


def word_id(word):


    return "w" + hashlib.sha256(word.encode("utf-8")).hexdigest()[:12]


def candidates(sample, book, view, recurring_words):










    rows = [{"id": row_id, "name": name, "value": value, "direction": direction,
             "floor": floor,
             "corpus": {"tasks_at_floor": sum(_meets(values.get(name), direction, floor)
                                              for values in view.values()),
                        "tasks": len(view)},
             "units": shown[:CITED_MAX]}
            for row_id, name, value, direction, floor, shown in _measured(sample.document)]
    rows += _rule_rows(sample.document, book)
    weighing = [unit for unit in sample.document.units if unit.weighs]
    for word, tasks, count in recurring_words:
        if word not in sample.words:
            continue
        shown = [unit.id for unit in weighing if word in word_set(unit.text.casefold())]
        rows.append({"id": word_id(word), "name": word,
                     "value": {"tasks": tasks, "count": count}, "direction": None,
                     "floor": None, "corpus": None, "units": shown[:CITED_MAX]})
    return rows


def _sha256(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def content_digest(sample, units_payload, candidate_rows, slips_payload):







    return _sha256({"document": sample.digest, "units": units_payload,
                    "candidates": [{"id": row["id"], "name": row["name"], "value": row["value"]}
                                   for row in candidate_rows
                                   if _COUNT_ROW.fullmatch(row["id"])],
                    "slips": slips_payload})


def learn_digest(content, rulebook_bytes, overlay_bytes):



    return _sha256({"content": content, "rulebook": hashlib.sha256(rulebook_bytes).hexdigest(),
                    "overlay": hashlib.sha256(overlay_bytes).hexdigest()})



THRESHOLDS = (f"Thresholds: two documents join one task at a word-set Jaccard of {GROUP_AT} or "
              f"above, a unit is layout at {LAYOUT_AT} line breaks per sentence or more, a word "
              f"recurs in {RECUR_IN} tasks or more, and the recurring words offered stop at "
              f"{RECUR_CAP}.")
KEPT = "This run left the list as it was, since no name was given."
REWROTE = "This run rewrote the list from the names given."
UNWRITTEN = "This run could not rewrite the list, so it stays as it was."
RECENT_OWN = ("The list is your own word on which documents are recent, and no date inside a "
              "document moves it. Run learn again with --recent and every name to change it, "
              "since the names given rewrite the list whole.")
NO_DOCUMENT = "the folder holds no document a handler reads, so no questions file was written"

LIMITS = (
    ("The grouping is lexical, a word-set Jaccard, and the threshold is one number, so two "
     "drafts of one task that share few words read as two tasks."),
    ("A family that changes shape needs a fresh home, since a task id is the digest of its "
     "members and a document joining a family moves the id the ledger holds."),
    ("A sentence is units.sentences' own, and a layout unit's sentences are runs of cells, "
     "so the counts and the marks leave every layout unit out."),
    ("The sentence rows and the paragraph row read paragraph units alone, so a heading, a "
     "list item and a table cell add no sentence to them, while the mark rows read every unit "
     "that is no layout unit."),
    ("The until cut reads a page's opening text on a PDF and a heading unit elsewhere, and a "
     "document the cut empties is skipped."),
    ("The counts, the marks, the rules, the recurring words and the slip forms are "
     "candidates, and the judge decides which of them belong to the writer."),
    (f"The recurring words stop at {RECUR_CAP} by task count and then by count, so a word "
     "past the cap is left out."),
    ("The recent list is your own word on which documents are recent and reads no date. It "
     "keys on a file's bytes, so a re-saved file needs a rerun with its name."),
    ("A questions folder of an earlier read member stays under the home until you remove "
     "it."),
    ("A document edited after its questions were asked gets a new folder under the home, so "
     "a verdicts file under its old digest is never read, and the questions folder names the "
     "digest it answers."),
    ("A document re-saved with new bytes joins its old text, read back from the questions "
     "file under the home, by the grouping's own rule, so it inherits the old task id and its "
     "earlier rows stay under the earlier digest."),
    ("A second stale run on one verdicts file names no half, since the fresh questions file "
     "carries the new digest alone."),
)



INSTRUCTIONS = ("Answer this file under the Learn section of references/judgment-checklist.md "
                "and write the traits you find to verdicts.json in this folder, with "
                "learn_digest copied across unchanged. The corpus counts, the rule counts, the "
                "recurring words and the known list are advice, and they can change between "
                "the asking and the applying, since a document added to the folder, a rulebook "
                "edit or a session's verdicts applied moves them and the content digest leaves "
                "them out.")


def write_questions(home, sample, payload):








    path = Path(home) / FOLDER / sample.digest / QUESTIONS_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, indent=1) + "\n").encode("utf-8"))
    return path


def _units(sample):

    return [{"id": unit.id, "surface": unit.surface, "text": unit.text,
             "sentences": len(spans(unit)), "layout": layout(unit)}
            for unit in sample.document.units if unit.weighs]


def _known(rows):




    known, seen = [], set()
    for row in rows:
        entry, kind = row.get("entry"), row.get("kind")
        if not (row.get("class") in voice.TEACHING and isinstance(entry, str)
                and entry.strip() and isinstance(kind, str)):
            continue
        key = (entry.strip().casefold(), kind)
        if key not in seen:
            seen.add(key)
            known.append({"entry": entry, "kind": kind})
    return known


def _payload(sample, state, asked):



    units_payload = _units(sample)
    rows = candidates(sample, asked["book"], asked["view"], asked["words"])
    slips = slip_candidates(sample)
    content = content_digest(sample, units_payload, rows, slips)
    return {"task": sample.task, "document": sample.digest, "format": sample.format,
            "content_digest": content,
            "learn_digest": learn_digest(content, asked["rulebook"], asked["overlay"]),
            "rulebook_digest": hashlib.sha256(asked["rulebook"]).hexdigest(),
            "overlay_digest": hashlib.sha256(asked["overlay"]).hexdigest(),
            "recent": sample.digest in state.recent, "family": len(state.tasks[sample.task]),
            "units": units_payload, "candidates": rows, "slips": slips,
            "known": asked["known"], "kinds": dict(KIND_LINES), "instructions": INSTRUCTIONS}



_CITED = re.compile(r"([^/]+)(?:/s([0-9]{3}))?")

_TRAIT_KINDS = tuple(kind for kind in voice.PROFILE_KINDS if kind != "avoid")

_WORD_ID = re.compile("w[0-9a-f]{12}")


def _optional_text(trait, field, index):


    value = trait.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise LearnError(f"trait {index} has {field} set to {type(value).__name__}, which is "
                         "no string or null")
    return value


def _shaped(trait, index):


    if not isinstance(trait, dict):
        raise LearnError(f"trait {index} is a {type(trait).__name__}, which is no object")
    entry, kind = trait.get("entry"), trait.get("kind")
    if not isinstance(entry, str) or not entry.strip():
        raise LearnError(f"trait {index} has entry holding no text, and every trait names one")
    if kind == "avoid":
        raise LearnError(f"trait {index} has kind 'avoid', which no sample teaches, since an "
                         "avoid entry names a shape the writer deleted")
    if kind not in voice.PROFILE_KINDS:
        raise LearnError(f"trait {index} has kind {kind!r}, which is none of "
                         f"{', '.join(_TRAIT_KINDS)}")
    expected = CLASS_OF.get(kind, "voice")
    if trait.get("class") != expected:
        raise LearnError(f"trait {index} has class {trait.get('class')!r}, and a trait of kind "
                         f"{kind} has class {expected}")
    cited = trait.get("units")
    if not isinstance(cited, list) or not cited:
        raise LearnError(f"trait {index} has units holding no unit id, and every trait cites "
                         "one or more")
    parsed = []
    for item in cited:
        match = _CITED.fullmatch(item) if isinstance(item, str) else None
        if match is None:
            raise LearnError(f"trait {index} has units naming {item!r}, which is no unit id "
                             "with an optional /sNNN suffix")
        parsed.append((match.group(1), int(match.group(2)) if match.group(2) else None))
    return ({"entry": entry, "kind": kind, "class": expected, "units": cited,
             "candidate": _optional_text(trait, "candidate", index),
             "note": _optional_text(trait, "note", index)}, parsed)


def _resolve(trait, parsed, index, payload, book):





    counts = {unit["id"]: unit["sentences"] for unit in payload["units"]}
    for item, (unit_id, sentence) in zip(trait["units"], parsed):
        if unit_id not in counts:
            raise LearnError(f"trait {index} has units naming {item!r}, a unit the questions "
                             "file does not hold")
        if sentence is not None and not 1 <= sentence <= counts[unit_id]:
            raise LearnError(f"trait {index} has units naming {item!r}, past the "
                             f"{counts[unit_id]} sentences the unit holds")
    candidate = trait["candidate"]
    rows = {row["id"] for row in payload["candidates"]} | {row["id"] for row in payload["slips"]}
    if candidate is None or candidate in rows or _WORD_ID.fullmatch(candidate):
        return book
    book = retro._shipped()[0] if book is None else book
    if candidate not in book.rules:
        raise LearnError(f"trait {index} has candidate {candidate!r}, which no candidate row "
                         f"or slip row of the questions file and no rule of the {book.name} "
                         "rulebook holds")
    return book


def read_verdicts(path, payload, book=None):



















    path = Path(path)
    if not path.is_file():
        return [], None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise LearnError(f"the verdicts file could not be read as JSON, {error}") from error
    if not isinstance(data, dict):
        raise LearnError(f"the verdicts file holds a {type(data).__name__}, which is no JSON "
                         "object")
    held = data.get("learn_digest")
    if not isinstance(held, str) or not held:
        raise LearnError("the verdicts file has learn_digest holding no text, so nothing proves "
                         "its answers belong to this document's questions. Copy learn_digest "
                         "from the questions file into the verdicts file")
    traits = data.get("traits")
    if not isinstance(traits, list):
        raise LearnError(f"the verdicts file has traits set to {type(traits).__name__}, which "
                         "is no list")
    shaped = [_shaped(trait, index) for index, trait in enumerate(traits, 1)]
    if held == payload["learn_digest"]:
        for index, (trait, parsed) in enumerate(shaped, 1):
            book = _resolve(trait, parsed, index, payload, book)
    return [trait for trait, _ in shaped], held


def trait_id(kind, entry, units):



    key = "\n".join([kind, entry.strip().casefold(), *sorted(units)])
    return "t" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def apply_verdicts(traits, payload, date, book=None):










    texts = {unit["id"]: unit["text"] for unit in payload["units"]}
    names = {row["id"]: row["name"] for row in payload["candidates"]}
    names.update((row["id"], row["form"]) for row in payload["slips"])
    rows = []
    for trait in traits:
        unit_id, suffix = _CITED.fullmatch(trait["units"][0]).groups()
        sentence = int(suffix) if suffix else None
        after = (texts[unit_id] if sentence is None
                 else dict(spans(SimpleNamespace(text=texts[unit_id])))[sentence])
        candidate = trait["candidate"]
        if candidate is None or candidate in names:
            name = names.get(candidate)
        elif _WORD_ID.fullmatch(candidate):
            name = trait["entry"]
        else:
            book = retro._shipped()[0] if book is None else book
            name = book.rules[candidate].name
        rows.append({"date": date, "task": payload["task"], "document": payload["document"],
                     "class": trait["class"], "rule": None, "before": "", "after": after,
                     "ratio": None, "change": None, "promotion": "", "entry": trait["entry"],
                     "kind": trait["kind"], "note": trait["note"] or "",
                     "piece": {"unit": unit_id, "sentence": sentence},
                     "cited": len(trait["units"]),
                     "candidate": name,
                     "source": "sample", "retro_digest": payload["learn_digest"],
                     "rid": trait_id(trait["kind"], trait["entry"], trait["units"])})
    return rows




UNUSABLE = "the verdicts file for {name} could not be used, so it was left where it is: {error}"


STALE_LINES = {
    "content": ("the verdicts file for {name} answers questions asked of another reading of "
                "the document, and it was left where it is. The content half of the learn "
                "digest moved, so the document's units, its counts or its slips read otherwise "
                "than when the questions were asked, through the until text or the code that "
                "reads them, and a unit id may now name another text"),
    "rulebook": ("the verdicts file for {name} answers questions asked under another rulebook, "
                 "and it was left where it is. The rulebook half of the learn digest moved, so "
                 "the rulebook file or its overlay changed after the questions were asked"),
    None: ("the verdicts file for {name} answers learn digest {held}, which differs from this "
           "run's, and it was left where it is. No questions file under its folder records "
           "that digest, so the half that moved cannot be named"),
}
FRESH_QUESTIONS = ("this run wrote a fresh questions file for {name}, so answer it, save the "
                   "answers over the refused verdicts file with learn_digest copied across, "
                   "then run learn again")
LEDGER_REFUSED = ("the ledger could not take the rows of the verdicts file for {name}, so the "
                  "file was left where it is")
OTHER_TASK = ("the ledger holds {name} under task {held}, and this run groups it under task "
              "{task}, since its family changed shape, so the run read no verdicts file and "
              "wrote no questions file for it. A family that changes shape needs a fresh home, "
              "as Limits says")


JOINED = ("{name} holds no row in the ledger and sits in the family the ledger holds under "
          "task {held}, and this run groups the family under task {task}, since the family "
          "changed shape, so the run read no verdicts file and wrote no questions file for it. "
          "A family that changes shape needs a fresh home, as Limits says")



UNREAD_QUESTIONS = ("no questions file under the home reads back for {count} the ledger holds "
                    "and this folder lacks, {digests}, so a re-saved copy of such a document "
                    "reads as a new task until its questions folder is restored or the home is "
                    "fresh")


@dataclass
class _Run:

    folder: Path
    book_name: str
    rulebook_digest: str
    overlay_digest: str | None
    names: tuple
    until_text: str | None
    samples: list = dataclasses.field(default_factory=list)
    skipped: list = dataclasses.field(default_factory=list)
    tasks: dict = dataclasses.field(default_factory=dict)
    nearest: float = 0.0
    recent: set = dataclasses.field(default_factory=set)
    rewrote: bool = False
    unwritten: bool = False
    view: dict = dataclasses.field(default_factory=dict)
    words: list = dataclasses.field(default_factory=list)
    found: dict = dataclasses.field(default_factory=dict)
    refused_formats: Counter = dataclasses.field(default_factory=Counter)
    cannot_see: list = dataclasses.field(default_factory=list)
    refused: bool = False
    applied: list = dataclasses.field(default_factory=list)
    profile: object = None
    ledger: list | None = None

    older: list | None = None

    elsewhere: list = dataclasses.field(default_factory=list)


    def refuse(self, line):
        self.cannot_see.append(line)
        self.refused = True


def _read(samples):
    return [sample for sample in samples if sample.twin_of is None]


def _plural(count, noun):
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _names(samples):
    names = sorted(report._inline(sample.path.name) for sample in samples)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _what_ran(state):
    lines = [f"Folder: {report._inline(str(state.folder))}.",
             f"Rulebook: {state.book_name}, sha256 {state.rulebook_digest}.",
             f"Overlay: sha256 {state.overlay_digest}." if state.overlay_digest
             else "Overlay: none."]
    lines.append(f"Recent names: {report._inline(', '.join(state.names))}." if state.names
                 else "Recent names: none given.")
    lines.append(f"Until: {report._inline(state.until_text)}." if state.until_text
                 else "Until: none, so each document was read whole.")
    lines.append(THRESHOLDS)
    return "\n".join(lines)


def _documents(state):
    read = _read(state.samples)
    if read:
        counts = Counter(sample.format for sample in read)
        formats = ", ".join(f"{name} {counts[name]}" for name in dict.fromkeys(FORMATS.values())
                            if counts[name])
        lines = [f"Read: {_plural(len(read), 'document')}, {formats}."]
    else:
        lines = ["Read: none, since no file of the folder reads as a document."]
    lines += (["Skipped:", *(f"- {report._inline(line)}." for line in state.skipped)]
              if state.skipped else ["Skipped: none."])
    if state.until_text and read:
        lines += ["Until cut:", *(f"- {report._inline(sample.path.name)}: {sample.cut}."
                                  for sample in read)]
    elif state.until_text:
        lines.append("Until cut: none, since no document was read.")
    else:
        lines.append("Until cut: none asked.")
    return "\n".join(lines)


def _joined(members):




    read = _read(members)
    values = [value for value in (jaccard(first.words, second.words) for first, second
                                  in itertools.combinations(read, 2))
              if value >= GROUP_AT]
    if not values:
        return ("through a document the ledger holds and this folder lacks" if len(read) > 1
                else "as equal texts")
    low, high = min(values), max(values)
    return f"at Jaccard {low:.3f}" if low == high else f"at Jaccard {low:.3f} to {high:.3f}"


def _tasks(state):
    if not state.tasks:
        return "None, since no document was read."
    lines = [f"{_plural(len(state.tasks), 'task')}."]
    families = {}
    for sample in state.samples:
        families.setdefault(sample.task, []).append(sample)
    joined = [f"- {len(members)} documents, {_names(members)}, joined {_joined(members)}."
              for task, members in sorted(families.items()) if len(members) > 1]
    lines += (["Families:", *joined] if joined
              else ["Families: none, so each task holds one document."])
    read = {sample.digest: sample for sample in _read(state.samples)}
    twins = [f"- {report._inline(sample.path.name)}, read as "
             f"{report._inline(read[sample.twin_of].path.name)}."
             for sample in state.samples if sample.twin_of is not None]
    lines += ["Equal texts read once:", *twins] if twins else ["Equal texts read once: none."]
    lines.append(f"Nearest between two tasks: Jaccard {state.nearest:.3f}, under the {GROUP_AT} "
                 "that joins." if len(state.tasks) > 1 else
                 "Nearest between two tasks: none, since one task holds every document.")
    return "\n".join(lines)


def _recency(state):
    read = _read(state.samples)
    named = [sample for sample in read if sample.digest in state.recent]
    lines = [f"Named: {_names(named)}." if named else "Named: none.",
             f"Not named: {len(read) - len(named)} of the {_plural(len(read), 'document')} "
             "read."]
    outside = len(state.recent - {sample.digest for sample in state.samples})
    if outside:
        lines.append(f"The list holds {_plural(outside, 'digest')} of documents outside this "
                     "folder.")
    lines += [REWROTE if state.rewrote else UNWRITTEN if state.unwritten else KEPT, RECENT_OWN]
    return "\n".join(lines)


def _number(value):
    return f"{value:g}" if isinstance(value, float) else str(value)


def _floors():


    rows = ([(name, direction, floor, name) for name, _, direction, floor in COUNTS]
            + [(name, AT_OR_ABOVE, floor, f"{name} per 100 words") for name, _, floor in MARKS])
    return [(f"c{index:02d}", *row) for index, row in enumerate(rows, 1)]


def _candidates(state):


    read = _read(state.samples)
    if not read:
        return "None, since no document was read."
    families, lines = {}, []
    for sample in read:
        families.setdefault(sample.task, []).append(sample)
    for task, members in sorted(families.items()):
        values = state.view.get(task, {})
        lines.append(f"Task {task[:12]}, {_plural(len(members), 'document')} read: "
                     f"{_names(members)}.")
        floors = [f"- {row_id} {label}: {_number(values.get(name))}, {direction} "
                  f"{_number(floor)}." for row_id, name, direction, floor, label in _floors()
                  if _meets(values.get(name), direction, floor)]
        lines += floors or ["- Counts and marks at their floor: none."]
        rules, slips = Counter(), Counter()
        for sample in members:
            rows, found = state.found.get(sample.digest, ([], []))
            rules.update({row["id"]: row["value"] for row in rows if "marks" in row})
            slips.update({row["form"]: row["count"] for row in found})
        lines.append("- Rules: " + (", ".join(f"{rule} {rules[rule]}" for rule in sorted(rules))
                                    or "none") + ".")
        lines.append("- Slip forms: " + (", ".join(f"{form} {slips[form]}"
                                                   for form in SLIP_PATTERNS if slips[form])
                                         or "none") + ".")
    if state.words:
        lines.append(f"Recurring words offered: {len(state.words)}, each in {RECUR_IN} tasks or "
                     "more:")
        lines += [f"- {word}, {word_id(word)}: {tasks} tasks, {count} times."
                  for word, tasks, count in state.words]
    else:
        lines.append(f"Recurring words offered: none, since no word passed the filters in "
                     f"{RECUR_IN} tasks or more.")
    return "\n".join(lines)


def _cannot_see(state):


    lines = list(state.cannot_see)
    if state.refused_formats:
        lines.append("Files in a format learn does not read, each skipped: " + ", ".join(
            f"{suffix} {state.refused_formats[suffix]}"
            for suffix in sorted(state.refused_formats)) + ".")
    layouts = [(sample.path.name, count) for sample in _read(state.samples)
               if (count := sum(layout(unit) for unit in sample.document.units
                                if unit.weighs))]
    if layouts:
        lines.append("Layout units, left out of the counts and the marks: " + ", ".join(
            f"{name} {count}" for name, count in layouts) + ".")
    return "\n".join(f"- {report._inline(line)}" for line in lines) or "None."


def _ledger(state):






    if state.ledger is None:
        return "None, since the run stopped before it read the ledger."
    lines = []
    for applied in state.applied:
        said = "appended " + ", ".join(applied["ids"]) if applied["ids"] else "appended no row"
        moved = (f", and the spent verdicts file moved to {applied['moved']}"
                 if applied["moved"] else "")
        lines.append(f"- {report._inline(applied['name'])}: {said}{moved}.")
    lines = (["Appended:", *lines] if lines
             else ["Appended: none, since no verdicts file was applied."])
    held = [f'- {report._inline(applied["name"])}: {kind} "{report._inline(entry)}", {line}.'
            for applied in state.applied for kind, entry, line in applied["held"]]
    lines += ["Refused as held:", *held] if held else ["Refused as held: none."]
    documents = {row["document"] for row in state.ledger
                 if row.get("source") == "sample" and isinstance(row.get("document"), str)}
    read = _read(state.samples)
    in_ledger = [sample for sample in read if sample.digest in documents]
    waiting = [sample for sample in read
               if sample.digest not in documents and sample not in state.elsewhere]
    lines.append(f"Held in the ledger: {_names(in_ledger)}." if in_ledger
                 else "Held in the ledger: none of this folder's documents.")
    absent = documents - {sample.digest for sample in state.samples}
    lines.append("Held in the ledger and absent from this folder: "
                 + (f"{_plural(len(absent), 'document')}." if absent else "none."))
    lines.append(f"Waiting on a verdicts file: {_names(waiting)}." if waiting
                 else "Waiting on a verdicts file: none.")
    lines.append(f"Held under another task id: {_names(state.elsewhere)}." if state.elsewhere
                 else "Held under another task id: none.")
    return "\n".join(lines)


def _profile(state):

    if state.profile is None:
        return ("None. No verdicts file was applied and no recent name moved an entry's "
                "recency, so the profile was not harvested.")
    if any(applied["ids"] for applied in state.applied):
        head = "The rows were appended"
    elif state.applied:
        head = "No row was appended"
    else:
        head = "No verdicts file was applied and the recent names rewrote the list"
    return retro._profile_text(state.profile, head)


def _older_only(state):


    if state.ledger is None:
        return "None, since the run stopped before it read the profile."
    if state.older is None:
        return "None, since no profile file exists."
    if not state.older:
        return "None, since every entry in force rests on a recent document or on no document."
    return "\n".join([
        "Each entry in force whose sample rows cite no document of the recent list:",
        *(f'- {entry["kind"]} "{report._inline(entry["entry"])}", evidence '
          f'{", ".join(entry["evidence"])}.' for entry in state.older)])


_SECTION_TEXT = {"What ran": _what_ran, "Documents": _documents, "Tasks": _tasks,
                 "Recency": _recency, "Candidates": _candidates, "Ledger": _ledger,
                 "Profile": _profile, "Older only": _older_only, "Cannot see": _cannot_see,
                 "Limits": lambda state: "\n".join(LIMITS)}


def _recent_digests(names, samples, folder, skipped=()):





    read = {sample.path.name: sample.twin_of or sample.digest for sample in samples}
    files = sorted(path.name for path in folder.iterdir() if path.is_file())
    digests, refusals = set(), []
    for name in names:
        if name in read:
            digests.add(read[name])
            continue
        other = next((file for file in files if file.casefold() == name.casefold()), None)
        if name in files and any(line.startswith(f"{name}: {EMPTIED},") for line in skipped):
            refusals.append(f"the recent name {name!r} names a file that {EMPTIED}, so the "
                            "run wrote nothing")
        elif name in files:
            refusals.append(f"the recent name {name!r} names a file this run did not read, "
                            "so the run wrote nothing")
        elif other is not None:
            refusals.append(f"the recent name {name!r} matches {other!r} in another case, and "
                            "a recent name matches a file's name exactly, so the run wrote "
                            "nothing")
        else:
            refusals.append(f"the recent name {name!r} names no file of the folder, so the "
                            "run wrote nothing")
    return digests, refusals


def _with_twins(recent, samples):






    touched = {sample.twin_of or sample.digest for sample in samples if sample.digest in recent}
    return set(recent) | {sample.digest for sample in samples
                          if (sample.twin_of or sample.digest) in touched}


def _ledger_tasks(rows):


    tasks = {}
    for row in rows:
        document, task = row.get("document"), row.get("task")
        if row.get("source") == "sample" and isinstance(document, str) and isinstance(task, str):
            tasks.setdefault(document, set()).add(task)
    return tasks


def _absent(rows, samples, home):








    present = {sample.digest for sample in samples}
    records, unread = [], []
    for document, tasks in sorted(_ledger_tasks(rows).items()):
        if document in present:
            continue
        try:
            asked = json.loads((Path(home) / FOLDER / document / QUESTIONS_NAME)
                               .read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            unread.append(document)
            continue
        units = asked.get("units") if isinstance(asked, dict) else None
        if not isinstance(units, list) or not all(
                isinstance(unit, dict) and isinstance(unit.get("text"), str) for unit in units):
            unread.append(document)
            continue
        text = normalised(SimpleNamespace(units=[SimpleNamespace(text=unit["text"], weighs=True)
                                                 for unit in units]))
        records.append(SimpleNamespace(digest=document, text=text, words=word_set(text),
                                       tasks=frozenset(tasks), task=""))
    return records, unread


def _held_elsewhere(rows, samples):





    tasks = _ledger_tasks(rows)
    return {sample.digest: sorted(tasks[sample.digest] - {sample.task}) for sample in samples
            if tasks.get(sample.digest, set()) - {sample.task}}


def _moved(path, held, payload):





    try:
        asked = json.loads(path.with_name(QUESTIONS_NAME).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(asked, dict) or asked.get("learn_digest") != held:
        return None
    return "content" if asked.get("content_digest") != payload["content_digest"] else "rulebook"


def _judged(state, sample, payload, path, book, date):








    name = sample.path.name
    try:
        traits, held = read_verdicts(path, payload, book)
    except LearnError as error:
        state.refuse(UNUSABLE.format(name=name, error=error))
        return False
    if held != payload["learn_digest"]:
        state.refuse(STALE_LINES[_moved(path, held, payload)].format(name=name,
                                                                     held=held[:12]))
        return False
    rows = apply_verdicts(traits, payload, date, book)
    ids, refusals = voice.append_rows(rows)
    recorded = voice.pairs(voice.read_ledger()[0])
    if any((row["retro_digest"], row["rid"]) not in recorded for row in rows):
        state.refuse(LEDGER_REFUSED.format(name=name))
        state.cannot_see += refusals
        return True
    entries = {row["rid"]: (row["kind"], row["entry"]) for row in rows}
    state.applied.append({"name": name, "path": path, "ids": ids, "moved": None,
                          "held": [(*entries[line.split()[1]], line) for line in refusals]})
    return True


def _retire(path):








    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target, count = path.with_name(f"{APPLIED_STEM}{stamp}.json"), 0
    while target.exists():
        count += 1
        target = path.with_name(f"{APPLIED_STEM}{stamp}-{count}.json")
    try:
        os.replace(path, target)
    except OSError as error:
        return None, (f"the spent verdicts file at {path} could not be moved aside, "
                      f"{type(error).__name__}: {error}. The next run finds every row it "
                      "answers in the ledger already and moves it then")
    return target, None


def _harvest(state, book, written):










    recorded, warnings = voice.read_ledger()
    state.ledger = recorded
    if state.applied or (state.rewrote
                         and any(row.get("source") == "sample" for row in recorded)):
        ids = {row_id for applied in state.applied for row_id in applied["ids"]}
        state.profile = retro._profile_step([row for row in recorded if row.get("id") in ids],
                                            book, (recorded, warnings), recent=state.recent)
        state.cannot_see += [line for line in state.profile.cannot_see
                             if line not in state.cannot_see]
        if not state.profile.written:
            state.refused = True
        for applied in state.applied:
            target, line = _retire(applied["path"])
            if target is None:
                state.cannot_see.append(line)
            else:
                written.append(target)
                applied["moved"] = target.name
    entries, _ = voice.load_profile()
    state.older = None if entries is None else [
        entry for entry in voice.in_force(entries, state.book_name)
        if entry.get("recent") is False]


def _write_recent(home, digests):


    path = Path(home) / voice.RECENT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(sorted(digests), indent=1) + "\n").encode("utf-8"))
    return path


def _render(state):


    parts = [report._neutralize_headings(f"# Learn report for {state.folder}", SECTIONS), ""]
    for heading in SECTIONS:
        body = report._neutralize_headings(_SECTION_TEXT[heading](state).rstrip(), SECTIONS)
        parts += [f"## {heading}", body or "None.", ""]
    return "\n".join(parts).rstrip() + "\n"


def run(folder, recent=(), until_text=None, book=None, rulebook_bytes=None, warnings=(),
        overlay_bytes=b""):

































    folder = Path(folder)
    if (book is None) != (rulebook_bytes is None):
        raise ValueError("book and rulebook_bytes are given together or not at all, since "
                         "the report prints the digest of the book in force")
    if book is None:
        book, rulebook_bytes = retro._shipped()
    state = _Run(folder, book.name, hashlib.sha256(rulebook_bytes).hexdigest(),
                 hashlib.sha256(overlay_bytes).hexdigest() if overlay_bytes else None,
                 tuple(recent), until_text)
    state.cannot_see += [f"Configuration warning, this run ignored it: {line}"
                         for line in warnings]
    if not folder.is_dir():
        state.refuse(f"the folder {folder} is no directory, so nothing was read")
        return retro.Result(_render(state), 1, [], list(state.cannot_see))
    state.samples, state.skipped = read_folder(folder, until_text)
    state.refused_formats = Counter(
        path.suffix.lower() or "no suffix" for path in folder.iterdir()
        if path.is_file() and not path.name.startswith(LOCK_PREFIX)
        and path.suffix.lower() not in FORMATS)
    state.tasks, state.nearest = group(state.samples)
    home, written = voice.home(), []
    if state.names:
        digests, refusals = _recent_digests(state.names, state.samples, folder, state.skipped)
        if refusals:
            for line in refusals:
                state.refuse(line)
            return retro.Result(_render(state), 1, [], list(state.cannot_see))
        try:
            written.append(_write_recent(home, digests))
        except OSError as error:
            state.refuse(f"the recent list could not be written, {error}, so it stays as it "
                         "was")
            state.unwritten = True
        else:
            state.rewrote = True
    listed, lines = voice.recent_documents()
    state.recent = _with_twins(listed, state.samples)
    state.cannot_see += lines
    read = _read(state.samples)
    if not read:
        state.refuse(NO_DOCUMENT)
    ledger, lines = voice.read_ledger()
    state.cannot_see += lines
    absent, unread = _absent(ledger, state.samples, home)
    if unread:
        state.cannot_see.append(UNREAD_QUESTIONS.format(
            count=_plural(len(unread), "document"),
            digests=", ".join(document[:12] for document in unread)))
    state.tasks, state.nearest = group(state.samples, absent=absent)
    state.view = corpus_view(state.samples)
    state.words = recurring(state.samples, {s.creator for s in state.samples if s.creator})
    asked = {"book": book, "view": state.view, "words": state.words, "known": _known(ledger),
             "rulebook": rulebook_bytes, "overlay": overlay_bytes}
    joined = [record for record in absent if record.task]
    elsewhere = _held_elsewhere(ledger, state.samples + joined)
    families = {}
    for sample in state.samples + joined:
        if sample.digest in elsewhere:
            families.setdefault(sample.task, set()).update(elsewhere[sample.digest])
    for sample in state.samples:
        if sample.task not in families:
            continue
        line = OTHER_TASK if sample.digest in elsewhere else JOINED
        held = ", ".join(task[:12] for task in elsewhere.get(sample.digest,
                                                            sorted(families[sample.task])))
        state.refuse(line.format(name=sample.path.name, held=held, task=sample.task[:12]))
        state.elsewhere.append(sample)
    date = datetime.now(timezone.utc).date().isoformat()
    for sample in read:
        payload = _payload(sample, state, asked)
        state.found[sample.digest] = (payload["candidates"], payload["slips"])
        if sample.task in families:
            continue
        verdicts = home / FOLDER / sample.digest / VERDICTS_NAME
        judged = verdicts.is_file()
        if judged and _judged(state, sample, payload, verdicts, book, date):
            continue
        try:
            written.append(write_questions(home, sample, payload))
        except OSError as error:
            state.refuse(f"the questions file for {sample.path.name} could not be written, "
                         f"{error}")
        else:
            if judged:
                state.cannot_see.append(FRESH_QUESTIONS.format(name=sample.path.name))
    _harvest(state, book, written)
    text, code = _render(state), 1 if state.refused else 0
    path = home / FOLDER / REPORT_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    except OSError as error:
        text += f"\nThe report could not be written to {path}, {error}.\n"
        code = 1
    return retro.Result(text, code, written, list(state.cannot_see))




_MEASURES = frozenset(row[0] for row in COUNTS) | frozenset(row[0] for row in MARKS)


def _holds(sample, wanted):


    if len(wanted) == 1:
        return wanted[0] in sample.words
    found, size = tokens(sample.text), len(wanted)
    return any(found[index:index + size] == wanted for index in range(len(found) - size + 1))


def _shows(sample, forms, measures, rules, book):



    if any(pattern.search(unit.text) for pattern in forms
           for unit in sample.document.units if unit.weighs):
        return True
    if measures:
        values = {name: (value, direction, floor)
                  for _, name, value, direction, floor, _ in _measured(sample.document)}
        if any(_meets(*values[name]) for name in measures):
            return True
    return bool(rules) and bool(rules & {finding.rule
                                         for finding in scan.scan(sample.document, book)})


def shown(entry, rows, documents, book=None):














    kind = entry.get("kind")
    if kind == "diction":
        wanted = tokens(entry["entry"].casefold())
        if wanted:
            return True, any(_holds(sample, wanted) for sample in documents)
    names = {row.get("candidate") for row in rows if isinstance(row.get("candidate"), str)}
    named = entry.get("entry", "").strip().casefold() if kind == voice.SLIP else ""
    forms = [SLIP_PATTERNS[name] for name in sorted(names | {named})
             if kind == voice.SLIP and name in SLIP_PATTERNS]
    measures = sorted(names & _MEASURES)
    rest, rules = names - set(SLIP_PATTERNS) - _MEASURES, set()
    if rest:
        book = retro._shipped()[0] if book is None else book
        ids = {rule.name: rule_id for rule_id, rule in book.rules.items()}
        rules = {ids[name] for name in rest if name in ids}
    if not (forms or measures or rules):
        return False, False
    return True, any(_shows(sample, forms, measures, rules, book) for sample in documents)


def changed_spans(before, after):





    spans = []
    matcher = difflib.SequenceMatcher(None, before.split(), after.split())
    for tag, start, end, _, _ in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            spans.append((start, end))
        elif tag == "insert":
            spans.append((start, start))
    return spans
