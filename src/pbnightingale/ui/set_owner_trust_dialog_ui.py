"""UI layout for the Set Owner Trust dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class Ui_SetOwnerTrustDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Set Owner Trust"))
        dialog.setMinimumWidth(380)

        layout = QVBoxLayout(dialog)

        self.lblExplanation = QLabel(dialog)
        self.lblExplanation.setWordWrap(True)
        layout.addWidget(self.lblExplanation)

        form = QFormLayout()
        self.cmbOwnerTrust = QComboBox(dialog)
        self.cmbOwnerTrust.addItem(_("Undefined"), userData="undefined")
        self.cmbOwnerTrust.addItem(_("Never"), userData="never")
        self.cmbOwnerTrust.addItem(_("Marginal"), userData="marginal")
        self.cmbOwnerTrust.addItem(_("Full"), userData="full")
        self.cmbOwnerTrust.addItem(_("Ultimate"), userData="ultimate")
        form.addRow(_("Owner trust:"), self.cmbOwnerTrust)
        layout.addLayout(form)

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
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_("Set"))
        layout.addWidget(self.buttonBox)
