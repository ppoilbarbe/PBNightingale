"""Delete Key dialog.

Strong confirmation (a checkbox, not just a button click) before
permanently erasing one or several keys from the keyring. Unlike
``RevokeKeyDialog``, this needs no passphrase (see
``GPGBackend.delete_key()``) and the keys no longer exist at all
afterwards, rather than merely being marked untrustworthy.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.ui.delete_key_dialog_ui import Ui_DeleteKeyDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


class DeleteKeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for permanently deleting one or several keys from the keyring."""

    def __init__(self, keys: Sequence[Key], parent: QDialog | None = None) -> None:
        """Build the dialog for deleting *keys*.

        Parameters
        ----------
        keys
            The keys to delete (at least one).
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        # (fingerprint, has_secret) pairs still to delete — pruned as each
        # one succeeds, so retrying after a mid-batch failure doesn't trip
        # over a key that's already gone.
        self._pending = [(key.fingerprint, key.has_secret) for key in keys]
        # Every key actually deleted so far, even if a later one failed:
        # the caller must reload the keyring then, dialog accepted or not.
        self.deleted_fingerprints: list[str] = []
        self._ui = Ui_DeleteKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("delete_key_dialog")
        self._init_key_operation()

        if len(keys) == 1:
            warning = _(
                "This permanently deletes {keyid} from your keyring, "
                "including any private key material. Unlike revoking, "
                "the key will no longer exist at all afterwards."
            ).format(keyid=keys[0].keyid)
        else:
            warning = _(
                "This permanently deletes these {n} keys from your keyring, "
                "including any private key material: {keyids}. Unlike "
                "revoking, the keys will no longer exist at all afterwards."
            ).format(n=len(keys), keyids=", ".join(key.keyid for key in keys))
        self._ui.lblWarning.setText(warning)
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.chkConfirm.toggled.connect(self._ok_button.setEnabled)

        self._ui.buttonBox.accepted.connect(self._on_delete)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _passphrase_line_edit(self):
        """Return ``None`` — deleting a key never needs a passphrase."""
        return

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the confirmation checkbox and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.chkConfirm.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.chkConfirm.isChecked())

    def _on_delete(self) -> None:
        """Delete every pending key via the backend, one after the other."""
        pending = list(self._pending)
        deleted = self.deleted_fingerprints

        def _delete_all() -> None:
            backend = gpg_backend.default_backend()
            for fingerprint, secret in pending:
                backend.delete_key(fingerprint, secret=secret)
                deleted.append(fingerprint)

        self._run_operation(
            _delete_all,
            busy_text=_("Deleting key…"),
            error_template=_("Could not delete key: {error}"),
        )

    def _on_operation_error(self, exc: Exception) -> None:
        """Forget the keys already deleted, then report *exc* as usual."""
        done = set(self.deleted_fingerprints)
        self._pending = [entry for entry in self._pending if entry[0] not in done]
        super()._on_operation_error(exc)

    def _on_operation_result(self, _result: None) -> None:
        """Close the dialog once every key has been deleted."""
        self.accept()
