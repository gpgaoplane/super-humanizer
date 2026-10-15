






import re

from scripts.units import LINK_PAREN

_SENTENCE_ENDERS = {".", "!", "?"}
_VOWEL_LETTERS = "aeio"




_UNRELIABLE_PREFIXES = ("h", "u", "eu", "one", "onc", "ew")





_FUNCTION_WORDS = {

    "and", "or", "but", "nor", "so", "yet", "if", "then", "than", "that", "which",
    "while", "when", "where", "because",

    "of", "in", "on", "at", "to", "for", "from", "with", "by", "as", "into", "over",
    "under", "after", "before",

    "is", "are", "was", "were", "be", "been", "being", "has", "have", "had", "do",
    "does", "did", "will", "would", "can", "could", "should", "may", "might", "must",

    "it", "its", "he", "she", "they", "them", "their", "this", "these", "those", "we",
    "you", "i", "me", "my", "our", "your", "his", "her",
}



JARGON_PAIRS = [
    (re.compile(r"\bcircle back to\b", re.I), "return to"),
    (re.compile(r"\bdouble down on\b", re.I), "commit to"),
    (re.compile(r"\bdeep dive\b", re.I), "analysis"),
]


def undash(text):

    out = re.sub(r"\s*[—–]\s*", ", ", text)
    out = re.sub(r",\s*,", ",", out)
    return re.sub(r",\s*\.", ".", out)


def unsemicolon(text):

    def _split(m):
        return ". " + m.group(1).upper()
    return re.sub(r";\s*([a-z])", _split, text)


def unarrow(text):

    return re.sub(r"\s*(?:→|->|=>)\s*", " to ", text)


def agree_article(text):
















    def _sentence_starts_at(pos):
        before = text[:pos].rstrip()
        return not before or before[-1] in _SENTENCE_ENDERS

    def _fix(m):
        article, space, word = m.group(1), m.group(2), m.group(3)
        if article[0].isupper() and not _sentence_starts_at(m.start(1)):
            return m.group(0)
        if not (word.isalpha() and word.islower()):
            return m.group(0)
        if word in _FUNCTION_WORDS:
            return m.group(0)
        if len(word) == 1:
            return m.group(0)
        if word.startswith(_UNRELIABLE_PREFIXES):
            return m.group(0)
        wants_an = word[0] in _VOWEL_LETTERS
        correct = "an" if wants_an else "a"
        if article[0].isupper():
            correct = correct.capitalize()
        return correct + space + word
    return re.sub(r"\b([Aa]n?)(\s+)(\w+)", _fix, text)


def jargon_pair(text):



    def _replacement(replacement):
        def _sub(m):
            if m.group(0)[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement
        return _sub

    out = text
    for pattern, replacement in JARGON_PAIRS:
        out = pattern.sub(_replacement(replacement), out)
    return agree_article(out)




_CHATBOT_UTM_SOURCES = frozenset({"chatgpt.com", "openai", "grok.com", "perplexity", "copilot"})


def strip_chatbot_utm(text):









    def _strip_target(match):
        target = match.group(1)
        if "?" not in target:
            return "](" + target + ")"
        base, _, rest = target.partition("?")
        query, hashsep, fragment = rest.partition("#")
        kept = [param for param in query.split("&")
                if not (param.startswith("utm_source=")
                        and param[len("utm_source="):] in _CHATBOT_UTM_SOURCES)]
        new_target = base + ("?" + "&".join(kept) if kept else "")
        if hashsep:
            new_target += "#" + fragment
        return "](" + new_target + ")"
    return LINK_PAREN.sub(_strip_target, text)


_CELL_RANGE = re.compile(r"\b([A-Za-z]{1,3}\d+):([A-Za-z]{1,3}\d+)\b")


def plain_locations(text):




    return _CELL_RANGE.sub(r"\1 to \2", text)



REGISTRY = {
    "undash": "a mark becomes a comma",
    "unsemicolon": "a semicolon becomes a sentence boundary and a capital",
    "unarrow": "an arrow becomes the word 'to'",
    "agree_article": "'a' and 'an' agree with the following word",
    "jargon_pair": "a one-sense jargon phrase becomes its plain equivalent",
    "strip_chatbot_utm": "a chatbot referrer value is stripped from a link target",
    "plain_locations": "a cell range's colon becomes the word 'to'",
}


def suggest(finding, unit_text):











    spec = finding.fix or {}
    if spec.get("kind") != "final":
        return {"kind": "change", "text": spec.get("text", "rewrite this unit by hand")}
    name = spec.get("function", "")
    function = globals()[name] if name in REGISTRY else None
    if function is None:
        return {"kind": "change", "text": "no fix function is registered for this rule"}
    candidate = function(unit_text)
    if candidate == unit_text:
        return {"kind": "change", "text": "the fix left the text unchanged, so rewrite it by hand"}
    return {"kind": "final", "text": candidate}
