"""UI layout for the About dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)


class Ui_AboutDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setMinimumWidth(360)
        dialog.setWindowTitle(_("About PBNightingale"))

        layout = QVBoxLayout(dialog)

        self.lblIcon = QLabel(dialog)
        self.lblIcon.setFixedSize(64, 64)
        self.lblIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblIcon.setScaledContents(True)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(self.lblIcon)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        self.lblAppName = QLabel(
            '<b style="font-size: 14pt;">PBNightingale</b>', dialog
        )
        self.lblAppName.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lblAppName)

        self.lblVersion = QLabel(dialog)
        self.lblVersion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lblVersion)

        self.lblDescription = QLabel(
            _("A graphical GPG key management utility."), dialog
        )
        self.lblDescription.setWordWrap(True)
        self.lblDescription.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lblDescription)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        def bold(text: str) -> str:
            return f"<b>{text}</b>"

        self.lblAuthor = QLabel("Marcel Spock &lt;mrspock@cardolan.net&gt;", dialog)
        form.addRow(bold(_("Author:")), self.lblAuthor)

        self.lblLicense = QLabel("GPLv3", dialog)
        form.addRow(bold(_("License:")), self.lblLicense)

        self.lblPythonVersion = QLabel(dialog)
        form.addRow(bold(_("Python:")), self.lblPythonVersion)

        self.lblPySideVersion = QLabel(dialog)
        form.addRow(bold(_("PySide6:")), self.lblPySideVersion)

        layout.addLayout(form)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)
