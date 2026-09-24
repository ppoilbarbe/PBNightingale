"""Tests for the About dialog."""

from __future__ import annotations

import platform

import PySide6
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pbnightingale import __version__
from pbnightingale.resources import path as _resource
from pbnightingale.ui.about_dialog import AboutDialog


def test_shows_version_and_license(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "About PBNightingale"
    assert dialog._ui.lblVersion.text() == __version__
    assert dialog._ui.lblLicense.text() == "GPLv3"


def test_shows_python_and_pyside_versions(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.lblPythonVersion.text() == platform.python_version()
    assert dialog._ui.lblPySideVersion.text() == PySide6.__version__


def test_shows_the_application_icon_when_set(qtbot):
    previous = QApplication.windowIcon()
    QApplication.setWindowIcon(QIcon(_resource("pbnightingale.png")))
    try:
        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        assert not dialog._ui.lblIcon.pixmap().isNull()
    finally:
        QApplication.setWindowIcon(previous)


def test_no_icon_pixmap_when_application_has_none(qtbot):
    previous = QApplication.windowIcon()
    QApplication.setWindowIcon(QIcon())
    try:
        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        assert dialog._ui.lblIcon.pixmap().isNull()
    finally:
        QApplication.setWindowIcon(previous)
