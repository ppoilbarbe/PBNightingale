"""Sign Key dialog.

Certifies every user ID of the selected key with one of the user's own
secret keys, the foundation of the web of trust.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.sign_key_dialog_ui import Ui_SignKeyDialog


def _format_key_choice(key: Key) -> str:
    """Return *key*'s label for the "sign as" combo box.

    Parameters
    ----------
    key
        The candidate signing key.

    Returns
    -------
    :
        ``"<first UID or fingerprint> (<key ID>)"``.
    """
    uid = key.uids[0].value if key.uids else key.fingerprint
    return f"{uid} ({key.keyid})"


class SignKeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for signing another key's user IDs."""

    def __init__(self, target_key: Key, my_keys: list[Key], parent=None) -> None:
        """Build the dialog for certifying *target_key*.

        Parameters
        ----------
        target_key
            The key being signed.
        my_keys
            Every key of the current user's own, to pick a signer from —
            only those with certify capability are offered.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._target_key = target_key
        self._ui = Ui_SignKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("sign_key_dialog")

        target_uid = target_key.uids[0].value if target_key.uids else target_key.keyid
        self._ui.lblExplanation.setText(
            _("Sign {uid} to vouch for it in the web of trust.").format(uid=target_uid)
        )

        self._signers = [key for key in my_keys if key.can_certify]
        for key in self._signers:
            self._ui.cmbSignAs.addItem(_format_key_choice(key), userData=key)

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if not self._signers:
            self._ok_button.setEnabled(False)
            self._ui.cmbSignAs.setEnabled(False)
            self._ui.lblStatus.setText(
                _("You have no personal key available to sign with.")
            )

        # After cmbSignAs has its items/selection, so the initial passphrase
        # prefill below reads the right signer.
        self._init_key_operation()
        self._ui.cmbSignAs.currentIndexChanged.connect(self._sync_cached_passphrase)

        self._ui.buttonBox.accepted.connect(self._on_sign)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _cache_fingerprint(self) -> str | None:
        """Return the currently-selected signer's fingerprint.

        Returns
        -------
        :
            The selected signing key's fingerprint, used as the
            passphrase-cache key, or ``None`` if none is selected.
        """
        signer: Key | None = self._ui.cmbSignAs.currentData()
        return signer.fingerprint if signer is not None else None

    def _bad_passphrase_message(self) -> str:
        """Return the message shown when the signing key's passphrase is wrong."""
        return _("Incorrect passphrase for the selected signing key.")

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.cmbSignAs.setEnabled(enabled)
        self._ui.cmbCertLevel.setEnabled(enabled)
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.chkLocalOnly.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and bool(self._signers))

    def _on_sign(self) -> None:
        """Sign the target key via the backend."""
        signer: Key = self._ui.cmbSignAs.currentData()
        cert_level = self._ui.cmbCertLevel.currentData()
        local_only = self._ui.chkLocalOnly.isChecked()
        passphrase = self._ui.txtPassphrase.text()

        self._run_operation(
            lambda: gpg_backend.default_backend().sign_key(
                self._target_key.fingerprint,
                passphrase,
                signing_key_fingerprint=signer.fingerprint,
                cert_level=cert_level,
                local_only=local_only,
            ),
            busy_text=_("Signing key…"),
            error_template=_("Could not sign key: {error}"),
        )
