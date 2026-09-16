"""Set Primary User ID dialog — flags an existing UID as the key's primary
identity. Reversible (another UID can always be set primary later), so no
strong confirmation is required, just the passphrase to authorize it."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Uid
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.set_primary_uid_dialog_ui import Ui_SetPrimaryUidDialog


class SetPrimaryUidDialog(GeometryMixin, KeyOperationDialog, QDialog):
    def __init__(self, fingerprint: str, uid: Uid, parent=None) -> None:
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._uid = uid
        self._ui = Ui_SetPrimaryUidDialog()
        self._ui.setupUi(self)
        self._init_geometry("set_primary_uid_dialog")
        self._init_key_operation()

        self._ui.lblExplanation.setText(
            _("Set {uid} as the primary user ID for this key.").format(uid=uid.value)
        )
        self._ui.buttonBox.accepted.connect(self._on_set)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_set(self) -> None:
        self._run_operation(
            lambda: gpg_backend.default_backend().set_primary_uid(
                self._fingerprint, self._ui.txtPassphrase.text(), self._uid.value
            ),
            busy_text=_("Setting primary user ID…"),
            error_template=_("Could not set primary user ID: {error}"),
        )
