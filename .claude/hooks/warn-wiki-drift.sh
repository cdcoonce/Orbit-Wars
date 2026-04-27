#!/usr/bin/env bash
# warn-wiki-drift.sh — Claude Code PostToolUse hook (Edit matcher)
#
# Warns when a src/*.py file is edited without the corresponding wiki page
# having been updated more recently than the source file.
#
# The hook receives a JSON payload on stdin with (at minimum):
#   tool_input.file_path — the absolute path of the file that was just edited
#
# Exit code is always 0 (non-blocking warning).

set -euo pipefail

# Read the full JSON payload from stdin.
payload="$(cat)"

# Extract the edited file path. The `|| file_path=""` guard ensures that a
# python3 failure (not in PATH, malformed JSON) produces an empty string and
# falls through to the early-exit check below rather than triggering set -e.
file_path="$(printf '%s' "$payload" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null)" || file_path=""

# Bail out silently if we couldn't determine the file path.
if [[ -z "$file_path" ]]; then
    exit 0
fi

# Normalise to a basename so we can do pattern matching without relying on
# the caller's cwd.  We still need to check the directory component.
dir_part="$(dirname "$file_path")"
base_name="$(basename "$file_path")"

# Only act on files whose immediate parent directory is named "src".
# Matches both "/abs/path/src/foo.py" and "src/foo.py".
if [[ "$(basename "$dir_part")" != "src" ]]; then
    exit 0
fi

# Only act on Python files.
if [[ "$base_name" != *.py ]]; then
    exit 0
fi

# Derive the module stem (filename without extension).
module_stem="${base_name%.py}"

# Derive the expected wiki page path.
# Reconstruct the repo root as everything up to (but not including) /src.
repo_root="$(dirname "$dir_part")"
wiki_page="${repo_root}/docs/wiki/src/${module_stem}.md"

# If the wiki page doesn't exist at all, always warn.
if [[ ! -f "$wiki_page" ]]; then
    echo "[wiki-drift] ${file_path} was edited — consider creating ${wiki_page}" >&2
    exit 0
fi

# Compare modification times.
# stat -f %m on macOS; stat -c %Y on Linux.
if stat --version &>/dev/null 2>&1; then
    # GNU stat (Linux)
    src_mtime="$(stat -c %Y "$file_path")"
    wiki_mtime="$(stat -c %Y "$wiki_page")"
else
    # BSD stat (macOS)
    src_mtime="$(stat -f %m "$file_path")"
    wiki_mtime="$(stat -f %m "$wiki_page")"
fi

# Warn when the wiki page is older than the source file.
if [[ "$wiki_mtime" -lt "$src_mtime" ]]; then
    rel_src="src/${base_name}"
    rel_wiki="docs/wiki/src/${module_stem}.md"
    echo "[wiki-drift] ${rel_src} was edited — consider updating ${rel_wiki}" >&2
fi

exit 0
