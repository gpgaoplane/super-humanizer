









import re

FILLER = "#"


def compile_patterns(entries):









    if not isinstance(entries, list):
        return [], [(entries, "not a list")]
    compiled, skipped = [], []
    for entry in entries:
        if isinstance(entry, str):
            if entry == "":
                skipped.append((entry, "empty"))
                continue
            if "\n" in entry or "\r" in entry:
                skipped.append((entry, "a literal holds a line break"))
                continue
            source = re.escape(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("regex"), str):
            source = entry["regex"]
        else:
            skipped.append((entry, "not a string or an object holding a string regex"))
            continue
        try:
            compiled.append(re.compile(source))
        except re.error as exc:
            skipped.append((entry, f"does not compile: {exc}"))
    return compiled, skipped


def apply(document, entries):







    compiled, _ = compile_patterns(entries)
    spans = []
    for unit in document.units:
        if not unit.weighs:
            continue
        for pattern in compiled:
            for m in pattern.finditer(unit.text):
                start, end = m.span()
                if start == end:
                    continue
                matched = unit.text[start:end]
                if "\n" in matched or "\r" in matched:
                    continue
                spans.append((unit.id, start, end, matched))
    return spans


def fill(text, spans):



    chars = list(text)
    for start, end in spans:
        chars[start:end] = FILLER * (end - start)
    return "".join(chars)
