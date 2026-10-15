





















import dataclasses
import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts import (extract_docx, extract_markdown, hookio, office, report, rulebook, scan,
                     structure, voice)
from scripts.records import Document, Unit
from scripts.units import word_count

UNCHANGED_AT, REWRITTEN_AT = 0.98, 0.35
QUESTIONS_SUFFIX = ".humanize-retro.json"
VERDICTS_SUFFIX = ".humanize-retro-verdicts.json"
REPORT_SUFFIX = ".humanize-retro-report.md"
APPLIED_STEM = ".humanize-retro-verdicts.applied-"
FORMATS = ("markdown", "txt", "docx")
KINDS = ("unchanged", "rewritten", "deleted", "added")
SECTIONS = ("What ran", "Alignment", "Flag rate", "Divergences", "Ledger", "Profile",
            "Promotions", "Cannot see", "Limits")



SLIP_FORMS = (("though", "tho"), ("through", "thru"), ("a lot", "alot"))

LIST_MARKER = re.compile(r"^\s*(?:[-*+\u2022\u2013]|\d+[.)])\s+")
CONTINUATION = "  "


PASSES = "anchored, second pass over leftovers"
ALIGNMENT = (UNCHANGED_AT, REWRITTEN_AT, LIST_MARKER.pattern, CONTINUATION, PASSES)


CLASS_LINES = {
    "calibration": ("The final moved a score or a judgment of degree, and the wording followed "
                    "the new level."),
    "scope or standard": ("The final judged against another standard or over another scope than "
                          "the draft did."),
    "evidence selection": ("The final supports the point with other evidence, an example added "
                           "or cut."),
    "voice": ("The final says what the draft said in the writer's own words, a habit the "
              "profile can learn."),
    "slop": ("The draft carried an AI tell a rule names and the final removed it, so the row "
             "names the rule."),
    "artifact conflict": ("The edit contradicts what the artifact under review shows, and an "
                          "edit being made does not make it correct, so the row carries the "
                          "evidence."),
}


NOTHING_ALIGNED = ("a verdicts file sits beside the draft, and nothing was aligned to compare "
                   "its retro_digest with, so it was left where it is")
UNUSABLE = "the verdicts file could not be used, so it was left where it is: {error}"
NO_DIGEST = ("the verdicts file records no retro_digest, so nothing proves its answers belong "
             "to this run's divergences, and it was left where it is. Copy retro_digest from "
             "the questions file into the verdicts file")


STALE_LINES = {
    "alignment": ("the verdicts file answers questions asked under another alignment, and it "
                  "was left where it is. The alignment half of the retro digest moved, so the "
                  "draft, the final, the until text or the alignment's constants changed after "
                  "the questions were asked, and a rid may now name another divergence"),
    "rulebook": ("the verdicts file answers questions asked under another rulebook, and it was "
                 "left where it is. The rulebook half of the retro digest moved, so the "
                 "rulebook file or its overlay changed after the questions were asked"),
    None: ("the verdicts file's retro_digest differs from this run's, and it was left where it "
           "is. No questions file beside the draft records that digest, so the half that "
           "moved cannot be named"),
}
FRESH_QUESTIONS = ("this run wrote a fresh questions file, {name}, so answer it, save the "
                   "answers over the refused verdicts file with its retro_digest copied "
                   "across, then run the retro again")
MISSING = ("the verdicts file leaves {count} of {total} divergences without a usable verdict, "
           "{rids}, so it was left where it is. A usable verdict names a class of the six, and "
           "a voice verdict names an entry and a kind as well")
UNKNOWN = ("the verdicts file answers {count} rids this run raised no divergence for, {rids}, "
           "and they were passed over")
LEDGER_REFUSED = "the ledger could not take the rows, so the verdicts file was left where it is"


PROFILE_REFUSED = ("the voice profile could not be written, {error}. The ledger holds the rows "
                   "and the profile stays as it was until the next judged retro or retro state "
                   "harvests the whole ledger again")


LEDGER_UNREAD = ("the ledger read back no row after this run appended {count}, so the "
                 "profile was neither harvested nor written and stays as it was")

LIMITS = (
    ("The alignment is lexical and anchored on exact matches, and it reads the bullet pieces "
     "of each side alone, so a draft with no bullet reads no divergence."),
    ("The cut needs a heading unit on both sides, since a bold paragraph is no heading unit, "
     "so a zero in one side's dropped count means the cut missed that side."),
    "The ratio is one signal of five, and it measures how many characters a rewrite kept.",
    ("The ratio is a difflib call, with its junk heuristic on a long piece, and "
     "no true similarity."),
    ("The classification is the judge's, so every divergence prints unjudged until a verdicts "
     "file answers it."),
    ("The template check reads the two reference files a rewriting model reads, and the "
     "plugin ships no drafting template beyond them."),
)


BINS = ((0.35, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 0.98))

_SUFFIXES = {".md": "markdown", ".markdown": "markdown", ".txt": "txt", ".docx": "docx"}

_BREAK = re.compile(r"\r\n|\r|\n")

_TEXT_FIELDS = ("rule", "entry", "kind", "note")


class RetroError(Exception):
    pass


@dataclass
class Piece:
    unit: str
    line: int
    text: str
    bullet: bool


@dataclass
class Row:
    rid: str
    kind: str
    ratio: float
    draft: Piece | None
    final: Piece | None


def _unit_lines(text):


    start = index = 0
    for match in _BREAK.finditer(text):
        yield index, start, match.start()
        start, index = match.end(), index + 1
    yield index, start, len(text)


def _pieces_and_spans(document):



    out, previous = [], None
    for unit in document.units:
        if not unit.weighs:
            continue
        if document.format == "docx":
            marker = LIST_MARKER.match(unit.text)
            text = unit.text[marker.end() if marker else 0:].strip()
            if text:
                out.append((Piece(unit.id, 0, text, marker is not None),
                            [(unit.id, 0, len(unit.text))]))
            continue
        for index, start, end in _unit_lines(unit.text):
            line = unit.text[start:end]
            if not line.strip():
                continue
            marker = LIST_MARKER.match(line)
            if marker:
                text = line[marker.end():].strip()
                if not text:
                    continue
                previous = (Piece(unit.id, index, text, True), [(unit.id, start, end)])
                out.append(previous)
            elif line.startswith(CONTINUATION) and previous is not None and previous[0].bullet:
                previous[0].text += " " + line.strip()
                previous[1].append((unit.id, start, end))
            else:
                previous = (Piece(unit.id, index, line.strip(), False), [(unit.id, start, end)])
                out.append(previous)
    return out


def pieces(document):






    return [piece for piece, _ in _pieces_and_spans(document)]


def until(document, text):




    if text:
        wanted = text.casefold()
        for index, unit in enumerate(document.units):
            if unit.kind == "heading" and wanted in unit.text.casefold():
                return (dataclasses.replace(document, units=document.units[:index]),
                        len(document.units) - index)
    return document, 0


def ratio(a, b):

    return difflib.SequenceMatcher(None, a, b).ratio()


def _folded(text):


    return " ".join(text.split()).casefold()


def _gap(draft, final):




    rows, used = [], set()
    for piece in draft:
        best, best_ratio = None, 0.0
        for index, candidate in enumerate(final):
            if index in used:
                continue
            measured = ratio(piece.text, candidate.text)
            if best is None or measured > best_ratio:
                best, best_ratio = index, measured
        if best is not None and best_ratio >= REWRITTEN_AT:
            used.add(best)
            kind = "unchanged" if best_ratio >= UNCHANGED_AT else "rewritten"
            rows.append(Row("", kind, best_ratio, piece, final[best]))
        else:
            rows.append(Row("", "deleted", 0.0, piece, None))
    rows.extend(Row("", "added", 0.0, None, candidate)
                for index, candidate in enumerate(final) if index not in used)
    return rows


def _anchored(draft_pieces, final_pieces):


    draft_keys = [_folded(piece.text) for piece in draft_pieces]
    final_keys = [_folded(piece.text) for piece in final_pieces]
    matcher = difflib.SequenceMatcher(None, draft_keys, final_keys, autojunk=False)
    rows, i, j = [], 0, 0
    for block in matcher.get_matching_blocks():
        rows.extend(_gap(draft_pieces[i:block.a], final_pieces[j:block.b]))
        rows.extend(Row("", "unchanged", 1.0, draft_pieces[block.a + k], final_pieces[block.b + k])
                    for k in range(block.size))
        i, j = block.a + block.size, block.b + block.size
    return rows


def _second_pass(rows):






    leftover = _anchored([row.draft for row in rows if row.kind == "deleted"],
                         [row.final for row in rows if row.kind == "added"])
    paired = {id(row.draft): row for row in leftover if row.kind in ("unchanged", "rewritten")}
    taken = {id(row.final) for row in paired.values()}
    out = []
    for row in rows:
        if row.kind == "deleted" and id(row.draft) in paired:
            out.append(paired[id(row.draft)])
        elif not (row.kind == "added" and id(row.final) in taken):
            out.append(row)
    return out


def align(draft_pieces, final_pieces):












    rows = _second_pass(_anchored(draft_pieces, final_pieces))
    for number, row in enumerate(rows, 1):
        row.rid = f"r{number:04d}"
    return rows


def comparable_rate(document, book, other_format):







    exact = [f for f in scan.scan(document, book) if f.tier in scan.EXACT_TIERS]
    aside = sorted({f.rule for f in exact if book.rules[f.rule].formats.get(other_format) == "off"})
    spans = {(f.unit, f.span) for f in exact if f.rule not in aside}
    words = word_count("\n".join(unit.text for unit in document.units if unit.weighs))
    rate = len(spans) / words * 100 if words else None
    return rate, len(spans), words, aside


def _digest_payload(draft_digest, final_digest, until_text):
    return {"draft": draft_digest, "final": final_digest, "until": until_text,
            "alignment": list(ALIGNMENT)}


def _sha256(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def alignment_digest(draft_digest, final_digest, until_text):


    return _sha256(_digest_payload(draft_digest, final_digest, until_text))


def retro_digest(draft_digest, final_digest, until_text, rulebook_bytes, overlay_bytes=b""):





    payload = _digest_payload(draft_digest, final_digest, until_text)
    payload["rulebook"] = hashlib.sha256(rulebook_bytes).hexdigest()
    payload["overlay"] = hashlib.sha256(overlay_bytes).hexdigest()
    return _sha256(payload)


def _format_of(path):

    return _SUFFIXES.get(Path(path).suffix.lower())


def _shipped(name="general"):


    path = hookio.plugin_root() / "references" / "rulebooks" / f"{name}.json"
    return rulebook.load(path), path.read_bytes()


def _hits(document, book):




    findings = [f for f in scan.scan(document, book)
                if f.tier in scan.EXACT_TIERS and f.span is not None]
    hits = {}
    for piece, spans in _pieces_and_spans(document):
        extent = {}
        for unit, start, end in spans:
            low, high = extent.get(unit, (start, end))
            extent[unit] = (min(low, start), max(high, end))
        hits[(piece.unit, piece.line)] = sorted({
            f.rule for f in findings if f.unit in extent
            and extent[f.unit][0] <= f.span[0] and f.span[1] <= extent[f.unit][1]})
    return hits


def write_questions(draft_path, draft, final, rows, task, digests, until_text, dropped, rates,
                    book=None, superseded=None):













    if book is None:
        book = _shipped()[0]
    hits = _hits(draft, book)
    divergences = []
    for row in rows:
        if row.kind == "unchanged":
            continue
        piece = row.draft or row.final
        divergences.append({
            "rid": row.rid, "kind": row.kind, "ratio": row.ratio,
            "before": row.draft.text if row.draft else "",
            "after": row.final.text if row.final else "",
            "unit": piece.unit, "line": piece.line, "bullet": piece.bullet,
            "hits": hits.get((row.draft.unit, row.draft.line), []) if row.draft else [],
        })
    retro_value, alignment_value, rulebook_value, overlay_value = digests
    payload = {
        "task": task, "retro_digest": retro_value, "alignment_digest": alignment_value,
        "rulebook_digest": rulebook_value, "overlay_digest": overlay_value,
        "draft_format": _format_of(draft.path),
        "final_format": _format_of(final.path), "until": until_text,
        "dropped": {"draft": dropped[0], "final": dropped[1]},
        "counts": {kind: sum(row.kind == kind for row in rows) for kind in KINDS},
        "rates": rates,
        "classes": {name: CLASS_LINES[name] for name in voice.CLASSES},
        "divergences": divergences,
    }
    if superseded is not None:
        payload["superseded"] = superseded
    path = Path(str(draft_path) + QUESTIONS_SUFFIX)
    path.write_bytes((json.dumps(payload, indent=1) + "\n").encode("utf-8"))
    return path


def _check_verdict(rid, row, book):





    if not isinstance(row, dict):
        raise RetroError(f"verdict row {rid!r} is a {type(row).__name__}, which is no object")
    for field in _TEXT_FIELDS:
        value = row.get(field)
        if value is not None and not isinstance(value, str):
            raise RetroError(f"verdict row {rid!r} has {field} set to "
                             f"{type(value).__name__}, which is no string or null")
    cls = row.get("class")
    if cls is not None and cls not in voice.CLASSES:
        raise RetroError(f"verdict row {rid!r} has class {cls!r}, which is none of the six "
                         f"classes, {', '.join(voice.CLASSES)}")
    kind = row.get("kind")
    if kind is not None and kind not in voice.KINDS:
        raise RetroError(f"verdict row {rid!r} has kind {kind!r}, which is none of "
                         f"{', '.join(voice.KINDS)}")
    rule = row.get("rule")
    if rule is not None and rule not in book.rules:
        raise RetroError(f"verdict row {rid!r} has rule {rule!r}, which the {book.name} "
                         "rulebook does not hold")


def read_verdicts(draft_path, book):







    path = Path(str(draft_path) + VERDICTS_SUFFIX)
    if not path.is_file():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise RetroError(f"the verdicts file could not be read as JSON, {error}") from error
    if not isinstance(data, dict):
        raise RetroError(f"the verdicts file holds a {type(data).__name__}, which is no JSON "
                         "object")
    verdicts = data.get("verdicts", {})
    if not isinstance(verdicts, dict):
        raise RetroError(f"the verdicts file's verdicts value is a {type(verdicts).__name__}, "
                         "which is no object")
    for rid, row in verdicts.items():
        _check_verdict(rid, row, book)
    held = data.get("retro_digest")
    return verdicts, held if isinstance(held, str) and held else None


def _usable(verdict):



    if not isinstance(verdict, dict) or verdict.get("class") not in voice.CLASSES:
        return False
    if verdict["class"] != "voice":
        return True
    entry = verdict.get("entry")
    return isinstance(entry, str) and bool(entry.strip()) and verdict.get("kind") in voice.KINDS


def apply_verdicts(rows, verdicts, task, digest, date):













    divergences = [row for row in rows if row.kind != "unchanged"]
    ledger, missing = [], []
    for row in divergences:
        verdict = verdicts.get(row.rid)
        if not _usable(verdict):
            missing.append(row.rid)
            continue
        piece = row.draft or row.final
        ledger.append({
            "date": date, "task": task, "class": verdict["class"], "rule": verdict.get("rule"),
            "before": row.draft.text if row.draft else "",
            "after": row.final.text if row.final else "",
            "ratio": row.ratio, "change": row.kind, "promotion": "",
            "entry": verdict.get("entry"), "kind": verdict.get("kind"),
            "note": verdict.get("note") or "",
            "piece": {"unit": piece.unit, "line": piece.line},
            "source": "judged", "retro_digest": digest, "rid": row.rid,
        })
    named = {row.rid for row in divergences}
    return ledger, missing, [rid for rid in verdicts if rid not in named]


def _final_at(opcodes, low, high, final_words):





    taken = []
    for tag, a1, a2, b1, b2 in opcodes:
        if tag == "equal":
            start, end = max(a1, low), min(a2, high)
            if start < end:
                taken.append((b1 + start - a1, b1 + end - a1))
        elif a1 == a2:
            if low < a1 < high:
                taken.append((b1, b2))
        elif a1 < high and a2 > low:
            taken.append((b1, b2))
    if not taken:
        return []
    return final_words[min(start for start, _ in taken):max(end for _, end in taken)]


def _slip(rewrite_text, final_text):




    a, b = rewrite_text.casefold(), final_text.casefold()
    if a == b:
        return False
    for full, slip in SLIP_FORMS:
        pattern = re.compile(r"\b" + re.escape(full) + r"\b")
        if pattern.sub(slip, a) == b:
            return True
    return False


def unnecessary_edits(before, rewrite, final):












    draft_words, rewrite_words, final_words = before.split(), rewrite.split(), final.split()
    at_final = difflib.SequenceMatcher(None, draft_words, final_words).get_opcodes()
    changed = unnecessary = slips = 0
    for tag, low, high, start, end in difflib.SequenceMatcher(
            None, draft_words, rewrite_words).get_opcodes():
        if tag not in ("replace", "delete"):
            continue
        changed += 1
        kept = _final_at(at_final, low, high, final_words)
        if _slip(" ".join(rewrite_words[start:end]), " ".join(kept)):
            slips += 1
        elif kept == draft_words[low:high]:
            unnecessary += 1
    return changed, unnecessary, slips


def drift(texts):


    units = [Unit(id=f"u{number:04d}", kind="paragraph", surface=f"paragraph {number}",
                  text=text, locator={"start": 0, "end": len(text)})
             for number, text in enumerate(texts, 1)]
    document = Document(path="", format="markdown", units=units, cannot_see=[],
                        encoding="utf-8", newline=chr(10))
    return (structure._opening_stem_count(document), structure._closing_stem_count(document),
            structure._shared_ngram_count(document))


def rewrite_questions(questions, verdicts, voice_block, book=None,
                      classes=("voice", "slop"), kinds=("rewritten",)):




























    if book is None:
        book = _shipped()[0]
    rows, by_kind, by_class, not_bullet = [], {}, {}, 0
    for payload in sorted(questions, key=lambda payload: payload["task"]):
        task = payload["task"]
        answered = verdicts.get(task)
        if not isinstance(answered, dict):
            raise RetroError(f"task {task[:12]} has no verdicts payload, so its divergences "
                             "hold no class")
        held = answered.get("verdicts") or {}
        for divergence in payload["divergences"]:
            rid, kind = divergence["rid"], divergence["kind"]
            verdict = held.get(rid)
            cls = verdict.get("class") if isinstance(verdict, dict) else None
            if cls not in voice.CLASSES:
                raise RetroError(f"divergence {rid} of task {task[:12]} has no class of the "
                                 "six, so the rewrite set cannot be drawn")
            if cls not in classes:
                by_class[cls] = by_class.get(cls, 0) + 1
            elif kind not in kinds:
                by_kind[kind] = by_kind.get(kind, 0) + 1
            elif not divergence["bullet"]:
                not_bullet += 1
            else:
                if "hits" not in divergence:
                    raise RetroError(f"divergence {rid} of task {task[:12]} holds no hits key, "
                                     "so its findings cannot reach its row")
                absent = [rule for rule in divergence["hits"] if rule not in book.rules]
                if absent:
                    raise RetroError(f"divergence {rid} of task {task[:12]} names the hit "
                                     f"{absent[0]}, which the {book.name} rulebook does not "
                                     "hold")
                hits = [{"id": rule, "name": book.rules[rule].name,
                         "question": book.rules[rule].question or ""}
                        for rule in divergence["hits"]]
                rows.append({"rid": f"{task[:12]}/{rid}", "task": task,
                             "text": divergence["before"], "voice": voice_block,
                             "hits": hits})
    named = [row["rid"] for row in rows]
    repeated = sorted({rid for rid in named if named.count(rid) > 1})
    if repeated:
        raise RetroError(f"rows {', '.join(repeated)} share one rid, so a rewrites file "
                         "could not key a rewrite to each")
    return {"questions_digest": _sha256(rows), "rows": rows,
            "left_out": {"kind": by_kind, "class": by_class, "bullet": not_bullet}}


@dataclass
class Result:

    text: str
    code: int

    written: list
    cannot_see: list = dataclasses.field(default_factory=list)


@dataclass
class _Run:

    draft: Path
    final: Path
    task: str | None
    until_text: str | None
    voice_setting: object
    book_name: str
    rulebook_digest: str
    overlay_digest: str | None
    formats: dict = dataclasses.field(default_factory=dict)
    dropped: dict = dataclasses.field(default_factory=dict)
    counted: dict = dataclasses.field(default_factory=dict)
    rates: dict = dataclasses.field(default_factory=dict)
    rows: list | None = None
    cannot_see: list = dataclasses.field(default_factory=list)
    refused: bool = False
    classes: dict = dataclasses.field(default_factory=dict)
    appended: list | None = None
    superseded: dict | None = None
    ledger_lines: list = dataclasses.field(default_factory=list)
    profile: object = None

    def refuse(self, line):
        self.cannot_see.append(line)
        self.refused = True


def _refused_format(side, path):

    suffix = Path(path).suffix
    what = f"a {suffix} file" if suffix else "a file with no suffix"
    formats = ", ".join(FORMATS[:-1]) + " and " + FORMATS[-1]
    return f"the {side} is {what}, and a retro reads {formats} alone, so nothing was aligned"


def _extract(path, name):
    return extract_docx.extract(path) if name == "docx" else extract_markdown.extract(path)


def _unread_line(document):



    lines = (office.missing_package(extract_docx.PACKAGE, extract_docx.FORMAT),
             office.below_floor(extract_docx.PACKAGE, extract_docx.FLOOR, extract_docx.FORMAT))
    return next((line for line in lines if line in document.cannot_see), None)


def _side_rates(document, own, other, book):


    raw, raw_findings, words, _ = comparable_rate(document, book, own)
    rate, findings, _, aside = comparable_rate(document, book, other)
    return {"format": own, "words": words, "raw": raw, "raw_findings": raw_findings,
            "comparable": rate, "comparable_findings": findings, "set_aside": aside}


def _recorded_alignment(draft, held):





    try:
        asked = json.loads(Path(str(draft) + QUESTIONS_SUFFIX).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(asked, dict):
        return None
    for pair in (asked, asked.get("superseded")):
        if isinstance(pair, dict) and pair.get("retro_digest") == held:
            return pair.get("alignment_digest")
    return None


def _promote(rows, book):






    held = voice.read_ledger()[0]
    pairs = voice.pairs(held)
    combined = held + [row for row in rows if (row["retro_digest"], row["rid"]) not in pairs]
    fresh = {id(row) for row in combined[len(held):]}
    for rule, value, _ in voice.promotions(combined, book):
        naming = [row for row in combined
                  if row.get("class") == "slop" and row.get("rule") == rule]
        completing = naming[voice.PROMOTE_AT - 1]
        if id(completing) in fresh:
            completing["promotion"] = value


@dataclass
class _Step:

    rows: int
    entries: list
    written: bool
    profile: list
    promotions: list
    cannot_see: list
    harvested: bool = True


def _promotion_line(rule, value, ids, book):


    rows = ", ".join(str(row_id) for row_id in ids)
    if value in book.tier_order and value == book.rules[rule].tier:
        return f"- {rule} is already there at {value}, from {rows}."
    if value in book.tier_order:
        return (f"- {rule} argues {value}, up from {book.rules[rule].tier} under {book.name}, "
                f"from {rows}.")
    if value in voice.HELD_BY.get(book.name, {}).values():
        return f"- {rule} is held by {value}, from {rows}."
    return f"- {rule} is {value}, from {rows}."


def _general():



    return rulebook.load(hookio.plugin_root() / "references" / "rulebooks" / "general.json",
                         hookio.plugin_data() / "general.overlay.json")


def _template_texts(cannot_see):


    texts = {}
    for name in voice.TEMPLATE_FILES:
        try:
            texts[name] = (hookio.plugin_root() / name).read_text(encoding="utf-8")
        except (OSError, ValueError) as error:
            cannot_see.append(f"the template check could not read {name}, {error}, so no "
                              "voice row was checked against it")
    return texts


def _profile_step(rows_appended, book, ledger=None, general=None, recent=None):



















    rows, warnings = voice.read_ledger() if ledger is None else ledger
    cannot_see = list(warnings)
    if rows_appended and not rows:
        cannot_see.append(LEDGER_UNREAD.format(count=len(rows_appended)))
        return _Step(0, [], False, [], [], cannot_see, harvested=False)
    general = _general() if general is None else general
    if book.name != "general":
        cannot_see += [f"the general rulebook the silences are measured under: {line}"
                       for line in general.warnings]
    entries, left_out = voice.harvest(rows, general, recent)
    held, _ = voice.load_profile()
    states = {(entry["kind"], entry["entry"].strip().casefold()): entry["state"]
              for entry in held or []}
    profile = []
    try:
        _, dropped = voice.write_profile(entries)
    except OSError as error:
        cannot_see.append(PROFILE_REFUSED.format(error=f"{type(error).__name__}: {error}"))
        written = False
    else:
        written = True
        for entry in entries:
            was = states.get((entry["kind"], entry["entry"].strip().casefold()))
            if was != entry["state"]:
                change = f"new at {entry['state']}" if was is None else f"{was} to {entry['state']}"
                profile.append(f'- {entry["kind"]} "{report._inline(entry["entry"])}", {change}, '
                               f'evidence {", ".join(entry["evidence"])}.')
        profile = profile or ["No entry changed state."]
        profile += [f'- Dropped: {kind} "{report._inline(str(text))}". The profile held it and '
                    "the harvest of the ledger does not, so a hand edit lasts until the next "
                    "retro, and a preference enters through retro state."
                    for text, kind in dropped]
        profile += [f"- Left out: {report._inline(line)}." for line in left_out]
    promotions = [_promotion_line(rule, value, ids, book)
                  for rule, value, ids in voice.promotions(rows, book)]
    promotions += [f"- {row_id}'s before shares a 5-gram with a sentence of {name}, a file a "
                   "rewriting model reads, so the file may teach what the writer corrected."
                   for row_id, name in voice.template_hits(rows, _template_texts(cannot_see))]
    appended = {row.get("id") for row in rows_appended}
    promotions += [f"- {row['id']} recorded {report._inline(row['promotion'])} for "
                   f"{row.get('rule')} when it completed the count."
                   for row in rows if isinstance(row.get("promotion"), str)
                   and row["promotion"] and row.get("id") not in appended]
    return _Step(len(rows), entries, written, profile, promotions, cannot_see)


def _profile_text(step, head):

    if step is None:
        return f"None. {head}, and no profile step ran."
    if not step.harvested:
        return (f"{head}, and the ledger read back no row, so the profile was neither "
                "harvested nor written and stays as it was, which Cannot see names.")
    if not step.written:
        return (f"{head}, and the profile could not be written, so it stays as it was, which "
                "Cannot see names.")
    confirmed = sum(entry["state"] == "confirmed" for entry in step.entries)
    count = len(step.entries)
    return chr(10).join([
        (f"{head}, and the profile was harvested from the {step.rows} rows the ledger holds "
         f"and written whole: {count} {'entry' if count == 1 else 'entries'}, {confirmed} "
         f"confirmed and {count - confirmed} at watch."), *step.profile])


def _promotions_text(step, head):


    if step is None:
        return f"None. {head}, and no profile step ran."
    if not step.harvested:
        return f"None. {head}, and the ledger read back no row, so no promotion was audited."
    if not step.promotions:
        return (f"None. {head}, and no rule reaches {voice.PROMOTE_AT} slop rows, no voice "
                "row's before shares a 5-gram with a reference file, and no earlier row "
                "carries a promotion.")
    return chr(10).join([f"{head}, and the audit read the {step.rows} rows the ledger holds.",
                         *step.promotions])


def _retire_verdicts(draft):








    source = Path(str(draft) + VERDICTS_SUFFIX)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target, count = Path(f"{draft}{APPLIED_STEM}{stamp}.json"), 0
    while target.exists():
        count += 1
        target = Path(f"{draft}{APPLIED_STEM}{stamp}-{count}.json")
    try:
        os.replace(source, target)
    except OSError as error:
        return None, (f"the spent verdicts file could not be moved aside, "
                      f"{type(error).__name__}: {error}. The next run finds every row it "
                      "answers already in the ledger and moves it then")
    return target, (f"The verdicts file was spent by this run and moved to {target.name}. A "
                    "run with no verdicts file beside the draft is the ordinary next state.")


def _judged(state, draft, book, digests, written):










    retro_value, alignment_value = digests
    try:
        verdicts, held = read_verdicts(draft, book)
    except RetroError as error:
        state.refuse(UNUSABLE.format(error=error))
        return False
    if held is None:
        state.refuse(NO_DIGEST)
        return False
    if held != retro_value:
        recorded, half = _recorded_alignment(draft, held), None
        if recorded is not None:
            half = "alignment" if recorded != alignment_value else "rulebook"
            state.superseded = {"retro_digest": held, "alignment_digest": recorded}
        state.refuse(STALE_LINES[half])
        return True
    rows, missing, unknown = apply_verdicts(state.rows, verdicts, state.task, retro_value,
                                            datetime.now(timezone.utc).date().isoformat())
    if unknown:
        state.cannot_see.append(UNKNOWN.format(count=len(unknown), rids=", ".join(unknown)))
    if missing:
        total = sum(row.kind != "unchanged" for row in state.rows)
        state.refuse(MISSING.format(count=len(missing), total=total, rids=", ".join(missing)))
        return False
    _promote(rows, book)
    ids, refusals = voice.append_rows(rows)
    recorded, recorded_warnings = voice.read_ledger()
    pairs = voice.pairs(recorded)
    if any((row["retro_digest"], row["rid"]) not in pairs for row in rows):
        state.refuse(LEDGER_REFUSED)
        state.cannot_see += refusals
        return False
    state.appended, state.ledger_lines = ids, [f"- {line}" for line in refusals]
    state.classes = {row["rid"]: row["class"] for row in rows}
    state.profile = _profile_step([row for row in recorded if row.get("id") in ids], book,
                                  (recorded, recorded_warnings))
    if state.profile is not None:
        state.cannot_see += state.profile.cannot_see


        if not state.profile.written:
            state.refused = True
    target, note = _retire_verdicts(draft)
    if target is None:
        state.cannot_see.append(note)
    else:
        written.append(target)
        state.ledger_lines.append(note)
    return False


def _rate_text(rate, findings, words):
    if rate is None:
        return "no words to rate"
    noun = "finding" if findings == 1 else "findings"
    return f"{rate:.3f} per 100 words, {findings} {noun} over {words} words"


def _what_ran(state):
    lines = []
    for side, path in (("Draft", state.draft), ("Final", state.final)):
        name = state.formats.get(side.lower())
        lines.append(f"{side}: {path} ({name or 'a format a retro does not read'}).")
    lines.append(f"Rulebook: {state.book_name}, sha256 {state.rulebook_digest}.")
    lines.append(f"Overlay: sha256 {state.overlay_digest}." if state.overlay_digest
                 else "Overlay: none.")
    if state.voice_setting == "mine":
        lines.append("Voice: mine.")
    else:
        lines.append("Voice: off.")
        lines.append("The harvested profile layers on no run until the marker sets mine.")
    lines.append("Task: none, since the draft was not read." if state.task is None
                 else f"Task: {report._inline(state.task)}.")
    lines.append(f"Thresholds: unchanged at {UNCHANGED_AT} or above, rewritten at "
                 f"{REWRITTEN_AT} or above, deleted or added below {REWRITTEN_AT}.")
    if state.until_text:
        lines.append(f"Until: {report._inline(state.until_text)}.")
    else:
        lines.append("Until: none, so each side was read whole.")
    if state.rows is None:
        lines.append("Units dropped: none, since nothing was aligned.")
    else:
        lines.append(f"Units dropped: draft {state.dropped['draft']}, "
                     f"final {state.dropped['final']}.")
    return "\n".join(lines)


def _alignment(state):
    if state.rows is None:
        return "None. Nothing was aligned, because a file was refused, which Cannot see names."
    (draft_pieces, draft_bullets) = state.counted["draft"]
    (final_pieces, final_bullets) = state.counted["final"]
    counts = {kind: sum(row.kind == kind for row in state.rows) for kind in KINDS}
    ratios = [row.ratio for row in state.rows if row.kind == "rewritten"]
    bins = ", ".join(f"{low:.2f} to {high:.2f}: {sum(low <= r < high for r in ratios)}"
                     for low, high in BINS)
    return "\n".join([
        f"Pieces: draft {draft_pieces}, final {final_pieces}.",
        f"Bullet pieces aligned: draft {draft_bullets}, final {final_bullets}.",
        (f"Unchanged {counts['unchanged']}, rewritten {counts['rewritten']}, "
         f"deleted {counts['deleted']}, added {counts['added']}."),
        f"Rewritten ratios: {bins}.",
    ])


def _flag_rate(state):
    if state.rows is None:
        return "None. No rate was read, because a file was refused, which Cannot see names."
    lines = [("Each side is read through its own extractor over the units the cut kept, and "
              "its comparable rate sets aside every rule the other side's format turns off.")]
    for side, other in (("draft", "final"), ("final", "draft")):
        rates = state.rates[side]
        aside = rates["set_aside"]
        raw = _rate_text(rates["raw"], rates["raw_findings"], rates["words"])
        comparable = _rate_text(rates["comparable"], rates["comparable_findings"],
                                rates["words"])
        named = f"set aside: {', '.join(aside)}." if aside else "nothing set aside."
        lines.append(f"{side.capitalize()} ({rates['format']}), raw: {raw}.")
        lines.append(f"{side.capitalize()}, comparable with the {state.formats[other]} side: "
                     f"{comparable}, {named}")
    return "\n".join(lines)


def _divergences(state):
    if state.rows is None:
        return "None. Nothing was aligned, because a file was refused, which Cannot see names."
    lines = []
    for row in state.rows:
        if row.kind == "unchanged":
            continue
        lines.append(f"- {row.rid}, {row.kind}, ratio {row.ratio:.3f}, "
                     f"{state.classes.get(row.rid, 'unjudged')}.")
        if row.draft is not None:
            lines += ["Before:", report._quote(row.draft.text)]
        if row.final is not None:
            lines += ["After:", report._quote(row.final.text)]
    return "\n".join(lines) or "None. Every aligned piece is unchanged."


def _ledger(state):
    if state.appended is None:
        return "None. No verdicts file was applied, so no row was appended."
    count = len(state.appended)
    head = (f"Appended {count} {'row' if count == 1 else 'rows'} to the ledger: "
            f"{', '.join(state.appended)}." if count else "Appended no row to the ledger.")
    return "\n".join([head, *state.ledger_lines])


def _cannot_see(state):
    return "\n".join(f"- {line}" for line in state.cannot_see) or "None."


def _appended_head(state):


    return "The rows were appended" if state.appended else "No row was appended"


_SECTION_TEXT = {
    "What ran": _what_ran,
    "Alignment": _alignment,
    "Flag rate": _flag_rate,
    "Divergences": _divergences,
    "Ledger": _ledger,
    "Profile": lambda state: (
        _profile_text(state.profile, _appended_head(state))
        if state.appended is not None
        else "None. No verdicts file was applied, so the profile was not harvested."),
    "Promotions": lambda state: (
        _promotions_text(state.profile, _appended_head(state))
        if state.appended is not None
        else "None. No verdicts file was applied, so no promotion was audited."),
    "Cannot see": _cannot_see,
    "Limits": lambda state: "\n".join(LIMITS),
}


def _render(state):


    parts = [report._neutralize_headings(f"# Retro report for {state.draft}", SECTIONS), ""]
    for heading in SECTIONS:
        body = report._neutralize_headings(_SECTION_TEXT[heading](state).rstrip(), SECTIONS)
        parts += [f"## {heading}", body or "None.", ""]
    return "\n".join(parts).rstrip() + "\n"


def run(draft, final, task=None, until_text=None, voice_setting=False, book=None,
        rulebook_bytes=None, warnings=(), overlay_bytes=b""):


























    draft, final = Path(draft), Path(final)
    if (book is None) != (rulebook_bytes is None):
        raise ValueError("book and rulebook_bytes are given together or not at all, since "
                         "the retro digest hashes the bytes of the book in force")
    if book is None:
        book, rulebook_bytes = _shipped()
    state = _Run(draft, final, task, until_text,
                 voice_setting, book.name, hashlib.sha256(rulebook_bytes).hexdigest(),
                 hashlib.sha256(overlay_bytes).hexdigest() if overlay_bytes else None)
    state.cannot_see += [f"Configuration warning, this run ignored it: {line}"
                         for line in warnings]
    sides = {"draft": draft, "final": final}
    for side, path in sides.items():
        state.formats[side] = _format_of(path)
        if state.formats[side] is None:
            state.refuse(_refused_format(side, path))
    documents, digests = {}, {}
    if not state.refused:
        for side, path in sides.items():
            try:
                digests[side] = hashlib.sha256(path.read_bytes()).hexdigest()
                documents[side] = _extract(path, state.formats[side])
            except (OSError, ValueError, office.OfficeError) as error:
                state.refuse(f"the {side} could not be read, {type(error).__name__}: {error}, "
                             "so nothing was aligned")
                continue
            unread = _unread_line(documents[side])
            if unread is not None:
                state.refuse(unread)
        if task is None and "draft" in digests:
            state.task = digests["draft"]
    written, retro_value, alignment_value, bodies = [], None, None, {}
    if not state.refused:
        for side in sides:
            bodies[side], state.dropped[side] = until(documents[side], until_text)
            found = pieces(bodies[side])
            state.counted[side] = (len(found), sum(piece.bullet for piece in found))
            state.cannot_see += [f"{side.capitalize()}: {line}"
                                 for line in documents[side].cannot_see]
        state.rows = align([p for p in pieces(bodies["draft"]) if p.bullet],
                           [p for p in pieces(bodies["final"]) if p.bullet])
        for side, other in (("draft", "final"), ("final", "draft")):
            state.rates[side] = _side_rates(bodies[side], state.formats[side],
                                            state.formats[other], book)
        retro_value = retro_digest(digests["draft"], digests["final"], until_text,
                                   rulebook_bytes, overlay_bytes)
        alignment_value = alignment_digest(digests["draft"], digests["final"], until_text)
    judged = Path(str(draft) + VERDICTS_SUFFIX).is_file()
    ask = not judged
    if judged and state.rows is None:
        state.refuse(NOTHING_ALIGNED)
    elif judged:
        ask = _judged(state, draft, book, (retro_value, alignment_value), written)
    if ask and state.rows is not None:
        digests_written = (retro_value, alignment_value, state.rulebook_digest,
                           hashlib.sha256(overlay_bytes).hexdigest())
        try:
            questions = write_questions(
                draft, bodies["draft"], bodies["final"], state.rows, state.task,
                digests_written, until_text, (state.dropped["draft"], state.dropped["final"]),
                state.rates, book, state.superseded)
        except OSError as error:
            state.refuse(f"the questions file could not be written, {error}")
        else:
            written.append(questions)
            if judged:
                state.cannot_see.append(FRESH_QUESTIONS.format(name=questions.name))
    text = _render(state)
    code = 1 if state.refused else 0
    path = Path(str(draft) + REPORT_SUFFIX)
    try:
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    except OSError as error:
        text += f"\nThe report could not be written to {path}, {error}.\n"
        code = 1
    return Result(text, code, written, list(state.cannot_see))


def state(kind, entry, task="stated", book=None, warnings=(), general=None):












    if kind not in voice.KINDS:
        raise ValueError(f"a stated preference names kind {kind!r}, which is none of "
                         f"{', '.join(voice.KINDS)}")
    if not isinstance(entry, str) or not entry.strip():
        raise ValueError("a stated preference names no entry text")
    if book is None:
        book = _shipped()[0]
    row = {"date": datetime.now(timezone.utc).date().isoformat(), "task": task,
           "class": "voice", "rule": None, "before": "", "after": "", "ratio": None,
           "change": None, "promotion": "", "entry": entry.strip(), "kind": kind, "note": "",
           "piece": None, "source": "stated", "retro_digest": None, "rid": None}
    ids, refusals = voice.append_rows([row])
    cannot_see = [f"Configuration warning, this run ignored it: {line}" for line in warnings]
    cannot_see += refusals
    step, head = None, "The row was appended"
    if ids:
        step = _profile_step([dict(row, id=ids[0])], book, general=general)
        cannot_see += step.cannot_see
    sections = {
        "Ledger": (f'Appended {ids[0]} to the ledger: a stated {kind} entry, '
                   f'"{report._inline(entry.strip())}".' if ids
                   else "None. The ledger could not take the row, which Cannot see names."),
        "Profile": (_profile_text(step, head) if ids
                    else "None. No row was appended, so the profile was not harvested."),
        "Promotions": (_promotions_text(step, head) if ids
                       else "None. No row was appended, so no promotion was audited."),
        "Cannot see": chr(10).join(f"- {line}" for line in cannot_see) or "None.",
    }
    parts = ["# Retro state", ""]
    for heading, body in sections.items():
        parts += [f"## {heading}", report._neutralize_headings(body, SECTIONS), ""]
    written = [voice.home() / voice.LEDGER_NAME] if ids else []
    if step is not None and step.written:
        written.append(voice.home() / voice.PROFILE_NAME)
    return Result(chr(10).join(parts).rstrip() + chr(10), 0 if len(written) == 2 else 1,
                  written, cannot_see)
