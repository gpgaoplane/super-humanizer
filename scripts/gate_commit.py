




































































import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import hookio, marker, selfcheck
from scripts.gate_write import (HOOK_TIERS, RULEBOOK_NAME, SESSION_ID, WARN_TIERS, _message,
                                _prints_record, budgeted, density_record, family_order,
                                finding_line, hook_findings, protect_spans,
                                protect_warnings, sweep_state, voice_profile)
from scripts.records import Document, Unit
from scripts.rulebook import load
from scripts.scan import scan

FORMAT = "code prose"
BANDS = ("light", "scattered", "pervasive")
DEDUPE_SECONDS = 5
NO_SESSION = "nosession"
SEPARATORS = ("&&", "||", ";", "\n")
BLANKS = " \t\r"
DELIMITER_ENDS = "<>()"
EXPANSION = re.compile(r"\$[A-Za-z_{(]")
HERE_OPEN = re.compile(r"@(['\"])[ \t]*(?=\r?\n)")
PS_SINGLE = "'‘’‚‛"
PS_DOUBLE = '"“”„'
BARE_SYNTAX = re.compile(r"[*?\[\]{}~()<>@,#!&|]")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
PROGRAM = re.compile(r"(?:^|[/\\])(git|gh)(?:\.exe)?$", re.IGNORECASE)
GIT_WORD = re.compile(r"\b(?:git|gh)\b", re.IGNORECASE)
GIT_SPACE = " \t\v\f\r"
SHELL_WRAPPER = re.compile(r"(?:^|[/\\])(bash|sh|pwsh|powershell|cmd)(?:\.exe)?$",
                           re.IGNORECASE)
SH_COMMAND_FLAG = re.compile(r"-[A-Za-z]*c[A-Za-z]*")

OPERATORS = frozenset({"|", "|&", "&"})
RESERVED = frozenset({"if", "then", "elif", "else", "do", "while", "until"})
WRAPPER = re.compile(r"(?:^|[/\\])(env|command|exec|nohup|sudo|nice|timeout|time)(?:\.exe)?$")
WRAPPER_OPTIONS = {
    "env": frozenset({"-u", "--unset", "-C", "--chdir"}),
    "command": frozenset(),
    "exec": frozenset({"-a"}),
    "nohup": frozenset(),
    "sudo": frozenset({"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
                       "-C", "--close-from", "-D", "--chdir", "-r", "--role", "-t", "--type",
                       "-U", "--other-user", "-T", "--command-timeout"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
    "time": frozenset({"-o", "--output", "-f", "--format"}),
}

GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                               "--config-env", "--attr-source"})
COMMIT_VALUE_SHORT = frozenset({"-F", "-C", "-c", "-t"})
COMMIT_VALUE_LONG = frozenset({"author", "date", "template", "cleanup", "trailer",
                               "pathspec-from-file", "reuse-message", "reedit-message",
                               "fixup", "squash", "file", "message"})
REUSE_LONG = ("reuse-message", "reedit-message")
FIXUP_REUSE = ("reword:", "amend:")
GH_REPO_OPTIONS = frozenset({"-R", "--repo"})
GH_PR_WRITES = frozenset({"create", "new", "edit", "merge"})
GH_BODY = re.compile(r"--body(?:-file)?(?==|$)|-[A-Za-z]*?[bF]")
GH_FLAGS = {"--body": "body", "-b": "body", "--body-file": "file", "-F": "file"}
GH_MERGE_FLAGS = {"--subject": "subject", "-t": "subject", **GH_FLAGS}
GH_TITLE = frozenset({"--title", "-t"})
SUBSTITUTED_HEREDOC = re.compile(
    r"""\$\(\s*cat\s+<<(-?)[ \t]*(['"]?)([A-Za-z0-9_.-]+)\2[ \t]*\r?\n""")
SHELL_EXPANDS = "$`\\"
CANDIDATE_RULES = frozenset({"C095", "C096", "C130"})
STDIN_NAMES = ("-", "/dev/stdin")
COMMIT_SURFACES = ("the commit subject", "the commit body", "commit message")
PR_SURFACES = ("the pull request title", "the pull request body", "pull request body")
EXPANDS = ("The message holds a shell expansion, such as a variable or a command "
           "substitution, and the shell resolves it after this hook reads the command")
PS_ESCAPE = "The message holds a PowerShell backtick escape, which this version does not read"
UNBALANCED = "The command carries quoting this version cannot balance"
NOT_ONE_STRING = ("The message argument is not one quoted string, "
                  "a form this version does not read")
STDIN = ("The message comes through {flag} from standard input with no heredoc in its "
         "command, such as a pipe, which this hook does not read")
MISSING_FILE = "The message file {name} that {flag} names is missing or is not a regular file"
NOT_UTF8 = "The message file {name} is not UTF-8 text, a form this version does not read"
CLUSTER = "The pull request body comes through {flag}, a form this version does not read"
WRAPPED = ("The command runs {wrapper} around a git or gh call, and this hook does not read "
           "the message inside it")


@dataclass
class Parsed:
    outcome: str
    subject: str = ""
    body: str = ""
    reason: str = ""
    surfaces: tuple = COMMIT_SURFACES


@dataclass
class _Piece:

    quote: str
    text: str
    expands: bool = False
    unread: bool = False
    closed: bool = True
    raw: str = ""
    bodies: tuple = ()


def _warn(reason):
    return Parsed("warn", reason=reason)


def _separator(command, i, shell):



    for sep in SEPARATORS:
        if command.startswith(sep, i):
            return len(sep)
    char = command[i]
    before = command[i - 1] if i else ""
    after = command[i + 1:i + 2]
    if char == "|" and after not in ("|", "&") and before != ">":
        return 1
    if char == "&" and after not in ("&", ">") and before not in (">", "<", "|"):
        return 1
    if shell == "PowerShell" and char in "{}":
        return 1
    return 0


def _heredoc_at(command, i):

    return (command.startswith("<<", i) and not command.startswith("<<<", i)
            and (i == 0 or command[i - 1] != "<"))


def _plain(command, i, shell):
    bash = shell != "PowerShell"
    escape = "\\" if bash else "`"
    stops = BLANKS + ("'\"`" if bash else PS_SINGLE + PS_DOUBLE)
    out, j, n, expands = [], i, len(command), False
    while j < n:
        c = command[j]
        if c == escape and j + 1 < n:
            nxt = command[j + 1]
            if nxt == "\n":
                j += 2
            elif nxt == "\r" and command.startswith("\n", j + 2):
                j += 3
            else:
                out.append(nxt)
                j += 2
            continue
        if (c in stops or _separator(command, j, shell) or HERE_OPEN.match(command, j)
                or (bash and _heredoc_at(command, j))):
            break
        expands = expands or c == "$"
        out.append(c)
        j += 1
    return j, _Piece("", "".join(out), expands)


def _single(command, i, shell):
    quotes = PS_SINGLE if shell == "PowerShell" else "'"
    out, j, n = [], i + 1, len(command)
    while j < n:
        c = command[j]
        if c in quotes:
            if shell == "PowerShell" and j + 1 < n and command[j + 1] in quotes:
                out.append("'")
                j += 2
                continue
            return j + 1, _Piece("'", "".join(out))
        out.append(c)
        j += 1
    return n, _Piece("'", "".join(out), closed=False)


def _substitution_end(command, j):




    opener = SUBSTITUTED_HEREDOC.match(command, j)
    if opener is None:
        return None
    tabs, delimiter = opener.group(1) == "-", opener.group(3)
    pos, n = opener.end(), len(command)
    while pos < n:
        eol = command.find("\n", pos)
        end = n if eol == -1 else eol
        line = command[pos:end].rstrip("\r")
        pos = end + 1
        if (line.lstrip("\t") if tabs else line) == delimiter:
            close = pos
            while close < n and command[close] in " \t\r\n":
                close += 1
            return close + 1 if command.startswith(")", close) else None
    return None


def _double(command, i, shell):




    powershell = shell == "PowerShell"
    quotes = PS_DOUBLE if powershell else '"'
    out, j, n = [], i + 1, len(command)
    expands = unread = False
    while j < n:
        c = command[j]
        if powershell and c == "`" and j + 1 < n:
            unread = True
            out.append(command[j:j + 2])
            j += 2
            continue
        if not powershell and c == "\\" and j + 1 < n:
            nxt = command[j + 1]
            if nxt in '$`"\\':
                out.append(nxt)
            elif nxt != "\n":
                out.append(c + nxt)
            j += 2
            continue
        if not powershell and c == "$":
            end = _substitution_end(command, j)
            if end is not None:
                out.append(command[j:end])
                expands = True
                j = end
                continue
        if c in quotes:
            if powershell and j + 1 < n and command[j + 1] in quotes:
                out.append('"')
                j += 2
                continue
            return j + 1, _Piece('"', "".join(out), expands, unread, raw=command[i + 1:j])
        expands = expands or c == "`" or bool(c == "$" and EXPANSION.match(command, j))
        out.append(c)
        j += 1
    return n, _Piece('"', "".join(out), expands, unread, closed=False)


def _backtick(command, i):

    j, n = i + 1, len(command)
    while j < n:
        if command[j] == "\\":
            j += 2
            continue
        if command[j] == "`":
            return j + 1, _Piece("`", command[i + 1:j], expands=True)
        j += 1
    return n, _Piece("`", command[i + 1:], expands=True, closed=False)


def _here_string(command, opener):


    quote = opener.group(1)
    close = re.compile(r"\r?\n" + re.escape(quote) + "@").search(command, opener.end())
    if close is None:
        return len(command), _Piece("@" + quote, command[opener.end():], closed=False)
    body = command[opener.end():close.start()]
    body = body[2:] if body.startswith("\r\n") else body[1:]
    literal = quote == "'"
    return close.end(), _Piece("@" + quote, body,
                               expands=not literal and bool(EXPANSION.search(body)),
                               unread=not literal and "`" in body)


def _heredoc_word(command, i):



    j, n = i + 2, len(command)
    tabs = command.startswith("-", j)
    j += tabs
    while j < n and command[j] in " \t":
        j += 1
    parts, quoted = [], False
    while j < n and command[j] not in BLANKS and not _separator(command, j, "Bash"):
        if command[j] == "'":
            j, piece = _single(command, j, "Bash")
        elif command[j] == '"':
            j, piece = _double(command, j, "Bash")
        else:
            end, piece = _plain(command, j, "Bash")
            cut = next((k for k in range(j, end) if command[k] in DELIMITER_ENDS), end)
            if cut < end:
                end, piece = _plain(command[:cut], j, "Bash")
            if end == j:
                break
            quoted = quoted or "\\" in command[j:end]
            j = end
        parts.append(piece.text)
        quoted = quoted or bool(piece.quote)
    return j, ("".join(parts), tabs, quoted)


def _heredoc_bodies(command, start, pending):




    pos, n, end, bodies = start, len(command), start, []
    for delimiter, tabs, quoted in pending:
        lines = []
        while True:
            if pos >= n:
                return n, _Piece("<<", command[start:], closed=False)
            eol = command.find("\n", pos)
            end = n if eol == -1 else eol
            line = command[pos:end].rstrip("\r")
            pos = end + 1
            line = line.lstrip("\t") if tabs else line
            if line == delimiter:
                break
            lines.append(line + "\n")
        bodies.append(("".join(lines), quoted))
    return end, _Piece("<<", command[start:end], bodies=tuple(bodies))


def _lex(command, shell):






    bash = shell != "PowerShell"
    singles = "'" if bash else PS_SINGLE
    doubles = '"' if bash else PS_DOUBLE
    i, n, word_start, pending = 0, len(command), True, []
    while i < n:
        length = _separator(command, i, shell)
        if length:
            yield "sep", i, i + length, None
            i += length
            word_start = True
            if pending and command[i - 1] == "\n":
                end, body = _heredoc_bodies(command, i, pending)
                yield "heredoc", i, end, body
                i, pending = end, []
            continue
        char = command[i]
        if char in BLANKS:
            j = i
            while j < n and command[j] in BLANKS:
                j += 1
            yield "blank", i, j, None
            i, word_start = j, True
            continue
        if word_start and char == "#":
            end = command.find("\n", i)
            end = n if end == -1 else end
            yield "comment", i, end, None
            i = end
            continue
        if word_start and not bash and command.startswith("<#", i):
            close = command.find("#>", i + 2)
            end = n if close == -1 else close + 2
            yield "comment", i, end, _Piece("<#", command[i:end], closed=close != -1)
            i = end
            continue
        if bash and _heredoc_at(command, i):
            end, delimiter = _heredoc_word(command, i)
            pending.append(delimiter)
            yield "redirect", i, end, None
            i, word_start = end, True
            continue
        opener = HERE_OPEN.match(command, i)
        if opener:
            end, piece = _here_string(command, opener)
        elif char in singles:
            end, piece = _single(command, i, shell)
        elif char in doubles:
            end, piece = _double(command, i, shell)
        elif char == "`" and bash:
            end, piece = _backtick(command, i)
        else:
            end, piece = _plain(command, i, shell)
        yield "piece", i, end, piece
        i, word_start = end, False


def _parts(command, shell):


    parts, start, owners = [], 0, []
    for kind, begin, end, piece in _lex(command, shell):
        if kind == "redirect":
            owners.append(len(parts))
        elif kind in ("sep", "heredoc"):
            parts.append((command[start:begin], []))
            start = end
            if kind == "heredoc":
                for owner, body in zip(owners, piece.bodies):
                    parts[owner][1].append(body)
                owners = []
    parts.append((command[start:], []))
    return [(text, bodies) for text, bodies in parts if text.strip()]


def segments(command, shell="Bash"):



    return [text for text, _ in _parts(command, shell)]


def _unbalanced(command, shell):


    return bool(GIT_WORD.search(command)) and any(
        piece is not None and not piece.closed for _, _, _, piece in _lex(command, shell))


def _words(segment, shell):


    words, current = [], None
    for kind, _, _, piece in _lex(segment, shell):
        if kind != "piece":
            current = None
        elif piece.quote or piece.text:
            if current is None:
                current = []
                words.append(current)
            current.append(piece)
    return words


def _text(word):
    return "".join(piece.text for piece in word)


def _is_operator(word):
    return len(word) == 1 and word[0].quote == "" and word[0].text in OPERATORS


def _command_words(segment, shell):



    words = _words(segment, shell)
    i = 0
    while i < len(words):
        head, text = words[i][0], _text(words[i])
        if head.quote == "" and head.text[:1] in ("(", "{", "!"):
            rest = head.text.lstrip("({!")
            words[i] = ([_Piece("", rest, head.expands)] if rest else []) + words[i][1:]
            if not words[i]:
                i += 1
            continue
        if head.quote == "" and (text in RESERVED or ASSIGNMENT.match(text)):
            i += 1
            continue
        wrapper = WRAPPER.search(text) if head.quote == "" else None
        if wrapper is None:
            break
        options = WRAPPER_OPTIONS[wrapper.group(1)]
        i += 1
        while i < len(words) and _text(words[i]).startswith("-"):
            i += 2 if _text(words[i]) in options else 1
        if wrapper.group(1) == "timeout":
            i += 1
    return words[i:]


def _program(words):
    match = PROGRAM.search(_text(words[0])) if words else None
    return match.group(1).lower() if match else None


def _command_flag(name, text):



    lowered = text.lower()
    if name in ("bash", "sh"):
        return bool(SH_COMMAND_FLAG.fullmatch(text))
    if name == "cmd":
        return lowered in ("/c", "/k")
    return lowered == "-c" or (len(lowered) >= 4 and "-command".startswith(lowered))


def _wrapped(words):


    match = SHELL_WRAPPER.search(_text(words[0])) if words else None
    if match is None:
        return None
    name = match.group(1).lower()
    for k, word in enumerate(words[1:], 1):
        if _command_flag(name, _text(word)):
            rest = " ".join(_text(later) for later in words[k + 1:])
            return f"{_text(words[0])} {_text(word)}" if GIT_WORD.search(rest) else None
    return None


def has_git_or_gh(command, shell="Bash"):
    return any(_program(_command_words(part, shell)) for part in segments(command, shell))


def targets(command, shell="Bash"):


    return [(text, bodies) for text, bodies in _parts(command, shell)
            if _program(_command_words(text, shell)) or _wrapped(_command_words(text, shell))]


def _cleanup(message):



    lines = []
    for line in message.replace("\r\n", "\n").split("\n"):
        line = line.rstrip(GIT_SPACE)
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def split_message(message):


    lines = _cleanup(message)
    if "" not in lines:
        return "\n".join(lines), ""
    cut = lines.index("")
    return "\n".join(lines[:cut]), "\n".join(lines[cut + 1:])


def message_text(subject, body):
    return f"{subject}\n\n{body}" if subject and body else subject or body


def _value(args, j):

    return args[j] if j < len(args) and not _is_operator(args[j]) else None


def _after(word, count):


    rest = []
    for piece in word:
        take = min(count, len(piece.text))
        count -= take
        if take and take == len(piece.text):
            continue
        rest.append(replace(piece, text=piece.text[take:], raw="") if take else piece)
    return rest


def _substituted_heredoc(raw):




    opener = SUBSTITUTED_HEREDOC.match(raw)
    if opener is None:
        return None
    tabs, quoted, delimiter = opener.group(1) == "-", bool(opener.group(2)), opener.group(3)
    lines = [line.rstrip("\r") for line in raw[opener.end():].split("\n")]
    lines = [line.lstrip("\t") for line in lines] if tabs else lines
    if delimiter not in lines:
        return None
    cut = lines.index(delimiter)
    if "".join(lines[cut + 1:]).strip() != ")":
        return None
    body = "\n".join(lines[:cut])
    if not quoted and any(char in body for char in SHELL_EXPANDS):
        return _warn(EXPANDS)
    return body


def _word_text(word, shell):

    if any(not piece.closed for piece in word):
        return _warn(UNBALANCED)
    if shell != "PowerShell" and len(word) == 1 and word[0].quote == '"':
        found = _substituted_heredoc(word[0].raw)
        if found is not None:
            return found
    if any(piece.expands for piece in word):
        return _warn(EXPANDS)
    if any(piece.unread for piece in word):
        return _warn(PS_ESCAPE)
    if len(word) != 1 or (word[0].quote == "" and BARE_SYNTAX.search(word[0].text)):
        return _warn(NOT_ONE_STRING)
    return word[0].text


def _file_text(flag, word, shell, cwd, heredocs):




    if word is None:
        return _warn(NOT_ONE_STRING)
    name = _word_text(word, shell)
    if isinstance(name, Parsed):
        return name
    if name in STDIN_NAMES:
        if not heredocs:
            return _warn(STDIN.format(flag=flag))
        body, quoted = heredocs[-1]
        if not quoted and any(char in body for char in SHELL_EXPANDS):
            return _warn(EXPANDS)
        return body
    path = Path(cwd or os.getcwd()) / name
    try:
        data = path.read_bytes() if path.is_file() else None
    except OSError:
        data = None
    if data is None:
        return _warn(MISSING_FILE.format(flag=flag, name=name))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return _warn(NOT_UTF8.format(name=name))


def _long_name(name, full):
    return len(name) >= 3 and full.startswith(name)


def _parse_commit(args, shell, cwd, heredocs):






    messages, files, reuse = [], [], False
    i = 0
    while i < len(args):
        word, text = args[i], _text(args[i])
        step = 1
        if text == "--" or _is_operator(word):
            break
        if text.startswith("--"):
            name, has_value, value = text[2:].partition("=")
            slot = (messages if _long_name(name, "message")
                    else files if _long_name(name, "file") else None)
            if slot is not None:
                if has_value:
                    slot.append((f"--{name}", _after(word, len(name) + 3)))
                else:
                    slot.append((f"--{name}", _value(args, i + 1)))
                    step = 2
            elif _long_name(name, "fixup"):
                if not has_value and i + 1 < len(args):
                    value = _text(args[i + 1])
                if value.startswith(FIXUP_REUSE):
                    reuse = True
            elif any(_long_name(name, full) for full in REUSE_LONG):
                reuse = True
            if not has_value and name in COMMIT_VALUE_LONG:
                step = 2
        elif text.startswith("-") and len(text) > 1:
            for k, flag in enumerate(text[1:], 1):
                if flag in "mF":
                    slot = messages if flag == "m" else files
                    if len(text) > k + 1:
                        slot.append((f"-{flag}", _after(word, k + 1)))
                    else:
                        slot.append((f"-{flag}", _value(args, i + 1)))
                        step = 2
                    break
                if flag in "Cc":
                    reuse = True
                    break
                if flag in "tSu":
                    break
            if text in COMMIT_VALUE_SHORT:
                step = 2
        i += step

    if reuse or (messages and files):
        return Parsed("skip")
    if files:
        text = _file_text(*files[-1], shell, cwd, heredocs)
        return text if isinstance(text, Parsed) else Parsed("gate", *split_message(text))
    if not messages:
        return Parsed("skip")
    texts = []
    for _, word in messages:
        text = _warn(NOT_ONE_STRING) if word is None else _word_text(word, shell)
        if isinstance(text, Parsed):
            return text
        texts.append(text)
    return Parsed("gate", *split_message("\n\n".join(texts)))


def _parse_git(args, shell, cwd, heredocs):
    if any(not piece.closed for word in args for piece in word):
        return _warn(UNBALANCED)
    i = 0
    while i < len(args) and _text(args[i]).startswith("-"):
        i += 2 if _text(args[i]) in GIT_VALUE_OPTIONS else 1
    if i >= len(args) or _text(args[i]) != "commit":
        return Parsed("skip")
    return _parse_commit(args[i + 1:], shell, cwd, heredocs)


def _gh_flag(args, i, flags):


    word, text = args[i], _text(args[i])
    for flag, slot in flags.items():
        if text == flag:
            return slot, flag, _value(args, i + 1), 2
        joint = flag + "=" if flag.startswith("--") else flag
        if text != flag and text.startswith(joint):
            return slot, flag, _after(word, len(joint)), 1
    return None


def _parse_gh(args, shell, cwd, heredocs):









    if any(not piece.closed for word in args for piece in word):
        return _warn(UNBALANCED)
    names = [_text(word) for word in args]
    verbs, i = [], 0
    while i < len(args) and len(verbs) < 2 and not _is_operator(args[i]):
        if names[i] in GH_REPO_OPTIONS:
            i += 2
        elif names[i].startswith("-"):
            i += 1
        else:
            verbs.append(names[i])
            i += 1
    if len(verbs) < 2 or verbs[0] != "pr" or verbs[1] not in GH_PR_WRITES:
        return Parsed("skip")
    merge = verbs[1] == "merge"
    found, i = {}, 0
    while i < len(args):
        if names[i] == "--" or _is_operator(args[i]):
            break
        if names[i] in GH_TITLE and not merge:
            i += 2
            continue
        flag = _gh_flag(args, i, GH_MERGE_FLAGS if merge else GH_FLAGS)
        if flag is not None:
            slot, name, value, step = flag
            found[slot] = (name, value)
            i += step
            continue
        if GH_BODY.match(names[i]):
            return _warn(CLUSTER.format(flag=names[i]))
        i += 1
    subject = found.pop("subject", None)
    if len(found) > 1 or not (found or subject):
        return Parsed("skip")
    pairs = list(found.items())
    if subject:
        pairs.insert(0, ("subject", subject))
    texts = {}
    for slot, (flag, word) in pairs:
        if slot == "file":
            text = _file_text(flag, word, shell, cwd, heredocs)
        else:
            text = _warn(NOT_ONE_STRING) if word is None else _word_text(word, shell)
        if isinstance(text, Parsed):
            return text
        texts["subject" if slot == "subject" else "body"] = "\n".join(_cleanup(text))
    if merge:
        return Parsed("gate", texts.get("subject", ""), texts.get("body", ""))
    return Parsed("gate", "", texts["body"], surfaces=PR_SURFACES)


def parse_message(command, shell="Bash", cwd=None, heredocs=()):



    words = _command_words(command, shell)
    wrapper = _wrapped(words)
    if wrapper:
        return _warn(WRAPPED.format(wrapper=wrapper))
    program = _program(words)
    if program == "git":
        return _parse_git(words[1:], shell, cwd, heredocs)
    if program == "gh":
        return _parse_gh(words[1:], shell, cwd, heredocs)
    return Parsed("skip")


def message_units(subject, body, surfaces=COMMIT_SURFACES):



    start = len(subject) + 2 if subject else 0
    return [
        Unit(id="u0001", kind="commit_subject", surface=surfaces[0], text=subject,
             locator={"start": 0, "end": len(subject)}),
        Unit(id="u0002", kind="commit_body", surface=surfaces[1], text=body,
             locator={"start": start, "end": start + len(body)}),
    ]


def _document(units):
    return Document(path="", format=FORMAT, units=units, cannot_see=[], encoding="utf-8",
                    newline="\n")


@dataclass
class _Scanned:
    text: str
    units: dict
    findings: list
    whole: Unit
    rekeyed: list
    candidates: list


def scan_message(parsed, book, number=None, protect_entries=(), profile=()):








    text = message_text(parsed.subject, parsed.body)
    units = message_units(parsed.subject, parsed.body, parsed.surfaces)
    if number is not None:
        for unit in units:
            unit.surface += f" of commit message {number}"
    document = _document(units)
    every = scan(document, book, protect_spans(document, protect_entries))
    by_id = {unit.id: unit for unit in units}
    findings = hook_findings(every, by_id, book, profile)
    candidates = [(unit, entry) for unit in units if unit.text.strip()
                  for entry in selfcheck.eligible(document, every, book, unit.id)
                  if entry["rule"] in CANDIDATE_RULES]
    whole = Unit(id=f"m{number or 1}", kind="commit_message", surface="the commit message",
                 text=text, locator={"start": 0, "end": len(text)})
    rekeyed = []
    for f in findings:
        shift = by_id[f.unit].locator["start"]
        rekeyed.append(replace(f, unit=whole.id, span=(f.span[0] + shift, f.span[1] + shift)))
    return _Scanned(text, by_id, findings, whole, rekeyed, candidates)


def candidate_line(unit, entry):

    return (f"{entry['rule']} self-check candidate {entry['id']} on {unit.surface}. "
            f"Answer pass or FIRE with a reason. Question: {entry['question']} "
            f"Pass: {entry['pass_line'].rstrip('.')}. {entry['fire_line'].rstrip('.')}.")


def commit_context(records, warns, book, reserved, candidates=()):





    lines = list(records)
    total = len("\n".join(lines))
    grouped = {}
    for scanned, f in warns:
        line = finding_line(scanned.text, scanned.units[f.unit], f, book, "warns on it")
        grouped.setdefault(f.rule, []).append(line)
    order = [rid for rid in family_order(book) if rid in grouped]
    for unit, entry in candidates:
        if entry["id"] not in grouped:
            order.append(entry["id"])
        grouped.setdefault(entry["id"], []).append(candidate_line(unit, entry))
    limit = hookio.BUDGET - reserved
    left_out = []
    for rule_id in order:
        family = grouped[rule_id]
        written = 0
        if not left_out:
            for line in family:
                addition = len(line) + (1 if lines else 0)
                if total + addition > limit:
                    break
                lines.append(line)
                total += addition
                written += 1
        if written < len(family):
            left_out.append((rule_id, len(family) - written))
    if left_out:
        lines.append("Findings left out for length: " +
                     ", ".join(f"{rid} {count}" for rid, count in left_out) + ".")
    return "\n".join(lines)


def _plural(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"


def marker_file(event, command):








    session_id = event.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        session_id = NO_SESSION
    state = hookio.plugin_data() / "state"
    tool_use_id = event.get("tool_use_id")
    if isinstance(tool_use_id, str) and SESSION_ID.fullmatch(tool_use_id):
        return state / f"commit-{session_id}-{tool_use_id}", True
    digest = hashlib.sha1(command.encode("utf-8", "surrogatepass")).hexdigest()
    return state / f"commit-{session_id}-{digest}", False


def _recorded(path):


    try:
        return float(path.read_text(encoding="ascii"))
    except ValueError:
        return path.stat().st_mtime


def first_run(path, now, windowed=False):











    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if not windowed:
                    return False
                try:
                    if now - _recorded(path) < DEDUPE_SECONDS:
                        return False
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write(repr(now))
            sweep_state(now)
            return True
    except OSError:
        pass
    return True


def _load(name):
    if not isinstance(name, str) or not RULEBOOK_NAME.fullmatch(name):
        raise ValueError(f"marker rulebook {name!r} is not a rulebook name")
    return load(hookio.plugin_root() / "references" / "rulebooks" / f"{name}.json",
                hookio.plugin_data() / f"{name}.overlay.json")


def handle(event):



    shell = "PowerShell" if event.get("tool_name") == "PowerShell" else "Bash"
    command = event["tool_input"]["command"]
    commands = targets(command, shell)
    unbalanced = _unbalanced(command, shell)
    if not commands and not unbalanced:
        return

    cwd = event.get("cwd") or os.getcwd()
    marker_path = marker.find_marker(Path(hookio.normalize_path(cwd)))
    if marker_path is None:
        return

    parsed = [parse_message(part, shell, cwd, heredocs) for part, heredocs in commands]
    gated = [p for p in parsed if p.outcome == "gate"]
    reasons = [p.reason for p in parsed if p.outcome == "warn"]
    if unbalanced and UNBALANCED not in reasons:
        reasons.append(UNBALANCED)
    if not gated and not reasons:
        return
    path, keyed = marker_file(event, command)
    if not first_run(path, time.time(), windowed=not keyed):
        return

    settings, marker_warnings = marker.load_marker(marker_path)
    warnings = [f"Marker warning: {w}" for w in marker_warnings]
    warnings += protect_warnings(settings["protect"])
    unscanned = f"{_plural(len(reasons), 'message')} not scanned"
    if not gated:
        hookio.emit_note(_message(unscanned, reasons + warnings))

    book = _load(settings["rulebook"])
    warnings += [f"Rulebook warning: {w}" for w in book.warnings]
    several = len(gated) > 1
    profile, voice_notes = voice_profile(settings)
    scanned = [scan_message(p, book, k if several else None, settings["protect"], profile)
               for k, p in enumerate(gated, 1)]
    notes = ([unscanned] + reasons) if reasons else []

    blocks = [(s, f) for s in scanned for f in s.findings if f.tier == "block"]
    if blocks:
        grouped = {}
        for s, f in blocks:
            grouped.setdefault(f.rule, []).append(
                finding_line(s.text, s.units[f.unit], f, book, "blocks it"))
        nouns = " and ".join(dict.fromkeys(p.surfaces[2] for p in gated))
        lines = [f"super-humanizer: rulebook {book.name} refused this {nouns}."]
        lines += [f"{sentence}." for sentence in notes + warnings]
        order = [rid for rid in family_order(book) if rid in grouped]
        hookio.emit_block(budgeted(lines, grouped, order, hookio.BUDGET))

    records, bands = [], []
    for k, s in enumerate(scanned, 1):
        if _prints_record(s.findings, book):
            record, band = density_record(_document([s.whole]), s.rekeyed, book,
                                          what="message")
            records.append(f"Commit message {k}. {record}" if several else record)
            bands.append(band)
    warns = [(s, f) for s in scanned for f in s.findings if f.tier in WARN_TIERS]
    if warns:
        head = f"{_plural(len(warns), 'warn')}, {book.name}"
    elif reasons:
        head = f"{unscanned}, {book.name}"
        notes = reasons
    elif records:
        head = f"density {max(bands, key=BANDS.index)}, {book.name}"
    else:
        head = f"clean, {book.name}"
    message = _message(head, notes + voice_notes + warnings)
    candidates = [pair for s in scanned for pair in s.candidates]
    context = commit_context(records, warns, book, reserved=len(message), candidates=candidates)
    if context:
        hookio.emit_context(context, message)
    hookio.emit_note(message)


if __name__ == "__main__":
    hookio.run_guarded(lambda: handle(hookio.read_event()))
