"""Download Unknown Keys report dialog — shown after fetching a key's
unknown signers from a keyserver, listing which ones were found.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbnightingale.core.gpg_backend import DownloadedSignature
from pbnightingale.ui.download_signatures_report_dialog_ui import (
    Ui_DownloadSignaturesReportDialog,
)
from pbnightingale.ui.geometry_mixin import GeometryMixin


class DownloadSignaturesReportDialog(GeometryMixin, QDialog):
    def __init__(self, downloaded: list[DownloadedSignature], parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_DownloadSignaturesReportDialog()
        self._ui.setupUi(self)
        self._init_geometry("download_signatures_report_dialog")

        found = [entry for entry in downloaded if entry.key is not None]
        missing = [entry for entry in downloaded if entry.key is None]
        if not downloaded:
            self._ui.lblSummary.setText(_("No unknown key to download."))
        else:
            self._ui.lblSummary.setText(
                _("{found} of {count} key(s) downloaded:").format(
                    found=len(found), count=len(downloaded)
                )
            )
        for entry in found:
            uid = entry.key.uids[0].value if entry.key.uids else entry.key.keyid
            self._ui.downloadedList.addItem(f"{uid} ({entry.key.keyid})")
        for entry in missing:
            self._ui.notFoundList.addItem(entry.identifier)

        self._ui.buttonBox.accepted.connect(self.accept)
