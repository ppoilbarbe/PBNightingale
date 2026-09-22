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
    QSizePolicy,
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
        # Fixed, not the QTabWidget default: without this, a vertical
        # resize grows the tabs as much as (or more than) treeCandidates
        # below, since each tab page's own layout otherwise reports an
        # expanding size hint — verified empirically (resizing 420→800px
        # grew the tabs by 229px and the tree by only 151px). The tabs'
        # own content (one text field, or a field + Browse button) never
        # needs more than its natural height; all the extra room from a
        # taller window should go to the candidate list instead.
        self.tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.tabs)

        server_tab = QWidget(dialog)
        server_form = QFormLayout(server_tab)
        self.txtQuery = QLineEdit(server_tab)
        self.txtQuery.setPlaceholderText(_("Fingerprint, key ID, or email address"))
        server_form.addRow(_("Key:"), self.txtQuery)
        self.tabs.addTab(server_tab, _("From keyserver"))

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
        self.tabs.addTab(file_tab, _("From file"))

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
