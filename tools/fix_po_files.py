#!/usr/bin/env python3
"""Normalise PO files after pybabel update.

- Resets POT-Creation-Date to a fixed sentinel (the .pot is untracked, so its
  timestamp would otherwise generate a spurious diff on every run).
- Strips the version number from Project-Id-Version so it never needs updating.
- Removes obsolete entries (lines starting with #~) left by pybabel update.
- Removes trailing comment-only lines (e.g. # AUTO markers) left at EOF.
- Re-wraps any msgid/msgstr block with a line longer than 80 characters to
  pybabel's own 76-column layout: a translation pasted in as one long line
  (sphinx-intl keeps those as-is) is unreadable and unreviewable in a diff.

Old translations are never kept around in the .po files themselves: to recover
one, check out a previous version of the file from Git.

Called by `make translate` immediately after `pybabel update`, and with
`--docs` by `make docs-translate` after `sphinx-intl update`. Docs catalogs
live in subdirectories (LC_MESSAGES/manual/*.po) and are owned by sphinx-intl,
so `--docs` only drops obsolete entries and trailing comments: it keeps their
headers and location comments untouched.
"""

import argparse
import re
from pathlib import Path

from babel.messages.pofile import normalize, unescape

POT_DATE_SENTINEL = "2001-01-01 00:00+0000"
# Same width pybabel uses when it writes a catalog; a block is only re-wrapped
# when one of its lines exceeds _MAX_LINE, so entries already laid out by
# pybabel/sphinx-intl are left byte-for-byte untouched.
_WRAP_WIDTH = 76
_MAX_LINE = 80

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument(
    "locale_dir", nargs="?", type=Path, default=Path("src/pbnightingale/locale")
)
parser.add_argument(
    "--docs",
    action="store_true",
    help="Sphinx docs catalogs: recurse into subdirectories, only remove "
    "obsolete entries and trailing comments",
)
args = parser.parse_args()
locale_dir: Path = args.locale_dir
pattern = "*/LC_MESSAGES/**/*.po" if args.docs else "*/LC_MESSAGES/*.po"

# In PO files the header strings use literal \n (two chars: backslash + n).
# re.sub replacement strings also interpret \n, so we must use a callable to
# prevent double interpretation.
_DATE_RE = re.compile(r'"POT-Creation-Date: [^\\"]+\\n"')
_VER_RE = re.compile(r'"Project-Id-Version: [^\\"]+\\n"')
# Obsolete entries: one or more consecutive lines beginning with #~, plus the
# blank line that separates them from the next block.
_OBSOLETE_RE = re.compile(r"(?:^#~[^\n]*\n)+\n?", re.MULTILINE)
# Location comments (#: file.py:line) injected by pybabel when --no-location is omitted.
_LOCATION_RE = re.compile(r"^#:[ \t][^\n]*\n", re.MULTILINE)
# First line of a message string block: keyword, then a quoted segment.
_KEYWORD_RE = re.compile(r'^(msgctxt|msgid|msgid_plural|msgstr(?:\[\d+\])?) (".*")$')


def _rewrap(lines: list[str]) -> list[str]:
    """Re-wrap every string block containing a line longer than ``_MAX_LINE``.

    Parameters
    ----------
    lines
        The catalog's lines, without line terminators.

    Returns
    -------
    :
        The same lines, with over-long blocks re-wrapped to ``_WRAP_WIDTH``.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        match = _KEYWORD_RE.match(lines[i])
        if match is None:
            out.append(lines[i])
            i += 1
            continue
        keyword, first = match.groups()
        j = i + 1
        while j < len(lines) and lines[j].startswith('"'):
            j += 1
        block = lines[i:j]
        if any(len(line) > _MAX_LINE for line in block):
            value = "".join(unescape(seg) for seg in [first, *lines[i + 1 : j]])
            wrapped = normalize(value, width=_WRAP_WIDTH).split("\n")
            block = [f"{keyword} {wrapped[0]}", *wrapped[1:]]
        out.extend(block)
        i = j
    return out


for po in sorted(locale_dir.glob(pattern)):
    text = po.read_text(encoding="utf-8")
    new = text
    if not args.docs:
        new = _DATE_RE.sub(
            lambda _: f'"POT-Creation-Date: {POT_DATE_SENTINEL}\\n"', new
        )
        new = _VER_RE.sub(lambda _: '"Project-Id-Version: PBNightingale\\n"', new)
        new = _LOCATION_RE.sub("", new)
    new = _OBSOLETE_RE.sub("", new)
    # Strip trailing comment-only and blank lines (leftover obsolete entries,
    # # AUTO markers left by pybabel, ...).
    lines = _rewrap(new.splitlines())
    while lines and (lines[-1].lstrip().startswith("#") or lines[-1].strip() == ""):
        lines.pop()
    new = "\n".join(lines).rstrip("\n") + "\n"
    if new != text:
        po.write_text(new, encoding="utf-8")
