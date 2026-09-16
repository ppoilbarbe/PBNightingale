"""UI layout for the Download Unknown Keys report dialog, shown after
fetching a selected key's unknown signers from a keyserver."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)


class Ui_DownloadSignaturesReportDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Download Unknown Keys — Report"))
        dialog.setMinimumSize(420, 400)

        layout = QVBoxLayout(dialog)

        self.lblSummary = QLabel(dialog)
        self.lblSummary.setWordWrap(True)
        layout.addWidget(self.lblSummary)

        grpDownloaded = QGroupBox(_("Downloaded"), dialog)
        grpDownloadedLayout = QVBoxLayout(grpDownloaded)
        self.downloadedList = QListWidget(grpDownloaded)
        grpDownloadedLayout.addWidget(self.downloadedList)
        layout.addWidget(grpDownloaded)

        grpNotFound = QGroupBox(_("Not found on the keyserver"), dialog)
        grpNotFoundLayout = QVBoxLayout(grpNotFound)
        self.notFoundList = QListWidget(grpNotFound)
        grpNotFoundLayout.addWidget(self.notFoundList)
        layout.addWidget(grpNotFound)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        layout.addWidget(self.buttonBox)
