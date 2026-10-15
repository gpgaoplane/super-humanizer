


import re

_CODE = re.compile(r"(`+)[^\n]*?\1(?!`)")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_ENTITY = re.compile(r"&(?:([A-Za-z][A-Za-z0-9]*)|(#[0-9]+)|(#[xX][0-9A-Fa-f]+));")






_NAMED_ENTITIES = frozenset({
    "amp", "lt", "gt", "quot", "apos", "nbsp", "ensp", "emsp", "thinsp",
    "mdash", "ndash", "minus", "hellip", "copy", "reg", "trade", "deg",
    "plusmn", "times", "divide", "frac12", "frac14", "frac34",
    "micro", "para", "sect", "middot", "bull", "dagger", "Dagger",
    "permil", "prime", "Prime", "laquo", "raquo", "lsquo", "rsquo",
    "sbquo", "ldquo", "rdquo", "bdquo", "semi",
})







_WIKI_ALIAS = re.compile(r"\[\[([^\[\]\n|]*)\|([^\[\]\n]*)\]\]")




LINK_PAREN = re.compile(r"\]\(((?:[^()\n]|\([^()\n]*\))*)\)")
_MAILTO = re.compile(r"<mailto:[^<>\n]*>")



_URL = re.compile(r"https?://[-A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%]+")
_ABBREV = {
    "approx.", "e.g.", "i.e.", "etc.", "vs.", "cf.", "fig.", "no.", "st.",
    "mr.", "mrs.", "ms.", "dr.", "prof.", "inc.", "ltd.", "co.", "jan.", "feb.",
    "mar.", "apr.", "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec.",
}
_BOUNDARY = re.compile(r'[.!?]+(?:["\')\]]+)?\s+')
_INITIAL = re.compile(r"\b[A-Z]\.$")
_DECIMAL = re.compile(r"\d\.$")
_WORD = re.compile(r"[A-Za-z0-9'’-]+")


def mask_quotes(text):














    text = text.replace('\u201c', '"').replace('\u201d', '"')
    out = []
    quoted = False
    for char in text:
        if char == '"':
            out.append(char)
            quoted = not quoted
        else:
            out.append(" " if quoted else char)
    return "".join(out)


def mask_code(text):










    def repl(m):
        run = m.group(1)
        inner = len(m.group(0)) - 2 * len(run)
        return run + " " * inner + run
    return _CODE.sub(repl, text)


def _blank_interior(m):







    run = m.group(0)
    if len(run) <= 2:
        return run
    interior = "".join(ch if ch == "\n" else " " for ch in run[1:-1])
    return run[0] + interior + run[-1]


def mask_html_comment(text):










    return _HTML_COMMENT.sub(_blank_interior, text)


def mask_entities(text):













    def repl(m):
        name = m.group(1)
        if name is not None and name not in _NAMED_ENTITIES:
            return m.group(0)
        return " " * len(m.group(0))
    return _ENTITY.sub(repl, text)


def mask_wiki_alias(text):














    def repl(m):
        target, alias = m.group(1), m.group(2)
        return "[[" + " " * len(target) + " " + alias + "]]"
    return _WIKI_ALIAS.sub(repl, text)


def mask_link_targets(text):









    def paren_repl(m):
        return "](" + " " * len(m.group(1)) + ")"
    text = LINK_PAREN.sub(paren_repl, text)
    return _MAILTO.sub(_blank_interior, text)


def mask_urls(text):











    return _URL.sub(_blank_interior, text)


def _is_delimiter_row(line):

    stripped = line.strip()
    return bool(stripped) and "|" in stripped and "-" in stripped and set(stripped) <= set("|-: ")


def _is_table_row(line):

    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


_UNESCAPED_BAR = re.compile(r"(?<!\\)\|")


def _bar_count(line):







    return len(_UNESCAPED_BAR.findall(line))


def mask_table_pipes(text):























    lines = text.split("\n")
    rows = _table_rows(lines)
    if rows is None:
        return text
    return "\n".join(
        line.replace("|", " ") if rows[i] else line
        for i, line in enumerate(lines)
    )


def mask_table_rows(text):



    lines = text.split("\n")
    rows = _table_rows(lines)
    if rows is None:
        return text
    return "\n".join(" " * len(line) if rows[i] else line for i, line in enumerate(lines))


def mask_block_quotes(text):



    return "\n".join(" " * len(line) if line.lstrip().startswith(">") else line
                     for line in text.split("\n"))


def _table_rows(lines):


    if not any(_is_delimiter_row(line) for line in lines):
        return None
    mask = [_is_table_row(line) for line in lines]
    for i, line in enumerate(lines):
        if not _is_delimiter_row(line):
            continue
        mask[i] = True
        bars = _bar_count(line)
        j = i - 1
        while j >= 0 and _bar_count(lines[j]) == bars:
            mask[j] = True
            j -= 1
        j = i + 1
        while j < len(lines) and _bar_count(lines[j]) == bars:
            mask[j] = True
            j += 1
    return mask


def _is_protected_boundary(masked, end_of_candidate):



    head = masked[:end_of_candidate]
    if _DECIMAL.search(head) or _INITIAL.search(head):
        return True
    last = head.split()[-1].lower() if head.split() else ""
    return last in _ABBREV


def sentences(text):

    masked = mask_quotes(text)
    spans, start = [], 0
    for m in _BOUNDARY.finditer(masked):
        cut = m.start() + len(m.group(0).rstrip())
        if _is_protected_boundary(masked, cut):
            continue
        if masked[start:cut].strip():
            spans.append((start, cut))
        start = m.end()
    if masked[start:].strip():
        spans.append((start, len(masked)))
    return spans


def word_count(text):

    return len(_WORD.findall(mask_quotes(text)))
