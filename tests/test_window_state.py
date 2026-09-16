"""Tests for ui.window_state — always against the isolated config directory."""

from __future__ import annotations

from PySide6.QtCore import QByteArray

from pbnightingale.ui import window_state


def test_load_geometry_missing_key_returns_none():
    assert window_state.load_geometry("does_not_exist") is None


def test_geometry_round_trips():
    data = QByteArray(b"some-geometry-bytes")

    window_state.save_geometry("main_window", data)

    assert window_state.load_geometry("main_window") == data


def test_load_splitter_state_missing_key_returns_none():
    assert window_state.load_splitter_state("main_window", "keys") is None


def test_splitter_state_round_trips():
    data = QByteArray(b"some-splitter-bytes")

    window_state.save_splitter_state("main_window", "keys", data)

    assert window_state.load_splitter_state("main_window", "keys") == data


def test_splitters_are_keyed_independently_per_window():
    window_state.save_splitter_state("main_window", "keys", QByteArray(b"a"))
    window_state.save_splitter_state("other_window", "keys", QByteArray(b"b"))

    assert window_state.load_splitter_state("main_window", "keys") == QByteArray(b"a")
    assert window_state.load_splitter_state("other_window", "keys") == QByteArray(b"b")


def test_load_header_state_missing_key_returns_none():
    assert window_state.load_header_state("main_window", "keys") is None


def test_header_state_round_trips():
    data = QByteArray(b"some-header-bytes")

    window_state.save_header_state("main_window", "keys", data)

    assert window_state.load_header_state("main_window", "keys") == data


def test_headers_are_keyed_independently_per_window():
    window_state.save_header_state("main_window", "keys", QByteArray(b"a"))
    window_state.save_header_state("other_window", "keys", QByteArray(b"b"))

    assert window_state.load_header_state("main_window", "keys") == QByteArray(b"a")
    assert window_state.load_header_state("other_window", "keys") == QByteArray(b"b")


def test_load_toolbar_state_missing_key_returns_none():
    assert window_state.load_toolbar_state("main_window") is None


def test_toolbar_state_round_trips():
    data = QByteArray(b"some-toolbar-bytes")

    window_state.save_toolbar_state("main_window", data)

    assert window_state.load_toolbar_state("main_window") == data
