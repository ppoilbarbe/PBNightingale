"""UI layout for the Set Expiration dialog (primary key or one subkey)."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_SetExpirationDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Set Expiration"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        self.lblExplanation = QLabel(dialog)
        self.lblExplanation.setWordWrap(True)
        layout.addWidget(self.lblExplanation)

        self.chkNoExpiration = QCheckBox(_("Never expires"), dialog)
        layout.addWidget(self.chkNoExpiration)

        form = QFormLayout()
        self.dateExpiration = QDateEdit(dialog)
        self.dateExpiration.setCalendarPopup(True)
        self.dateExpiration.setMinimumDate(QDate.currentDate().addDays(1))
        self.dateExpiration.setDate(QDate.currentDate().addYears(1))
        form.addRow(_("Expiration date:"), self.dateExpiration)

        self._build_passphrase_field(dialog, layout, form=form)
        layout.addLayout(form)

        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Set"))
