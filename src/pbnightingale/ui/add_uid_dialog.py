"""Add User ID dialog.

Adds a new identity (name/email/comment) to a key already in the keyring
(the key must have its secret part available).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.add_uid_dialog_ui import Ui_AddUidDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


def _looks_like_email(value: str) -> bool:
    """Return a loose heuristic check for whether *value* looks like an email.

    Parameters
    ----------
    value
        The candidate address.

    Returns
    -------
    :
        ``True`` if *value* has a non-empty local part and a domain
        containing a dot that doesn't start with one.
    """
    user, _sep, domain = value.partition("@")
    return bool(user) and "." in domain and not domain.startswith(".")


class AddUidDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for adding a new user ID to a key."""

    def __init__(self, fingerprint: str, parent=None) -> None:
        """Build the dialog for the key identified by *fingerprint*.

        Parameters
        ----------
        fingerprint
            The key to add the identity to.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._ui = Ui_AddUidDialog()
        self._ui.setupUi(self)
        self._init_geometry("add_uid_dialog")
        self._init_key_operation()

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.txtName.textChanged.connect(self._sync_ok_enabled)
        self._ui.txtEmail.textChanged.connect(self._sync_ok_enabled)

        self._ui.buttonBox.accepted.connect(self._on_add)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _sync_ok_enabled(self) -> None:
        """Enable OK once the name is non-empty and the email looks valid."""
        self._ok_button.setEnabled(
            bool(self._ui.txtName.text().strip())
            and _looks_like_email(self._ui.txtEmail.text().strip())
        )

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.txtName.setEnabled(enabled)
        self._ui.txtEmail.setEnabled(enabled)
        self._ui.txtComment.setEnabled(enabled)
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and bool(self._ui.txtName.text().strip()))

    def _on_add(self) -> None:
        """Add the new user ID via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().add_uid(
                self._fingerprint,
                Passphrase(self._ui.txtPassphrase.text()),
                name=self._ui.txtName.text().strip(),
                email=self._ui.txtEmail.text().strip(),
                comment=self._ui.txtComment.text().strip(),
            ),
            busy_text=_("Adding user ID…"),
            error_template=_("Could not add user ID: {error}"),
        )
