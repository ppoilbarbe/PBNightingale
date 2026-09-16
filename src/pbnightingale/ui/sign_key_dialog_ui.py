"""UI layout for the Sign Key dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_SignKeyDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Sign Key"))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        self.lblExplanation = QLabel(dialog)
        self.lblExplanation.setWordWrap(True)
        layout.addWidget(self.lblExplanation)

        form = QFormLayout()
        self.cmbSignAs = QComboBox(dialog)
        form.addRow(_("Sign as:"), self.cmbSignAs)

        self.cmbCertLevel = QComboBox(dialog)
        self.cmbCertLevel.addItem(_("No particular claim"), userData=0)
        self.cmbCertLevel.addItem(_("I have not verified this key at all"), userData=1)
        self.cmbCertLevel.addItem(_("I have done casual verification"), userData=2)
        self.cmbCertLevel.addItem(_("I have done extensive verification"), userData=3)
        form.addRow(_("Verification:"), self.cmbCertLevel)

        self._build_passphrase_field(dialog, layout, label=_("Passphrase:"), form=form)
        layout.addLayout(form)

        self.chkLocalOnly = QCheckBox(
            _("Local signature only (not exportable)"), dialog
        )
        self.chkLocalOnly.setToolTip(
            _(
                "A local signature stays in your own keyring — it never "
                "gets published or exported, and only affects how you "
                "personally see this key's validity."
            )
        )
        self.chkLocalOnly.setChecked(True)
        layout.addWidget(self.chkLocalOnly)

        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Sign"))
