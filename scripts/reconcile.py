





































import dataclasses
import difflib
import json
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone

from scripts import selfcheck
from scripts.records import Finding

CANDIDATES_SUFFIX = ".humanize-candidates.json"
VERDICTS_SUFFIX = ".humanize-verdicts.json"

_VALID_VERDICTS = {"pass", "FIRE", "n-a"}

ROTATED_OUT_REASON = "rotated out of this unit's budget"



NO_MEANING = "no meaning line"


class VerdictsError(Exception):
    pass















class CoverageError(Exception):
    pass



@dataclass
class Result:
    findings: list
    missing: list
    unknown: list
    accepted: list
    reverted: list
    caps: dict = dataclasses.field(default_factory=dict)





def _candidates_path(artifact_path):
    return pathlib.Path(str(artifact_path) + CANDIDATES_SUFFIX)


def _verdicts_path(artifact_path):
    return pathlib.Path(str(artifact_path) + VERDICTS_SUFFIX)


def _check_fids(findings):



























    seen = set()
    for f in findings:
        if f.verdict == "candidate" and not f.fid:
            raise CoverageError(
                "a candidate Finding carries an empty fid; call records.number() first")
        if not f.fid:
            continue
        if f.fid in seen:
            raise CoverageError(f"fid {f.fid!r} is shared by more than one Finding")
        seen.add(f.fid)


def _self_check_text(finding, plan):









    if finding.unit == "document":
        entries = plan.per_document
        match = next((e for e in entries if e.get("id") == finding.rule), None)
    else:
        slot = plan.per_unit.get(finding.unit)
        match = None
        if slot is not None:
            match = next((e for e in slot.asked if e.get("rule") == finding.rule), None)
    if match is None:
        return "", "", ""
    return match.get("question", ""), match.get("pass_line", ""), match.get("fire_line", "")


def _rotated_out(finding, plan):


















    if finding.unit == "document":
        return False
    slot = plan.per_unit.get(finding.unit)
    if slot is None:
        return False
    if any(e.get("rule") == finding.rule for e in slot.asked):
        return False
    return any(uid.split("-", 1)[0] == finding.rule for uid in slot.unasked)


def verdicts_digest(artifact_path):
















    return _recorded_digest(_verdicts_path(artifact_path))


def candidates_digest(artifact_path):












    return _recorded_digest(_candidates_path(artifact_path))


def _recorded_digest(path):














    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    digest = data.get("artifact_digest")
    return digest if isinstance(digest, str) and digest else None


def write_candidates(artifact_path, document, findings, plan, digest="", voice=None):




































    unit_text = {u.id: u.text for u in document.units}
    rows = []
    unasked_rows = []
    rulebook_name = ""
    for f in findings:
        if not rulebook_name and f.rulebook:
            rulebook_name = f.rulebook
        if f.verdict != "candidate":
            continue
        if _rotated_out(f, plan):
            f.verdict = "n-a"
            f.exception = ROTATED_OUT_REASON
            unasked_rows.append({
                "fid": f.fid, "rule": f.rule, "unit": f.unit, "reason": f.exception,
            })
            continue
        question, pass_line, fire_line = _self_check_text(f, plan)
        row = {
            "fid": f.fid,
            "rule": f.rule,
            "unit": f.unit,
            "span": f.span,
            "text": unit_text.get(f.unit, ""),
            "question": question,
            "pass_line": pass_line,
            "fire_line": fire_line,
        }
        if f.rulebook == "strict":
            row["category"] = f.category
        rows.append(row)
    payload = {
        "artifact": str(artifact_path),
        "artifact_digest": digest,
        "rulebook": rulebook_name,
        "generated": datetime.now(timezone.utc).isoformat(),
        "candidates": rows,
        "unasked": unasked_rows,
    }
    if voice is not None:
        payload["voice"] = voice
    path = _candidates_path(artifact_path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def read_verdicts(artifact_path):
























    path = _verdicts_path(artifact_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise VerdictsError(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise VerdictsError(f"{path}: top-level JSON is a {type(data).__name__}, not an object")
    verdicts = data.get("verdicts", {})
    if not isinstance(verdicts, dict):
        raise VerdictsError(
            f"{path}: 'verdicts' is a {type(verdicts).__name__}, not an object")
    for fid, row in verdicts.items():
        _check_row(path, fid, row)
    return verdicts




_TEXT_FIELDS = ("verdict", "exception", "rewrite", "twin", "meaning", "risk")


def _check_row(path, fid, row):





























    if not isinstance(row, dict):
        raise VerdictsError(
            f"{path}: verdict row {fid!r} is {type(row).__name__} and not an object")
    for field in _TEXT_FIELDS:
        value = row.get(field)
        if value is not None and not isinstance(value, str):
            raise VerdictsError(
                f"{path}: verdict row {fid!r} has {field} set to "
                f"{type(value).__name__}, which is not a string or null")


def coverage(findings, verdicts):












    _check_fids(findings)
    missing = []
    for f in findings:
        if f.verdict != "candidate":
            continue
        row = verdicts.get(f.fid)
        if not row or row.get("verdict") not in _VALID_VERDICTS:
            missing.append(f.fid)
    return missing


def apply_verdicts(findings, verdicts):

















    by_fid = {f.fid: f for f in findings}
    missing = coverage(findings, verdicts)
    unknown = [fid for fid in verdicts if fid not in by_fid]
    for f in findings:
        if f.verdict != "candidate":
            continue
        row = verdicts.get(f.fid)
        if not row or row.get("verdict") not in _VALID_VERDICTS:
            continue
        f.verdict = row["verdict"]
        f.exception = row.get("exception")



        f.twin = row.get("twin") or ""
        f.rewrite = row.get("rewrite") or ""
        f.meaning = row.get("meaning") or ""
        f.risk = row.get("risk") or ""
    return Result(findings=findings, missing=missing, unknown=unknown, accepted=[], reverted=[])


def meaning_refusal(meaning):










    text = (meaning or "").strip()
    if not text:
        return NO_MEANING
    if text.lower() == "kept":
        return None
    return text


def change_share(before, after):









    before_words, after_words = before.split(), after.split()
    if not before_words:
        return 0.0
    changed = 0
    matcher = difflib.SequenceMatcher(None, before_words, after_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            changed += i2 - i1
        elif tag == "insert":
            changed += j2 - j1
    return changed / len(before_words)


def cap_refusal(before, after, cap):



    share = change_share(before, after)
    if share <= cap:
        return None
    return (f"the rewrite changes a share of {share:.3f} of the unit's words, over the refine "
            f"cap of {cap:.3f}, so the original stands.")


def accept(rewrites, fidelity_results, meanings=None, caps=None):




























    meanings = meanings or {}
    caps = caps or {}
    accepted = []
    reverted = []
    for fid in rewrites:
        if caps.get(fid) is not None or (
                fid in meanings and meaning_refusal(meanings[fid]) is not None):
            reverted.append(fid)
        elif fidelity_results.get(fid):
            accepted.append(fid)
        else:
            reverted.append(fid)
    return accepted, reverted


def document_findings(plan, book):













    findings = []
    for entry in plan.per_document:
        rule = book.rules.get(entry.get("rule", ""))
        findings.append(Finding(
            rule=entry["id"], rulebook=book.name, unit="document", span=None,
            tier="self-check", source="model", verdict="candidate",
            category=rule.category if rule else "",
        ))
    return findings


def _pattern_runs(rule, document_format, kind):


    specs = (rule.formats.get(document_format), rule.formats.get(kind))
    if "off" in specs:
        return False
    return any(all(not isinstance(spec, list) or entry.id in spec for spec in specs)
               for entry in rule.patterns)


def unit_findings(plan, document, book, findings):

























    entries = {entry["id"]: entry for entry in book.self_check.get("per_unit", [])}
    units = {unit.id: unit for unit in document.units}
    raised = {(f.unit, f.rule) for f in findings}
    out = []
    for unit_id, slot in plan.per_unit.items():
        unit = units[unit_id]
        eligible = list(slot.asked) + [entries[i] for i in slot.unasked if i in entries]
        for entry in eligible:
            rule = book.rules.get(entry.get("rule", ""))
            if rule is None or (unit_id, rule.id) in raised or selfcheck.reads_hits(entry):
                continue
            if (not selfcheck.alternatives(entry.get("generator"))
                    and _pattern_runs(rule, document.format, unit.kind)):
                continue
            raised.add((unit_id, rule.id))
            out.append(Finding(
                rule=rule.id, rulebook=book.name, unit=unit_id, span=None,
                tier="self-check", source="model", verdict="candidate",
                category=rule.category,
            ))
    return out
