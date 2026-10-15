


























































































import json
import os
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from scripts import marker, office, records



SECOND_SUFFIX = ".humanize-second.json"






A_PAGE_IN_WORDS = 500





ALWAYS_ON_FORMATS = frozenset({"pptx", "xlsx", "docx"})






AUTHORITY_FILES = ("references/judgment-checklist.md", "references/twins.md")















RULEBOOK_DIR = "references/rulebooks"







BRIEF_KEYS = ("artifact_digest", "format", "rulebook", "read", "units", "findings")




UNIT_KEYS = ("id", "kind", "surface", "weighs", "text")


TERMINAL_VERDICTS = frozenset({"pass", "FIRE", "n-a"})




ROW_TEXT_FIELDS = ("rule", "unit", "verdict", "twin", "exception")




APPLIED_STEM = ".humanize-second.applied-"



_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


_MISSING = object()

_DELETE_TO_ASK_AGAIN = ("Delete that file to have the next run write a fresh brief, "
                        "and read it first if the rows in it are worth keeping.")

_OVERRIDE_ON = "the second_reader setting reads on, which overrides the default"
_OVERRIDE_OFF = "the second_reader setting reads off, which overrides the default"


@dataclass
class Resolution:












    on: bool
    rule: str


@dataclass
class Read:







    findings: list = field(default_factory=list)
    note: str = ""
    filled: bool = False


def brief_path(artifact_path):
    return pathlib.Path(str(artifact_path) + SECOND_SUFFIX)


def word_count(document):







    return sum(len(unit.text.split()) for unit in document.units if unit.weighs)


def resolve(settings, document):













    value = settings.get("second_reader", "auto")
    if value in (True, "on"):
        return Resolution(True, _OVERRIDE_ON)
    if value in (False, "off"):
        return Resolution(False, _OVERRIDE_OFF)

    prefix = ""
    if value != "auto":
        prefix = (f"the second_reader setting reads {value!r}, which is none of on, "
                  f"off or auto, so the settled row's own default decided it: ")
    if document.format in ALWAYS_ON_FORMATS:
        return Resolution(True, prefix + (
            f"the format is {document.format}, one of the three the settled row turns "
            f"the second reader on for"))
    words = word_count(document)
    if words > A_PAGE_IN_WORDS:
        return Resolution(True, prefix + (
            f"the document runs {words} words over the units that weigh, past the "
            f"{A_PAGE_IN_WORDS}-word page threshold"))
    return Resolution(False, prefix + (
        f"the document runs {words} words over the units that weigh, inside the "
        f"{A_PAGE_IN_WORDS}-word page threshold, and {document.format} is outside the "
        f"three formats the settled row turns the second reader on for"))


def second_reader_on(settings, document):

    return resolve(settings, document).on


def read_list(rulebook):



    return [f"{RULEBOOK_DIR}/{rulebook}.json", *AUTHORITY_FILES]


def write_brief(artifact_path, document, rulebook="", digest=""):
























    if rulebook not in marker.RULEBOOKS:
        raise ValueError(
            f"write_brief was given rulebook {rulebook!r}, which is not one of "
            f"{marker.RULEBOOKS}. This value is copied into the brief, so anything "
            "else is a channel for the main judge's own work.")
    if digest and not _DIGEST_RE.match(digest):
        raise ValueError(
            f"write_brief was given a digest of {len(digest)} characters that is not a "
            "sha256 hexdigest. This value is copied into the brief, so anything else "
            "is a channel for the main judge's own work.")
    payload = {
        "artifact_digest": digest,
        "format": document.format,
        "rulebook": rulebook,
        "read": read_list(rulebook),
        "units": [{"id": unit.id, "kind": unit.kind, "surface": unit.surface,
                   "weighs": unit.weighs, "text": unit.text}
                  for unit in document.units],
        "findings": [],
    }
    path = brief_path(artifact_path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def retire_brief(artifact_path, copy=None):


















    source = brief_path(artifact_path)
    if not source.exists():
        return None, None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = pathlib.Path(f"{artifact_path}{APPLIED_STEM}{stamp}.json")
    try:
        os.replace(source, target)
    except OSError as exc:
        return None, (f"the spent second reader brief could not be moved aside: "
                      f"{type(exc).__name__}: {exc}. Delete or rename it before the next "
                      "run, or that run will refuse it as stale and write no replacement.")
    if copy is not None:
        return target, (f"the second reader's brief was spent by this run on the "
                        f"{office.written_as(artifact_path)[0]} at "
                        f"{pathlib.Path(copy).name} and moved to {target.name}. The original "
                        "is unchanged, and the next run writes a fresh brief.")
    return target, (f"the second reader's brief was spent by this run and moved to "

                    f"{target.name}. The artifact has changed, so those findings no "
                    "longer address it, and the next run writes a fresh brief.")


def read_findings(artifact_path, document, book, digest=""):




































    path = brief_path(artifact_path)
    if not path.exists():
        return Read()
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return Read(note=_refused(
            path, f"it could not be read: {type(exc).__name__}: {exc}"), filled=True)
    except UnicodeDecodeError as exc:
        return Read(note=_refused(path, f"it is not valid UTF-8: {exc}"), filled=True)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return Read(note=_refused(path, f"it does not read as JSON: {exc}"), filled=True)
    if not isinstance(payload, dict):
        return Read(note=_refused(
            path, f"its top level is a {type(payload).__name__} and not an object"),
            filled=True)
    rows = payload.get("findings", _MISSING)
    if rows is _MISSING:
        return Read(note=_refused(path, (
            "it carries no 'findings' key at all, and every brief this tool writes "
            f"carries one. The keys it does carry are {sorted(payload)}. An answer "
            "written under any other key is not read, and this run left the file alone "
            "rather than replacing it")), filled=True)
    if not isinstance(rows, list):
        return Read(note=_refused(
            path, f"its 'findings' key holds a {type(rows).__name__} and not a list"),
            filled=True)
    if not rows:
        return Read()
    if payload.get("artifact_digest", "") != digest:
        return Read(note=_refused(path, (
            "its artifact_digest is not this run's own, so it answers a different "
            "reading of this artifact under different rules or a different voice "
            "profile, and every unit id in it may now name different text")), filled=True)

    units = {unit.id: unit.text for unit in document.units}
    findings = []
    for index, row in enumerate(rows):
        problem = _check_row(row, units, book)
        if problem:
            return Read(note=_refused(path, f"its findings row {index} {problem}"),
                        filled=True)
        findings.append(_finding(row, book))
    return Read(findings=findings, filled=True)


def merge(main_findings, second_findings):














































    merged = list(main_findings)
    seen = set()
    for finding in second_findings:
        key = (finding.rule, finding.unit, finding.span)
        if key in seen:
            continue
        seen.add(key)
        finding.source = "model"
        finding.second_reader = True
        merged.append(finding)
    return records.number(merged)


def _refused(path, reason):
    return (f"the second reader's brief at {path} was refused, so nothing in it was "
            f"merged into this report: {reason}. {_DELETE_TO_ASK_AGAIN}")


def _check_row(row, units, book):



    if not isinstance(row, dict):
        return f"is a {type(row).__name__} and not an object"
    for name in ROW_TEXT_FIELDS:
        if name in row and row[name] is not None and not isinstance(row[name], str):
            return f"holds {name} as {type(row[name]).__name__} and not a string"
    rule = row.get("rule", "")
    if rule not in book.rules:
        return f"names rule {rule!r}, which the {book.name} rulebook does not carry"
    unit = row.get("unit", "")
    if unit != "document" and unit not in units:
        return f"names unit {unit!r}, which this reading of the artifact does not hold"
    verdict = row.get("verdict", "")
    if verdict not in TERMINAL_VERDICTS:
        return (f"carries verdict {verdict!r}, and a second reader has already judged, "
                f"so its own finding carries one of {sorted(TERMINAL_VERDICTS)}")
    span = row.get("span")
    if span is None:
        return ""
    if unit == "document":
        return "is scoped to the whole document and still carries a span"
    if (not isinstance(span, list) or len(span) != 2
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in span)):
        return f"carries span {span!r}, which is neither null nor a pair of integers"
    start, end = span
    if not 0 <= start <= end <= len(units[unit]):
        return f"carries span {span!r}, which falls outside unit {unit!r}"
    return ""


def _finding(row, book):










    rule = book.rules[row["rule"]]
    span = row.get("span")
    return records.Finding(
        rule=row["rule"], rulebook=book.name, unit=row["unit"],
        span=tuple(span) if span is not None else None,
        tier=rule.tier, source="model", verdict=row["verdict"],
        exception=row.get("exception") or None,
        category=rule.category, twin=row.get("twin") or "",
    )
