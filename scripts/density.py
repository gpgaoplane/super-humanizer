





from scripts import office
from scripts.records import DensityRecord

DENSE_AT_MARKS = 3
PERVASIVE_AT_DENSE_SHARE = 0.5
SCATTERED_AT_MARKS_PER_UNIT = 1.0
PROVISIONAL = "the band numbers were first measured on slide decks and stay provisional on markdown"


def _group(document, unit):




    if document.format in office.FORMATS:
        return office.density_key(document, unit)
    return unit.id


def _notes(key):

    return isinstance(key, tuple) and key[0] == "notes"


def density(document, findings, mark_rules, vocab_rules):











    weighing = [u for u in document.units if u.weighs]
    units_by_id = {u.id: u for u in weighing}
    group_of = {u.id: _group(document, u) for u in weighing}
    groups = list(dict.fromkeys(group_of.values()))
    groups = [g for g in groups if not _notes(g)] + [g for g in groups if _notes(g)]
    marks = {g: 0 for g in groups}
    vocab = {g: set() for g in groups}
    for f in findings:
        if f.unit not in group_of:
            continue
        group = group_of[f.unit]
        if f.rule in mark_rules:
            marks[group] += 1
        elif f.rule in vocab_rules:
            if f.span is None:
                key = ("rule", f.rule)
            else:
                start, end = f.span
                key = units_by_id[f.unit].text[start:end].casefold().strip()
            vocab[group].add(key)
    records = [
        DensityRecord(unit=office.group_label(g), marks=marks[g], vocab=len(vocab[g]),
                      dense=marks[g] >= DENSE_AT_MARKS)
        for g in groups
    ]
    banded = [r for g, r in zip(groups, records) if not _notes(g)]
    if not banded:
        return records, "light"
    dense_share = sum(1 for r in banded if r.dense) / len(banded)
    per_unit = sum(r.marks for r in banded) / len(banded)
    if dense_share >= PERVASIVE_AT_DENSE_SHARE:
        band = "pervasive"
    elif per_unit >= SCATTERED_AT_MARKS_PER_UNIT:
        band = "scattered"
    else:
        band = "light"
    return records, band
