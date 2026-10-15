



























import functools
import pathlib
import re
from dataclasses import dataclass, field

from scripts import fidelity, marker, office
from scripts.voice import NO_PROFILE, PROFILE_KINDS, TAKEN_FROM_C018

SECTIONS = ("What ran", "Configuration in force", "Findings", "Self-check", "Density",
            "Rewrites applied", "Left for the human", "Cannot see", "Not applicable",
            "Validation", "Limits")
REPORT_SUFFIX = ".humanize-report.md"

DISCLAIMER = (
    "This run covered visible prose defects, chat wrappers, repetition, house style and "
    "protected-token comparison. It does not claim to have verified every fact. It flags "
    "a claim that cannot be true on its face, and it never checks a claim against a source."
)














CONDUCT_LINES = (
    "It never claims authorship of the text, and it never says the output is undetectable "
    "or proves human authorship.",
    "It never scores the artifact. It reports findings and leaves the judgment to the "
    "reader.",
    "It never infers who or what wrote the input.",
    "It never invents a fact to make a rewrite work. Specificity comes from a source, "
    "a valid derivation or the author.",
)





_LIMITS_ROWS = (
    "Managed settings can block plugin hooks entirely through `allowManagedHooksOnly`.",
    "`disableAllHooks` turns every hook off.",
    "Whether workspace trust holds plugin hooks back is undocumented. An interactive "
    "session holds settings-file hooks back until the trust dialog is accepted, and a "
    "`-p` or SDK session treats the folder as trusted.",
    "A timed-out hook's output is discarded, so the fail-open notice cannot cover a "
    "timeout.",
    "The inline gate sees Write and Edit calls only. A shell write is never scanned, and "
    "the FileChanged event cannot block it.",
    "A model can run `marker.py` itself, so the marker guard is a speed bump. This report "
    "prints the marker's state on every run.",
    "Hook scripts run with the user's full permissions.",
    "Hook output is capped at 10,000 characters, and output over the cap goes to a file "
    "with a preview.",
    "Under `strict`, a file written before the plugin was turned on refuses every "
    "Edit until a post-hoc run cleans it.",
    "The tests mention in the Validation scope is a literal substring search of the test "
    "files for each edited unit's text, so a short unit can match by accident.",
    "A file a project's prettier ignores is never checked, and the formatter stage reads "
    "pass for it, as the project's own check would.",
    "Under CI=1, which the validation stage sets for npm test, a jest run that needs a new "
    "snapshot fails, so such a package reads fail before any rewrite.",
    "A class list passed through a member call on a helper object, an array, or a cva variant "
    "value is read as a prose string, since C145 catches the bare clsx, cn, classNames and "
    "cva calls alone.",
)

_UNINSTALL_LINE = (
    "The voice profile and the ledger live at `~/.claude/super-humanizer/` and survive an "
    "uninstall. The rulebook overlay and the refusal state live in the plugin's data "
    "folder, `${CLAUDE_PLUGIN_DATA}`, and do not survive one."
)



_DENSITY_SENTENCES = (
    "Bands describe coverage. They never pick rewrite scope.",
    "The band numbers were first measured on slide decks and stay provisional on markdown.",
)





OFFICE_BAND_SENTENCE = ("The band numbers were first measured on slide decks and stay "
                        "provisional on this format.")

_VALIDATION_TEXT = (
    "not applicable (no code run). The formatter and the test suite run around a code "
    "run's write back."
)



MEANING_REFUSED = "A rewrite is accepted only when its verdicts row's meaning line reads kept."



_NOT_VALIDATED = ("not run", "the rewrite stage was off on this run, so nothing was written "
                  "back")












@functools.cache
def _heading_re(headings):
    return re.compile(
        r"^## (" + "|".join(re.escape(h) for h in headings) + r")[ \t]*$", re.MULTILINE)


@dataclass
class Context:



    document: object
    findings: list
    plan: object


    density: tuple
    result: object


    rulebook: object
    rulebook_source: str
    settings: dict
    overlay_changes: list
    scope: str
    handler: str

    left: list
    second_reader: object = None





    fidelity: dict = field(default_factory=dict)






    rewrite_skipped: str = ""




    validation: tuple | None = None



    reverted_after: str = ""


    refusals: dict = field(default_factory=dict)



    copy_refused: dict = field(default_factory=dict)



    voice_note: str = ""




    voice_counts: dict = field(default_factory=dict)





    voice_silences: list = field(default_factory=list)





def _quote(text):











    lines = re.split(r"\r\n|\r|\n", text)
    return "\n".join(("> " + line) if line else ">" for line in lines)


def _inline(text):


























    if text is None:
        return ""
    return str(text).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _neutralize_headings(text, headings=SECTIONS):


































    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _heading_re(tuple(headings)).sub(lambda m: "\\" + m.group(0), text)


def _class_of(finding, book):











    rule = book.rules.get(finding.rule)
    if rule is None and "-" in finding.rule:
        rule = book.rules.get(finding.rule.split("-", 1)[0])
    if rule is not None:
        return rule.rule_class
    if finding.rule == "mine" or finding.rule.startswith("mine-"):
        return "voice profile"
    return "unclassified"


def _unasked_by_unit(plan):



    return {unit_id: list(slot.unasked)
            for unit_id, slot in plan.per_unit.items() if slot.unasked}


def _voice_layers(context):







    counts = [(kind, context.voice_counts.get(kind, 0)) for kind in PROFILE_KINDS]
    counts = [(kind, count) for kind, count in counts if count]
    total = sum(count for _, count in counts)
    noun = "entry" if total == 1 else "entries"
    tail = f", {total} {noun} in force"
    if counts:
        tail += ": " + ", ".join(f"{kind} {count}" for kind, count in counts)
    if context.rulebook.name != "general":
        tail += f", silences and licences off under {context.rulebook.name}"
    return tail


def _what_ran(context):
    lines = [f"Rulebook: {context.rulebook.name} ({context.rulebook_source})."]

    voice = context.settings.get("voice", False)
    if not voice:
        lines.append("Voice: off.")
    elif context.voice_note.startswith(NO_PROFILE):
        hint = context.voice_note[len(NO_PROFILE):].strip()
        lines.append(f"Voice: on ({voice}), no profile learned yet." + (f" {hint}" if hint else ""))
    else:
        older = context.voice_counts.get("older_only", 0)
        tail = f", {older} resting on older documents alone" if older else ""
        lines.append(f"Voice: on ({voice}){_voice_layers(context)}{tail}.")

    resolution = context.second_reader
    if resolution is None:
        second = context.settings.get("second_reader", "auto")
        lines.append(
            f"Second reader: the marker's second_reader key reads {second!r}, and this "
            "run's caller resolved nothing, so this line prints the setting alone. "
            "A setting of 'auto' resolves on for pptx, xlsx and docx and for a "
            "document past the page-length threshold, and off otherwise.")
    else:
        state = "on" if resolution.on else "off"
        lines.append(f"Second reader: {state}, because {resolution.rule}.")

    if context.rewrite_skipped:
        lines.append(f"Rewrite stage: skipped, because {context.rewrite_skipped}.")

    lines.append(f"Scope: {context.scope}.")

    if context.overlay_changes:
        lines.append("The overlay changed:")
        lines.extend(f"- {row}" for row in _overlay_lines(context.overlay_changes))
    else:
        lines.append("No rule was changed by an overlay.")

    return "\n".join(lines)


def _overlay_lines(overlay_changes):
    lines = []
    for row in overlay_changes:
        rid, field, old, new = row
        if field == "patterns":
            lines.append(f"{rid} patterns changed from the shipped set.")
        else:
            lines.append(f"{rid} {field}: {old!r} to {new!r}.")
    return lines


def _configuration(context):
    lines = []
    protect = context.settings.get("protect", [])
    lines.append("Protect list:")
    if protect:
        lines.extend(f"- {entry!r}" for entry in protect)
    else:
        lines.append("- none.")

    diffs = []
    for key in marker.DEFAULTS:
        default = marker.DEFAULTS[key]
        current = context.settings.get(key, default)
        if current != default:
            diffs.append(f"- {key}: default {default!r}, in force {current!r}.")
    lines.append("Marker keys that differ from the shipped defaults:")
    lines.extend(diffs if diffs else ["- none."])

    lines.append("Rulebook fields the overlay changed:")
    if context.overlay_changes:
        lines.extend(f"- {row}" for row in _overlay_lines(context.overlay_changes))
    else:
        lines.append("- none.")

    return "\n".join(lines)


def second_reader_pairs(findings):
















    main = {}
    for f in findings:
        if not f.second_reader:
            main.setdefault((f.rule, f.unit), []).append(f)
    pairs = {}
    for f in findings:
        if not f.second_reader:
            continue
        rows = main.get((f.rule, f.unit), [])
        partner = next((m for m in rows if m.span == f.span), None)
        if partner is None:
            partner = next((m for m in rows if m.span is None or f.span is None), None)
        if partner is not None:
            pairs[id(f)] = partner
    return pairs


def _pair_line(second, main):







    if second.verdict == main.verdict:
        return (f"- {second.rule} (unit {second.unit}), the second reader agrees: "
                f"{second.verdict}.")
    if main.verdict == "candidate":
        main_says = "the main judge has no verdict yet"
    else:
        main_says = f"the main judge says {main.verdict}"
    return (f"- {second.rule} (unit {second.unit}), the second reader disagrees: it says "
            f"{second.verdict} where {main_says}.")


def _findings(context):



























    pairs = second_reader_pairs(context.findings)
    counted = [f for f in context.findings if id(f) not in pairs]
    total = len(counted)
    span_findings = [f for f in counted if f.span is not None]
    span_total = len(span_findings)
    distinct_spans = len({(f.unit, f.span) for f in span_findings})
    doc_scoped = total - span_total

    lines = [f"{total} findings in all."]
    lines.append(f"{span_total} findings over {distinct_spans} spans.")
    lines.append("Overlapping flags on one span count as one finding, "
                 "against the raw ledger's one row per hit.")
    if doc_scoped:
        lines.append(f"{doc_scoped} of them carry no single span and are scoped "
                     "to the whole document.")
    if pairs:
        lines.append(f"{len(pairs)} second reader rows stand beside a main judge row and "
                     "count as that row's finding.")

    if not context.findings:
        lines.append("None were raised on this document.")
        return "\n".join(lines)

    grouped = {}
    for f in context.findings:
        grouped.setdefault(_class_of(f, context.rulebook), []).append(f)

    for cls in sorted(grouped):
        lines.append(f"Class: {cls}")
        for f in grouped[cls]:
            main = pairs.get(id(f))
            if main is not None:
                lines.append(_pair_line(f, main))
                continue
            row = f"- {f.rule} (unit {f.unit}"
            row += f", span {f.span})" if f.span is not None else ")"
            row += f", verdict {f.verdict}"
            if f.category:
                row += f", category {_inline(f.category)}"
            if f.twin:
                row += f', twin "{_inline(f.twin)}"'
            if f.second_reader:
                row += ", raised by the second reader"
            row += "."
            if f.tier == "metric" and f.fix:
                row += f" {_inline(f.fix.get('text', ''))}."
            lines.append(row)

    return "\n".join(lines)


def _self_check(context):
    lines = []
    plan = context.plan
    unasked = _unasked_by_unit(plan)
    any_content = False

    for unit_id, slot in plan.per_unit.items():
        if not slot.asked and unit_id not in unasked:
            continue
        any_content = True
        lines.append(f"Unit {unit_id}:")
        for entry in slot.asked:
            lines.append("- " + _self_check_line(entry, context.rulebook))
        if unit_id in unasked:
            lines.append("- Not asked, the five-per-unit cap held these back this run: "
                         + ", ".join(unasked[unit_id]) + ".")

    if plan.per_document:
        any_content = True
        lines.append("Document:")
        for entry in plan.per_document:
            lines.append("- " + _self_check_line(entry, context.rulebook))

    if not any_content:
        lines.append("None. No self-check question was eligible on this document.")

    return "\n".join(lines)


def _self_check_line(entry, book):























    verdict = entry.get("verdict") or "no verdict"
    question = _inline(entry.get("question", ""))
    line = f"{entry.get('id', '')} ({verdict})"
    if question:
        line += f': "{question}"'
    exception_id = entry.get("exception")
    if verdict == "pass" and exception_id:
        pass_line = book.exceptions.get(exception_id, {}).get("pass_line", "")
        line += f", resting on exception {_inline(exception_id)}: {_inline(pass_line)}"
    return line + "."


def _density(context):
    records_list, band = context.density
    ids = {unit.id for unit in context.document.units}
    lines = []
    if not records_list:
        lines.append("None. This document carries no weighing unit.")
    else:
        for r in records_list:
            state = "dense" if r.dense else "not dense"


            name = f"Unit {r.unit}" if r.unit in ids else r.unit
            lines.append(f"- {name}: marks {r.marks}, vocab {r.vocab}, {state}.")
    lines.extend(f'Voice silence: {rule} by the {kind} entry "{_inline(entry)}", so '
                 + ("its warns are left out." if rule in TAKEN_FROM_C018
                    else "the counts above leave its hits out.")
                 for rule, entry, kind in context.voice_silences)
    lines.append(f"Document band: {band}.")
    lines.append(_DENSITY_SENTENCES[0])
    lines.append(OFFICE_BAND_SENTENCE if context.document.format in office.FORMATS
                 else _DENSITY_SENTENCES[1])
    return "\n".join(lines)


def _rewrites_applied(context):

















    units_by_id = {u.id: u for u in context.document.units}
    accepted = set(getattr(context.result, "accepted", None) or [])
    reverted = set(getattr(context.result, "reverted", None) or [])

    rewritten = {}
    for f in context.findings:
        if f.rewrite and f.unit not in rewritten:
            rewritten[f.unit] = f









    recorded = [f for f in context.findings if f.weight == "recorded"]

    lines = []
    if not rewritten and not recorded:
        lines.append("None. No unit was rewritten in this run.")
    else:
        for unit_id, f in rewritten.items():
            unit = units_by_id.get(unit_id)
            original = unit.text if unit is not None else ""
            if f.fid in (context.copy_refused or {}):
                lines.append(f"- Unit {unit_id}, proposed and never applied: "
                             f"{_inline(context.copy_refused[f.fid])}.")
                lines.append("Before:")
                lines.append(_quote(original))
                lines.append("After:")
                lines.append(_quote(f.rewrite))
            elif f.fid in accepted:
                if context.reverted_after:
                    lines.append(f"- Unit {unit_id}, reverted: {context.reverted_after} "
                                 "failed after the write back.")
                else:
                    lines.append(f"- Unit {unit_id}, accepted.")
                lines.append("Before:")
                lines.append(_quote(original))
                lines.append("After:")
                lines.append(_quote(f.rewrite))
            elif f.fid in reverted:
                lines.append(f"- Unit {unit_id}, reverted.")


                cap = (getattr(context.result, "caps", None) or {}).get(f.fid)
                if cap is not None:
                    lines.append(f"Cap: {_inline(cap)}")
                refusal = (context.refusals or {}).get(f.fid)
                if refusal is not None:
                    lines.append(f"Meaning: {_inline(refusal)}")
                    lines.append(MEANING_REFUSED)
                result = (context.fidelity or {}).get(f.fid)
                if result is None:
                    lines.append(
                        "No fidelity detail was supplied for this unit. "
                        "Context.fidelity carries no entry for this fid.")
                else:
                    if result.lost:
                        lines.append(f"Lost: {sorted(result.lost)}.")
                    if result.gained:
                        lines.append(f"Gained: {sorted(result.gained)}.")
                    if (not result.lost and not result.gained and refusal is None
                            and cap is None):







                        lines.append(
                            "The token check names nothing lost or gained. "
                            "This record does not carry the reason for the "
                            "revert.")
            else:
                lines.append(f"- Unit {unit_id}, rewrite pending reconciliation.")
        for f in recorded:
            lines.append(
                f"- Unit {f.unit}, span {f.span}: recorded at zero weight, a "
                "Finding whose weight field reads \"recorded\" instead of "
                "\"counted\". The row is meant for a span the marker's protect list "
                "masked, and nothing sets that weight yet.")

    lines.append(f"Caveat: {fidelity.CAVEAT}.")
    return "\n".join(lines)


def _left_for_human(context):














    if not context.left:
        return "None. Nothing was left for the human in this run."
    lines = []
    for item in context.left:
        fid = item.get("fid", "")
        rule = item.get("rule", "")
        unit = item.get("unit", "")
        header = " ".join(part for part in (fid, f"({rule}, unit {unit})" if rule or unit
                                             else "") if part)
        lines.append(f"- {header}" if header else "-")
        lines.append(f"Change: {_inline(item.get('change', ''))}")
        lines.append(f"Risk: {_inline(item.get('risk', ''))}")
    return "\n".join(lines)


def _cannot_see(context):
    lines = [f"Handler: {context.handler}."]
    if context.document.cannot_see:
        lines.extend(f"- {item}" for item in context.document.cannot_see)
    else:
        lines.append("- nothing named for this handler.")

    unasked = _unasked_by_unit(context.plan)
    if unasked:
        lines.append("Self-check questions the five-per-unit cap skipped:")
        for unit_id, ids in unasked.items():
            lines.append(f"- Unit {unit_id}: {', '.join(ids)}.")
    else:
        lines.append("No self-check question was skipped by the cap.")

    return "\n".join(lines)


def _not_applicable(context):
    fmt = context.document.format
    rows = []
    for rid in sorted(context.rulebook.rules):
        rule = context.rulebook.rules[rid]
        if rule.formats.get(fmt) == "off":
            rows.append(f"- {rid} {_inline(rule.name)} (off for {fmt}).")
    if not rows:
        return f"None. Every rule in {context.rulebook.name} applies to the {fmt} format."
    return "\n".join(rows)


def _validation(context):


    if context.document.format != "code prose":
        return _VALIDATION_TEXT
    formatter, tests = context.validation or (_NOT_VALIDATED, _NOT_VALIDATED)
    return "\n".join(f"{name}: {state} ({scope})"
                     for name, (state, scope) in (("formatter", formatter), ("tests", tests)))


def _limits(context):
    lines = list(_LIMITS_ROWS)
    lines.append(_UNINSTALL_LINE)
    lines.append(DISCLAIMER)
    lines.extend(CONDUCT_LINES)
    return "\n".join(lines)


_SECTION_FUNCS = {
    "What ran": _what_ran,
    "Configuration in force": _configuration,
    "Findings": _findings,
    "Self-check": _self_check,
    "Density": _density,
    "Rewrites applied": _rewrites_applied,
    "Left for the human": _left_for_human,
    "Cannot see": _cannot_see,
    "Not applicable": _not_applicable,
    "Validation": _validation,
    "Limits": _limits,
}


def render(context):









    title = _neutralize_headings(f"# Humanize report for {context.document.path}")
    parts = [title, ""]
    for heading in SECTIONS:
        body = _neutralize_headings(_SECTION_FUNCS[heading](context).rstrip())
        parts.append(f"## {heading}")
        parts.append(body if body else "None.")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def section(text, heading, headings=SECTIONS):







    matches = list(_heading_re(tuple(headings)).finditer(text))
    for i, m in enumerate(matches):
        if m.group(1) != heading:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        return text[start:end]
    return ""


def write(artifact_path, text):




    path = pathlib.Path(str(artifact_path) + REPORT_SUFFIX)
    path.write_text(text, encoding="utf-8")
    return path
