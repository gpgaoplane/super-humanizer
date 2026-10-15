





import codecs
import hashlib
import io
import itertools
import os
import re
import shutil
import stat
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

SUFFIXES = {".pptx": "pptx", ".xlsx": "xlsx", ".docx": "docx"}
PDF_SUFFIX = ".pdf"
FORMATS = ("pptx", "xlsx", "docx", "pdf")




INSTALL_LINE = ('pip install "python-pptx>=1.0" "openpyxl>=3.1" "python-docx>=1.1" "pypdf>=3" '
                '"lxml>=4" tree-sitter-language-pack pytest ruff')



READ_ONLY = "read and counted in this version, the rewrite is left for the human"



SPLIT_WORD = ("the rewrite of {surface} had too few spaces for the runs it was spread over, so "
              "a word was split across runs and its formatting may be mixed")




TEMP_SUFFIX = ".humanize-tmp"


COPY = "copy"
IN_PLACE = "in-place"
OFFICE_WRITES = (COPY, IN_PLACE)


IN_PLACE_PARTS = ("{path} was written in place, {count} of {total} package parts replaced "
                  "({names}), and every other part is byte for byte what it was")
IN_PLACE_OPEN = ("the original, or the temporary file beside it, is held by another program or "
                 "read-only: {error}")
IN_PLACE_STEP = "the in-place write failed at {step}: {error}"
IN_PLACE_CENSUS = ("the rebuilt file did not read back as expected, so it was discarded: "
                   "{reason}")


IN_PLACE_CHANGED = "the rebuilt file was discarded and the original left as it now is: {reason}"


IN_PLACE_NOTHING = ("the in-place write was handed no package part to replace, so nothing "
                    "was written")


IN_PLACE_LEFT = ("The temporary file {temp} could not be removed and is left beside the "
                 "original")



RENAME_TRIES = 5
RENAME_PAUSE = 0.1


class OfficeError(Exception):
    pass


def format_of(path):

    suffix = Path(path).suffix.lower()
    if suffix == PDF_SUFFIX:
        return "pdf"
    return SUFFIXES.get(suffix)


def copy_path(path):

    path = Path(path)
    return path.with_name(f"{path.stem}.humanized{path.suffix}")


def markdown_path(path):

    path = Path(path)
    return path.with_name(f"{path.stem}.humanized.md")


def written_as(path):



    if format_of(path) == "pdf":
        return "delivery", "markdown delivery"
    return "copy", "side-by-side copy"


def distribute(lengths, text):












    total = sum(lengths)
    size = len(text)
    pieces, previous, seen = [], 0, 0
    for index, length in enumerate(lengths[:-1]):
        seen += length
        if length == 0 or total == 0:
            cut = previous
        elif seen == total:
            cut = size
        else:
            share = (2 * size * seen + total) // (2 * total)
            space = text.rfind(" ", previous, share + 1)
            cut = space + 1 if space >= 0 else share
            later = sum(1 for rest in lengths[index + 1:] if rest)
            cut = max(previous, min(max(cut, previous + 1), size - later))
        pieces.append(text[previous:cut])
        previous = cut
    pieces.append(text[previous:])
    return pieces


def splits_a_word(pieces):




    text = "".join(pieces)
    cut = 0
    for piece in pieces[:-1]:
        cut += len(piece)
        if 0 < cut < len(text) and not text[cut - 1].isspace() and not text[cut].isspace():
            return True
    return False


def missing_package(package, format):


    return (f"the {format} handler needs the package {package}, which is not installed, so "
            f"nothing in the file was read. The install notes carry the line: {INSTALL_LINE}")


def below_floor(package, floor, format):



    return (f"the {format} handler needs the package {package} {floor} or later, and the one "
            f"installed is older, so nothing in the file was read. The install notes carry the "
            f"line: {INSTALL_LINE}")


def digest_changed(path, file_digest):


    try:
        data = Path(path).read_bytes()
    except OSError:
        return True
    return hashlib.sha256(data).hexdigest() != file_digest


def read_unchanged(path, file_digest):



    try:
        data = Path(path).read_bytes()
    except OSError as error:
        return None, f"the original could not be read: {type(error).__name__}: {error}"
    if hashlib.sha256(data).hexdigest() != file_digest:
        return None, "the original changed on disk between extract and write"
    return data, None


def save_copy(target, save):










    target = Path(target)
    handle, temp = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".",
                                    suffix=TEMP_SUFFIX)
    os.close(handle)
    try:
        save(temp)
        os.replace(temp, target)
    except BaseException as error:
        traceback.clear_frames(error.__traceback__)
        try:
            if os.path.exists(temp):
                os.unlink(temp)
        except OSError:
            pass
        raise


_CR, _LF = bytes([13]), bytes([10])
_DECLARATION_SPACES = (b" ", bytes([9]), _CR, _LF)


def leading_bytes(part):







    start = len(codecs.BOM_UTF8) if part.startswith(codecs.BOM_UTF8) else 0
    opening = start + len(b"<?xml")
    if not part.startswith(b"<?xml", start) or part[opening:opening + 1] not in _DECLARATION_SPACES:
        return part[:start]
    end = part.find(b"?>", opening)
    if end < 0:
        return part[:start]
    end += len(b"?>")
    for line_end in (_CR + _LF, _LF, _CR):
        if part.startswith(line_end, end):
            return part[:end + len(line_end)]
    return part[:end]



_ENCODING = re.compile(rb"encoding\s*=\s*(['\"])(.*?)\1")


def with_leading_bytes(original_part, serialized):








    head = leading_bytes(original_part)
    named = _ENCODING.search(head)
    if named is not None and named.group(2).lower() != b"utf-8":
        return serialized
    return head + serialized[len(leading_bytes(serialized)):]


def entry_digests(data):

    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return [(info.filename, hashlib.sha256(package.read(info)).hexdigest())
                for info in package.infolist()]


def rebuild_package(data, replacements, target):








    with zipfile.ZipFile(io.BytesIO(data)) as source:
        infos = source.infolist()
        names = {info.filename for info in infos}
        for name in replacements:
            if name not in names:
                raise KeyError(name)
        with zipfile.ZipFile(target, "w") as rebuilt:
            for info in infos:
                body = source.read(info)
                rebuilt.writestr(info, replacements.get(info.filename, body))


def _line_fed(text):


    return text.replace(chr(13) + chr(10), chr(10))


def reads_as(document, reopened, applied):











    for index, unit in enumerate(document.units):
        if index >= len(reopened.units):
            return f"unit {unit.id} ({unit.surface}) is missing from the rebuilt file"
        other = reopened.units[index]
        if (other.id, other.surface, other.locator) != (unit.id, unit.surface, unit.locator):
            return (f"unit {unit.id} ({unit.surface}) reads back under another id, surface "
                    "or locator")
        expected = applied.get(unit.id, unit.text)
        if unit.id in applied and (unit.frame or {}).get("kind") == "cell":
            expected = expected.strip()
        if _line_fed(other.text) != _line_fed(expected):
            return (f"unit {unit.id} ({unit.surface}) reads back with other text than the "
                    "write put there")
    if len(reopened.units) > len(document.units):
        extra = reopened.units[len(document.units)]
        return (f"the rebuilt file holds unit {extra.id} ({extra.surface}), which the "
                "original did not")
    return None


def _kept(digests, replacements):


    return [(name, None if name in replacements else value) for name, value in digests]


def _discard(temp):





    if temp is None or not os.path.exists(temp):
        return ""
    try:
        os.chmod(temp, stat.S_IREAD | stat.S_IWRITE)
        os.unlink(temp)
    except OSError:
        return ". " + IN_PLACE_LEFT.format(temp=temp)
    return ""


def _replace(temp, path):



    for attempt in range(RENAME_TRIES):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == RENAME_TRIES - 1:
                raise
            time.sleep(RENAME_PAUSE)


def write_in_place(path, data, replacements, census):


























    path = Path(path)
    if not replacements:
        return IN_PLACE_NOTHING
    temp, step = None, "the temporary file"
    try:
        handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
                                        suffix=TEMP_SUFFIX + path.suffix)
        os.close(handle)
        step = "the rebuild"
        with open(temp, "wb") as target:
            rebuild_package(data, replacements, target)
            target.flush()
            os.fsync(target.fileno())
        step = "the census"
        reason = census(temp)
        if reason is None:
            step = "the entry check"
            before = _kept(entry_digests(data), replacements)
            after = _kept(entry_digests(Path(temp).read_bytes()), replacements)
            differing = [old or new for old, new in itertools.zip_longest(before, after)
                         if old != new]
            if differing:
                reason = ("the rebuilt package differs from the original at the part "
                          f"{differing[0][0]}")
        if reason is not None:
            return IN_PLACE_CENSUS.format(reason=reason) + _discard(temp)
        step = "the mode"
        shutil.copymode(path, temp)
        step = "the recheck"
        _, changed = read_unchanged(path, hashlib.sha256(data).hexdigest())
        if changed is not None:
            return IN_PLACE_CHANGED.format(reason=changed) + _discard(temp)
        step = "the rename"
        _replace(temp, path)
    except BaseException as error:
        traceback.clear_frames(error.__traceback__)
        left = _discard(temp)
        if not isinstance(error, Exception):
            raise
        named = f"{type(error).__name__}: {error}"
        if step == "the rename" and isinstance(error, PermissionError):
            return IN_PLACE_OPEN.format(error=named) + left
        return IN_PLACE_STEP.format(step=step, error=named) + left
    return None


def density_key(document, unit):










    if document.format == "pptx":
        slide = unit.locator["slide"]
        return ("notes", slide) if unit.locator.get("notes") else ("slide", slide)
    if document.format == "xlsx":
        name = unit.locator["sheet"]
        return ("sheet", f"{name} (hidden)" if unit.locator.get("hidden") else name)
    if document.format == "pdf":
        return ("page", unit.locator["page"])
    if document.format != "prompt":
        return unit.id
    section = 0
    for other in document.units:
        if other.kind == "heading":
            section += 1
        if other.id == unit.id:
            return section
    raise ValueError(f"{unit.id} is no unit of {document.path}")


def company_keys(document):




    if document.format != "prompt":
        return {unit.id: density_key(document, unit)
                for unit in document.units if unit.weighs}
    keys, section = {}, 0
    for unit in document.units:
        if unit.kind == "heading":
            section += 1
        if unit.weighs:
            keys[unit.id] = section
    return keys


_GROUP_LABELS = {"slide": "slide {}", "notes": "slide {} notes", "sheet": "sheet {}",
                 "page": "page {}"}


def group_label(key):


    if isinstance(key, tuple):
        kind, value = key
        return _GROUP_LABELS[kind].format(value)
    return key
