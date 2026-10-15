



















































































import argparse
import difflib
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts import (code_metrics, extract_code, extract_docx, extract_markdown, extract_pdf,
                     extract_pptx, extract_prompt, extract_xlsx, fidelity, fixes, hookio, learn,
                     marker, measures, office, protect, reconcile, records, report, retro,
                     rulebook, scan, selfcheck, structure, validate, voice)



from scripts import second_reader as second_reader_stage
from scripts.density import density
from scripts.gate_write import CODE_DECODE_FAILED, MARK_RULES
from scripts.units import sentences



DEFAULT_BRANCHES = ("main", "master")
GIT_TIMEOUT = 10




NO_MARKER_SOURCE = ("the shipped defaults, since no .humanize.json sits above "
                    "this path. Run /humanize on to set the rulebook for this repo")







LEFT_TIERS = frozenset({"block", "warn", "warn-with-company"})







RISK_UNSUPPLIED = ("not supplied. The Risk line is the judge's own answer under C003, "
                   "given in the risk field of a FIRE verdicts row with no rewrite, and "
                   "this item printed none.")




MODEL_REWRITE_STANDS = (
    "the model rewrote this unit and the fidelity check accepted the rewrite. No rule "
    "was re-checked against the replacement, so this finding stands for a reader to "
    "confirm against the new text, which the Rewrites applied section prints in full.")




MEANING_REFUSED_CHANGE = (
    "the rewrite this run produced was refused, because its meaning line does not read "
    "kept, so the original stands. Rewrite this unit by hand.")




REWRITE_OFF_CHANGE = ("a registered substitution can rewrite this unit, and the rewrite "
                      "stage was off on this run.")






COVERAGE_HELD_CHANGE = ("a registered substitution can rewrite this unit, and the rewrite "
                        "stage did not run on this run, because coverage failed.")
COVERAGE_HELD_LINE = ("the rewrite stage did not run on this run, because coverage failed. "
                      "Answer the candidates named above in the same verdicts file and run "
                      "again.")
COVERAGE_HELD_STAGE = "coverage failed against the verdicts file beside this artifact"





REFUSED_SHAPE_STAGE = "the verdicts file beside this artifact could not be used"
REFUSED_STALE_STAGE = ("the verdicts file beside this artifact was refused, since nothing "
                       "proves its answers belong to this run's questions")





BASELINE_FAILED_STAGE = "the project's {stages} failed before any rewrite"
BASELINE_FAILED_CHANGE = ("a registered substitution can rewrite this unit, and the rewrite "
                          "stage did not run on this run, because the project's {stages} "
                          "failed before any rewrite.")
BASELINE_FAILED_LINE = ("the project's {stages} failed before any rewrite, so this run "
                        "rewrote nothing and retired nothing. {details}")




VALIDATION_REVERTED_CHANGE = ("the rewrite this run wrote back was reverted, because the "
                              "project's {stages} failed after the write back, so the "
                              "original stands. Rewrite this unit by hand.")
VALIDATION_REVERTED_LINE = ("the project's {stages} failed after the write back, so the bytes "
                            "this run read were written back to {path} and nothing was "
                            "retired.")
REVERT_FAILED_LINE = ("the project's {stages} failed after the write back, and the bytes this "
                      "run read could not be written back to {path}, so the rewritten file "
                      "stands and nothing was retired.")



CODE_VALIDATION_FAILED_LINE = ("this run's code validation failed, because the project's "
                               "{stages} failed {when}. It covers the Python files alone, so "
                               "any rewrite this run wrote back to this file stands.")



CODE_VALIDATION_FAILED_COPY_LINE = ("this run's code validation failed, because the project's "
                                    "{stages} failed {when}. It covers the Python files "
                                    "alone, so any rewrite this run wrote to this file's "
                                    "{long} stands.")


_STAGES = ("formatter", "tests")




UNHANDLED_ROUTES = {
    "other": "a format no handler in this build reads. Nothing in this file was read "
             "on this run",
}


OFFICE_EXTRACTORS = {"pptx": extract_pptx, "xlsx": extract_xlsx, "docx": extract_docx,
                     "pdf": extract_pdf}




OFFICE_WRITERS = {"pptx": extract_pptx, "xlsx": extract_xlsx, "docx": extract_docx,
                  "pdf": extract_pdf}




PDF_PASSED_OVER = ", {count} pdf {files} passed over, name one directly to read it"




COPY_CANDIDATES_LINE = ("the candidates file still matches this original, and the answers "
                        "were spent on the {kind} at {copy}")


IN_PLACE_REFUSED_LINE = ("{path} was not written in place, because {reason}. The rewrites stay "
                         "in the report, and the file is unchanged.")
IN_PLACE_EVERY_REFUSED_LINE = ("every rewrite this run accepted was refused by the in-place "
                               "writer, so {path} was not written. The file is unchanged, and "
                               "no answer was spent.")


PDF_NEVER_IN_PLACE_LINE = ("the marker asks for in-place writes, and a PDF is never edited in "
                           "place, so the markdown delivery was written beside it")

_PROSE_SUFFIXES = (".md", ".markdown", ".txt")
_TEMP_SUFFIX = ".humanize-tmp"



VERDICTS_APPLIED_STEM = ".humanize-verdicts.applied-"


@dataclass
class Result:


    text: str
    findings: list
    blocks: list
    warns: list
    fixed: set
    rewrites: list
    reverted: list
    cannot_see: list
    written: list
    code: int




    path: str = ""
    left: list = field(default_factory=list)


@dataclass
class _Settled:

    states: tuple
    failed: tuple = ()
    reverted: bool = False
    code_failed: tuple = ()


@dataclass
class _Pending:




    path: pathlib.Path
    finish: object
    progress: dict
    wrote: bool = False
    original_bytes: bytes = b""
    units: list = field(default_factory=list)






def _emit(text, stream=None):










    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None) or "utf-8"
    print(text.encode(encoding, "replace").decode(encoding, "replace"), file=stream)


def _print_diff(path, surface, before, after, state="after"):











    for line in difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=f"{path} {surface} before", tofile=f"{path} {surface} {state}",
            lineterm=""):
        _emit(line)






def _file_digest(data):



    return hashlib.sha256(data).hexdigest()


def _rule_bytes(settings, plugin_root):










    name = settings["rulebook"]
    shipped = plugin_root / "references" / "rulebooks" / f"{name}.json"
    overlay = hookio.plugin_data() / f"{name}.overlay.json"
    out = []
    for path in (shipped, overlay):
        try:
            out.append(path.read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            out.append(b"")
    return tuple(out)


def _profile_bytes():




    try:
        return (voice.home() / voice.PROFILE_NAME).read_bytes()
    except OSError:
        return b""


def _sorted_protect(entries):








    if not isinstance(entries, list):
        return entries
    return sorted(entries, key=lambda entry: json.dumps(entry, sort_keys=True, default=str))


def _question_digest(file_digest, document, settings, rulebook_bytes, overlay_bytes,
                     profile_bytes=b""):















































    payload = json.dumps({
        "file": file_digest,
        "rulebook_file": hashlib.sha256(rulebook_bytes).hexdigest(),
        "overlay_file": hashlib.sha256(overlay_bytes).hexdigest(),
        "format": document.format,
        "protect": _sorted_protect(settings.get("protect", [])),
        "profile_file": hashlib.sha256(profile_bytes).hexdigest(),
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extractor(route):
    return extract_prompt.extract_text if route == "prompt" else extract_markdown.extract_text


def _handler_name(route, path):




    if route in UNHANDLED_ROUTES or route in ("prompt", "code"):
        return route
    if route in ("office", "pdf"):
        return office.format_of(path)
    if path.suffix.lower() == ".txt":
        return "txt"
    return "markdown"


def _empty_document(path, route, cannot_see):







    formats = {"prompt": "prompt", "code": extract_code.FORMAT,
               "office": office.format_of(path), "pdf": "pdf"}
    return records.Document(
        path=str(path), format=formats.get(route, "markdown"),
        units=[], cannot_see=list(cannot_see), encoding="utf-8", newline="\n")


def _relative(path, root):


    if root is not None:
        try:
            return pathlib.Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            pass
    return pathlib.Path(path).name


def _extract_code(path, data, file_digest, root):





    try:
        encoding = extract_code.encoding_of(data)
    except extract_code.ExtractError as exc:
        return (_empty_document(path, "code", [CODE_DECODE_FAILED.format(error=exc)]),
                file_digest, False)
    text = data.decode(encoding)
    if text.startswith("\ufeff"):
        text = text[1:]
    newline = "\r\n" if b"\r\n" in data else "\n"
    try:
        document = extract_code.extract_text(text, _relative(path, root), newline)
    except Exception as exc:
        return (_empty_document(
            path, "code", [f"the extractor failed on this file: {type(exc).__name__}: {exc}"]),
                file_digest, False)
    document.encoding = encoding
    document.text = text
    document.original_bytes = data
    document.path = str(path)
    return document, file_digest, True


def _extract_office(path, route, data, file_digest):












    fmt = office.format_of(path)
    extractor = OFFICE_EXTRACTORS[fmt]
    try:
        document = extractor.extract(path)
    except Exception as exc:


        message = str(exc).removeprefix(f"{path}: ")
        return (_empty_document(
            path, route, [f"the extractor failed on this file: {type(exc).__name__}: "
                          f"{message}"]), file_digest, False)
    document.original_bytes = data
    document.text = ""
    unread = (office.missing_package(extractor.PACKAGE, fmt),
              office.below_floor(extractor.PACKAGE, extractor.FLOOR, fmt))
    return document, file_digest, bool(document.units) or (
        fmt != "pdf" and not any(line in document.cannot_see for line in unread))


def _extract(path, route, root=None):








    if route in UNHANDLED_ROUTES:
        return _empty_document(path, route, [UNHANDLED_ROUTES[route]]), "", False
    try:
        data = path.read_bytes()
    except OSError as exc:
        return (_empty_document(path, route,
                                [f"the file could not be read: {type(exc).__name__}: {exc}"]),
                "", False)
    file_digest = _file_digest(data)
    if route == "code":
        return _extract_code(path, data, file_digest, root)
    if route in ("office", "pdf"):
        return _extract_office(path, route, data, file_digest)
    encoding = extract_markdown.encoding_of(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:
        return (_empty_document(
            path, route,
            [f"the file's encoding could not be decoded. The encoding tried was {encoding}, "
             f"and it raised {type(exc).__name__}: {exc}"]), file_digest, False)
    newline = "\r\n" if b"\r\n" in data else "\n"
    try:
        document = _extractor(route)(text, str(path), newline)
    except Exception as exc:


        return (_empty_document(
            path, route,
            [f"the extractor failed on this file: {type(exc).__name__}: {exc}"]),
                file_digest, False)
    document.encoding = encoding
    return document, file_digest, True






def _vocab_rules(book):



    return {rid for rid, rule in book.rules.items()
            if rule.tier == "density" and rid not in MARK_RULES}


def _protected_spans(document, entries):
    spans = {}
    for unit_id, start, end, _ in protect.apply(document, entries):
        spans.setdefault(unit_id, []).append((start, end))
    return spans


def _drop_silenced(findings, document, book, entries, fired):






    units = {unit.id: unit for unit in document.units}
    kept = voice.drop_silenced(findings, units, entries, book.name)
    if len(kept) < len(findings):
        for entry in entries:
            left = {id(f) for f in voice.drop_silenced(findings, units, [entry], book.name)}
            for rule in dict.fromkeys(f.rule for f in findings if id(f) not in left):
                fired.append((rule, entry["entry"], entry["kind"]))
    return kept


def _scan_all(document, book, settings, entries=(), fired=None):
























    protected = _protected_spans(document, settings.get("protect", []))
    findings = _drop_silenced(scan.scan(document, book, protected), document, book, entries,
                              [] if fired is None else fired)
    findings += structure.structural(document, book)
    if structure.PATTERN_ROW_IDS <= set(book.rules):
        findings += structure.pattern_rows(document, book)
    findings += structure.count_rows(document, book)
    findings += measures.measure_rows(document, book)
    findings += structure.notes_caveat(document, book)
    return findings


def _code_findings(document, book, settings, root, entries=(), fired=None):
















    findings = _drop_silenced(
        scan.scan(document, book, _protected_spans(document, settings.get("protect", []))),
        document, book, entries, [] if fired is None else fired)
    if document.skipped:
        return findings
    return findings + code_metrics.metrics(document.text, document.path, book, root, document)


_COMPREHENSIVE = re.compile(r"\bcomprehensive\b", re.IGNORECASE)


def _readme_note(path, document, book):




    rule = book.rules.get("C129")
    if rule is None or not pathlib.Path(path).name.upper().startswith("README"):
        return []
    unit = next((u for u in document.units if u.weighs and u.kind == "paragraph"), None)
    spans = sentences(unit.text) if unit is not None else []
    if not spans:
        return []
    start, end = spans[0]
    m = _COMPREHENSIVE.search(unit.text, start, end)
    if m is None:
        return []
    return [records.Finding(rule="C129", rulebook=book.name, unit=unit.id, span=m.span(),
                            tier="metric", source="regex", verdict="n-a",
                            category=rule.category)]






def _falls_silent(rule_id, text, document, unit, book, settings):









    probe = records.Document(
        path=document.path, format=document.format,
        units=[records.Unit(id=unit.id, kind=unit.kind, surface=unit.surface, text=text,
                            locator=dict(unit.locator), weighs=True)],
        cannot_see=[], encoding=document.encoding, newline=document.newline)
    protected = _protected_spans(probe, settings.get("protect", []))
    return not any(f.rule == rule_id for f in scan.scan(probe, book, protected))


def _substitute(document, findings, book, settings, skip_units):


















    texts, fixed, applied, reasons = {}, set(), {}, {}
    units = {unit.id: unit for unit in document.units}
    for finding in findings:
        unit = units.get(finding.unit)
        if unit is None or finding.unit in skip_units:
            continue
        if (finding.fix or {}).get("kind") != "final":
            continue
        current = texts.get(unit.id, unit.text)
        suggestion = fixes.suggest(finding, current)
        if suggestion["kind"] != "final":
            if _falls_silent(finding.rule, current, document, unit, book, settings):
                fixed.add(finding.fid)
            else:
                reasons[finding.fid] = suggestion["text"]
            continue
        if not _falls_silent(finding.rule, suggestion["text"], document, unit, book, settings):



            reasons[finding.fid] = (
                f"the substitution left {finding.rule} still matching, so its Final "
                "text was withheld. Rewrite this unit by hand.")
            continue
        texts[unit.id] = suggestion["text"]
        fixed.add(finding.fid)
        applied.setdefault(unit.id, []).append(finding.fix["function"])
    return texts, fixed, applied, reasons


def _model_units(findings):
    return {f.unit for f in findings if f.rewrite}


def _refuse_unit_less_rewrites(document, findings):


















    unit_ids = {unit.id for unit in document.units}
    refusals = []
    for finding in findings:
        if not finding.rewrite or finding.unit in unit_ids:
            continue
        refusals.append(
            f"the verdicts file carries a rewrite for {finding.fid} ({finding.rule}), "
            f"whose unit is {finding.unit!r} and names no unit of this document. A "
            "model rewrites only a whole unit a Finding sits in, so this "
            "rewrite was refused and the verdict alone was applied.")
        finding.rewrite = ""
    return refusals


def _joined(plan, findings):
















    by_unit_rule, by_doc_id = {}, {}
    for f in findings:
        if f.unit == "document":
            by_doc_id.setdefault(f.rule, []).append(f)
        else:
            by_unit_rule.setdefault((f.unit, f.rule), []).append(f)

    def _fold(entry, matches):
        entry = dict(entry)
        if not matches:
            return entry
        chosen = next((f for f in matches if f.verdict == "FIRE"), None)
        if chosen is None:
            chosen = next((f for f in matches if f.verdict == "pass"), None)
        if chosen is None:
            chosen = matches[0]
        if chosen.verdict != "candidate":
            entry["verdict"] = chosen.verdict
            entry["exception"] = chosen.exception
        return entry

    per_unit = {}
    for unit_id, slot in plan.per_unit.items():
        per_unit[unit_id] = selfcheck.Slot(
            asked=[_fold(entry, by_unit_rule.get((unit_id, entry.get("rule")), []))
                   for entry in slot.asked],
            unasked=list(slot.unasked))
    per_document = [_fold(entry, by_doc_id.get(entry.get("id"), []))
                    for entry in plan.per_document]
    return selfcheck.Plan(per_unit=per_unit, per_document=per_document)






def _atomic_write(path, text, encoding):








    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
                                    suffix=_TEMP_SUFFIX)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def _retire_verdicts(path, copy=None):




















    source = pathlib.Path(str(path) + reconcile.VERDICTS_SUFFIX)
    if not source.exists():
        return None, None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = pathlib.Path(f"{path}{VERDICTS_APPLIED_STEM}{stamp}.json")
    try:
        os.replace(source, target)
    except OSError as exc:
        return None, (f"the spent verdicts file could not be moved aside: "
                      f"{type(exc).__name__}: {exc}. Delete or rename it before the "
                      "next run, or that run will refuse it as stale.")
    if copy is not None:
        return target, (f"the verdicts file was spent by this run on the "
                        f"{office.written_as(path)[0]} at "
                        f"{pathlib.Path(copy).name} and moved to {target.name}. The original "
                        "is unchanged, and a run with no verdicts file beside it is the "
                        "ordinary next state.")
    return target, (f"the verdicts file was spent by this run and moved to "
                    f"{target.name}. The artifact has changed, so those answers no "
                    "longer match its questions. A run with no verdicts file beside "
                    "the artifact is the ordinary next state.")


def _write_report(path, text):





















    try:
        return [report.write(path, text)], []
    except OSError as exc:
        line = (f"the report file could not be written beside {path}: "
                f"{type(exc).__name__}: {exc}. The report's own text is in this run's "
                "result and was printed to the session.")
        _emit(line)
        return [], [line]


def _write_brief(path, document, rulebook_name, question_digest):



















    try:
        return [second_reader_stage.write_brief(
            path, document, rulebook_name, question_digest)], []
    except OSError as exc:
        line = (f"the second reader's brief could not be written beside {path}: "
                f"{type(exc).__name__}: {exc}. The Second reader section reads on for "
                "this artifact and nothing was asked of a second reader on this run, "
                "since the brief is the only channel the question travels through.")
        _emit(line)
        return [], [line]


def _write_candidates(path, document, findings, plan, question_digest, voice_block=None):













    try:
        return [reconcile.write_candidates(path, document, findings, plan,
                                           digest=question_digest, voice=voice_block)], []
    except OSError as exc:
        line = (f"the candidates file could not be written beside {path}: "
                f"{type(exc).__name__}: {exc}. Every candidate this run raised is in "
                "the report's own Findings section, and no model can answer them until "
                "this file can be written, since a verdicts file answers the fids in "
                "it.")
        _emit(line)
        return [], [line]


def _write_back(path, document, texts, file_digest):
















































    try:
        data = path.read_bytes()
    except OSError as exc:
        return False, (f"{path} could not be read back before the write back, so no "
                       f"rewrite was applied to it: {type(exc).__name__}: {exc}. The "
                       "rewrites stay in the report.")
    if _file_digest(data) != file_digest:
        return False, (f"{path} changed on disk between extract and write back, so no "
                       "rewrite was applied to it. The rewrites stay in the report.")
    text = data.decode(document.encoding)
    if document.format == extract_code.FORMAT:
        mark = "\ufeff" if text.startswith("\ufeff") else ""
        source = text[len(mark):]
        for unit in sorted((u for u in document.units if u.id in texts),
                           key=lambda u: u.span[0], reverse=True):
            try:
                source = extract_code.emit(source, unit, texts[unit.id].replace("\r\n", "\n"))
            except ValueError as exc:
                return False, (f"{path} was not written back, because the rewrite of "
                               f"{unit.surface} cannot be written inside its delimiters: "
                               f"{exc}. The rewrites stay in the report and the file on "
                               "disk is unchanged.")
        text = mark + source
    else:
        spans = sorted(((unit.locator["start"], unit.locator["end"], texts[unit.id])
                        for unit in document.units if unit.id in texts),
                       key=lambda row: row[0], reverse=True)
        for start, end, replacement in spans:
            restored = replacement.replace("\r\n", "\n").replace("\n", document.newline)
            text = text[:start] + restored + text[end:]
    try:
        _atomic_write(path, text, document.encoding)
    except OSError as exc:
        return False, (f"{path} could not be written back: {type(exc).__name__}: "
                       f"{exc}. The rewrites stay in the report and the file on disk "
                       "is unchanged.")
    except UnicodeEncodeError as exc:
        held = ", ".join(f"U+{ord(c):04X}" for c in exc.object[exc.start:exc.end])
        return False, (f"{path} was not written back, because a rewrite holds {held}, "
                       f"which the file's encoding, {document.encoding}, cannot write. The "
                       "rewrites stay in the report and the file on disk is unchanged.")
    return True, None


def _write_side_by_side(path, document, texts, file_digest, in_place=False):
























    module = OFFICE_WRITERS[document.format]
    if in_place:
        target, _, refused = module.write_in_place(path, document, texts, file_digest)
        if target is not None:
            return target, None, refused
        if refused[0][0] is not None:
            return None, IN_PLACE_EVERY_REFUSED_LINE.format(path=path), refused
        (_, reason), = refused
        return None, IN_PLACE_REFUSED_LINE.format(path=path, reason=reason), refused
    write = module.write_markdown if document.format == "pdf" else module.write_copy
    copy, _, refused = write(path, document, texts, file_digest)
    if copy is not None:
        return copy, None, refused
    short, long = office.written_as(path)
    if refused[0][0] is not None:
        return None, (f"every rewrite this run accepted was refused by the {short} writer, so "
                      f"no {long} was written beside {path}, since it would hold the "
                      "original's text alone. The original is unchanged, and no answer was "
                      "spent."), refused
    (_, reason), = refused
    return None, (f"no {long} was written beside {path}, because {reason}. "
                  "The rewrites stay in the report, and the original is unchanged."), refused






def _route(path, settings, marker_dir, named):








    outcome = marker.route(settings, marker_dir, hookio.normalize_path(str(path.resolve())))
    if not named or outcome not in ("exclude", "no-include"):
        return outcome, None
    suffix = path.suffix.lower()
    if suffix in _PROSE_SUFFIXES:
        override = "prose"
    elif extract_code.language_of(path) is not None:
        override = "code"
    elif office.format_of(path) is not None:
        override = "pdf" if office.format_of(path) == "pdf" else "office"
    else:
        override = "other"
    return override, (f"the marker in force routes this path as {outcome}, and the run read "
                      "it because it was named directly")


def _git(args, cwd):


    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None


def _scope(path):











    named = f"named paths: {path}"
    top = _git(["rev-parse", "--show-toplevel"], path)
    if top is None:
        return f"{named}, because a git call failed", None
    if top.returncode:
        return f"{named}, because not inside a git repository", None
    default = None
    for name in DEFAULT_BRANCHES:
        found = _git(["rev-parse", "--verify", name], path)
        if found is None:
            return f"{named}, because a git call failed", None
        if found.returncode == 0:
            default = name
            break
    if default is None:
        return f"{named}, because no main or master branch", None
    head = _git(["symbolic-ref", "-q", "HEAD"], path)
    if head is None or head.returncode:
        reason = "a git call failed" if head is None else "HEAD is detached"
        return f"{named}, because {reason}", None
    base = _git(["merge-base", default, "HEAD"], path)
    if base is None or base.returncode:
        return f"{named}, because git merge-base failed", None
    tip = _git(["rev-parse", "HEAD"], path)
    if tip is None or tip.returncode:
        return f"{named}, because a git call failed", None
    if tip.stdout.strip() == base.stdout.strip():
        return named, None
    root = pathlib.Path(os.fsdecode(top.stdout.strip()))
    listed = [_git(["diff", "--name-only", "-z", os.fsdecode(base.stdout.strip())], root),
              _git(["ls-files", "--others", "--exclude-standard", "-z"], root)]
    if any(done is None or done.returncode for done in listed):
        return f"{named}, because a git call failed", None
    changed = {(root / os.fsdecode(name)).resolve()
               for done in listed for name in done.stdout.split(b"\0") if name}
    return f"working tree against {default}", changed


def _artifacts(path, settings, marker_dir):













    if not path.is_dir():
        route, note = _route(path, settings, marker_dir, named=True)
        return [(path, route, note)], f"named paths: {path}", 0
    scope, changed = _scope(path)
    rows, passed_over = [], 0
    for child in _walk(path, settings, marker_dir):
        if not child.is_file():
            continue
        if changed is not None and child.resolve() not in changed:
            continue
        route, _ = _route(child, settings, marker_dir, named=False)
        if route in ("prose", "prompt", "code", "office", "pdf"):
            rows.append((child, route, None))
        elif route == "no-include" and office.format_of(child) == "pdf":
            passed_over += 1
    return rows, scope, passed_over


def _walk(path, settings, marker_dir):




    files = []
    for folder, names, children in os.walk(path):
        names[:] = [name for name in names if name != ".git" and not marker.excludes_folder(
            settings, marker_dir, hookio.normalize_path(str((pathlib.Path(folder) / name)
                                                            .resolve())))]
        files += [pathlib.Path(folder) / name for name in children]
    return sorted(files)




_REDO = ("Run `/humanize report <path>` to regenerate the candidates file, answer it "
         "again, then run `/humanize <path>`.")





_ANSWER_FRESH = ("This run has already written a fresh candidates file beside the "
                 "artifact and rewrote nothing, so answer that file, save the answers "
                 "over the refused verdicts file, then run `/humanize <path>`.")


def _stale_reason(path, question_digest, fresh):
































    redo = _ANSWER_FRESH if fresh else _REDO
    recorded = reconcile.verdicts_digest(path)
    if recorded is None:
        return ("the verdicts file records no artifact_digest, so nothing proves its "
                "answers belong to the questions this run is asking. Copy "
                "artifact_digest from the candidates file into the verdicts file "
                "beside it. The verdicts file was refused and nothing was judged or "
                "rewritten. " + redo)
    if recorded != question_digest:



        return ("the verdicts file answers questions asked under different conditions. "
                "The digest covers the artifact's text, the rulebook file, the overlay "
                "file, the format, the protect list and, under voice mine, the voice "
                "profile file. A fid is stamped by position, so every answer would land "
                "on a different finding. The "
                f"verdicts file records {recorded} and this run's own questions hash "
                f"to {question_digest}. The verdicts file was refused and nothing was "
                "judged or rewritten. " + redo)
    return None


def _load_book(settings, plugin_root):
    name = settings["rulebook"]
    return rulebook.load(plugin_root / "references" / "rulebooks" / f"{name}.json",
                         hookio.plugin_data() / f"{name}.overlay.json")






def _run_one(path, route, note, settings, book, rulebook_source, warnings, rewrite,
             rule_bytes=(b"", b""), progress=None, root=None, baseline=None, scope=None,
             waits=False):








    if progress is None:
        progress = {"rewrites": [], "written": []}
    scope = scope or f"named paths: {path}"
    document, file_digest, readable = _extract(path, route, root)
    if note:
        document.cannot_see.append(note)




    document.cannot_see.extend(f"Configuration warning, this run ignored it: {w}"
                               for w in warnings)







    voice_note = ""
    entries = []
    profile_bytes = b""
    capped = False
    if settings["voice"] == "mine":
        profile_bytes = _profile_bytes()
        profile, profile_warnings = voice.load_profile()
        capped = profile is not None
        document.cannot_see.extend(f"Configuration warning, this run ignored it: {w}"
                                   for w in profile_warnings)
        if profile is None:
            document.cannot_see.append(voice.NO_PROFILE)
            document.cannot_see.append(voice.LEARN_HINT)
            voice_note = voice.NO_PROFILE + "\n" + voice.LEARN_HINT
        entries = voice.in_force(profile, book.name)
    voice_counts = {}
    for entry in entries:
        voice_counts[entry["kind"]] = voice_counts.get(entry["kind"], 0) + 1


    voice_counts["older_only"] = sum(1 for entry in entries if entry.get("recent") is False)
    handler = _handler_name(route, path)
    written = []




    in_place = route == "office" and settings["office_write"] == office.IN_PLACE



    if in_place and document.format == "xlsx":
        document.cannot_see[:] = [line for line in document.cannot_see
                                  if line not in extract_xlsx.COPY_LINES]

    resolution = second_reader_stage.resolve(settings, document)

    if not readable:
        findings = []
        plan = selfcheck.Plan(per_unit={}, per_document=[])
        outcome = reconcile.Result(findings=[], missing=[], unknown=[], accepted=[], reverted=[])



        if resolution.on:
            document.cannot_see.append(
                "the second reader resolved on for this artifact and no brief was "
                "written for it, since nothing in the file was read")

        def finish_unread(settled=None):
            context = report.Context(
                document=document, findings=findings, plan=plan, density=([], "light"),
                result=outcome, rulebook=book, rulebook_source=rulebook_source,
                settings=settings, overlay_changes=book.overlay_changes,
                scope=scope, handler=handler, left=[],
                second_reader=resolution, fidelity={},
                validation=settled.states if settled is not None else None,
                voice_note=voice_note, voice_counts=voice_counts)
            text = report.render(context)
            paths, failures = _write_report(path, text)
            written.extend(paths)
            return Result(text=text, findings=[], blocks=[], warns=[], fixed=set(),
                          rewrites=[], reverted=[],
                          cannot_see=list(document.cannot_see) + failures,
                          written=written, code=0, path=str(path))

        if waits:
            return _Pending(path=path, finish=finish_unread, progress=progress)
        return _deferred(baseline, path, finish_unread, progress)

    voice_silences = []
    if route == "code":
        findings = _code_findings(document, book, settings, root, entries, voice_silences)
    else:
        findings = _scan_all(document, book, settings, entries, voice_silences)
    density_record = density(document, findings, MARK_RULES, _vocab_rules(book))
    plan = selfcheck.plan_questions(document, findings, book,
                                    voice=voice.avoid_lines(entries, book.name))


    unit_rows = reconcile.unit_findings(plan, document, book, findings)
    findings += reconcile.document_findings(plan, book)
    if route == "prose":
        findings += _readme_note(path, document, book)
    findings += unit_rows
    records.number(findings)

    verdicts_path = pathlib.Path(str(path) + reconcile.VERDICTS_SUFFIX)
    judged = verdicts_path.exists()
    question_digest = _question_digest(file_digest, document, settings, *rule_bytes,
                                       profile_bytes)











    second_merged = False
    if resolution.on:
        second = second_reader_stage.read_findings(path, document, book, question_digest)
        if second.note:
            document.cannot_see.append(second.note)
        if second.findings:
            findings = second_reader_stage.merge(findings, second.findings)
            second_merged = True
        if not second.filled:
            paths, failures = _write_brief(path, document, book.name, question_digest)
            written.extend(paths)
            document.cannot_see.extend(failures)
            progress["written"] = list(written)






    paths, failures = _write_candidates(path, document, findings, plan, question_digest,
                                        voice.rewrite_block(entries, book.name))
    written.extend(paths)
    document.cannot_see.extend(failures)
    progress["written"] = list(written)
    candidates_written = bool(paths)

    broken = False
    refused_stage = ""
    verdicts = {}
    if judged:



        try:
            verdicts = reconcile.read_verdicts(path)
        except reconcile.VerdictsError as exc:
            broken = True
            refused_stage = REFUSED_SHAPE_STAGE
            verdicts = {}
            document.cannot_see.append(
                f"the verdicts file could not be used, so nothing was judged and "
                f"nothing was rewritten on this run: {exc}")
        else:
            stale = _stale_reason(path, question_digest, candidates_written)
            if stale:
                broken = True
                refused_stage = REFUSED_STALE_STAGE
                verdicts = {}
                document.cannot_see.append(stale)
    outcome = reconcile.apply_verdicts(findings, verdicts)
    coverage_failed = judged and not broken and bool(outcome.missing)
    code = 1 if broken or coverage_failed else 0









    held = rewrite and coverage_failed


    red = _failed(baseline)
    if red:
        code = 1
        document.cannot_see.append(BASELINE_FAILED_LINE.format(
            stages=" and ".join(red),
            details=" ".join(f"The {name} ran {getattr(baseline, name)[1]}." for name in red)))
    stage_runs = rewrite and not broken and not coverage_failed and not red



    if coverage_failed:
        document.cannot_see.append(
            f"coverage failed. {len(outcome.missing)} candidates carry no usable verdict "
            f"in the verdicts file: {', '.join(outcome.missing)}")
        if held:
            document.cannot_see.append(COVERAGE_HELD_LINE)
    if outcome.unknown:
        document.cannot_see.append(
            f"the verdicts file answers {len(outcome.unknown)} ids this run raised no "
            f"finding for: {', '.join(outcome.unknown)}")


    document.cannot_see.extend(_refuse_unit_less_rewrites(document, findings))

    fixed, reasons, standing = set(), {}, {}
    fidelity_results, refusals = {}, {}
    rewrites, reverted = [], []
    units = {unit.id: unit for unit in document.units}
    written_back = False
    written_units = []
    copied, copy_refused = None, {}
    if stage_runs:
        model_units = _model_units(findings)
        texts, fixed, applied, reasons = _substitute(document, findings, book, settings,
                                                      model_units)






        carriers, meanings, caps = {}, {}, {}
        for finding in findings:
            if finding.rewrite and finding.unit not in carriers:
                carriers[finding.unit] = (finding.fid, finding.rewrite, ())
                meanings[finding.fid] = finding.meaning
        for finding in findings:
            if finding.unit in carriers or finding.unit not in texts:
                continue
            if finding.fid in fixed:
                carriers[finding.unit] = (finding.fid, texts[finding.unit],
                                           tuple(applied.get(finding.unit, ())))
        for unit_id, (fid, new_text, names) in carriers.items():
            unit = units[unit_id]




            fidelity_results[fid] = fidelity.check(
                unit.text, new_text, applied=names, document=document, kind=unit.kind)




            if capped and unit_id in model_units:
                caps[fid] = reconcile.cap_refusal(unit.text, new_text, settings["refine_cap"])
        accepted_fids, reverted_fids = reconcile.accept(
            [fid for fid, _, _ in carriers.values()], fidelity_results, meanings, caps)
        outcome.accepted = accepted_fids
        outcome.reverted = reverted_fids
        outcome.caps = {fid: reason for fid, reason in caps.items() if reason is not None}
        by_fid = {f.fid: f for f in findings}
        for unit_id, (fid, new_text, _) in carriers.items():
            unit = units[unit_id]
            by_fid[fid].rewrite = new_text
            row = {"fid": fid, "unit": unit_id, "before": unit.text, "after": new_text}
            if fid in accepted_fids:
                standing[unit_id] = new_text
                rewrites.append(row)
                if unit_id in model_units:















                    for f in findings:
                        if f.unit == unit_id:
                            reasons[f.fid] = MODEL_REWRITE_STANDS
            else:
                check = fidelity_results[fid]
                row["lost"] = sorted(check.lost)
                row["gained"] = sorted(check.gained)


                cap = outcome.caps.get(fid)
                refusal = (reconcile.meaning_refusal(meanings[fid])
                           if fid in meanings and cap is None else None)
                if cap is not None:
                    row["cap"] = cap
                if refusal is not None:
                    row["reason"] = refusals[fid] = refusal
                reverted.append(row)


                for f in findings:
                    if f.unit == unit_id:
                        fixed.discard(f.fid)
                        if cap is not None:
                            reasons[f.fid] = f"{cap} Rewrite this unit by hand."
                            continue
                        reasons[f.fid] = MEANING_REFUSED_CHANGE if refusal is not None else (
                            "the rewrite this run produced was reverted by the fidelity "
                            "check, so the original stands. Rewrite this unit by hand.")



        written_units = [units[unit_id] for unit_id in standing]
        if standing and route in ("office", "pdf"):











            target, refusal, refused = _write_side_by_side(path, document, standing,
                                                           file_digest, in_place)





            whole = bool(refused) and refused[0][0] is None
            if whole:
                (_, reason), = refused
                refused = [(unit_id, reason) for unit_id in standing]
            for unit_id, reason in refused:
                row = next(r for r in rewrites if r["unit"] == unit_id)
                rewrites.remove(row)
                reverted.append(dict(row, reason=reason))
                outcome.accepted = [fid for fid in outcome.accepted if fid != row["fid"]]
                outcome.reverted = list(outcome.reverted) + [row["fid"]]
                copy_refused[row["fid"]] = reason
                if not whole:
                    document.cannot_see.append(f"the rewrite of {units[unit_id].surface} was "
                                               f"left for the human: {reason}")
                for f in findings:
                    if f.unit == unit_id:
                        fixed.discard(f.fid)
                        reasons[f.fid] = f"{reason}."
            if target is None:
                document.cannot_see.append(refusal)
            elif in_place:
                written_back = True
                written.append(path)
                progress["rewrites"] = list(rewrites)
                progress["written"] = list(written)
            else:
                copied = target
                progress["copied"] = copied
                written.append(copied)
                progress["rewrites"] = list(rewrites)
                progress["written"] = list(written)


                if settings["office_write"] == office.IN_PLACE:
                    document.cannot_see.append(PDF_NEVER_IN_PLACE_LINE)
        elif standing:
            written_back, refusal = _write_back(path, document, standing, file_digest)
            if written_back:
                progress["wrote_back"] = (document.original_bytes, written_units)





                written.append(path)
                progress["rewrites"] = list(rewrites)
                progress["written"] = list(written)
            else:
                document.cannot_see.append(refusal)










    if stage_runs:
        off_line = None
    elif held:
        off_line = COVERAGE_HELD_CHANGE
    elif red:
        off_line = BASELINE_FAILED_CHANGE.format(stages=" and ".join(red))
    else:
        off_line = REWRITE_OFF_CHANGE



    if held:
        skipped = COVERAGE_HELD_STAGE
    elif rewrite and broken:
        skipped = refused_stage
    elif red:
        skipped = BASELINE_FAILED_STAGE.format(stages=" and ".join(red))
    else:
        skipped = ""

    def finish(settled=None):




        if waits and settled.code_failed:
            document.cannot_see.append(_code_failed_line(route, path, *settled.code_failed,
                                                         in_place))
        failed = settled.failed if settled is not None else ()
        reverted_after = ""
        final_code = code
        if written_back and failed:
            final_code = 1
            stages = " and ".join(failed)
            if settled.reverted:
                reverted_after = stages


                written.remove(path)
                progress["rewrites"] = []
                progress["written"] = list(written)
                document.cannot_see.append(
                    VALIDATION_REVERTED_LINE.format(stages=stages, path=path))
                for f in findings:
                    if f.unit in standing:
                        fixed.discard(f.fid)
                        reasons[f.fid] = VALIDATION_REVERTED_CHANGE.format(stages=stages)
            else:
                document.cannot_see.append(REVERT_FAILED_LINE.format(stages=stages, path=path))
        elif written_back or copied is not None:


            retired, retire_note = _retire_verdicts(path, copied)
            if retire_note:
                document.cannot_see.append(retire_note)
            if retired is not None:
                written.append(retired)
                progress["written"] = list(written)






            if second_merged:
                spent, brief_note = second_reader_stage.retire_brief(path, copied)

                if brief_note:
                    document.cannot_see.append(brief_note)
                if spent is not None:
                    written.append(spent)
                    progress["written"] = list(written)














            if candidates_written and copied is not None:
                document.cannot_see.append(COPY_CANDIDATES_LINE.format(
                    kind=office.written_as(path)[0], copy=copied))
            elif candidates_written:
                document.cannot_see.append(
                    "the candidates file beside this artifact was written before the "
                    "rewrite stage ran, so its questions belong to the text this run "
                    "replaced and its recorded digest can never match again. " + _REDO)



        if reverted_after:
            state = "reverted after the write back"
        elif copied is not None:
            state = f"in the {office.written_as(path)[0]} at {copied}"
        else:
            state = "after" if written_back else "proposed and never applied"
        for row in rewrites:
            _print_diff(path, units[row["unit"]].surface, row["before"], row["after"], state)




        paired = report.second_reader_pairs(findings)
        shown = [f for f in findings if id(f) not in paired]
        left = _left_rows(document, shown, {} if reverted_after else standing, fixed,
                          reasons, off_line)
        context = report.Context(
            document=document, findings=findings, plan=_joined(plan, shown),
            density=density_record, result=outcome, rulebook=book,
            rulebook_source=rulebook_source, settings=settings,
            overlay_changes=book.overlay_changes, scope=scope,
            handler=handler, left=left, second_reader=resolution,
            fidelity=fidelity_results, refusals=refusals, rewrite_skipped=skipped,
            copy_refused=copy_refused,
            validation=settled.states if settled is not None else None,
            reverted_after=reverted_after, voice_note=voice_note,
            voice_counts=voice_counts, voice_silences=voice_silences)
        text = report.render(context)
        paths, failures = _write_report(path, text)
        written.extend(paths)
        progress["written"] = list(written)
        undone = [dict(row, validation=f"{reverted_after} failed after the write back")
                  for row in rewrites] if reverted_after else []




        return Result(
            text=text, findings=findings,
            blocks=[f for f in shown if f.tier == "block"],
            warns=[f for f in shown if f.tier in ("warn", "warn-with-company")],
            fixed=fixed, rewrites=[] if reverted_after else rewrites,
            reverted=reverted + undone, cannot_see=list(document.cannot_see) + failures,
            written=written, code=final_code, path=str(path), left=left)

    if waits:
        return _Pending(path=path, finish=finish, progress=progress)
    return _deferred(baseline, path, finish, progress, written_back,
                     document.original_bytes, written_units if written_back else [])


def _guarded_run_one(path, route, note, settings, book, rulebook_source, warnings, rewrite,
                     rule_bytes=(b"", b""), root=None, baseline=None, scope=None, waits=False):























    progress = {"rewrites": [], "written": []}
    try:
        return _run_one(path, route, note, settings, book, rulebook_source, warnings,
                        rewrite, rule_bytes, progress, root, baseline, scope, waits)
    except Exception as exc:
        if baseline is not None and "wrote_back" in progress:
            return _raised_pending(path, progress, exc)
        return _raised(path, progress, exc)


def _raised_pending(path, progress, exc):



    original_bytes, units = progress["wrote_back"]

    def finish(settled):
        if settled.failed and settled.reverted:
            progress["rewrites"] = []
            progress["written"] = [written for written in progress["written"]
                                   if written != path]
        return _raised(path, progress, exc)

    return _Pending(path=path, finish=finish, progress=progress, wrote=True,
                    original_bytes=original_bytes, units=list(units))


def _raised(path, progress, exc):



    line = (f"the run raised on this artifact and the rest of the run continued: "
            f"{type(exc).__name__}: {exc}. No report file was written for it.")
    if progress["rewrites"] and progress.get("copied") is not None:
        line += (f" {len(progress['rewrites'])} rewrites had already been written to the "
                 f"{office.written_as(path)[1]} at {progress['copied']}, and the artifact "
                 "itself is unchanged.")
    elif progress["rewrites"]:
        line += (f" {len(progress['rewrites'])} rewrites had already been written "
                 "back to the artifact and stand in the file on disk.")
    _emit(line)
    return Result(text="", findings=[], blocks=[], warns=[], fixed=set(),
                  rewrites=list(progress["rewrites"]), reverted=[], cannot_see=[line],
                  written=list(progress["written"]), code=1, path=str(path))






def _deferred(baseline, path, finish, progress, wrote=False, original_bytes=b"", units=()):


    if baseline is None:
        return finish()
    return _Pending(path=path, finish=finish, progress=progress, wrote=wrote,
                    original_bytes=original_bytes, units=list(units))


def _failed(validation):

    if validation is None:
        return ()
    return tuple(name for name in _STAGES if getattr(validation, name)[0] == validate.FAIL)


def _validation_states(baseline, after, reverted, mentions):









    states = []
    for name in _STAGES:
        state, scope = getattr(baseline if after is None else after, name)
        if state == validate.FAIL:
            if after is None:
                scope = "before any rewrite"
            elif reverted:
                state = validate.REVERTED
        if name == "tests" and mentions:
            scope += ", tests mention: " + ", ".join(mentions)
        states.append((state, scope))
    return tuple(states)


def _code_failed_line(route, path, stages, when, in_place=False):





    if route in ("office", "pdf") and not in_place:
        return CODE_VALIDATION_FAILED_COPY_LINE.format(stages=stages, when=when,
                                                       long=office.written_as(path)[1])
    return CODE_VALIDATION_FAILED_LINE.format(stages=stages, when=when)


def _settle(results, baseline, groups, roots):














    pending = [r for r in results if isinstance(r, _Pending)]
    wrote = [p for p in pending if p.wrote]
    after = validate.run_roots(groups) if wrote else None
    failed = _failed(after)
    back = {id(p): validate.revert(p.path, p.original_bytes) for p in wrote} if failed else {}
    texts = {}
    for p in pending:
        if p.units and roots[p.path] not in texts:
            texts[roots[p.path]] = validate.test_texts(roots[p.path])
    red = _failed(baseline)
    code_failed = ()
    if red or failed:
        code_failed = (" and ".join(red or failed),
                       "before any rewrite" if red else "after the write back")
    settled = []
    for result in results:
        if isinstance(result, _Pending):
            root = roots[result.path]
            mentions = [unit.surface for unit in
                        validate.referenced(root, result.units, texts.get(root, []))]
            reverted = back.get(id(result), all(back.values()))
            outcome = _Settled(
                states=_validation_states(baseline, after, reverted, mentions),
                failed=failed if result.wrote else (), reverted=back.get(id(result), False),
                code_failed=code_failed)
            try:
                result = result.finish(outcome)
            except Exception as exc:
                result = _raised(result.path, result.progress, exc)
        settled.append(result)
    return settled


def _left_rows(document, findings, texts, fixed, reasons, off_line):










    units = {unit.id: unit for unit in document.units}
    rows = []
    for finding in findings:
        if finding.fid in fixed:
            continue
        if finding.tier not in LEFT_TIERS and finding.verdict != "FIRE":
            continue
        unit = units.get(finding.unit)
        current = texts.get(finding.unit, unit.text if unit else "")
        rows.append({
            "fid": finding.fid, "rule": finding.rule, "unit": finding.unit,
            "change": _change_line(finding, current, reasons, off_line),
            "risk": (finding.risk.strip() if finding.verdict == "FIRE" and not finding.rewrite
                     and finding.risk.strip() else RISK_UNSUPPLIED),
        })
    return rows


def _change_line(finding, unit_text, reasons, off_line):
    if finding.fid in reasons:
        return reasons[finding.fid]
    suggestion = fixes.suggest(finding, unit_text)
    if suggestion["kind"] == "change":
        return suggestion["text"]
    if off_line is not None:
        return off_line
    return "rewrite this unit by hand."






def run(path, rewrite=True, rulebook_name=None, second_reader=None, office_write=None):
















    path = pathlib.Path(path)
    base = path if path.is_dir() else path.parent
    marker_path = marker.find_marker(base.resolve())
    settings, warnings = marker.load_marker(marker_path)
    if marker_path is None:
        marker_dir = base.resolve()
        rulebook_source = NO_MARKER_SOURCE
    else:
        marker_dir = marker_path.parent
        rulebook_source = f"the marker at {marker_path}"
    if rulebook_name is not None:
        settings["rulebook"] = rulebook_name
    if second_reader is not None:
        settings["second_reader"] = second_reader
    if office_write is not None:
        settings["office_write"] = office_write

    plugin_root = hookio.plugin_root()
    book = _load_book(settings, plugin_root)


    rule_bytes = _rule_bytes(settings, plugin_root)
    warnings = list(warnings) + [f"rulebook: {w}" for w in book.warnings]







    top = validate.root_of(path, marker_path)
    rows, scope, passed_over = _artifacts(path, settings, marker_dir)
    roots = {target: validate.package_root(target, top) for target, _, _ in rows}
    grouped = {}
    for target, route, _ in rows:
        if route == "code":
            grouped.setdefault(roots[target], []).append(target)
    groups = [(root.relative_to(top).as_posix(), root, files)
              for root, files in grouped.items()]




    baseline = None
    if rewrite and groups:
        baseline = validate.run_roots(groups)
    results = [_guarded_run_one(target, route, note, settings, book, rulebook_source,
                                 warnings, rewrite, rule_bytes, roots[target],
                                 baseline if route == "code" else None, scope,
                                 waits=baseline is not None and route != "code")
               for target, route, note in rows]
    if baseline is not None:
        results = _settle(results, baseline, groups, roots)



    passed = ""
    if passed_over:
        passed = PDF_PASSED_OVER.format(count=passed_over,
                                        files="file" if passed_over == 1 else "files")
    if path.is_dir() and not results:
        _emit(f"humanize: 0 artifacts, scope: {scope}{passed}.")
    elif path.is_dir():
        _emit(f"humanize: {len(results)} artifacts, "
              f"{sum(len(r.written) for r in results)} files written, "
              f"{sum(len(r.findings) for r in results)} findings, "
              f"{sum(len(r.rewrites) for r in results)} rewrites applied{passed}.")
    return results


def run_retro(draft, final, task=None, until_text=None):





    draft = pathlib.Path(draft)
    settings, warnings = marker.load_marker(marker.find_marker(draft.resolve().parent))
    plugin_root = hookio.plugin_root()
    book = _load_book(settings, plugin_root)
    shipped, overlay = _rule_bytes(settings, plugin_root)
    result = retro.run(draft, final, task=task, until_text=until_text,
                       voice_setting=settings["voice"], book=book, rulebook_bytes=shipped,
                       overlay_bytes=overlay,
                       warnings=list(warnings) + [f"rulebook: {w}" for w in book.warnings])
    _emit(result.text)
    return result


def run_state(kind, entry):




    book = _load_book({"rulebook": "general"}, hookio.plugin_root())
    result = retro.state(kind, entry, book=book, general=book,
                         warnings=[f"rulebook: {line}" for line in book.warnings])
    _emit(result.text)
    return result


def run_learn(folder, recent=(), until_text=None):




    settings = {"rulebook": "general"}
    plugin_root = hookio.plugin_root()
    book = _load_book(settings, plugin_root)
    shipped, overlay = _rule_bytes(settings, plugin_root)
    result = learn.run(folder, recent=recent, until_text=until_text, book=book,
                       rulebook_bytes=shipped, overlay_bytes=overlay,
                       warnings=[f"rulebook: {line}" for line in book.warnings])
    _emit(result.text)
    return result


def main(argv=None):










    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:2] == ["retro", "state"]:
        parser = argparse.ArgumentParser(prog="humanize.py retro state")
        parser.add_argument("kind", choices=voice.KINDS)
        parser.add_argument("entry", nargs="+")
        args = parser.parse_args(argv[2:])
        entry = " ".join(args.entry)
        if not entry.strip():
            parser.error("the entry holds no text")
        return run_state(args.kind, entry).code
    if argv and argv[0] == "retro":
        parser = argparse.ArgumentParser(prog="humanize.py retro")
        parser.add_argument("draft")
        parser.add_argument("final")
        parser.add_argument("--task")
        parser.add_argument("--until")
        args = parser.parse_args(argv[1:])
        return run_retro(args.draft, args.final, task=args.task, until_text=args.until).code
    if argv and argv[0] == "learn":
        parser = argparse.ArgumentParser(prog="humanize.py learn")
        parser.add_argument("folder")
        parser.add_argument("--recent", nargs="+", action="extend", default=[], metavar="NAME")
        parser.add_argument("--until")
        args = parser.parse_args(argv[1:])
        return run_learn(args.folder, recent=tuple(args.recent), until_text=args.until).code
    rewrite = True
    if argv and argv[0] == "run":
        argv = argv[1:]
    elif argv and argv[0] == "report":
        rewrite = False
        argv = argv[1:]

    parser = argparse.ArgumentParser(prog="humanize.py")
    parser.add_argument("path")
    parser.add_argument("--rulebook", choices=marker.RULEBOOKS)
    parser.add_argument("--second-reader", choices=("on", "off", "auto"))
    parser.add_argument("--office-write", choices=office.OFFICE_WRITES)
    args = parser.parse_args(argv)

    results = run(args.path, rewrite=rewrite, rulebook_name=args.rulebook,
                  second_reader=args.second_reader, office_write=args.office_write)
    for result in results:
        _emit(result.text)
    return max([result.code for result in results], default=0)


if __name__ == "__main__":
    sys.exit(main())
