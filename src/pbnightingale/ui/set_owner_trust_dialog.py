"""Set Owner Trust dialog — records how much the current user trusts a
key's owner to correctly certify *other* people's keys. A purely local
judgment call: no passphrase or secret key is involved (see
``core.gpg_backend.GPGBackend.set_owner_trust()``)."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import GPGBackendError, Key
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.set_owner_trust_dialog_ui import Ui_SetOwnerTrustDialog

# Maps gpg's single-letter ownertrust colon code (Key.owner_trust) back to
# the keyword --quick-set-ownertrust itself expects — the inverse of what
# GPGBackend.set_owner_trust() sends, needed here only to preselect the
# combo box on the key's current value.
_TRUST_CODE_TO_KEYWORD = {
    "n": "never",
    "q": "undefined",
    "-": "undefined",
    "m": "marginal",
    "f": "full",
    "u": "ultimate",
}


class SetOwnerTrustDialog(GeometryMixin, QDialog):
    def __init__(self, key: Key, parent=None) -> None:
        super().__init__(parent)
        self._fingerprint = key.fingerprint
        self._ui = Ui_SetOwnerTrustDialog()
        self._ui.setupUi(self)
        self._init_geometry("set_owner_trust_dialog")
        self._pool = QThreadPool(self)
        self.updated_key: Key | None = None

        uid = key.uids[0].value if key.uids else key.keyid
        self._ui.lblExplanation.setText(
            _(
                "How much do you trust {uid} to correctly verify other "
                "people's keys before signing them?"
            ).format(uid=uid)
        )
        keyword = _TRUST_CODE_TO_KEYWORD.get(key.owner_trust, "undefined")
        idx = self._ui.cmbOwnerTrust.findData(keyword)
        if idx >= 0:
            self._ui.cmbOwnerTrust.setCurrentIndex(idx)

        self._ui.buttonBox.accepted.connect(self._on_set)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.cmbOwnerTrust.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_set(self) -> None:
        trust = self._ui.cmbOwnerTrust.currentData()
        self._set_form_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Setting owner trust…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().set_owner_trust(
                self._fingerprint, trust
            ),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    def _on_success(self, key: Key) -> None:
        self.updated_key = key
        self.accept()

    def _on_error(self, exc: GPGBackendError) -> None:
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            _("Could not set owner trust: {error}").format(error=str(exc))
        )
        self._set_form_enabled(True)
