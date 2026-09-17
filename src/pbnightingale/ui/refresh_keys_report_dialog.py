"""Refresh Keys report dialog — lists which keys picked up a change.

Shown after a keyserver refresh completes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbnightingale.core.gpg_backend import RefreshedKey
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.refresh_keys_report_dialog_ui import Ui_RefreshKeysReportDialog


class RefreshKeysReportDialog(GeometryMixin, QDialog):
    """Summarizes a keyserver refresh: how many keys were checked, and which of them actually picked up a change."""

    def __init__(self, refreshed: list[RefreshedKey], parent=None) -> None:
        """Build the dialog from the refresh's own per-key results.

        Parameters
        ----------
        refreshed
            One entry per key that was refreshed, each flagged with
            whether it actually changed.
        parent
            The owning window.
        """
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
