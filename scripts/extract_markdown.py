
import re
from pathlib import Path

from scripts.records import Document, Unit

_FENCE = re.compile(r"^([ \t]*)(```|~~~)", re.M)
_HEADING = re.compile(r"^#{1,6}\s+\S")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
_NEWLINE = re.compile(r"\r\n|\r|\n")
_INDENT4 = re.compile(r"^ {4,}\S")
_COMMENT_MARKER = re.compile(r"<!--|-->")
_MAX_TOP_LEVEL_FENCE_INDENT = 3

CANNOT_SEE = [
    "fenced code (three spaces of indent or fewer at the top level, any indent inside "
    "a list item), an indented code block that follows no list item, and front matter, "
    "which C140 records",
]


def _open_comment_spans(text, start, stop):




















    markers = list(_COMMENT_MARKER.finditer(text, start, stop))
    i = 0
    while i < len(markers):
        m = markers[i]
        if m.group(0) == "<!--" and i + 1 < len(markers) and markers[i + 1].group(0) == "-->":
            yield (m.start(), markers[i + 1].end())
            i += 2
        else:
            i += 1


def _blocks(text):












    pos, n = 0, len(text)
    state = [False]
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 3)
        if end != -1:
            end = text.find("\n", end + 1)
            end = n if end == -1 else end + 1
            yield ("front_matter", 0, end)
            pos = end
    prose_start = pos
    search_from = pos
    while True:
        fence = _FENCE.search(text, search_from)
        if fence is None:
            yield from _prose_blocks(text, prose_start, n, state)
            return
        yield from _prose_blocks(text, prose_start, fence.start(), state)
        indent = len(fence.group(1))
        if indent > _MAX_TOP_LEVEL_FENCE_INDENT and not state[0]:



            prose_start = fence.start()
            search_from = fence.end()
            continue
        marker = fence.group(2)
        closer = re.compile(r"^[ \t]*" + re.escape(marker), re.M)
        close = closer.search(text, fence.end())
        end = n if close is None else text.find("\n", close.end())
        end = n if end == -1 else end + 1
        yield ("code", fence.start(), end)
        state[0] = False
        prose_start = end
        search_from = end


def _line_spans(text, start, stop):

    pos = start
    while pos < stop:
        m = _NEWLINE.search(text, pos, stop)
        end = m.start() if m else stop
        yield (pos, end)
        pos = m.end() if m else stop


def _prose_blocks(text, start, stop, state):













    spans = list(_open_comment_spans(text, start, stop))
    def _in_open_span(pos):
        return any(s <= pos < e for s, e in spans)
    block_start = block_end = None
    for line_start, line_end in _line_spans(text, start, stop):
        if text[line_start:line_end].strip() or _in_open_span(line_start):
            if block_start is None:
                block_start = line_start
            block_end = line_end
        elif block_start is not None:
            yield from _classify_block(text, block_start, block_end, state)
            block_start = None
    if block_start is not None:
        yield from _classify_block(text, block_start, block_end, state)


def _classify_block(text, s, e, state):











    chunk = text[s:e]
    if _HEADING.match(chunk):
        state[0] = False
        yield ("heading", s, e)
    elif _LIST_ITEM.match(chunk):
        state[0] = True
        off = s
        for line in chunk.splitlines(keepends=True):
            if line.strip():
                yield ("list_item", off, off + len(line.rstrip("\r\n")))
            off += len(line)
    elif _INDENT4.match(chunk):
        if state[0]:
            yield ("paragraph", s, e)
        else:
            yield ("code", s, e)
    else:
        state[0] = False
        yield ("paragraph", s, e)


def encoding_of(data):




    return "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"


def extract(path):
    path = Path(path)
    data = path.read_bytes()
    encoding = encoding_of(data)
    text = data.decode(encoding)
    newline = "\r\n" if b"\r\n" in data else "\n"
    document = extract_text(text, str(path), newline)
    document.encoding = encoding
    return document


def extract_text(text, path, newline="\n"):


    units, counter = [], 0
    for kind, start, end in _blocks(text):
        counter += 1
        units.append(Unit(
            id=f"u{counter:04d}", kind=kind,
            surface=f"{kind.replace('_', ' ')} {counter}",
            text=text[start:end], locator={"start": start, "end": end},
            weighs=kind not in ("code", "front_matter"),
        ))
    return Document(path=path, format="markdown", units=units,
                    cannot_see=list(CANNOT_SEE), encoding="utf-8", newline=newline)
