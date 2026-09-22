"""UI layout for the Activity (advanced) window."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)


class Ui_ActivityLogDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setMinimumSize(640, 360)
        dialog.setWindowTitle(_("Activity (advanced)"))

        layout = QVBoxLayout(dialog)

        self.tblActivity = QTableWidget(0, 3, dialog)
        self.tblActivity.setHorizontalHeaderLabels([_("#"), _("Time"), _("Command")])
        self.tblActivity.verticalHeader().setVisible(False)
        self.tblActivity.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblActivity.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tblActivity.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tblActivity.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tblActivity.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tblActivity.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.tblActivity.setToolTip(
            _("Select a row and press Ctrl+C to copy its command to the clipboard.")
        )
        layout.addWidget(self.tblActivity)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        self.btnClearActivity = QPushButton(_("Clear History"), dialog)
        buttons_row.addWidget(self.btnClearActivity)
        layout.addLayout(buttons_row)
