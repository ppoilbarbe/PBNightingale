"""UI layout for the Search Keyserver dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class Ui_SearchKeyDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Search Keyserver"))
        dialog.setMinimumSize(480, 360)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        self.txtQuery = QLineEdit(dialog)
        self.txtQuery.setPlaceholderText(_("Name, email, fingerprint, or key ID"))
        form.addRow(_("Query:"), self.txtQuery)
        self.txtKeyserver = QLineEdit(dialog)
        form.addRow(_("Keyserver:"), self.txtKeyserver)
        layout.addLayout(form)

        self.lblKeyserverHint = QLabel(dialog)
        self.lblKeyserverHint.setWordWrap(True)
        self.lblKeyserverHint.setVisible(False)
        layout.addWidget(self.lblKeyserverHint)

        search_row = QHBoxLayout()
        search_row.addStretch()
        self.btnSearch = QPushButton(_("Search"), dialog)
        search_row.addWidget(self.btnSearch)
        layout.addLayout(search_row)

        self.resultsList = QListWidget(dialog)
        layout.addWidget(self.resultsList)

        self.progress = QProgressBar(dialog)
        self.progress.setRange(0, 0)  # busy indicator: duration isn't known
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lblStatus = QLabel(dialog)
        self.lblStatus.setWordWrap(True)
        self.lblStatus.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.lblStatus)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_("Import"))
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.buttonBox)
