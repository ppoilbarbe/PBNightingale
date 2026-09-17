"""Import Key dialog — imports a public key from a file or keyserver, by fingerprint, key ID, or email address.

Never imports blindly: "Check…" first previews every candidate key
(identities, full key ID, fingerprint, and whether it's already in the
keyring) without touching the keyring, then only the ones the user checks
are actually committed via "Import".
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QTreeWidgetItem

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import (
    DEFAULT_KEYSERVER,
    ImportedKey,
    ImportPreview,
)
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.import_key_dialog_ui import Ui_ImportKeyDialog
from pbnightingale.ui.key_list_view import _format_fingerprint

_FILE_TAB = 0
_CANDIDATE_ROLE = Qt.ItemDataRole.UserRole


class ImportKeyDialog(GeometryMixin, QDialog):
    """Dialog for previewing and importing a key from a file or keyserver."""

    def __init__(self, parent=None) -> None:
        """Build the dialog and wire its check/import flow."""
        super().__init__(parent)
        self._ui = Ui_ImportKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("import_key_dialog")
        self._pool = QThreadPool(self)
        self.imported_keys: list[ImportedKey] = []
        self._pending_commit = None

        self._ui.txtKeyserver.setText(DEFAULT_KEYSERVER)
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.btnBrowse.clicked.connect(self._on_browse)
        self._ui.btnCheck.clicked.connect(self._on_check)
        self._ui.txtQuery.returnPressed.connect(self._on_check)
        self._ui.treeCandidates.itemChanged.connect(self._update_ok_enabled)
        self._ui.buttonBox.accepted.connect(self._on_import)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _on_browse(self) -> None:
        """Prompt for a key file and fill the file-path field with it."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            _("Choose Key File"),
            "",
            _("OpenPGP keys (*.asc *.gpg *.pgp *.key);;All files (*)"),
        )
        if not path:
            return
        self._ui.txtFilePath.setText(path)

    def _set_editing_enabled(self, enabled: bool) -> None:
        """Enable or disable the source tabs and the Check button.

        Parameters
        ----------
        enabled
            Whether the file/keyserver source fields are editable.
        """
        self._ui.tabs.setEnabled(enabled)
        self._ui.btnCheck.setEnabled(enabled)

    def _on_check(self) -> None:
        """Preview the candidate key(s) from the currently selected source, without touching the keyring."""
        if self._ui.tabs.currentIndex() == _FILE_TAB:
            path = self._ui.txtFilePath.text()
            if not path:
                self._ui.lblStatus.setText(_("Choose a file to import."))
                return

            def call():
                return gpg_backend.default_backend().preview_import_from_file(path)

            self._pending_commit = lambda approved: (
                gpg_backend.default_backend().commit_import_from_file(path, approved)
            )
        else:
            query = self._ui.txtQuery.text().strip()
            if not query:
                self._ui.lblStatus.setText(
                    _("Enter a fingerprint, key ID, or email address.")
                )
                return
            keyserver = self._ui.txtKeyserver.text().strip() or DEFAULT_KEYSERVER

            def call():
                return gpg_backend.default_backend().preview_import_from_keyserver(
                    query, keyserver
                )

            def commit(approved):
                return gpg_backend.default_backend().commit_import_from_keyserver(
                    query, keyserver, approved
                )

            self._pending_commit = commit

        self._set_editing_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Checking…"))
        run_async(
            self._pool, call, on_success=self._on_check_success, on_error=self._on_error
        )

    def _on_check_success(self, candidates: list[ImportPreview]) -> None:
        """Populate the candidate tree, pre-checking every new key.

        Parameters
        ----------
        candidates
            Keys that would be imported, as reported by the preview.
        """
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(_("{n} key(s) found.").format(n=len(candidates)))
        tree = self._ui.treeCandidates
        tree.blockSignals(True)
        tree.clear()
        for candidate in candidates:
            item = QTreeWidgetItem(
                [
                    ", ".join(candidate.uids) or _("(no user ID)"),
                    candidate.keyid,
                    _format_fingerprint(candidate.fingerprint),
                    "" if candidate.is_new else _("Already in keyring"),
                ]
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0,
                Qt.CheckState.Unchecked if candidate.is_new else Qt.CheckState.Checked,
            )
            item.setData(0, _CANDIDATE_ROLE, candidate)
            tree.addTopLevelItem(item)
        for column in range(tree.columnCount()):
            tree.resizeColumnToContents(column)
        tree.blockSignals(False)
        self._update_ok_enabled()

    def _update_ok_enabled(self) -> None:
        """Enable the Import button only while at least one candidate is checked."""
        tree = self._ui.treeCandidates
        any_checked = any(
            tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
            for i in range(tree.topLevelItemCount())
        )
        self._ok_button.setEnabled(any_checked)

    def _approved_fingerprints(self) -> set[str]:
        """Return the fingerprints of every checked candidate.

        Returns
        -------
        :
            One fingerprint per checked row in the candidate tree.
        """
        tree = self._ui.treeCandidates
        return {
            tree.topLevelItem(i).data(0, _CANDIDATE_ROLE).fingerprint
            for i in range(tree.topLevelItemCount())
            if tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        }

    def _on_import(self) -> None:
        """Commit the checked candidates from the last check, for real."""
        if self._pending_commit is None:
            return
        approved = self._approved_fingerprints()
        pending_commit = self._pending_commit
        self._ui.treeCandidates.setEnabled(False)
        self._ok_button.setEnabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Importing…"))
        run_async(
            self._pool,
            lambda: pending_commit(approved),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    def _on_success(self, keys: list[ImportedKey]) -> None:
        """Record the imported key(s) and close the dialog.

        Parameters
        ----------
        keys
            The keys produced by the commit.
        """
        self.imported_keys = keys
        self.accept()

    def _on_error(self, exc: Exception) -> None:
        """Show the failure and reset back to the editing state.

        Parameters
        ----------
        exc
            The exception raised by the failed check or import.
        """
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            _("Could not import key: {error}").format(error=str(exc))
        )
        self._pending_commit = None
        self._ui.treeCandidates.clear()
        self._ui.treeCandidates.setEnabled(True)
        self._set_editing_enabled(True)
        self._ok_button.setEnabled(False)
