"""Tests for the PasswordLineEdit show/hide toggle."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from pbnightingale.ui.password_line_edit import PasswordLineEdit


def test_starts_masked(qtbot):
    field = PasswordLineEdit()
    qtbot.addWidget(field)

    assert field.echoMode() == QLineEdit.EchoMode.Password
    assert field._toggle_action.isChecked() is False


def test_toggling_reveals_and_hides_again(qtbot):
    field = PasswordLineEdit()
    qtbot.addWidget(field)

    field._toggle_action.trigger()
    assert field.echoMode() == QLineEdit.EchoMode.Normal

    field._toggle_action.trigger()
    assert field.echoMode() == QLineEdit.EchoMode.Password


def test_text_survives_toggling(qtbot):
    field = PasswordLineEdit()
    qtbot.addWidget(field)
    field.setText("s3cret")

    field._toggle_action.trigger()

    assert field.text() == "s3cret"
