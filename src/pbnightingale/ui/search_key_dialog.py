"""Search Keyserver dialog — searches a keyserver for a name, email,
fingerprint or key ID, and imports whichever match the user picks."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidgetItem

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import (
    DEFAULT_KEYSERVER,
    ImportedKey,
    SearchResult,
)
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.key_list_view import _format_algo, _format_date
from pbnightingale.ui.search_key_dialog_ui import Ui_SearchKeyDialog


class SearchKeyDialog(GeometryMixin, QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_SearchKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("search_key_dialog")
        self._pool = QThreadPool(self)
        self.imported_keys: list[ImportedKey] = []

        self._ui.txtKeyserver.setText(DEFAULT_KEYSERVER)
        self._ui.txtKeyserver.textChanged.connect(self._update_keyserver_hint)
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
        is_default = self._ui.txtKeyserver.text().strip() == DEFAULT_KEYSERVER
        if is_default:
            self._ui.lblKeyserverHint.setText(
                _(
                    "keys.openpgp.org does not support searching by name or "
                    "email, and never returns user IDs in search results "
                    "(privacy by design). Search by exact key ID or "
                    "fingerprint instead, or use Import… for a known email "
                    "address."
                )
            )
        self._ui.lblKeyserverHint.setVisible(is_default)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.txtQuery.setEnabled(enabled)
        self._ui.txtKeyserver.setEnabled(enabled)
        self._ui.btnSearch.setEnabled(enabled)
        self._ui.resultsList.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.resultsList.currentRow() >= 0)

    def _on_search(self) -> None:
        query = self._ui.txtQuery.text().strip()
        if not query:
            self._ui.lblStatus.setText(_("Enter a search query."))
            return
        keyserver = self._ui.txtKeyserver.text().strip() or DEFAULT_KEYSERVER

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
        self._ui.progress.setVisible(False)
        self._set_form_enabled(True)
        self._ui.lblStatus.setText(
            _("Could not search: {error}").format(error=str(exc))
        )

    def _on_import(self) -> None:
        item = self._ui.resultsList.currentItem()
        if item is None:
            return
        result: SearchResult = item.data(Qt.ItemDataRole.UserRole)
        keyserver = self._ui.txtKeyserver.text().strip() or DEFAULT_KEYSERVER

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
        self.imported_keys = keys
        self.accept()

    def _on_import_error(self, exc: Exception) -> None:
        self._ui.progress.setVisible(False)
        self._set_form_enabled(True)
        self._ui.lblStatus.setText(
            _("Could not import key: {error}").format(error=str(exc))
        )
