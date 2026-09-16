"""Tests for pbnightingale.resources."""

from __future__ import annotations

from pathlib import Path

from pbnightingale.resources import path


def test_path_resolves_to_an_existing_svg_file():
    resolved = path("preferences-system.svg")

    assert Path(resolved).is_file()
    assert resolved.endswith("preferences-system.svg")


def test_path_is_absolute():
    assert Path(path("help-about.svg")).is_absolute()


def test_application_icon_file_exists():
    assert Path(path("pbnightingale.png")).is_file()
