"""Refresh Keys report dialog — shown after a keyserver refresh completes,
listing which keys actually picked up a change.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbnightingale.core.gpg_backend import RefreshedKey
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.refresh_keys_report_dialog_ui import Ui_RefreshKeysReportDialog


class RefreshKeysReportDialog(GeometryMixin, QDialog):
    def __init__(self, refreshed: list[RefreshedKey], parent=None) -> None:
        super().__init__(parent)
        self._ui = Ui_RefreshKeysReportDialog()
        self._ui.setupUi(self)
        self._init_geometry("refresh_keys_report_dialog")

        updated = [entry for entry in refreshed if entry.updated]
        if not updated:
            self._ui.lblSummary.setText(
                _("Checked {count} key(s) — nothing new.").format(count=len(refreshed))
            )
        else:
            self._ui.lblSummary.setText(
                _("{updated} of {count} key(s) picked up changes:").format(
                    updated=len(updated), count=len(refreshed)
                )
            )
        for entry in updated:
            uid = entry.key.uids[0].value if entry.key.uids else entry.key.keyid
            self._ui.updatedList.addItem(f"{uid} ({entry.key.keyid})")

        self._ui.buttonBox.accepted.connect(self.accept)
