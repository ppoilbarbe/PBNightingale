"""UI layout for the Add User ID dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_AddUidDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Add User ID"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        self.txtName = QLineEdit(dialog)
        form.addRow(_("Name:"), self.txtName)
        self.txtEmail = QLineEdit(dialog)
        form.addRow(_("Email:"), self.txtEmail)
        self.txtComment = QLineEdit(dialog)
        form.addRow(_("Comment (optional):"), self.txtComment)

        self._build_passphrase_field(dialog, layout, form=form)
        layout.addLayout(form)

        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Add"), ok_enabled=False)
