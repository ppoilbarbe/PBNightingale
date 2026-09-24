"""About dialog."""

from __future__ import annotations

import platform

import PySide6
from PySide6.QtWidgets import QApplication, QDialog

from pbnightingale import __version__
from pbnightingale.ui.about_dialog_ui import Ui_AboutDialog


class AboutDialog(QDialog):
    """Application About dialog."""

    def __init__(self, parent=None) -> None:
        """Build the dialog, showing the app, Python and PySide versions."""
        super().__init__(parent)
        self._ui = Ui_AboutDialog()
        self._ui.setupUi(self)
        self._ui.lblVersion.setText(__version__)
        self._ui.lblPythonVersion.setText(platform.python_version())
        self._ui.lblPySideVersion.setText(PySide6.__version__)

        icon = QApplication.windowIcon()
        if not icon.isNull():
            self._ui.lblIcon.setPixmap(icon.pixmap(64, 64))
