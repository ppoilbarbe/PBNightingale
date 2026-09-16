"""Shared widget-building blocks for the ``Ui_XxxDialog`` layouts of every
add/set/revoke dialog: a passphrase field, the busy-indicator/status
label pair, the ``buttonBox`` (Ok relabeled/Cancel), and — for the
strong-confirmation "revoke" dialogs — the confirmation checkbox. Mirrors
``key_operation_dialog.py``'s ``.py``-side mixin: that one factors out the
*behavior* every such dialog shares, this one factors out the *layout*.

Usage — a ``Ui_XxxDialog`` inherits this and calls whichever pieces it
needs, interleaved with its own dialog-specific widgets::

    class Ui_MyDialog(KeyOperationDialogUiMixin):
        def setupUi(self, dialog: QDialog) -> None:
            dialog.setWindowTitle(_("My Dialog"))
            layout = QVBoxLayout(dialog)
            ...  # dialog-specific widgets first
            self._build_passphrase_field(dialog, layout)
            self._build_progress_and_status(dialog, layout)
            self._build_button_box(dialog, layout, ok_text=_("Do it"))
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLayout,
    QProgressBar,
)

from pbnightingale.ui.password_line_edit import PasswordLineEdit


class KeyOperationDialogUiMixin:
    def _build_confirm_checkbox(self, dialog: QDialog, layout: QLayout) -> None:
        """The checkbox gating Ok on a "strong confirmation" revoke dialog."""
        self.chkConfirm = QCheckBox(
            _("I understand this action is permanent and cannot be undone."),
            dialog,
        )
        layout.addWidget(self.chkConfirm)

    def _build_passphrase_field(
        self,
        dialog: QDialog,
        layout: QLayout,
        *,
        label: str | None = None,
        form: QFormLayout | None = None,
    ) -> None:
        """Add the passphrase row to *form* if given (an existing form
        with other fields already in it, e.g. Add Subkey's purpose/
        algorithm/size), else create and append a new one-row form."""
        self.txtPassphrase = PasswordLineEdit(dialog)
        if form is None:
            form = QFormLayout()
            layout.addLayout(form)
        form.addRow(label or _("Primary key passphrase:"), self.txtPassphrase)

    def _build_progress_and_status(self, dialog: QDialog, layout: QLayout) -> None:
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

    def _build_button_box(
        self, dialog: QDialog, layout: QLayout, *, ok_text: str, ok_enabled: bool = True
    ) -> None:
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok_enabled)
        layout.addWidget(self.buttonBox)
