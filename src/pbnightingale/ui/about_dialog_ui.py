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

        self.lblAuthor = QLabel("Marcel Spock &lt;mrspock@cardolan.net&gt;", dialog)
        form.addRow("<b>" + _("Author:") + "</b>", self.lblAuthor)

        self.lblLicense = QLabel("GPLv3", dialog)
        form.addRow(_("<b>" + "License:" + "</b>"), self.lblLicense)

        layout.addLayout(form)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)
