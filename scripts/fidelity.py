

















import inspect
import json
import pathlib
import re
from dataclasses import dataclass, field

from scripts import fixes
from scripts.units import mask_quotes

CAVEAT = "protected-token comparison is necessary and insufficient"

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_LEXICON_PATH = _ROOT / "references" / "lexicons.json"
_LEXICONS = json.loads(_LEXICON_PATH.read_text(encoding="utf-8"))

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))


def _word_list_pattern(words):


    ordered = sorted(words, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in ordered) + r")\b", re.I)


_HEDGE_RE = _word_list_pattern(
    _LEXICONS["hedge"] + _LEXICONS["negation"] + _LEXICONS["modal"])
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(_LEXICONS["unit"], key=len, reverse=True))
_UNIT_TAIL_RE = re.compile(r"[ \t]+(?:" + _UNIT_ALT + r")\b", re.I)

_NUMBER_CORE_RE = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?%?")

_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_MDY_RE = re.compile(
    r"\b(?:" + _MONTH_ALT + r")\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
_DATE_DMY_RE = re.compile(
    r"\b(\d{1,2})\s+(?:" + _MONTH_ALT + r")\s+(\d{4})\b", re.I)
_DATE_MONTH_RE = re.compile(r"(" + _MONTH_ALT + r")", re.I)

_CITATION_RE = re.compile(
    r"https?://\S+"
    r"|\[\^?[\w:.,\- ]{1,40}\]"
    r"|\((?:[A-Z][A-Za-z]+(?:,|\s+and\s+|\s+et al\.,?)\s*)+\d{4}\)"
)




_URL_TRAILING_PUNCT = ".,;:!?)]\"'"





IDENTIFIER = re.compile(
    r"\[\^?[^\[\]\n]{1,40}\]"
    r"|\b[A-Za-z]{1,3}\d+(?::[A-Za-z]{1,3}\d+)+\b"
    r"|\b[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)+\b"
    r"|\b(?=\w*_)\w+\b"
    r"|\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])\w+\b"
    r"|\b[A-Za-z](?=[A-Za-z0-9_]*[A-Z])[A-Za-z0-9_]*\b"
)

_CAP_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _numbers(text):
    found = set()
    for m in _NUMBER_CORE_RE.finditer(text):
        token = m.group(0)
        tail = _UNIT_TAIL_RE.match(text, m.end())
        if tail:
            token = text[m.start():tail.end()]
        found.add(token.replace(",", ""))
    return found


def _canonical_date(year, month, day):
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _date_matches(text):
    matches = list(_DATE_ISO_RE.finditer(text))
    matches += list(_DATE_MDY_RE.finditer(text))
    matches += list(_DATE_DMY_RE.finditer(text))
    return matches


def _dates(text):
    found = set()
    for m in _DATE_ISO_RE.finditer(text):
        found.add(_canonical_date(*m.groups()))
    for m in _DATE_MDY_RE.finditer(text):
        month_name = _DATE_MONTH_RE.match(m.group(0)).group(1).lower()
        found.add(_canonical_date(m.group(2), _MONTHS[month_name], m.group(1)))
    for m in _DATE_DMY_RE.finditer(text):
        month_name = _DATE_MONTH_RE.search(m.group(0)).group(1).lower()
        found.add(_canonical_date(m.group(2), _MONTHS[month_name], m.group(1)))
    return found


def _mask_dates(text):







    if not text:
        return text
    chars = list(text)
    for m in _date_matches(text):
        for i in range(m.start(), m.end()):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def _citations(text):
    found = set()
    for m in _CITATION_RE.finditer(text):
        token = m.group(0)
        if token.startswith("http"):
            token = token.rstrip(_URL_TRAILING_PUNCT)
        found.add(token)
    return found


def _hedges(text):
    return {m.group(0).lower() for m in _HEDGE_RE.finditer(text)}


def _quoted_spans(text):




    t = text.replace("“", '"').replace("”", '"')
    spans = set()
    quoted = False
    start = 0
    for i, ch in enumerate(t):
        if ch != '"':
            continue
        if quoted:
            inner = t[start:i].strip()
            if inner:
                spans.add(inner)
        else:
            start = i + 1
        quoted = not quoted
    return spans


def _has_lowercase_word(sentence):
    return any(w[0].islower() for w in _CAP_WORD_RE.findall(sentence))


def _names(text):








































    names = set()
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if not _has_lowercase_word(sentence):
            continue
        for i, m in enumerate(_CAP_WORD_RE.finditer(sentence)):
            if i == 0:
                continue
            word = m.group(0)
            if word[0].isupper() and any(c.islower() for c in word[1:]):
                names.add(word)
    names |= {m.group(0) for m in IDENTIFIER.finditer(text)}
    return names


def detect(text):

    masked = _mask_dates(text)
    return {
        "numbers": _numbers(masked),
        "dates": _dates(text),
        "names": _names(masked),
        "quotes": _quoted_spans(text),
        "citations": _citations(text),
        "hedges": _hedges(masked),
    }







_HEADING_KINDS = frozenset({"heading", "title"})


def _document_names(document):














    names = set()
    for unit in document.units:
        if unit.kind in _HEADING_KINDS:
            continue
        names |= _names(_mask_dates(unit.text))
    return names


def _capitalized_tokens(text):





    return {m.group(0) for m in _CAP_WORD_RE.finditer(text)
            if m.group(0)[0].isupper() and any(c.islower() for c in m.group(0)[1:])}


def _name_candidates(text):








    return _capitalized_tokens(text) | {m.group(0) for m in IDENTIFIER.finditer(text)}


def _names_in_context(text, kind):





    if kind in _HEADING_KINDS:
        return {m.group(0) for m in IDENTIFIER.finditer(text)}
    return _names(text)


def _names_for_lost(text, kind, document, doc_names):





























    ids = {m.group(0) for m in IDENTIFIER.finditer(text)}
    confirmed = _capitalized_tokens(text) & doc_names
    if kind in _HEADING_KINDS:
        return ids | confirmed
    if document is None:
        return _names(text)
    return _names(text) | confirmed


@dataclass
class Result:
    lost: set = field(default_factory=set)
    gained: set = field(default_factory=set)
    ok: bool = True
    caveat: str = CAVEAT

    def __bool__(self):




        return self.ok


def check(original, rewritten, applied=(), document=None, kind=None):



































































    base = original
    for name in applied:
        if name in fixes.REGISTRY:
            base = getattr(fixes, name)(base)

    before = detect(base)
    after = detect(rewritten)

    masked_base = _mask_dates(base)
    masked_rewritten = _mask_dates(rewritten)
    doc_names = _document_names(document) if document is not None else set()

    lost_names = (_names_for_lost(masked_base, kind, document, doc_names)
                  - _names_for_lost(masked_rewritten, kind, document, doc_names))
    gained_names = (_names_in_context(masked_rewritten, kind)
                    - _name_candidates(masked_base) - doc_names)

    lost = set(lost_names)
    gained = set(gained_names)
    for cls in before:
        if cls == "names":
            continue
        before_set = before[cls]
        after_set = after[cls]
        lost |= before_set - after_set
        gained |= after_set - before_set

    for name in getattr(document, "protected_names", None) or ():
        word = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
        if word.search(base) and not word.search(rewritten):
            lost.add(name)

    return Result(lost=lost, gained=gained, ok=not (lost or gained), caveat=CAVEAT)


def unregistered():




    public = {
        name for name, obj in inspect.getmembers(fixes, inspect.isfunction)
        if not name.startswith("_") and obj.__module__ == fixes.__name__ and name != "suggest"
    }
    return sorted(public - set(fixes.REGISTRY))
