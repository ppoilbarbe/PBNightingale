"""Set Owner Trust dialog.

Records how much the current user trusts a key's owner to correctly
certify *other* people's keys — for one key, or the same level for
several at once. A purely local judgment call: no
passphrase or secret key is involved (see
``core.gpg_backend.GPGBackend.set_owner_trust()``).
"""

from __future__ import annotations

from collections.abc import Sequence

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
    """Dialog for setting how much a key's owner is trusted to certify others."""

    def __init__(self, keys: Sequence[Key], parent=None) -> None:
        """Build the dialog for *keys*, preselecting their current owner trust.

        The combo box starts on the keys' current owner trust when they
        all share it, on "Undefined" otherwise.

        Parameters
        ----------
        keys
            The keys whose owner trust is being set (at least one).
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprints = [key.fingerprint for key in keys]
        self._ui = Ui_SetOwnerTrustDialog()
        self._ui.setupUi(self)
        self._init_geometry("set_owner_trust_dialog")
        self._pool = QThreadPool(self)
        self.updated_key: Key | None = None

        if len(keys) == 1:
            key = keys[0]
            uid = key.uids[0].value if key.uids else key.keyid
            explanation = _(
                "How much do you trust {uid} to correctly verify other "
                "people's keys before signing them?"
            ).format(uid=uid)
        else:
            explanation = _(
                "How much do you trust the owners of these {n} keys "
                "({keyids}) to correctly verify other people's keys before "
                "signing them?"
            ).format(n=len(keys), keyids=", ".join(key.keyid for key in keys))
        self._ui.lblExplanation.setText(explanation)
        keywords = {
            _TRUST_CODE_TO_KEYWORD.get(key.owner_trust, "undefined") for key in keys
        }
        keyword = keywords.pop() if len(keywords) == 1 else "undefined"
        idx = self._ui.cmbOwnerTrust.findData(keyword)
        if idx >= 0:
            self._ui.cmbOwnerTrust.setCurrentIndex(idx)

        self._ui.buttonBox.accepted.connect(self._on_set)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the combo box and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.cmbOwnerTrust.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_set(self) -> None:
        """Apply the chosen owner trust to every key via the backend."""
        trust = self._ui.cmbOwnerTrust.currentData()
        fingerprints = list(self._fingerprints)
        self._set_form_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Setting owner trust…"))

        def _set_all() -> Key:
            backend = gpg_backend.default_backend()
            key = None
            # Idempotent, so a retry after a mid-batch failure can safely
            # redo the keys already set.
            for fingerprint in fingerprints:
                key = backend.set_owner_trust(fingerprint, trust)
            return key

        run_async(
            self._pool,
            _set_all,
            on_success=self._on_success,
            on_error=self._on_error,
        )

    def _on_success(self, key: Key) -> None:
        """Store the updated key and close the dialog.

        Parameters
        ----------
        key
            The (last) key with its new owner trust applied.
        """
        self.updated_key = key
        self.accept()

    def _on_error(self, exc: GPGBackendError) -> None:
        """Show the error and re-enable the form.

        Parameters
        ----------
        exc
            The error raised by the backend.
        """
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            _("Could not set owner trust: {error}").format(error=str(exc))
        )
        self._set_form_enabled(True)
