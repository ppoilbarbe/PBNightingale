"""UI layout for the Settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class Ui_SettingsDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setMinimumSize(420, 480)
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
        self.spinActivityLogMaxEntries = QSpinBox(dialog)
        self.spinActivityLogMaxEntries.setRange(1, 1000)
        self.spinActivityLogMaxEntries.setSuffix(_(" commands"))
        self.spinActivityLogMaxEntries.setToolTip(
            _("How many recent commands the Activity (advanced) window keeps")
        )
        form.addRow(_("Activity history:"), self.spinActivityLogMaxEntries)
        layout.addLayout(form)

        keyservers_group = QGroupBox(_("Key Servers"), dialog)
        keyservers_layout = QVBoxLayout(keyservers_group)
        keyservers_row = QHBoxLayout()
        self.lstKeyservers = QListWidget(keyservers_group)
        self.lstKeyservers.setToolTip(
            _(
                "Checked servers are used to search for and fetch keys; "
                "unchecked ones are kept for reference only."
            )
        )
        keyservers_row.addWidget(self.lstKeyservers)
        keyservers_buttons = QVBoxLayout()
        self.btnKeyserverAdd = QPushButton(_("Add…"), keyservers_group)
        self.btnKeyserverRemove = QPushButton(_("Remove"), keyservers_group)
        self.btnKeyserverUp = QPushButton(_("Move Up"), keyservers_group)
        self.btnKeyserverDown = QPushButton(_("Move Down"), keyservers_group)
        keyservers_buttons.addWidget(self.btnKeyserverAdd)
        keyservers_buttons.addWidget(self.btnKeyserverRemove)
        keyservers_buttons.addWidget(self.btnKeyserverUp)
        keyservers_buttons.addWidget(self.btnKeyserverDown)
        keyservers_buttons.addStretch()
        keyservers_row.addLayout(keyservers_buttons)
        keyservers_layout.addLayout(keyservers_row)
        self.btnKeyserverRestoreDefaults = QPushButton(
            _("Restore Default List"), keyservers_group
        )
        keyservers_layout.addWidget(self.btnKeyserverRestoreDefaults)
        self.chkThirdPartySignatures = QCheckBox(
            _("Import other people's signatures along with keys"), keyservers_group
        )
        self.chkThirdPartySignatures.setToolTip(
            _(
                "Off by default: GnuPG then keeps only the owner's own "
                "signatures when fetching a key from a keyserver."
            )
        )
        self.chkThirdPartySignatures.setWhatsThis(
            _(
                "By default, GnuPG discards every signature made by other "
                "people when it fetches a key from a keyserver, keeping only "
                "the owner's own. This protects against an attack where "
                "someone attaches tens of thousands of bogus signatures to a "
                "key to make it unusable. Check this box to import those "
                "signatures anyway, so the web of trust can work from "
                "keyserver data: keys.openpgp.org never serves them, but "
                "keyserver.ubuntu.com does. Only do so if you rely on the web "
                "of trust."
            )
        )
        keyservers_layout.addWidget(self.chkThirdPartySignatures)
        self.lblThirdPartySignaturesWarning = QLabel(
            _(
                "Leave unchecked unless you rely on the web of trust: a key "
                "flooded with bogus signatures can then slow down or block "
                "GnuPG."
            ),
            keyservers_group,
        )
        self.lblThirdPartySignaturesWarning.setWordWrap(True)
        keyservers_layout.addWidget(self.lblThirdPartySignaturesWarning)
        layout.addWidget(keyservers_group)

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
