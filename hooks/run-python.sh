#!/bin/sh
# Runs a plugin script, with its arguments, under the first Python 3.10 or newer on PATH.
# Order: python, python3, then the Windows launcher py -3. `python` comes first since it
# is the one packages are most often installed into, and on Windows the `python3` alias
# can be a separate Microsoft Store install. A candidate that fails the version check,
# such as the Store stub, the Python 2 an old Mac carries or a stock macOS 3.9, is skipped.
# The check hands back sys.executable, the interpreter's own path, and that path is
# remembered in the plugin's data folder, since the checks cost about 200 ms a call on
# Windows and a version manager's shim can name another Python in another folder. It is
# looked for again once that path is gone.
# With no script or no interpreter it fails open: it prints a notice and exits 0, since a
# hook's exit 2 is a block. A hook prints the notice at most once a day.
# Each command line ends in a comment and no line is blank, so a checkout that turns the
# line endings into CRLF leaves every carriage return inside a comment, and any sh runs it.
target="$1" #
shift #
data="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/super-humanizer}" #
memo="$data/python-path" #
#
notice() { #
  case "$target" in #
    *gate_*.py) #
      stamp="$data/notice-$(date +%Y%m%d 2>/dev/null)" #
      [ -f "$stamp" ] && exit 0 #
      { [ -d "$data" ] || mkdir -p "$data"; true > "$stamp"; } 2>/dev/null #
      ;; #
  esac #
  printf '{"systemMessage": "super-humanizer: %s, so the writing guard is off. %s"}\n' "$1" "$2" #
  exit 0 #
} #
#
[ -f "$target" ] || notice "the plugin script is missing" "Reinstall the plugin." #
if [ -f "$memo" ]; then #
  read -r found < "$memo" #
  if [ -n "$found" ] && [ -x "$found" ]; then #
    exec "$found" "$target" "$@" #
  fi #
fi #
for cand in python python3 py; do #
  command -v "$cand" >/dev/null 2>&1 || continue #
  flag= #
  [ "$cand" = py ] && flag=-3 #
  found=$("$cand" $flag -c 'import sys; sys.version_info >= (3, 10) or sys.exit(1); sys.stdout.write(sys.executable)' </dev/null 2>/dev/null) || continue #
  [ -n "$found" ] || continue #
  { [ -d "$data" ] || mkdir -p "$data"; printf '%s\n' "$found" > "$memo"; } 2>/dev/null #
  exec "$found" "$target" "$@" #
done #
notice "no Python 3.10 or newer was found" "Install Python 3.10 or newer and restart Claude Code." #
