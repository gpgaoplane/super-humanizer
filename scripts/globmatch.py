




import re
from functools import lru_cache

_TOKEN = re.compile(r"\*\*/|/\*\*|\*\*|\*|\?|\[[^\]]*\]|[^*?\[]+")


@lru_cache(maxsize=512)
def compile_glob(pattern):





    anchored = pattern.startswith("/")
    body = pattern[1:] if anchored else pattern
    if "/" not in body and not anchored:
        body = "**/" + body
    out = []
    for token in _TOKEN.findall(body):
        if token == "**/":
            out.append(r"(?:[^/]+/)*")
        elif token == "/**":
            out.append(r"(?:/.*)?")
        elif token == "**":
            out.append(r".*")
        elif token == "*":
            out.append(r"[^/]*")
        elif token == "?":
            out.append(r"[^/]")
        elif token.startswith("["):
            out.append(token)
        else:
            out.append(re.escape(token))
    return re.compile("^" + "".join(out) + "$")


def matches(pattern, relative_path):

    return compile_glob(pattern).fullmatch(relative_path) is not None
