"""Search Keyserver dialog — searches by name, email, fingerprint or key ID, and imports whichever match the user picks.

The keyserver field is a combobox listing every server defined in
Preferences ("Key Servers"), checked or not — unlike the Import dialog,
here a single, explicit keyserver is what "Search" and "Import" both act
on, so the full list (not just the checked ones) stays available to pick
from, with the first entry preselected.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidgetItem

from pbnightingale import preferences
from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import ImportedKey, SearchResult
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.key_list_view import _format_algo, _format_date
from pbnightingale.ui.search_key_dialog_ui import Ui_SearchKeyDialog

#: Not "the app's default keyserver" (there's no such single constant
#: anymore — see preferences.get_checked_keyserver_urls()): this is
#: specifically about keys.openpgp.org's own documented search
#: limitations (see _update_keyserver_hint() below), which apply to that
#: keyserver regardless of where it sits in the user's configured list.
_KEYS_OPENPGP_ORG = "hkps://keys.openpgp.org"


class SearchKeyDialog(GeometryMixin, QDialog):
    """Dialog for searching a keyserver and importing a chosen result."""

    def __init__(self, parent=None) -> None:
        """Build the dialog and wire its search/import flow."""
        super().__init__(parent)
        self._ui = Ui_SearchKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("search_key_dialog")
        self._pool = QThreadPool(self)
        self.imported_keys: list[ImportedKey] = []

        self._ui.cmbKeyserver.addItems(
            [url for url, _checked in preferences.get_keyservers()]
        )
        if self._ui.cmbKeyserver.count():
            self._ui.cmbKeyserver.setCurrentIndex(0)
        self._ui.cmbKeyserver.currentTextChanged.connect(self._update_keyserver_hint)
        self._update_keyserver_hint()
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self._ui.buttonBox.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        # QDialogButtonBox auto-promotes another button to "default" whenever
        # the current default one is disabled — with Ok/Import starting
        # disabled, Cancel silently becomes the button Enter activates,
        # which closed the dialog instead of running the search below.
        # Disabling autoDefault on both stops Enter from activating either
        # button on its own; only an explicit click (or the returnPressed
        # connection just below) does.
        self._ok_button.setAutoDefault(False)
        cancel_button.setAutoDefault(False)
        self._ui.btnSearch.clicked.connect(self._on_search)
        self._ui.txtQuery.returnPressed.connect(self._on_search)
        self._ui.resultsList.currentRowChanged.connect(
            lambda row: self._ok_button.setEnabled(row >= 0)
        )
        self._ui.buttonBox.accepted.connect(self._on_import)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _update_keyserver_hint(self) -> None:
        """Show the keys.openpgp.org identity-verification hint when applicable."""
        is_keys_openpgp_org = (
            self._ui.cmbKeyserver.currentText().strip() == _KEYS_OPENPGP_ORG
        )
        if is_keys_openpgp_org:
            self._ui.lblKeyserverHint.setText(
                _(
                    "keys.openpgp.org only shows identities (name/email) the "
                    "key's owner has verified there — at upload time or "
                    "afterward. An address that was never verified won't "
                    "appear in search results even if the key itself is on "
                    "the server."
                )
            )
        self._ui.lblKeyserverHint.setVisible(is_keys_openpgp_org)

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the search form.

        Parameters
        ----------
        enabled
            Whether the form should be interactive. The Import button
            also requires a selected result, regardless of *enabled*.
        """
        self._ui.txtQuery.setEnabled(enabled)
        self._ui.cmbKeyserver.setEnabled(enabled)
        self._ui.btnSearch.setEnabled(enabled)
        self._ui.resultsList.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.resultsList.currentRow() >= 0)

    def _on_search(self) -> None:
        """Search the entered query against the configured keyserver."""
        query = self._ui.txtQuery.text().strip()
        if not query:
            self._ui.lblStatus.setText(_("Enter a search query."))
            return
        keyserver = self._ui.cmbKeyserver.currentText().strip()
        if not keyserver:
            self._ui.lblStatus.setText(
                _("No keyserver is defined. Add one in Preferences → Key Servers.")
            )
            return

        self._ui.resultsList.clear()
        self._set_form_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Searching…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().search_keyserver(query, keyserver),
            on_success=self._on_search_success,
            on_error=self._on_search_error,
        )

    def _on_search_success(self, results: list[SearchResult]) -> None:
        """Populate the results list.

        Parameters
        ----------
        results
            Matches found for the search query.
        """
        self._ui.progress.setVisible(False)
        self._set_form_enabled(True)
        for result in results:
            uids = ", ".join(result.uids) or _("(no user ID)")
            text = _("{uids} — {algo}, {length} bits — created {date}").format(
                uids=uids,
                algo=_format_algo(result.algo),
                length=result.length,
                date=_format_date(result.created),
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self._ui.resultsList.addItem(item)
        self._ui.lblStatus.setText(_("{n} result(s) found.").format(n=len(results)))

    def _on_search_error(self, exc: Exception) -> None:
        """Show the search failure.

        Parameters
        ----------
        exc
            The exception raised by the failed search.
        """
        self._ui.progress.setVisible(False)
        self._set_form_enabled(True)
        self._ui.lblStatus.setText(
            _("Could not search: {error}").format(error=str(exc))
        )

    def _on_import(self) -> None:
        """Import the currently selected search result."""
        item = self._ui.resultsList.currentItem()
        if item is None:
            return
        result: SearchResult = item.data(Qt.ItemDataRole.UserRole)
        keyserver = self._ui.cmbKeyserver.currentText().strip()

        self._set_form_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Importing…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().import_from_keyserver(
                result.fingerprint, keyserver
            ),
            on_success=self._on_import_success,
            on_error=self._on_import_error,
        )

    def _on_import_success(self, keys: list[ImportedKey]) -> None:
        """Record the imported key(s) and close the dialog.

        Parameters
        ----------
        keys
            The keys produced by the import.
        """
        self.imported_keys = keys
        self.accept()

    def _on_import_error(self, exc: Exception) -> None:
        """Show the import failure.

        Parameters
        ----------
        exc
            The exception raised by the failed import.
        """
        self._ui.progress.setVisible(False)
        self._set_form_enabled(True)
        self._ui.lblStatus.setText(
            _("Could not import key: {error}").format(error=str(exc))
        )
