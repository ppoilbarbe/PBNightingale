"""UI layout for the new-key creation wizard's individual pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWizardPage,
)

from pbnightingale.ui.password_line_edit import PasswordLineEdit
from pbnightingale.ui.password_strength_meter import PasswordStrengthMeter


class Ui_IdentityPage:
    def setupUi(self, page: QWizardPage) -> None:
        page.setTitle(_("Identity"))
        page.setSubTitle(
            _(
                "This identifies you on the key. It is shown to anyone you "
                "exchange keys with."
            )
        )

        layout = QFormLayout(page)
        self.txtName = QLineEdit(page)
        layout.addRow(_("Name:"), self.txtName)
        self.txtEmail = QLineEdit(page)
        layout.addRow(_("Email:"), self.txtEmail)
        self.txtComment = QLineEdit(page)
        layout.addRow(_("Comment (optional):"), self.txtComment)


class Ui_ParametersPage:
    def setupUi(self, page: QWizardPage) -> None:
        page.setTitle(_("Key parameters"))
        page.setSubTitle(
            _(
                "A dedicated signing and/or encryption subkey is recommended: "
                "it can be replaced or revoked without affecting your identity "
                "or existing signatures."
            )
        )

        layout = QVBoxLayout(page)

        form = QFormLayout()
        self.cmbAlgorithm = QComboBox(page)
        self.cmbAlgorithm.addItem(_("RSA"), userData="RSA")
        self.cmbAlgorithm.addItem(
            _("Ed25519 (modern, smaller keys)"), userData="ED25519"
        )
        form.addRow(_("Algorithm:"), self.cmbAlgorithm)
        self.cmbKeySize = QComboBox(page)
        for size in (2048, 3072, 4096):
            self.cmbKeySize.addItem(str(size), userData=size)
        self.cmbKeySize.setCurrentIndex(self.cmbKeySize.count() - 1)
        form.addRow(_("Key size (bits):"), self.cmbKeySize)
        layout.addLayout(form)

        self.chkSigningSubkey = QCheckBox(_("Create a dedicated signing subkey"), page)
        self.chkSigningSubkey.setChecked(True)
        layout.addWidget(self.chkSigningSubkey)

        self.chkEncryptionSubkey = QCheckBox(
            _("Create a dedicated encryption subkey"), page
        )
        self.chkEncryptionSubkey.setChecked(True)
        layout.addWidget(self.chkEncryptionSubkey)


class Ui_PassphrasePage:
    def setupUi(self, page: QWizardPage) -> None:
        page.setTitle(_("Passphrase"))
        page.setSubTitle(
            _(
                "Protects your private key. Leave both fields empty for no "
                "passphrase (not recommended)."
            )
        )

        layout = QFormLayout(page)
        self.txtPassphrase = PasswordLineEdit(page)
        layout.addRow(_("Passphrase:"), self.txtPassphrase)
        self.strengthMeter = PasswordStrengthMeter(page)
        layout.addRow(self.strengthMeter)
        self.txtPassphraseConfirm = PasswordLineEdit(page)
        layout.addRow(_("Confirm:"), self.txtPassphraseConfirm)

        self.lblMismatch = QLabel(_("Passphrases do not match."), page)
        self.lblMismatch.setStyleSheet("color: red;")
        self.lblMismatch.setVisible(False)
        layout.addRow(self.lblMismatch)


class Ui_GeneratePage:
    def setupUi(self, page: QWizardPage) -> None:
        page.setTitle(_("Create the key"))
        page.setSubTitle("")

        layout = QVBoxLayout(page)

        self.lblSummary = QLabel(page)
        self.lblSummary.setWordWrap(True)
        layout.addWidget(self.lblSummary)

        self.progress = QProgressBar(page)
        self.progress.setRange(0, 0)  # busy indicator: duration isn't known
        layout.addWidget(self.progress)

        self.lblStatus = QLabel(page)
        self.lblStatus.setWordWrap(True)
        self.lblStatus.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.lblStatus)

        layout.addStretch()
