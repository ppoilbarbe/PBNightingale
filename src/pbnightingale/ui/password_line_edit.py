"""A password/passphrase field with a built-in show/hide toggle.

The toggle is a trailing ``QAction`` embedded directly in the line edit
(``QLineEdit.addAction()``) rather than a separate ``QToolButton`` next to
it — no extra layout needed, and it behaves like every other Qt password
reveal control.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLineEdit

from pbnightingale.resources import path as _resource


class PasswordLineEdit(QLineEdit):
    """A ``QLineEdit`` pre-configured for password entry, with a trailing show/hide toggle action built in."""

    def __init__(self, parent=None) -> None:
        """Build the field, masked by default."""
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self._toggle_action = self.addAction(
            QIcon(_resource("password-view.svg")),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self._toggle_action.setCheckable(True)
        self._toggle_action.setToolTip(_("Show password"))
        self._toggle_action.toggled.connect(self._on_toggled)

    def _on_toggled(self, visible: bool) -> None:
        """Switch the field's echo mode and toggle icon/tooltip to match.

        Parameters
        ----------
        visible
            Whether the toggle action is now checked, i.e. whether the
            password should be shown in the clear.
        """
        self.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self._toggle_action.setIcon(
            QIcon(_resource("password-mask.svg" if visible else "password-view.svg"))
        )
        self._toggle_action.setToolTip(
            _("Hide password") if visible else _("Show password")
        )
