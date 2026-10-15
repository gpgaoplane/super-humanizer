
from scripts import office, protect
from scripts.records import Finding
from scripts.units import (mask_block_quotes, mask_code, mask_entities, mask_html_comment,
                            mask_link_targets, mask_quotes, mask_table_pipes, mask_table_rows,
                            mask_urls, mask_wiki_alias, sentences)

EXACT_TIERS = {"block", "warn", "density"}
CANDIDATE_TIERS = {"self-check", "warn-with-company"}




















_MASK_ORDER = ("block-quote-mask", "html-comment-mask", "markdown-table-mask",
               "markdown-table-pipe", "quote-mask", "code-mask", "url-mask", "entity-mask",
               "wiki-alias-mask", "link-target-mask")
_MASK_FUNCS = {"quote-mask": mask_quotes, "code-mask": mask_code, "url-mask": mask_urls,
               "markdown-table-pipe": mask_table_pipes, "html-comment-mask": mask_html_comment,
               "entity-mask": mask_entities, "wiki-alias-mask": mask_wiki_alias,
               "link-target-mask": mask_link_targets, "markdown-table-mask": mask_table_rows,
               "block-quote-mask": mask_block_quotes}


def _masked_text(text, cache, exceptions):





    keys = tuple(name for name in _MASK_ORDER if name in exceptions)
    if not keys:
        return text
    if keys not in cache:
        masked = text
        for name in keys:
            masked = _MASK_FUNCS[name](masked)
        cache[keys] = masked
    return cache[keys]


def _company_units(document):











    return office.company_keys(document)














def _promote_warn_with_company(findings, document):







    keys = _company_units(document)
    groups = {}
    for f in findings:
        if f.weight != "counted":
            continue
        key = keys.get(f.unit)
        if key is None:
            continue
        groups.setdefault(key, []).append(f)
    for group in groups.values():
        if len(group) < 2:
            continue
        for f in group:
            if f.tier == "warn-with-company":
                f.tier = "warn"


def _matches(entry, text):



    if "sentence" not in entry.flags:
        return [m.span() for m in entry.compiled.finditer(text)]
    return [(start + m.start(), start + m.end())
            for start, end in sentences(text)
            for m in entry.compiled.finditer(text[start:end])]


def scan(document, rulebook, protected=None):
























    findings = []
    for unit in document.units:
        if not unit.weighs:
            continue
        mask_cache = {}
        spans = protected.get(unit.id) if protected else None
        for rule in rulebook.rules.values():
            if rule.tier not in EXACT_TIERS | CANDIDATE_TIERS:
                continue
            format_spec = rule.formats.get(document.format)
            kind_spec = rule.formats.get(unit.kind)
            if "off" in (format_spec, kind_spec):
                continue
            verdict = "hit" if rule.tier in EXACT_TIERS else "candidate"
            for entry in rule.patterns:
                if isinstance(format_spec, list) and entry.id not in format_spec:
                    continue
                if isinstance(kind_spec, list) and entry.id not in kind_spec:
                    continue
                text = _masked_text(unit.text, mask_cache, entry.exceptions)
                if spans:
                    text = protect.fill(text, spans)
                for span in _matches(entry, text):
                    findings.append(Finding(
                        rule=rule.id, rulebook=rulebook.name, unit=unit.id,
                        span=span, tier=rule.tier, source="regex",
                        verdict=verdict, fix=entry.fix, category=rule.category,
                    ))
    _promote_warn_with_company(findings, document)
    return findings
