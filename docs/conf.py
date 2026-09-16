"""Sphinx configuration for PBNightingale."""

import os
import re
import sys
from pathlib import Path

# Make the src layout importable by autodoc without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pbnightingale import __version__

project = "PBNightingale"
author = "Marcel Spock"
copyright = "2026, PBMou"
release = __version__
version = ".".join(__version__.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/pbnightingale.png"
html_favicon = "_static/pbnightingale.png"
html_theme_options = {
    "navigation_depth": 4,
    "titles_only": False,
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_format = "short"

# Mock PySide6 and every generated *_ui.py module so autodoc never triggers
# PySide6's shibokensupport import hooks, which cause inspect.unwrap() to
# loop on MagicMock wrappers and raise ValueError. The *_ui.py list is
# discovered from the source tree rather than hardcoded — this app has ~25
# dialogs, each with its own hand-written layout module (see CODING.md,
# "Project layout"), and the list grows with every new dialog.
_UI_ROOT = Path(__file__).parent.parent / "src" / "pbnightingale" / "ui"
autodoc_mock_imports = [
    "PySide6",
    *(f"pbnightingale.ui.{path.stem}" for path in sorted(_UI_ROOT.glob("*_ui.py"))),
]

# key_list_view.py, import_key_dialog.py and (transitively, via the former)
# search_key_dialog.py cannot be autodoc'd even with PySide6 mocked above:
# each defines a module-level `Qt.ItemDataRole.UserRole [+ N]` constant
# (custom QTreeWidgetItem data roles), and evaluating `+` against the mock
# object standing in for `Qt.ItemDataRole.UserRole` raises inside PySide6's
# own shiboken import hook rather than cleanly — which, once triggered,
# poisons every *other* module's mocked import for the rest of this
# process with a spurious "wrapper loop when unwrapping" ValueError.
# Verified empirically (isolated to exactly these three, reproducibly,
# across repeated clean builds). Their automodule sections are left out
# of api.rst entirely rather than added to autodoc_mock_imports — mocking
# a real logic module would only render an empty section, no better than
# omitting it outright. See CODING.md, "Packaging & docs".

napoleon_google_docstring = False
napoleon_numpy_docstring = False

# Kept True deliberately, even though api.rst uses plain
# `.. automodule::` directives with no `.. autosummary::` tables (so this
# setting has no effect on the rendered output either way). Flipping it to
# False was tried and made the shiboken "wrapper loop when unwrapping"
# poisoning (see the mock-imports comment above) considerably worse —
# empirically, autosummary's own extra scan of the doctree cascades the
# poisoning from the 3 known offenders (key_list_view.py,
# import_key_dialog.py, search_key_dialog.py) to ~19 unrelated modules
# instead. Not fully root-caused; kept as found since it demonstrably
# works. See CODING.md, "Packaging & docs".
autosummary_generate = True

# ---------------------------------------------------------------------------
# Internationalisation — narrative pages (index.rst, manual/) are
# translated via sphinx-intl; api.rst and changelog.rst stay English-only
# (autodoc output and a changelog are never worth translating — see
# CLAUDE.md, "CHANGELOG — language").
# ---------------------------------------------------------------------------

locale_dirs = ["locale/"]
gettext_compact = False

# Read the Docs injects READTHEDOCS_LANGUAGE per-project (see "Packaging &
# docs" in CODING.md — one RTD project per language, each pinned to a
# language in its own Admin → Settings). Falls back to English, this
# project's source language (CLAUDE.md — `full-en` mode), for local builds.
language = os.environ.get("READTHEDOCS_LANGUAGE", "en")

# ---------------------------------------------------------------------------
# Changelog — generated from CHANGELOG.md at build time
# ---------------------------------------------------------------------------

_H2_DATED = re.compile(r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$")
_H2_UNRELEASED = re.compile(r"^## \[Unreleased\]\s*$")
_H3 = re.compile(r"^### (.+)$")
_LINK = re.compile(r"^\[[^\]]+\]:\s*https?://")

_UNDERLINES = {1: "=", 2: "-", 3: "^"}


def _md_inline(text: str) -> str:
    """Convert inline Markdown to RST (bold, inline code, backticks)."""
    text = re.sub(r"`([^`]+)`", r"``\1``", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"**\1**", text)
    return text


def _heading(out: list[str], title: str, level: int) -> None:
    """Append a RST heading with exactly one blank line before it."""
    char = _UNDERLINES[level]
    while out and out[-1] == "":
        out.pop()
    out.append("")
    out.append(title)
    out.append(char * len(title))


def _convert_section(title: str, body_lines: list[str]) -> list[str] | None:
    """Render one ``## [...]`` section (h3 subsections + content) to RST lines.

    Returns ``None`` if the section has no actual content under any of its
    subsections (e.g. an "Unreleased" section with only empty Added/Changed
    headings), so callers can drop it instead of emitting orphan titles.
    """
    out: list[str] = []
    has_content = False

    # Inline conversion runs on the *whole* body at once, not line by line:
    # a Markdown inline code span can wrap its closing backtick onto the
    # next physical line within the same list item (this CHANGELOG.md does
    # that routinely), and `[^`]+` matches across the embedded newline just
    # fine — a per-line regex pass never sees the matching backtick at all,
    # leaving stray single backticks that break the generated RST.
    converted_lines = _md_inline("\n".join(body_lines)).split("\n")

    for line in converted_lines:
        m3 = _H3.match(line)
        if m3:
            _heading(out, m3.group(1), 3)
            continue

        if line == "" and out and out[-1] == "":
            continue
        if line.strip():
            has_content = True
        out.append(line)

    if not has_content:
        return None

    heading: list[str] = []
    _heading(heading, title, 2)
    return heading + out


def _convert_changelog(md_path: Path) -> str:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []

    for line in lines:
        # Skip reference link lines at the bottom
        if _LINK.match(line):
            continue

        m2 = _H2_DATED.match(line)
        m2_unreleased = _H2_UNRELEASED.match(line)
        if m2 or m2_unreleased:
            if current_title is not None:
                sections.append((current_title, current_body))
            current_title = f"{m2.group(1)} ({m2.group(2)})" if m2 else "Unreleased"
            current_body = []
            continue

        if current_title is not None:
            current_body.append(line)

    if current_title is not None:
        sections.append((current_title, current_body))

    out: list[str] = []
    for title, body in sections:
        rendered = _convert_section(title, body)
        if rendered is not None:
            out.extend(rendered)

    header = ["Changelog", "=" * len("Changelog")]
    preamble = [
        "",
        "All notable changes to this project are documented here.",
        (
            "The format is based on `Keep a Changelog"
            " <https://keepachangelog.com/en/1.1.0/>`_."
        ),
    ]
    return "\n".join(header + preamble + out).rstrip() + "\n"


_DOCS_DIR = Path(__file__).parent
_CHANGELOG_MD = _DOCS_DIR.parent / "CHANGELOG.md"
_CHANGELOG_RST = _DOCS_DIR / "changelog.rst"

_CHANGELOG_RST.write_text(_convert_changelog(_CHANGELOG_MD), encoding="utf-8")

# ---------------------------------------------------------------------------
# Logo / favicon — copied from the app's own icon at build time, so the
# artwork has a single source of truth (src/pbnightingale/resources/
# pbnightingale.png). PBNightingale has no root SVG logo (its SVGs are
# all per-action toolbar glyphs, not a standalone mark), so the raster
# app icon is copied as-is — no viewBox/width fixup needed.
# ---------------------------------------------------------------------------

_APP_ICON = (
    _DOCS_DIR.parent / "src" / "pbnightingale" / "resources" / "pbnightingale.png"
)
_STATIC_ICON = _DOCS_DIR / "_static" / "pbnightingale.png"

_STATIC_ICON.write_bytes(_APP_ICON.read_bytes())

# ---------------------------------------------------------------------------
# Toolbar icons — copied from resources/*.svg at build time (same single-
# source-of-truth reasoning as the app icon above) so the manual can put
# the actual button glyph next to the paragraph explaining that button,
# letting the reader match prose to what they'll see in the app itself.
# Exposed as global `|icon-<stem>|` substitutions (`rst_epilog`, so every
# page gets them with no per-file `.. |...| image::` boilerplate) styled
# by the `.action-icon` CSS rule in _static/custom.css to float like a
# drop cap at the start of the paragraph that names that action.
# ---------------------------------------------------------------------------

_ICONS_SRC = _DOCS_DIR.parent / "src" / "pbnightingale" / "resources"
_ICONS_STATIC = _DOCS_DIR / "_static" / "icons"
_ICONS_STATIC.mkdir(exist_ok=True)

_icon_substitutions = []
for _svg in sorted(_ICONS_SRC.glob("*.svg")):
    (_ICONS_STATIC / _svg.name).write_bytes(_svg.read_bytes())
    _icon_substitutions.append(
        f".. |icon-{_svg.stem}| image:: /_static/icons/{_svg.name}\n"
        f"   :class: action-icon\n"
        f"   :alt: \n"
    )

rst_epilog = "\n" + "\n".join(_icon_substitutions)
