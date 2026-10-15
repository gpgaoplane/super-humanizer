






















import math
import re

from scripts.records import Finding
from scripts.structure import word_tokens, sentence_texts

EM_DASH = "—"
RUN_TOLERANCE = 3
MIN_SENTENCES = 2
MATTR_WINDOW = 50
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _weighing_texts(document):
    return [u.text for u in document.units if u.weighs]


def _sentence_lengths(texts):
    lengths = []
    for text in texts:
        for sentence in sentence_texts(text):
            count = len(word_tokens(sentence))
            if count:
                lengths.append(count)
    return lengths


def _row(rule, book, text):
    return Finding(rule=rule, rulebook=book.name, unit="document", span=None,
                   tier="metric", source="cross-unit", verdict="n-a",
                   category=book.rules[rule].category,
                   fix={"kind": "none", "text": text})


def _c019(texts):
    count = sum(text.count(EM_DASH) for text in texts)
    words = sum(len(word_tokens(text)) for text in texts)
    rate = count / words * 1000 if words else 0.0
    return f"em dashes: {count}, {rate:.1f} per thousand words"


def _c086(texts):
    lengths = _sentence_lengths(texts)
    if len(lengths) < MIN_SENTENCES:
        plural = "sentence" if len(lengths) == 1 else "sentences"
        return f"sentence length: n-a, {len(lengths)} {plural}, needs {MIN_SENTENCES}"
    mean = sum(lengths) / len(lengths)
    deviation = math.sqrt(sum((n - mean) ** 2 for n in lengths) / len(lengths))
    longest = run = 1
    for before, after in zip(lengths, lengths[1:]):
        run = run + 1 if abs(after - before) <= RUN_TOLERANCE else 1
        longest = max(longest, run)
    return (f"sentence length: mean {mean:.2f} words, standard deviation {deviation:.2f}, "
            f"longest run within {RUN_TOLERANCE} words: {longest} sentences")


def _mattr(words):
    windows = len(words) - MATTR_WINDOW + 1
    total = sum(len(set(words[i:i + MATTR_WINDOW])) for i in range(windows))
    return total / windows / MATTR_WINDOW


def _syllables(word):
    return max(1, len(_VOWEL_GROUP.findall(word)))


def _c088(texts):
    streams = [word_tokens(text) for text in texts]
    words = [w for stream in streams for w in stream]
    if len(words) >= MATTR_WINDOW:
        mattr = f"{_mattr(words):.2f}"
    else:
        mattr = f"n-a ({len(words)} words, needs {MATTR_WINDOW})"
    total = 0
    distinct = set()
    for stream in streams:
        grams = [tuple(stream[i:i + 3]) for i in range(len(stream) - 2)]
        total += len(grams)
        distinct.update(grams)
    repetition = 1 - len(distinct) / total if total else 0.0
    sentences = len(_sentence_lengths(texts))
    if words and sentences:
        grade = (0.39 * len(words) / sentences
                 + 11.8 * sum(_syllables(w) for w in words) / len(words) - 15.59)
        grade = f"{grade:.2f}"
    else:
        grade = f"n-a ({len(words)} words)"
    return (f"MATTR-50 {mattr}, trigram repetition {repetition:.2f}, "
            f"Flesch-Kincaid grade {grade}")


_MEASURES = (("C019", _c019), ("C086", _c086), ("C088", _c088))


def measure_rows(document, book):


    texts = _weighing_texts(document)
    return [_row(rule, book, measure(texts))
            for rule, measure in _MEASURES
            if rule in book.rules and book.rules[rule].formats.get(document.format) != "off"]
