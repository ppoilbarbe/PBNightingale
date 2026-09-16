"""UI layout for the Import Key dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_ImportKeyDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Import Key"))
        dialog.setMinimumSize(520, 420)

        layout = QVBoxLayout(dialog)

        self.tabs = QTabWidget(dialog)
        layout.addWidget(self.tabs)

        file_tab = QWidget(dialog)
        file_layout = QVBoxLayout(file_tab)
        file_row = QHBoxLayout()
        self.txtFilePath = QLineEdit(file_tab)
        self.txtFilePath.setReadOnly(True)
        self.txtFilePath.setPlaceholderText(_("No file selected"))
        file_row.addWidget(self.txtFilePath)
        self.btnBrowse = QPushButton(_("Browse…"), file_tab)
        file_row.addWidget(self.btnBrowse)
        file_layout.addLayout(file_row)
        file_layout.addStretch()
        self.tabs.addTab(file_tab, _("From file"))

        server_tab = QWidget(dialog)
        server_form = QFormLayout(server_tab)
        self.txtQuery = QLineEdit(server_tab)
        self.txtQuery.setPlaceholderText(_("Fingerprint, key ID, or email address"))
        server_form.addRow(_("Key:"), self.txtQuery)
        self.txtKeyserver = QLineEdit(server_tab)
        server_form.addRow(_("Keyserver:"), self.txtKeyserver)
        self.tabs.addTab(server_tab, _("From keyserver"))

        check_row = QHBoxLayout()
        check_row.addStretch()
        self.btnCheck = QPushButton(_("Check…"), dialog)
        check_row.addWidget(self.btnCheck)
        layout.addLayout(check_row)

        self.treeCandidates = QTreeWidget(dialog)
        self.treeCandidates.setHeaderLabels(
            [_("Identities"), _("Key ID"), _("Fingerprint"), _("Status")]
        )
        self.treeCandidates.setRootIsDecorated(False)
        layout.addWidget(self.treeCandidates)

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
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(_("Import"))
        ok_button.setEnabled(False)
        # Both buttons: QDialogButtonBox auto-promotes another button to
        # "default" whenever the current default one is disabled — with Ok
        # starting disabled, Cancel would silently become the button Enter
        # activates in either text field, closing the dialog instead of
        # doing nothing. See CODING.md, "Keyserver management".
        ok_button.setAutoDefault(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setAutoDefault(
            False
        )
        layout.addWidget(self.buttonBox)
