"""UI layout for the Refresh Keys report dialog, shown after a keyserver
refresh completes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)


class Ui_RefreshKeysReportDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Refresh Keys — Report"))
        dialog.setMinimumSize(420, 320)

        layout = QVBoxLayout(dialog)

        self.lblSummary = QLabel(dialog)
        self.lblSummary.setWordWrap(True)
        layout.addWidget(self.lblSummary)

        self.updatedList = QListWidget(dialog)
        layout.addWidget(self.updatedList)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        layout.addWidget(self.buttonBox)
