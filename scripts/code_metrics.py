



























import ast
import configparser
import io
import re
import statistics
import tokenize
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePath

from scripts import extract_code
from scripts.records import Finding



RULES = ("C097", "C098", "C099", "C100", "C101", "C102", "C103", "C131", "C132", "C133",
         "C134", "C135", "C136", "C137", "C138")


CAP = 20


GENERIC_NAMES = frozenset({"data", "result", "value", "item", "obj", "tmp", "temp", "info",
                           "handler", "manager", "helper", "util", "utils", "process",
                           "handle", "do_stuff"})



LINT_RULES = {"C098": "E30", "C102": "ARG001", "C103": "T201"}



ESLINT_RULES = {"C098": "padding-line-between-statements", "C102": "no-unused-vars",
                "C103": "no-console"}


_ESLINT_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", ".eslintrc.json",
                 ".eslintrc", ".eslintrc.cjs", ".eslintrc.js")

_RUFF_TABLES = ("tool.ruff", "tool.ruff.lint")
_RUFF_KEY = re.compile(r"\s*(?:lint\.)?(select|extend-select|ignore|extend-ignore)\s*=(.*)")
_QUOTED = re.compile(r"""["']([^"']*)["']""")
_FLAKE8_FILES = ("setup.cfg", "tox.ini", ".flake8")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFINITIONS = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_TRIVIA = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
           tokenize.ENDMARKER}
_UPPER_CASE = re.compile(r"_*[A-Z][A-Z0-9_]*")
_MIRROR_NAME = re.compile(r"test_\w+_returns_expected_value")
_WORD = re.compile(r"\w+")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


@dataclass
class _Source:

    text: str
    lines: list
    path: str
    root: object
    document: object


def metrics(text, path, book, root=None, document=None):













    if extract_code.language_of(path) in _SCRIPT_LANGUAGES:
        measure = _script_measure(text, str(path), root, document)
        enforced = _eslint_enforced(root)
    else:
        tree = _parse(text)
        if tree is None:
            return []
        measure = _python_measure(tree, _Source(text=text, lines=_LINE_BREAK.split(text),
                                                path=str(path), root=root, document=document))
        selected = _enforced(root)
        enforced = {rule_id: name for rule_id, name in LINT_RULES.items() if name in selected}
    if measure is None:
        return []
    shown = _shown(path, root)
    findings = []
    for rule_id in RULES:
        rule = book.rules.get(rule_id)
        if rule is None or rule.formats.get(extract_code.FORMAT) == "off":
            continue
        found = measure(rule_id)
        if rule_id == "C099":
            comments, code = found
            if not code:
                continue
            lines = [1]
            head = (f"{_count(comments, 'comment line')} over {_count(code, 'code line')}, "
                    f"a ratio of {comments / code:.2f}")
        else:
            lines = sorted(set(found))
            if not lines:
                continue
            head = _count(len(lines), "site")
        if rule_id in enforced:
            head += f", enforced by {enforced[rule_id]}"
        if len(lines) > CAP:
            head += f", the first {CAP} listed"
        sites = ", ".join(f"{shown}:{line}" for line in lines[:CAP])
        findings.append(Finding(
            rule=rule_id, rulebook=book.name, unit="document", span=None, tier="metric",
            source="ast", verdict="n-a", category=rule.category,
            fix={"kind": "none", "text": f"{head}: {sites}"}))
    return findings


def _python_measure(tree, source):


    def measure(rule_id):
        if rule_id == "C099":
            return _comment_lines(source)
        if rule_id in _SOURCE_MEASURES:
            return _SOURCE_MEASURES[rule_id](tree, source)
        return _MEASURES[rule_id](tree) if rule_id in _MEASURES else []
    return measure


def _parse(text):


    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            return ast.parse(text)
        except (SyntaxError, ValueError):
            return None


def _shown(path, root):


    if root is not None:
        try:
            return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            pass
    return PurePath(path).name


def _count(number, noun):
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _enforced(root):


    if root is None:
        return set()
    configs = [_ruff_lists(Path(root) / "pyproject.toml")]
    configs += [_flake8_lists(Path(root) / name) for name in _FLAKE8_FILES]
    return {rule for select, ignore in configs for rule in LINT_RULES.values()
            if _covers(select, rule) and not _covers(ignore, rule)}


def _covers(codes, rule):



    return any(code == "ALL" or rule == code
               or (code and rule.startswith(code)
                   and (code[-1].isdigit() or rule[len(code)].isdigit()))
               for code in codes)


def _ruff_lists(path):





    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return [], []
    lists = {"select": [], "ignore": []}
    table, key, value = None, None, ""
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        if key is None:
            if line.strip().startswith("["):
                table = line.strip().strip("[]").strip()
                continue
            match = _RUFF_KEY.fullmatch(line)
            if table not in _RUFF_TABLES or match is None:
                continue
            key, value = match.group(1).removeprefix("extend-"), match.group(2)
        else:
            value += line
        if "]" in value or "[" not in value:
            lists[key] += _QUOTED.findall(value)
            key = None
    return lists["select"], lists["ignore"]


def _flake8_lists(path):



    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8-sig")
    except (configparser.Error, UnicodeDecodeError):
        return [], []
    if not parser.has_section("flake8"):
        return [], []
    return tuple(re.split(r"[\s,]+", parser.get("flake8", key, fallback="").strip())
                 for key in ("select", "ignore"))


def _eslint_enforced(root):





    if root is None:
        return {}
    texts = []
    for name in _ESLINT_FILES:
        try:
            texts.append((Path(root) / name).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError):
            continue
    text = "\n".join(_without_comments(config) for config in texts)
    return {rule_id: name for rule_id, name in ESLINT_RULES.items()
            if any(match.group(1) not in ("off", "0") for match in _severity(name).finditer(text))}


def _without_comments(config):



    config = "\n".join(line for line in config.splitlines() if not line.lstrip().startswith("#"))
    out, i, quote = [], 0, None
    while i < len(config):
        char = config[i]
        if quote is not None:
            step = 2 if char == "\\" else 1
            out.append(config[i:i + step])
            quote = None if char == quote else quote
            i += step
        elif char in "\"'`":
            quote = char
            out.append(char)
            i += 1
        elif config.startswith("//", i):
            newline = config.find("\n", i)
            i = len(config) if newline < 0 else newline
        elif config.startswith("/*", i):
            close = config.find("*/", i + 2)
            i = len(config) if close < 0 else close + 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def _severity(rule):



    return re.compile(r"""(?:["']|(?<![\w@/-]))(?:@[\w-]+/)?""" + re.escape(rule)
                      + r"""["']?\s*:\s*\[?\s*["']?(\w+)""")


def _name_of(node):

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _functions(tree):
    return [node for node in ast.walk(tree) if isinstance(node, _FUNCTIONS)]


def _is_docstring(statement):
    return (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str))


def _is_main_guard(node):

    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    sides = (test.left, test.comparators[0])
    return (any(isinstance(side, ast.Name) and side.id == "__name__" for side in sides)
            and any(isinstance(side, ast.Constant) and side.value == "__main__"
                    for side in sides))


def _assignment(statement):


    if isinstance(statement, ast.Assign):
        return statement.targets, statement.value
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        return [statement.target], statement.value
    return [], None






def _c097(tree):



    calls, others, targets = {}, {}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _name_of(node.func) is not None:
            name = _name_of(node.func)
            calls[name] = calls.get(name, 0) + 1
            targets.add(id(node.func))
    for node in ast.walk(tree):
        name = _name_of(node)
        if name is not None and id(node) not in targets:
            others[name] = others.get(name, 0) + 1
    lines = [f.lineno for f in _functions(tree) if calls.get(f.name) == 1 and f.name not in others]
    lines += _parameter_checks(tree)
    lines += [node.lineno for node in ast.walk(tree)
              if isinstance(node, ast.Call) and _name_of(node.func) == "cast"]
    return lines


def _parameter_checks(tree):



    lines = []
    for function in _functions(tree):
        if not function.name.startswith("_"):
            continue
        args = function.args
        params = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
        params.update(a.arg for a in (args.vararg, args.kwarg) if a is not None)
        body = function.body[1:] if _is_docstring(function.body[0]) else function.body
        for statement in body:
            if not isinstance(statement, (ast.If, ast.Assert)):
                break
            if not _checks(statement.test, params):
                break
            lines.append(statement.lineno)
    return lines


def _checks(test, params):


    while isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        test = test.operand
    if isinstance(test, ast.Compare):
        return (isinstance(test.left, ast.Name) and test.left.id in params
                and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Is, ast.IsNot))
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value is None)
    return (isinstance(test, ast.Call) and isinstance(test.func, ast.Name)
            and test.func.id == "isinstance" and bool(test.args)
            and isinstance(test.args[0], ast.Name) and test.args[0].id in params)


def _c098(tree, source):




    return [function.body[0].lineno for function in _functions(tree)
            if len(function.body) >= 3
            and all(_blank_between(first, second, source.lines)
                    for first, second in zip(function.body, function.body[1:]))]


def _blank_between(first, second, lines):
    return any(not lines[row - 1].strip() for row in range(first.end_lineno + 1, second.lineno))


def _comment_lines(source):





    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source.text).readline))
    except (tokenize.TokenError, SyntaxError):
        return 0, 0
    code = set()
    for token in tokens:
        if token.type not in _TRIVIA:
            code.update(range(token.start[0], token.end[0] + 1))
    document = source.document
    if document is None:
        document = extract_code.extract_text(source.text, source.path)
    comments = sum(source.text.count("\n", *unit.span) + 1 for unit in document.units
                   if unit.kind == "comment")
    return comments, len(code)


def _c100(tree):


    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            name = node.id
        elif (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
              and isinstance(node.value, ast.Name) and node.value.id == "self"):
            name = node.attr
        else:
            continue
        if name in GENERIC_NAMES:
            lines.append(node.lineno)
    return lines


def _c102(tree):



    lines = []
    for function in _functions(tree):
        decorators = {_name_of(d.func if isinstance(d, ast.Call) else d)
                      for d in function.decorator_list}
        if decorators & {"abstractmethod", "overload"}:
            continue
        reads = {node.id for statement in function.body for node in ast.walk(statement)
                 if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        args = function.args
        for arg in args.posonlyargs + args.args + args.kwonlyargs:
            if arg.arg in ("self", "cls") or arg.arg.startswith("_") or arg.arg in reads:
                continue
            lines.append(arg.lineno)
    return lines


def _c103(tree):

    if not any(_imports_logging(node) for node in ast.walk(tree)):
        return []
    guarded = {id(node) for guard in ast.walk(tree) if _is_main_guard(guard)
               for statement in guard.body for node in ast.walk(statement)}
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "print" and id(node) not in guarded]


def _imports_logging(node):
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        names = [node.module]
    else:
        return False
    return any(name == "logging" or name.startswith("logging.") for name in names)


def _c131(tree):



    private = [f for f in _functions(tree) if f.name.startswith("_")
               and not (f.name.startswith("__") and f.name.endswith("__"))]
    if len(private) < 3 or any(ast.get_docstring(f) is None for f in private):
        return []
    return [f.lineno for f in private]


def _c132(tree):

    groups = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef) + _FUNCTIONS):
            continue
        if not node.body or not _is_docstring(node.body[0]):
            continue
        words = tuple(_WORD.findall(node.body[0].value.value.lower())[:3])
        if len(words) == 3:
            groups.setdefault(words, []).append(node.body[0].lineno)
    return [line for group in groups.values() if len(group) >= 3 for line in group]


def _c133(tree):


    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Try) and len(node.body) == 1
            and isinstance(node.body[0], (ast.Expr, ast.Assign))
            and sum(isinstance(inner, ast.Call) for inner in ast.walk(node.body[0])) == 1]


def _c134(tree):


    stores, loads = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            counts = stores if isinstance(node.ctx, ast.Store) else loads
            counts[node.id] = counts.get(node.id, 0) + 1
    lines = []
    for statement in tree.body:
        targets, _ = _assignment(statement)
        for target in targets:
            for node in ast.walk(target):
                if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
                        and _UPPER_CASE.fullmatch(node.id)
                        and stores.get(node.id) == 1 and loads.get(node.id) == 1):
                    lines.append(statement.lineno)
    return lines


def _c135(tree):

    lines = []
    for statement in tree.body:
        _, value = _assignment(statement)
        if isinstance(value, ast.Dict) and len(value.keys) == 1 and value.keys[0] is not None:
            lines.append(value.lineno)
    return lines


def _c136(tree):


    body = tree.body[1:] if tree.body and _is_docstring(tree.body[0]) else tree.body
    guards = [s for s in body if _is_main_guard(s)]
    mains = [s for s in body if isinstance(s, _FUNCTIONS) and s.name == "main"]
    rest = [s for s in body if not _is_main_guard(s) and not isinstance(s, _DEFINITIONS)]
    if len(guards) != 1 or not mains or rest:
        return []
    called = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "main"
                 for statement in guards[0].body for node in ast.walk(statement))
    return [mains[-1].lineno] if called else []


def _c137(tree):

    functions = _functions(tree)
    if len(functions) < 5:
        return []
    lengths = [f.end_lineno - f.lineno + 1 for f in functions]
    middle = statistics.median(lengths)
    if any(abs(length - middle) > 2 for length in lengths):
        return []
    return [f.lineno for f in functions]


def _c138(tree, source):



    if not PurePath(source.path).name.startswith("test_"):
        return []
    tests = [f for f in _functions(tree) if f.name.startswith("test_")]
    lines = [f.lineno for f in tests if _MIRROR_NAME.fullmatch(f.name)]
    if source.root is None:
        return lines
    for module in _imported_modules(tree, Path(source.root)):
        public = [s.name for s in module.body
                  if isinstance(s, _FUNCTIONS) and not s.name.startswith("_")]
        owned = {}
        for test in tests:
            owner = max((name for name in public if test.name == f"test_{name}"
                         or test.name.startswith(f"test_{name}_")), key=len, default=None)
            if owner is not None:
                owned.setdefault(owner, []).append(test.lineno)
        if public and all(len(owned.get(name, [])) == 1 for name in public):
            lines += [owned[name][0] for name in public]
    return lines


def _imported_modules(tree, root):


    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            names += [f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"]
    seen, modules = set(), []
    for name in names:
        base = root.joinpath(*name.split("."))
        for candidate in (base.with_name(base.name + ".py"), base / "__init__.py"):
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            module = _read_module(candidate)
            if module is not None:
                modules.append(module)
            break
    return modules


def _read_module(path):

    try:
        with tokenize.open(path) as handle:
            return _parse(handle.read())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None



_MEASURES = {"C097": _c097, "C100": _c100, "C102": _c102, "C103": _c103, "C131": _c131,
             "C132": _c132, "C133": _c133, "C134": _c134, "C135": _c135, "C136": _c136,
             "C137": _c137}
_SOURCE_MEASURES = {"C098": _c098, "C138": _c138}







_SCRIPT_LANGUAGES = ("javascript", "typescript")
_SCRIPT_FUNCTIONS = ("function_declaration", "generator_function_declaration",
                     "method_definition")
_FUNCTION_VALUES = ("arrow_function", "function_expression", "generator_function")
_NAME_NODES = ("identifier", "property_identifier", "private_property_identifier",
               "shorthand_property_identifier", "shorthand_property_identifier_pattern")
_SCRIPT_TRIVIA = ("comment", "hash_bang_line")
_EQUALITY = ("===", "!==", "==", "!=")
_DECLARATIONS = ("lexical_declaration", "variable_declaration")
_DEFINITIONS_JS = ("import_statement", "function_declaration", "generator_function_declaration",
                   "class_declaration", "abstract_class_declaration", "interface_declaration",
                   "type_alias_declaration", "enum_declaration")
_SCRIPT_MIRROR_TITLE = re.compile(r"\w+ returns expected value")
_SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs")


@dataclass
class _Script:



    tree: object
    text: str
    lines: list
    path: str
    folder: object
    document: object
    functions: list
    docstrings: set


def _script_measure(text, path, root, document):



    script, _ = extract_code.parse_script(text, path)
    if script is None or script.root.has_error:
        return None
    if document is None:
        document = extract_code.extract_text(text, path)
    source = _Script(tree=script.root, text=text, lines=_LINE_BREAK.split(text), path=path,
                     folder=root, document=document, functions=_script_functions(script.root),
                     docstrings={text.count("\n", 0, unit.span[0]) + 1
                                 for unit in document.units if unit.kind == "docstring"})

    def measure(rule_id):
        if rule_id == "C099":
            return _script_comment_lines(source)
        return _SCRIPT_MEASURES[rule_id](source) if rule_id in _SCRIPT_MEASURES else []
    return measure


def _text(node):
    return node.text.decode("utf-8")


def _line(node):
    return node.start_point[0] + 1


def _script_functions(tree):





    found = []
    for node in extract_code.walk(tree):
        if node.type in _SCRIPT_FUNCTIONS:
            name = node.child_by_field_name("name")
            if name is not None and node.child_by_field_name("body") is not None:
                found.append((name, node, node))
        elif node.type == "variable_declarator":
            name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
            if (name is not None and name.type == "identifier" and value is not None
                    and value.type in _FUNCTION_VALUES):
                found.append((name, node, value))
    return found


def _callee(call):

    target = call.child_by_field_name("function")
    if target is not None and target.type == "member_expression":
        target = target.child_by_field_name("property")
    return target if target is not None and target.type in _NAME_NODES else None


def _parameters(function):

    single = function.child_by_field_name("parameter")
    if single is not None:
        return [single]
    parameters = function.child_by_field_name("parameters")
    return [] if parameters is None else [name for child in parameters.named_children
                                          for name in extract_code.bound(child)]


def _plain_parameters(function):



    single = function.child_by_field_name("parameter")
    if single is not None:
        return [single]
    plain = []
    parameters = function.child_by_field_name("parameters")
    for child in [] if parameters is None else parameters.named_children:
        if child.type in ("required_parameter", "optional_parameter"):
            if any(c.type in ("accessibility_modifier", "override_modifier", "readonly")
                   for c in child.children):
                continue
            child = child.child_by_field_name("pattern")
        if child is not None and child.type == "assignment_pattern":
            child = child.child_by_field_name("left")
        if child is not None and child.type == "identifier":
            plain.append(child)
    return plain


def _top_declarations(tree):

    for statement in tree.named_children:
        if statement.type == "export_statement":
            statement = statement.child_by_field_name("declaration") or statement
        if statement.type in _DECLARATIONS:
            yield statement


def _script_c097(source):


    definitions = {(name.start_byte, name.end_byte) for name, _, _ in source.functions}
    calls, targets, others = {}, set(), {}
    for node in extract_code.walk(source.tree):
        callee = _callee(node) if node.type == "call_expression" else None
        if callee is not None:
            calls[_text(callee)] = calls.get(_text(callee), 0) + 1
            targets.add((callee.start_byte, callee.end_byte))
    for node in extract_code.walk(source.tree):
        key = (node.start_byte, node.end_byte)
        if node.type in _NAME_NODES and key not in targets and key not in definitions:
            others[_text(node)] = others.get(_text(node), 0) + 1
    lines = [_line(outer) for name, outer, _ in source.functions
             if calls.get(_text(name)) == 1 and _text(name) not in others]
    lines += [_line(node) for node in extract_code.walk(source.tree)
              if node.type == "as_expression" and node.children[-1].type != "const"]
    return lines


def _script_c098(source):


    lines = []
    for _, _, function in source.functions:
        body = function.child_by_field_name("body")
        if body.type != "statement_block":
            continue
        statements = [s for s in body.named_children if s.type != "comment"]
        if len(statements) >= 3 and all(
                any(not source.lines[row].strip()
                    for row in range(first.end_point[0] + 1, second.start_point[0]))
                for first, second in zip(statements, statements[1:])):
            lines.append(_line(statements[0]))
    return lines


def _script_comment_lines(source):



    code = set()
    for node in extract_code.walk(source.tree):
        if (node.child_count == 0 and node.end_byte > node.start_byte
                and node.type not in _SCRIPT_TRIVIA):
            code.update(range(node.start_point[0], node.end_point[0] + 1))
    comments = sum(source.text.count("\n", *unit.span) + 1 for unit in source.document.units
                   if unit.kind == "comment")
    return comments, len(code)


def _script_c100(source):



    lines = []
    for node in extract_code.walk(source.tree):
        if node.type == "formal_parameters":
            names = _parameters(node.parent)
        elif node.type == "arrow_function" and node.child_by_field_name("parameter"):
            names = [node.child_by_field_name("parameter")]
        elif node.type == "variable_declarator":
            names = list(extract_code.bound(node.child_by_field_name("name")))
        elif node.type == "for_in_statement":
            names = list(extract_code.bound(node.child_by_field_name("left")))
        elif node.type in ("assignment_expression", "augmented_assignment_expression"):
            left = node.child_by_field_name("left")
            names = [left] if left.type == "identifier" else []
            if (left.type == "member_expression"
                    and _text(left.child_by_field_name("object")) == "this"):
                names = [left.child_by_field_name("property")]
        else:
            continue
        lines += [_line(name) for name in names if _text(name) in GENERIC_NAMES]
    return lines


def _exports(function, exported):


    parent = function.parent
    if parent is not None and parent.type == "export_statement":
        return True
    name = function.child_by_field_name("name")
    if (function.type in _FUNCTION_VALUES and parent is not None
            and parent.type == "variable_declarator"):
        name = parent.child_by_field_name("name")
    return function.type != "method_definition" and name is not None and _text(name) in exported


def _exported_parameter(name, exported):

    node = name.parent
    while node is not None:
        if (node.type in _SCRIPT_FUNCTIONS + _FUNCTION_VALUES and _exports(node, exported)
                and _text(name) in {_text(p) for p in _parameters(node)}):
            return True
        node = node.parent
    return False


def _script_c101(source):



    exported = set(source.document.protected_names)
    lines = []
    for node in extract_code.walk(source.tree):
        if node.type != "unary_expression" or node.child_by_field_name("operator").type != "typeof":
            continue
        parent = node.parent
        if parent.type == "binary_expression":
            if parent.child_by_field_name("operator").type not in _EQUALITY:
                continue
            other = parent.child_by_field_name("right" if parent.child_by_field_name("left") == node
                                               else "left")
            if other.type == "string" and _text(other)[1:-1] == "undefined":
                continue
        elif not (parent.type == "parenthesized_expression"
                  and parent.parent.type == "switch_statement"):
            continue
        operand = node.child_by_field_name("argument")
        if _text(operand).startswith("process.env"):
            continue
        if operand.type == "identifier" and _exported_parameter(operand, exported):
            continue
        lines.append(_line(node))
    return lines


def _script_c102(source):



    lines = []
    for _, _, function in source.functions:
        reads = {_text(n) for n in extract_code.walk(function.child_by_field_name("body"))
                 if n.type in ("identifier", "shorthand_property_identifier")}
        lines += [_line(name) for name in _plain_parameters(function)
                  if not _text(name).startswith("_") and _text(name) not in reads]
    return lines


def _script_c103(source):

    return [_line(node) for node in extract_code.walk(source.tree)
            if node.type == "call_expression"
            and _text(node.child_by_field_name("function")) == "console.log"]


def _has_jsdoc(outer, docstrings):





    node = outer.parent if outer.type == "variable_declarator" else outer
    if node.parent is not None and node.parent.type == "export_statement":
        node = node.parent
    previous = node.prev_named_sibling
    while previous is not None and previous.type in ("comment", "decorator"):
        if (previous.type == "comment" and _text(previous).startswith("/**")
                and any(previous.start_point[0] < line <= previous.end_point[0] + 1
                        for line in docstrings)):
            return True
        previous = previous.prev_named_sibling
    return False


def _script_c131(source):


    private = [outer for name, outer, _ in source.functions if _text(name)[:1] in ("_", "#")]
    if len(private) < 3 or not all(_has_jsdoc(outer, source.docstrings) for outer in private):
        return []
    return [_line(outer) for outer in private]


def _script_c132(source):


    groups = {}
    for node in extract_code.walk(source.tree):
        if (node.type == "comment" and _text(node).startswith("/**")
                and extract_code.documents(node)):
            words = tuple(_WORD.findall(_text(node)[3:-2].lower())[:3])
            if len(words) == 3:
                groups.setdefault(words, []).append(_line(node))
    return [line for group in groups.values() if len(group) >= 3 for line in group]


def _script_c133(source):


    lines = []
    for node in extract_code.walk(source.tree):
        if node.type != "try_statement":
            continue
        body = [s for s in node.child_by_field_name("body").named_children if s.type != "comment"]
        if (len(body) == 1 and body[0].type in ("expression_statement",) + _DECLARATIONS
                and sum(n.type in ("call_expression", "new_expression")
                        for n in extract_code.walk(body[0])) == 1):
            lines.append(_line(node))
    return lines


def _is_store(name):

    parent = name.parent
    field = {"variable_declarator": "name", "assignment_expression": "left",
             "augmented_assignment_expression": "left", "for_in_statement": "left"}
    return parent.type in field and parent.child_by_field_name(field[parent.type]) == name


def _script_c134(source):


    stores, loads = {}, {}
    for node in extract_code.walk(source.tree):
        if node.type in ("identifier", "shorthand_property_identifier"):
            counts = stores if _is_store(node) else loads
            counts[_text(node)] = counts.get(_text(node), 0) + 1
    lines = []
    for statement in _top_declarations(source.tree):
        for declarator in statement.named_children:
            name = declarator.child_by_field_name("name")
            if (declarator.type == "variable_declarator" and name.type == "identifier"
                    and _UPPER_CASE.fullmatch(_text(name))
                    and stores.get(_text(name)) == 1 and loads.get(_text(name)) == 1):
                lines.append(_line(statement))
    return lines


def _script_c135(source):


    lines = []
    for statement in _top_declarations(source.tree):
        for declarator in statement.named_children:
            value = declarator.child_by_field_name("value")
            if declarator.type != "variable_declarator" or value is None or value.type != "object":
                continue
            entries = [e for e in value.named_children if e.type != "comment"]
            if len(entries) == 1 and entries[0].type != "spread_element":
                lines.append(_line(value))
    return lines


def _is_iife(statement):

    if statement.type != "expression_statement":
        return False
    node = statement.named_children[0]
    while node.type in ("parenthesized_expression", "unary_expression", "await_expression"):
        node = node.named_children[-1]
    if node.type != "call_expression":
        return False
    callee = node.child_by_field_name("function")
    while callee.type == "parenthesized_expression":
        callee = callee.named_children[0]
    return callee.type in _FUNCTION_VALUES


def _defines(statement):


    if statement.type == "export_statement":
        inner = statement.child_by_field_name("declaration")
        return None if inner is None else _defines(inner)
    if statement.type in _DEFINITIONS_JS:
        name = statement.child_by_field_name("name")
        return [(_text(name), statement)] if name is not None else []
    if statement.type == "expression_statement":
        return [] if statement.named_children[0].type == "string" else None
    if statement.type in _DECLARATIONS:
        values = [d.child_by_field_name("value") for d in statement.named_children
                  if d.type == "variable_declarator"]
        if all(v is not None and (v.type in _FUNCTION_VALUES or _text(v).startswith("require("))
               for v in values):
            return [(_text(d.child_by_field_name("name")), d) for d in statement.named_children
                    if d.type == "variable_declarator"]
    return None


def _script_c136(source):



    runners, rest, mains = [], [], []
    for statement in source.tree.named_children:
        if statement.type == "comment":
            continue
        defined = _defines(statement)
        if defined is not None:
            mains += [node for name, node in defined if name == "main"]
        elif _is_iife(statement) or any(
                n.type == "call_expression" and _text(n.child_by_field_name("function")) == "main"
                for n in extract_code.walk(statement)):
            runners.append(statement)
        else:
            rest.append(statement)
    if len(runners) != 1 or rest:
        return []
    if _is_iife(runners[0]):
        return [_line(runners[0])]
    return [_line(mains[-1])] if mains else []


def _script_c137(source):

    if len(source.functions) < 5:
        return []
    lengths = [outer.end_point[0] - outer.start_point[0] + 1 for _, outer, _ in source.functions]
    middle = statistics.median(lengths)
    if any(abs(length - middle) > 2 for length in lengths):
        return []
    return [_line(outer) for _, outer, _ in source.functions]


def _script_c138(source):





    name = PurePath(source.path).name
    if ".test." not in name and ".spec." not in name:
        return []
    tests = []
    for node in extract_code.walk(source.tree):
        if (node.type == "call_expression"
                and _text(node.child_by_field_name("function")) in ("it", "test")):
            arguments = node.child_by_field_name("arguments").named_children
            if arguments and arguments[0].type in ("string", "template_string"):
                tests.append((_text(arguments[0])[1:-1], _line(node)))
    lines = [line for title, line in tests if _SCRIPT_MIRROR_TITLE.fullmatch(title)]
    if source.folder is None:
        return lines
    for module in _script_imports(source):
        exported = set(extract_code.exported_names(module))
        public = [_text(n) for n, outer, _ in _script_functions(module)
                  if _text(n) in exported and outer.type != "method_definition"]
        owned = {}
        for title, line in tests:
            owner = max((n for n in public if title == n or title.startswith(n + " ")),
                        key=len, default=None)
            if owner is not None:
                owned.setdefault(owner, []).append(line)
        if public and all(len(owned.get(n, [])) == 1 for n in public):
            lines += [owned[n][0] for n in public]
    return lines


def _script_imports(source):



    specifiers = []
    for node in extract_code.walk(source.tree):
        target = None
        if node.type == "import_statement":
            target = node.child_by_field_name("source")
        elif (node.type == "call_expression"
              and _text(node.child_by_field_name("function")) == "require"):
            arguments = node.child_by_field_name("arguments").named_children
            target = arguments[0] if arguments else None
        if target is not None and target.type == "string" and _text(target)[1:-1].startswith("."):
            specifiers.append(_text(target)[1:-1])
    folder, root = Path(source.path).parent, Path(source.folder).resolve()
    seen, modules = set(), []
    for specifier in specifiers:
        base = folder / specifier
        candidates = [base] if base.suffix in _SCRIPT_SUFFIXES else []
        candidates += [base.with_name(base.name + suffix) for suffix in _SCRIPT_SUFFIXES]
        candidates += [base / f"index{suffix}" for suffix in _SCRIPT_SUFFIXES]
        candidate = next((c.resolve() for c in candidates if c.is_file()), None)
        if candidate is None or candidate in seen or not candidate.is_relative_to(root):
            continue
        seen.add(candidate)
        module = _read_script(candidate)
        if module is not None:
            modules.append(module)
    return modules


def _read_script(path):


    try:
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    script, _ = extract_code.parse_script(text, str(path))
    return None if script is None or script.root.has_error else script.root



_SCRIPT_MEASURES = {"C097": _script_c097, "C098": _script_c098, "C100": _script_c100,
                    "C101": _script_c101, "C102": _script_c102, "C103": _script_c103,
                    "C131": _script_c131, "C132": _script_c132, "C133": _script_c133,
                    "C134": _script_c134, "C135": _script_c135, "C136": _script_c136,
                    "C137": _script_c137, "C138": _script_c138}
