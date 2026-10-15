

























import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from shutil import which

from scripts import extract_code

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not run"
NOT_APPLICABLE = "not applicable"

REVERTED = "reverted"


NO_FORMATTER = "no formatter configured"
NO_TEST_SUITE = "no test suite found"


NO_FORMATTER_FOR_FILES = "no configured formatter checks a file this run reads"

NO_PYTEST = "pytest is not installed for {python}"


_VENV_PYTHON = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")


_FINDS = "import importlib.util, sys; sys.exit(importlib.util.find_spec(sys.argv[1]) is None)"
_FINDS_TIMEOUT = 30



_KILL_GRACE = 10

_OWN_SESSION = {} if os.name == "nt" else {"start_new_session": True}



_NPM_ENV = {"CI": "1"}

_RUFF_TABLE = re.compile(r"^\[tool\.ruff", re.MULTILINE)
_BLACK_TABLE = re.compile(r"^\[tool\.black\]", re.MULTILINE)
_PYTEST_TABLE = re.compile(r"^\[tool\.pytest\.ini_options\]", re.MULTILINE)
_PYTEST_SECTION = re.compile(r"^\[pytest\]", re.MULTILINE)
_PASSED = re.compile(r"(\d+) passed")



_PRETTIER_FILES = (".prettierrc", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.yml",
                   ".prettierrc.json5", ".prettierrc.toml", ".prettierrc.js", ".prettierrc.cjs",
                   ".prettierrc.mjs", "prettier.config.js", "prettier.config.cjs",
                   "prettier.config.mjs")



_PRETTIER = ["prettier", "--check", "--no-error-on-unmatched-pattern"]



_RUFF = ["format", "--check", "--force-exclude"]



_NAMES_BUDGET = 4000


_LOCAL_PRETTIER = ("node_modules", ".bin", "prettier.cmd" if os.name == "nt" else "prettier")

_NPM_INIT_TEST = 'echo "Error: no test specified" && exit 1'


_SCRIPT_TEST_FOLDERS = frozenset({"test", "tests", "__tests__"})
_SCRIPT_TEST_FILE = re.compile(r"[.](?:test|spec)[.]")


_COLOR = re.compile(r"\x1b\[[0-9;]*m")


_PRETTIER_WARN = "[warn] "
_PRETTIER_SUMMARY = "[warn] Code style issues"
_PRETTIER_ERROR = "[error] "

_PRETTIER_NAMES = 3


_TAP_FAILURE = re.compile(r"not ok\b")
_ERROR_LINE = re.compile(r"\w*Error\b")



_JEST_SUMMARY = re.compile(r"Tests:\s+\d+ failed\b")


_NO_TESTS_COLLECTED = 5

_TEMP_SUFFIX = ".humanize-tmp"


@dataclass
class Validation:

    formatter: tuple
    tests: tuple


def _text(path):

    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _package(root):


    try:
        data = json.loads(_text(Path(root) / "package.json") or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _test_script(package):


    scripts = package.get("scripts")
    script = scripts.get("test") if isinstance(scripts, dict) else None
    return isinstance(script, str) and script.strip() not in ("", _NPM_INIT_TEST)


def _holds_python(folder):


    return folder.is_dir() and any(folder.rglob("*.py"))


def _is_prettier(command):

    return Path(command[0]).stem == "prettier"


def _checks(command):



    if _is_prettier(command):
        return "script"
    tool = command[2] if command[1:2] == ["-m"] else Path(command[0]).stem
    return "python" if tool in ("ruff", "black") else None


def _is_pytest(command):
    return command[1:3] == ["-m", "pytest"]


def interpreter(root):



    for folder in (Path(root) / ".venv", os.environ.get("VIRTUAL_ENV")):
        if folder and Path(folder).joinpath(*_VENV_PYTHON).is_file():
            return str(Path(folder).joinpath(*_VENV_PYTHON))
    return sys.executable


def _finds(python, name):




    if python == sys.executable:
        return find_spec(name) is not None
    try:
        done = subprocess.run([python, "-c", _FINDS, name], capture_output=True,
                              timeout=_FINDS_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def _tool(name, python):





    if python != sys.executable and _finds(python, name):
        return [python, "-m", name]
    if which(name) is None and find_spec(name) is not None:
        return [sys.executable, "-m", name]
    return [name]


def discover(root):
















    root = Path(root)
    python = interpreter(root)
    pyproject = _text(root / "pyproject.toml")
    package = _package(root)
    formatters = []
    if _RUFF_TABLE.search(pyproject) or (root / "ruff.toml").is_file():
        formatters.append(_tool("ruff", python) + _RUFF)
    elif _BLACK_TABLE.search(pyproject):
        formatters.append(_tool("black", python) + ["--check"])
    dev = package.get("devDependencies")
    if (any((root / name).is_file() for name in _PRETTIER_FILES) or "prettier" in package
            or (isinstance(dev, dict) and "prettier" in dev)):
        local = root.joinpath(*_LOCAL_PRETTIER)
        formatters.append([str(local) if local.is_file() else _PRETTIER[0], *_PRETTIER[1:]])
    scripted = _test_script(package)
    suites = []
    if ((root / "pytest.ini").is_file() or _PYTEST_SECTION.search(_text(root / "tox.ini"))
            or _PYTEST_TABLE.search(pyproject)
            or (not scripted and (_holds_python(root / "tests")
                                  or _holds_python(root / "checks")))):
        suites.append([python, "-m", "pytest", "-q"])
    if scripted:
        suites.append(["npm", "test"])
    return {"formatter": formatters or None, "tests": suites or None}


def _shown(command):



    program = command[0]
    if program == sys.executable or not os.path.isabs(program):
        program = Path(program).stem
    return " ".join([program] + command[1:])


def _lines(output):
    return [line.strip() for line in output.splitlines() if line.strip()]


def _prettier_failure(lines):


    names = [line[len(_PRETTIER_WARN):] for line in lines
             if line.startswith(_PRETTIER_WARN) and not line.startswith(_PRETTIER_SUMMARY)]
    if names:
        more = len(names) - _PRETTIER_NAMES
        return ("would reformat " + ", ".join(names[:_PRETTIER_NAMES])
                + (f" and {more} more" if more > 0 else ""))
    errors = [line[len(_PRETTIER_ERROR):] for line in lines if line.startswith(_PRETTIER_ERROR)]
    return errors[0] if errors else (lines[-1] if lines else None)


def _npm_failure(lines):




    for pattern in (_TAP_FAILURE, _ERROR_LINE, _JEST_SUMMARY):
        found = [line for line in lines if pattern.match(line)]
        if found:
            return " ".join(found[0].split())
    kept = [line for line in lines if not line.startswith((">", "#"))]
    return kept[-1] if kept else None


def _failure_line(command, done):



    if _is_prettier(command) or command[:2] == ["npm", "test"]:
        lines = _lines(_COLOR.sub("", done.stdout + "\n" + done.stderr))
        return _prettier_failure(lines) if _is_prettier(command) else _npm_failure(lines)
    lines = _lines(done.stdout) or _lines(done.stderr)
    return lines[-1] if lines else None


def _plural(number, noun):
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _kill_tree(process):



    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           capture_output=True, timeout=_KILL_GRACE, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    process.kill()


def _execute(argv, cwd, timeout, env=None):








    process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", env=env,
                               **_OWN_SESSION)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        try:
            process.communicate(timeout=_KILL_GRACE)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _run(command, root, timeout, counts_tests, shown=None):




    shown = shown or _shown(command)
    program = command[0] if os.path.isabs(command[0]) else which(command[0])
    if program is None:
        return NOT_RUN, f"{shown}, {command[0]} is not on the path"
    env = {**os.environ, **_NPM_ENV} if Path(command[0]).stem == "npm" else None
    try:
        done = _execute([program, *command[1:]], cwd=str(root), timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return NOT_RUN, f"{shown}, stopped after {_plural(timeout, 'second')}"
    except FileNotFoundError:
        return NOT_RUN, f"{shown}, {command[0]} is not on the path"
    except OSError as exc:
        return NOT_RUN, f"{shown}, could not start: {type(exc).__name__}: {exc}"
    lines = _lines(done.stdout) or _lines(done.stderr)
    if counts_tests and done.returncode == _NO_TESTS_COLLECTED:
        return NOT_RUN, f"{shown}, which collected no test"
    if done.returncode != 0:
        line = _failure_line(command, done)
        return FAIL, f"{shown}, {line}" if line else shown
    if counts_tests:
        found = [m for m in map(_PASSED.search, reversed(lines[-3:])) if m]
        if not found:
            return PASS, f"{shown}, count not read"
        return PASS, f"{shown}, {_plural(int(found[0].group(1)), 'test')}"
    return PASS, shown


def _combined(results):




    states = {state for state, _ in results}
    state = FAIL if FAIL in states else NOT_RUN if NOT_RUN in states else PASS
    return state, ", and ".join(scope for _, scope in results)


def _suite(command, root, timeout):





    if _is_pytest(command) and not _finds(command[0], "pytest"):
        return NOT_RUN, NO_PYTEST.format(python=command[0])
    return _run(command, root, timeout, counts_tests=_is_pytest(command))


def _named(command, names, root, timeout):




    more = len(names) - _PRETTIER_NAMES
    shown = (_shown(command + names[:_PRETTIER_NAMES])
             + (f" and {more} more" if more > 0 else ""))
    batches = [[]]
    for name in names:
        if batches[-1] and len(" ".join(batches[-1] + [name])) > _NAMES_BUDGET:
            batches.append([])
        batches[-1].append(name)
    results = [_run(command + batch, root, timeout, counts_tests=False, shown=shown)
               for batch in batches]
    state = _combined(results)[0]
    return state, next(scope for each, scope in results if each == state)


def run(root, files=(), timeout=120):






    commands = discover(root)
    base = Path(root).resolve()
    names = {"script": [], "python": []}
    for path in files:
        language = extract_code.language_of(path)
        if language is not None:
            names["python" if language == "python" else "script"].append(
                Path(path).resolve().relative_to(base).as_posix())
    formatter = (NOT_APPLICABLE, NO_FORMATTER)
    if commands["formatter"]:
        results = [_run(command, root, timeout, counts_tests=False) if _checks(command) is None
                   else _named(command, names[_checks(command)], root, timeout)
                   for command in commands["formatter"]
                   if _checks(command) is None or names[_checks(command)]]
        formatter = _combined(results) if results else (NOT_APPLICABLE, NO_FORMATTER_FOR_FILES)
    tests = (_combined([_suite(command, root, timeout) for command in commands["tests"]])
             if commands["tests"] else (NOT_RUN, NO_TEST_SUITE))
    return Validation(formatter=formatter, tests=tests)


def run_roots(groups, timeout=120):





    if len(groups) == 1:
        _, root, files = groups[0]
        return run(root, files, timeout)
    validations = [(name, run(root, files, timeout)) for name, root, files in groups]
    stages = {}
    for stage in ("formatter", "tests"):
        results = [(getattr(each, stage)[0], f"{name}: {getattr(each, stage)[1]}")
                   for name, each in validations]
        state, scope = _combined(results)
        if all(each == NOT_APPLICABLE for each, _ in results):
            state = NOT_APPLICABLE
        stages[stage] = (state, scope)
    return Validation(**stages)


def _script_tests(root):



    found = []
    for folder, names, files in os.walk(root):
        names[:] = sorted(n for n in names if n != "node_modules" and not n.startswith("."))
        inside = _SCRIPT_TEST_FOLDERS.intersection(Path(folder).relative_to(root).parts)
        found += [Path(folder) / name for name in sorted(files)
                  if inside or _SCRIPT_TEST_FILE.search(name)]
    return found


def test_texts(root):





    paths = []
    for folder in ("tests", "checks"):
        base = Path(root) / folder
        if base.is_dir():
            paths += [path for path in sorted(base.rglob("*")) if path.is_file()]
    if (Path(root) / "package.json").is_file():
        seen = set(paths)
        paths += [path for path in _script_tests(Path(root)) if path not in seen]
    return [_text(path) for path in paths if ".humanize-" not in path.name]


def referenced(root, units, texts=None):




    if not units:
        return []
    if texts is None:
        texts = test_texts(root)
    return [unit for unit in units if unit.text and any(unit.text in text for text in texts)]


def root_of(path, marker_path=None):






    if marker_path is not None:
        return Path(marker_path).resolve().parent
    start = Path(path).resolve()
    start = start if start.is_dir() else start.parent
    try:
        home = Path.home().resolve()
    except RuntimeError:
        home = None
    for folder in (start, *start.parents):
        if home is not None and (folder == home or folder in home.parents):
            break
        if ((folder / "pyproject.toml").is_file() or (folder / "package.json").is_file()
                or (folder / ".git").exists()):
            return folder
    return start


def package_root(path, top):




    top = Path(top).resolve()
    folder = Path(path).resolve()
    folder = folder if folder.is_dir() else folder.parent
    while top in folder.parents:
        if (folder / "pyproject.toml").is_file() or (folder / "package.json").is_file():
            return folder
        folder = folder.parent
    return top


def revert(path, original_bytes):




    path = Path(path)
    temp = None
    try:
        handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
                                        suffix=_TEMP_SUFFIX)
        with os.fdopen(handle, "wb") as stream:
            stream.write(original_bytes)
        os.replace(temp, path)
    except OSError:
        if temp is not None and os.path.exists(temp):
            os.unlink(temp)
        return False
    return True
