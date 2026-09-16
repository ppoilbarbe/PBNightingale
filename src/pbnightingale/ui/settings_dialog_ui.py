"""UI layout for the Settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class Ui_SettingsDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setMinimumWidth(360)
        dialog.setWindowTitle(_("Settings"))

        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        self.cmbLanguage = QComboBox(dialog)
        self.cmbLanguage.setToolTip(_("Select the interface language"))
        form.addRow(_("Language:"), self.cmbLanguage)
        self.cmbAlgorithm = QComboBox(dialog)
        self.cmbAlgorithm.setToolTip(
            _("Default algorithm proposed by the new-key wizard")
        )
        form.addRow(_("Preferred key algorithm:"), self.cmbAlgorithm)
        self.cmbIconSize = QComboBox(dialog)
        self.cmbIconSize.setToolTip(_("Size of the toolbar icons"))
        form.addRow(_("Toolbar icon size:"), self.cmbIconSize)
        self.spinPassphraseCache = QSpinBox(dialog)
        self.spinPassphraseCache.setRange(0, 120)
        self.spinPassphraseCache.setSuffix(_(" minutes"))
        self.spinPassphraseCache.setSpecialValueText(_("Never"))
        self.spinPassphraseCache.setToolTip(
            _(
                "How long a passphrase you enter stays remembered in memory "
                "(0 to never remember it)"
            )
        )
        form.addRow(_("Remember passphrases for:"), self.spinPassphraseCache)
        layout.addLayout(form)

        self.lblNotice = QLabel(
            _("A restart is required for the language change to take effect."),
            dialog,
        )
        self.lblNotice.setWordWrap(True)
        layout.addWidget(self.lblNotice)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            dialog,
        )
        self.buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(self.buttonBox)
