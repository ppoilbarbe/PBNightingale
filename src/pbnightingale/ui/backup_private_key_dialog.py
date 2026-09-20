"""Back Up Private Key dialog.

Exports the full secret key material to a chosen file (unlike Export…,
which only ever exports the public key). GnuPG requires the passphrase to
do this at all — see ``GPGBackend.export_secret_key()``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.backup_private_key_dialog_ui import Ui_BackupPrivateKeyDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


class BackupPrivateKeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for exporting a key's full private key material to a file."""

    def __init__(self, key: Key, parent=None) -> None:
        """Build the dialog for backing up *key*.

        Parameters
        ----------
        key
            The key to back up.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = key.fingerprint
        self._destination: str | None = None
        self._ui = Ui_BackupPrivateKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("backup_private_key_dialog")
        self._init_key_operation()

        self._ui.lblWarning.setText(
            _(
                "This exports the full private key for {keyid}, not just "
                "the public key. Anyone who gets this file and its "
                "passphrase can fully impersonate this key — store it "
                "somewhere safe."
            ).format(keyid=key.keyid)
        )
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)

        self._ui.buttonBox.accepted.connect(self._on_backup)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the passphrase field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ok_button.setEnabled(enabled)

    def _on_backup(self) -> None:
        """Prompt for a destination file, then export the secret key to it."""
        # An absolute default directory, not a bare relative filename: this
        # dialog's own suggested name resolving against the process's
        # working directory (rather than somewhere the user would expect,
        # e.g. their home directory) is an easy way to end up with real
        # private key material sitting in an unexpected place, such as the
        # source tree of whatever program happened to launch this one from.
        suggested = Path.home() / f"{self._fingerprint}-secret.asc"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            _("Back Up Private Key"),
            str(suggested),
            _("ASCII-armored keys (*.asc)"),
        )
        if not path:
            return
        self._destination = path
        self._run_operation(
            lambda: gpg_backend.default_backend().export_secret_key(
                self._fingerprint, Passphrase(self._ui.txtPassphrase.text())
            ),
            busy_text=_("Backing up private key…"),
            error_template=_("Could not back up private key: {error}"),
        )

    def _on_operation_result(self, armored: str) -> None:
        """Write the exported key to the chosen destination file.

        Parameters
        ----------
        armored
            The ASCII-armored secret key block returned by the backend.
        """
        try:
            Path(self._destination).write_text(armored, encoding="utf-8")
        except OSError as exc:
            self._ui.progress.setVisible(False)
            self._ui.lblStatus.setText(
                _("Could not write file: {error}").format(error=str(exc))
            )
            self._set_form_enabled(True)
            return
        self.accept()
