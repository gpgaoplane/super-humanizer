






import re

from scripts import extract_markdown




_BLOCK_QUOTE = re.compile(r"^\s*>")




_HEADING_NAMES_EXAMPLE = re.compile(r"\bexample", re.IGNORECASE)




_INTRO_WORD = re.compile(r"\b(?:example|input|output)\b", re.IGNORECASE)


def _introduces_example(text):


    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    last = lines[-1].rstrip()
    return last.endswith(":") and bool(_INTRO_WORD.search(last))


CANNOT_SEE = [
    "whatever sits inside a recorded C149 span: a fenced or four-space block, which "
    "C140 already exempts in every format regardless of any heading, and a block "
    "quote that sits under a heading naming an example or directly follows a line "
    "that introduces one, which this handler exempts on its own, so C149's own "
    "spans are recorded and reported and never scanned",
    "a settings file or a hook script inside one of the fourteen prompt_globs "
    "directories, which the glob's own extension keeps out",
]


def extract_text(text, path, newline="\n"):
















    document = extract_markdown.extract_text(text, path, newline)
    document.format = "prompt"





    for entry in CANNOT_SEE:
        if entry not in document.cannot_see:
            document.cannot_see.append(entry)
    heading_names_example = False
    previous_text = None
    for unit in document.units:
        if unit.weighs and _BLOCK_QUOTE.match(unit.text):
            introduced = previous_text is not None and _introduces_example(previous_text)
            if heading_names_example or introduced:
                unit.weighs = False
        if unit.kind == "heading":
            heading_names_example = bool(_HEADING_NAMES_EXAMPLE.search(unit.text))
        previous_text = unit.text
    return document
