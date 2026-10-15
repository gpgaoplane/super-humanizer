


import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import extract_code, globmatch, office

MARKER_NAME = ".humanize.json"
SCHEMA_VERSION = 1
RULEBOOKS = ("general", "strict")

DEFAULTS = {
    "version": 1,
    "rulebook": "general",
    "voice": False,
    "spelling": "any",
    "include": ["**/*.md", "**/*.txt", "**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx",
                "**/*.mjs", "**/*.cjs", "**/*.mts", "**/*.cts", "**/*.pptx", "**/*.xlsx",
                "**/*.docx"],
    "exclude": ["**/node_modules/**", "vendor/**", "**/*.min.js", "tests/fixtures/**",
                "requirements*.txt", "*.lock",
                "**/dist/**", "**/build/**", "coverage/**", ".next/**", ".vercel/**",
                "**/*.humanize-report.md", "**/*.humanize-candidates.json",
                "**/*.humanize-verdicts.json", "**/*.humanize-verdicts.applied-*.json",
                "**/*.humanize-second.json", "**/*.humanize-second.applied-*.json",
                "**/*.humanized.*", "**/*.humanize-tmp.*", "**/*.humanize-retro*.json",
                "**/*.humanize-retro-report.md", "**/~$*"],
    "prompt_globs": [".claude/**/*.md", ".agent/**/*.md", ".agents/**/*.md", ".codex/**/*.md",
                      ".continue/**/*.md", ".cursor/**/*.md", ".gemini/**/*.md",
                      ".opencode/**/*.md", ".pi/**/*.md", ".roo/**/*.md", ".windsurf/**/*.md",
                      "**/AGENTS.md", "**/SKILL.md", "**/CLAUDE.md"],
    "protect": [],
    "second_reader": "auto",
    "imperfection": False,
    "office_write": office.COPY,
    "refine_cap": 0.35,
}

_LIST_KEYS = {"include", "exclude", "prompt_globs", "protect"}
_PROSE_EXTENSIONS = (".md", ".markdown", ".txt")



CASE_FOLD_PLATFORMS = sys.platform in ("win32", "darwin")


def _has_git(directory):
    return (directory / ".git").exists()


def find_marker(start):






    current = start
    while True:
        candidate = current / MARKER_NAME
        if candidate.exists():
            return candidate
        if _has_git(current):
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def repo_root(start):

    current = start
    while True:
        if _has_git(current):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_marker(path):































    if path is None:
        return copy.deepcopy(DEFAULTS), []
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if raw.get("version") != SCHEMA_VERSION:
        warning = f"marker version {raw.get('version')!r} is not supported, using defaults"
        return copy.deepcopy(DEFAULTS), [warning]

    settings = copy.deepcopy(DEFAULTS)
    warnings = []
    for key, value in raw.items():
        if key == "version":
            continue
        if key not in DEFAULTS:
            warnings.append(f"unknown marker key {key!r} is ignored")
            continue
        if key in _LIST_KEYS and isinstance(value, dict):
            merged = list(DEFAULTS[key])
            operations = {}
            for operation in ("add", "remove"):
                entries = value.get(operation, [])
                if not isinstance(entries, list):
                    warnings.append(f"marker key {key!r} has {operation} set to {entries!r}, "
                                    "which is not a list, so it is ignored")
                    entries = []
                operations[operation] = entries
            for entry in operations["add"]:
                merged.append(entry)
            for entry in operations["remove"]:
                if entry in DEFAULTS[key]:
                    merged.remove(entry)
                else:
                    warnings.append(f"{entry!r} in {key} remove is not a default entry")
            settings[key] = merged
        elif key in _LIST_KEYS and not isinstance(value, list):
            warnings.append(f"marker key {key!r} holds {value!r}, not a list or an "
                             "add/remove object, using the default")
        else:
            settings[key] = value

    if settings["rulebook"] not in RULEBOOKS:
        warnings.append(f"marker key 'rulebook' holds {settings['rulebook']!r}, which "
                        f"names no shipped rulebook, using {DEFAULTS['rulebook']!r}. The "
                        f"two that ship are {', '.join(RULEBOOKS)}")
        settings["rulebook"] = DEFAULTS["rulebook"]

    if settings["office_write"] not in office.OFFICE_WRITES:
        warnings.append(f"marker key 'office_write' holds {settings['office_write']!r}, "
                        "which names no office write mode, using "
                        f"{DEFAULTS['office_write']!r}. The two are "
                        f"{' and '.join(office.OFFICE_WRITES)}")
        settings["office_write"] = DEFAULTS["office_write"]

    if settings["voice"] is not False and settings["voice"] != "mine":
        warnings.append(f"marker key 'voice' holds {settings['voice']!r}, which is neither "
                        'false nor "mine", using false')
        settings["voice"] = DEFAULTS["voice"]

    cap = settings["refine_cap"]
    if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not 0 < cap <= 1:
        warnings.append(f"marker key 'refine_cap' holds {cap!r}, which is no number above 0 "
                        f"and at most 1, using {DEFAULTS['refine_cap']!r}")
        settings["refine_cap"] = DEFAULTS["refine_cap"]

    if settings["spelling"] != "any":
        warnings.append("no spelling rule ships in this version, so the key changes nothing")
    if settings["imperfection"]:
        warnings.append("the imperfection mode is not built in this version, so the key "
                         "changes nothing")
    return settings, warnings


def route(settings, marker_dir, file_path):








    fold = (lambda text: text.casefold()) if CASE_FOLD_PLATFORMS else (lambda text: text)
    prefix = fold(marker_dir.as_posix() + "/")
    folded_path = fold(file_path)
    if not folded_path.startswith(prefix):
        return "no-include"
    relative = folded_path[len(prefix):]

    for pattern in settings["exclude"]:
        if globmatch.matches(fold(pattern), relative):
            return "exclude"
    if not any(globmatch.matches(fold(pattern), relative) for pattern in settings["include"]):
        return "no-include"


    suffix = Path(relative).suffix
    if suffix in office.SUFFIXES:
        return "office"
    if suffix == office.PDF_SUFFIX:
        return "pdf"
    for pattern in settings["prompt_globs"]:
        if globmatch.matches(fold(pattern), relative):
            return "prompt"

    if suffix in _PROSE_EXTENSIONS:
        return "prose"
    if extract_code.language_of(relative) is not None:
        return "code"
    return "other"


def excludes_folder(settings, marker_dir, folder_path):




    fold = (lambda text: text.casefold()) if CASE_FOLD_PLATFORMS else (lambda text: text)
    prefix = fold(marker_dir.as_posix() + "/")
    folded_path = fold(folder_path)
    if not folded_path.startswith(prefix):
        return False
    relative = folded_path[len(prefix):] + "/"
    return any(pattern.endswith("**") and globmatch.matches(fold(pattern), relative)
               for pattern in settings["exclude"])


def turn_on(root, rulebook=None):





    if root is None:
        return None
    path = root / MARKER_NAME
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        data["version"] = SCHEMA_VERSION
        if rulebook is not None:
            data["rulebook"] = rulebook
    else:
        data = {"version": SCHEMA_VERSION, "rulebook": rulebook or "general"}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def turn_off(root):

    if root is None:
        return False
    path = root / MARKER_NAME
    if path.exists():
        path.unlink()
        return True
    return False


def add_protect(root, pattern, regex=False):








    if root is None:
        return None
    path = root / MARKER_NAME
    if not path.exists():
        raise FileNotFoundError(f"no marker at {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    entry = {"regex": pattern} if regex else pattern
    protect = data.get("protect")
    if protect is None:
        data["protect"] = [entry]
    elif isinstance(protect, list):
        protect.append(entry)
    elif isinstance(protect, dict):
        add = protect.setdefault("add", [])
        if not isinstance(add, list):
            raise ValueError(f"marker key 'protect' has add set to {add!r}, "
                             "which is not a list")
        add.append(entry)
    else:
        raise ValueError(f"marker key 'protect' holds {protect!r}, not a list or an add/remove object")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(prog="marker.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    on_parser = subparsers.add_parser("on")
    on_parser.add_argument("--rulebook", choices=RULEBOOKS)

    subparsers.add_parser("off")

    protect_parser = subparsers.add_parser("protect")
    protect_parser.add_argument("pattern")
    protect_parser.add_argument("--regex", action="store_true")

    args = parser.parse_args(argv)

    root = repo_root(Path.cwd().resolve())
    if root is None:
        print("no repository found. marker.py needs a .git file or folder above "
              "the working directory.", file=sys.stderr)
        return 1

    if args.command == "on":
        path = turn_on(root, args.rulebook)
        print(path)
        return 0
    if args.command == "off":
        turn_off(root)
        print(root / MARKER_NAME)
        return 0
    if args.command == "protect":
        try:
            add_protect(root, args.pattern, regex=args.regex)
        except FileNotFoundError:
            print(f"no marker at {root / MARKER_NAME}. Run 'on' to create one first.",
                  file=sys.stderr)
            return 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(root / MARKER_NAME)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
