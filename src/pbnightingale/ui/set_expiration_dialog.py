"""Set Expiration dialog — sets the expiration date of either the primary
key itself, or one of its subkeys (mutually exclusive; the primary key's
own expiration and each subkey's are set independently, see
``core.gpg_backend.GPGBackend.set_key_expiration()``/
``set_subkey_expiration()``)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key, Subkey
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.set_expiration_dialog_ui import Ui_SetExpirationDialog


class SetExpirationDialog(GeometryMixin, KeyOperationDialog, QDialog):
    def __init__(
        self, fingerprint: str, subkey: Subkey | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._subkey = subkey
        self._ui = Ui_SetExpirationDialog()
        self._ui.setupUi(self)
        self._init_geometry("set_expiration_dialog")
        self._init_key_operation()

        if subkey is None:
            self.setWindowTitle(_("Set Key Expiration"))
            self._ui.lblExplanation.setText(_("Set the expiration date for this key."))
            current_expires = None
        else:
            self.setWindowTitle(_("Set Subkey Expiration"))
            self._ui.lblExplanation.setText(
                _("Set the expiration date for subkey {keyid}.").format(
                    keyid=subkey.keyid
                )
            )
            current_expires = subkey.expires

        if current_expires is not None:
            date = datetime.fromtimestamp(current_expires).date()  # noqa: DTZ006
            self._ui.dateExpiration.setDate(QDate(date.year, date.month, date.day))
        self._ui.chkNoExpiration.setChecked(current_expires is None)

        self._ui.chkNoExpiration.toggled.connect(self._on_no_expiration_toggled)
        self._on_no_expiration_toggled(self._ui.chkNoExpiration.isChecked())

        self._ui.buttonBox.accepted.connect(self._on_set)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _on_no_expiration_toggled(self, checked: bool) -> None:
        self._ui.dateExpiration.setEnabled(not checked)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.chkNoExpiration.setEnabled(enabled)
        self._ui.dateExpiration.setEnabled(
            enabled and not self._ui.chkNoExpiration.isChecked()
        )
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _expire_argument(self) -> str:
        if self._ui.chkNoExpiration.isChecked():
            return "0"
        return self._ui.dateExpiration.date().toString("yyyy-MM-dd")

    def _on_set(self) -> None:
        passphrase = self._ui.txtPassphrase.text()
        expire = self._expire_argument()

        def _call() -> Key:
            backend = gpg_backend.default_backend()
            if self._subkey is None:
                return backend.set_key_expiration(self._fingerprint, passphrase, expire)
            return backend.set_subkey_expiration(
                self._fingerprint, passphrase, self._subkey.fingerprint, expire
            )

        self._run_operation(
            _call,
            busy_text=_("Setting expiration…"),
            error_template=_("Could not set expiration: {error}"),
        )
