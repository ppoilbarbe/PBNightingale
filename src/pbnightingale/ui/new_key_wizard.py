"""Personal key creation wizard.

Collects an identity, key parameters and an optional passphrase, then
generates the key on a background thread (see ``core.gpg_backend.
GPGBackend.generate_key``) while showing progress on the final page.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QWizard, QWizardPage

from pbnightingale import preferences
from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key, NewKeyRequest
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.new_key_wizard_ui import (
    Ui_GeneratePage,
    Ui_IdentityPage,
    Ui_ParametersPage,
    Ui_PassphrasePage,
)


def _looks_like_email(value: str) -> bool:
    user, _sep, domain = value.partition("@")
    return bool(user) and "." in domain and not domain.startswith(".")


class _IdentityPage(QWizardPage):
    def __init__(self, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_IdentityPage()
        self._ui.setupUi(self)
        self._ui.txtName.textChanged.connect(self.completeChanged)
        self._ui.txtEmail.textChanged.connect(self.completeChanged)

    def isComplete(self) -> bool:
        return bool(self._ui.txtName.text().strip()) and _looks_like_email(
            self._ui.txtEmail.text().strip()
        )

    def name(self) -> str:
        return self._ui.txtName.text().strip()

    def email(self) -> str:
        return self._ui.txtEmail.text().strip()

    def comment(self) -> str:
        return self._ui.txtComment.text().strip()


class _ParametersPage(QWizardPage):
    def __init__(self, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_ParametersPage()
        self._ui.setupUi(self)
        idx = self._ui.cmbAlgorithm.findData(preferences.get_preferred_algorithm())
        if idx >= 0:
            self._ui.cmbAlgorithm.setCurrentIndex(idx)
        self._ui.cmbAlgorithm.currentIndexChanged.connect(self._on_algorithm_changed)
        self._on_algorithm_changed()

    def _on_algorithm_changed(self) -> None:
        is_rsa = self.algorithm() == "RSA"
        self._ui.cmbKeySize.setEnabled(is_rsa)
        # EdDSA cannot itself encrypt: a dedicated Curve25519 subkey is the
        # only way to get encryption capability, so it can't be unchecked.
        self._ui.chkEncryptionSubkey.setEnabled(is_rsa)
        if not is_rsa:
            self._ui.chkEncryptionSubkey.setChecked(True)

    def algorithm(self) -> str:
        return self._ui.cmbAlgorithm.currentData()

    def key_length(self) -> int:
        return self._ui.cmbKeySize.currentData()

    def signing_subkey(self) -> bool:
        return self._ui.chkSigningSubkey.isChecked()

    def encryption_subkey(self) -> bool:
        return self._ui.chkEncryptionSubkey.isChecked()


class _PassphrasePage(QWizardPage):
    def __init__(self, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_PassphrasePage()
        self._ui.setupUi(self)
        self._ui.txtPassphrase.textChanged.connect(self._on_text_changed)
        self._ui.txtPassphraseConfirm.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self) -> None:
        self._ui.lblMismatch.setVisible(not self._matches())
        self._ui.strengthMeter.set_password(self._ui.txtPassphrase.text())
        self.completeChanged.emit()

    def _matches(self) -> bool:
        return self._ui.txtPassphrase.text() == self._ui.txtPassphraseConfirm.text()

    def isComplete(self) -> bool:
        return self._matches()

    def passphrase(self) -> str:
        return self._ui.txtPassphrase.text()


class _GeneratePage(QWizardPage):
    def __init__(self, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_GeneratePage()
        self._ui.setupUi(self)
        self._pool = QThreadPool(self)
        self._started = False
        self._succeeded = False
        self.generated_key: Key | None = None

    def initializePage(self) -> None:
        if self._started:
            return
        self._started = True
        wizard: NewKeyWizard = self.wizard()
        request = wizard.build_request()
        self._ui.lblSummary.setText(wizard.summary_text(request))
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(_("Generating key…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().generate_key(request),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    def _on_success(self, key: Key) -> None:
        self.generated_key = key
        self._succeeded = True
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(_("Key created successfully."))
        self.completeChanged.emit()

    def _on_error(self, exc: Exception) -> None:
        self._started = False  # allow a retry once the user fixes the inputs
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            _("Could not create the key: {error}").format(error=str(exc))
        )
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._succeeded

    def isFinalPage(self) -> bool:
        return True


class NewKeyWizard(GeometryMixin, QWizard):
    """Wizard creating a personal key: identity, parameters, passphrase,
    then a certify-only primary key with signing/encryption subkeys
    (each optional, both proposed by default)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Create a New Personal Key"))
        self._init_geometry("new_key_wizard")

        self._page_identity = _IdentityPage(self)
        self._page_parameters = _ParametersPage(self)
        self._page_passphrase = _PassphrasePage(self)
        self._page_generate = _GeneratePage(self)
        self.addPage(self._page_identity)
        self.addPage(self._page_parameters)
        self.addPage(self._page_passphrase)
        self.addPage(self._page_generate)

    @property
    def generated_key(self) -> Key | None:
        return self._page_generate.generated_key

    def build_request(self) -> NewKeyRequest:
        return NewKeyRequest(
            name=self._page_identity.name(),
            email=self._page_identity.email(),
            comment=self._page_identity.comment(),
            algorithm=self._page_parameters.algorithm(),
            key_length=self._page_parameters.key_length(),
            passphrase=self._page_passphrase.passphrase(),
            signing_subkey=self._page_parameters.signing_subkey(),
            encryption_subkey=self._page_parameters.encryption_subkey(),
        )

    def summary_text(self, request: NewKeyRequest) -> str:
        subkeys = []
        if request.signing_subkey:
            subkeys.append(_("a dedicated signing subkey"))
        if request.encryption_subkey or request.algorithm == "ED25519":
            subkeys.append(_("a dedicated encryption subkey"))
        if not subkeys:
            subkeys_text = _("no additional subkeys")
        elif len(subkeys) == 1:
            subkeys_text = subkeys[0]
        else:
            subkeys_text = _("{first} and {second}").format(
                first=subkeys[0], second=subkeys[1]
            )
        uid = f"{request.name} <{request.email}>"
        if request.algorithm == "ED25519":
            return _(
                "About to create an Ed25519 key for {uid}, with {subkeys}."
            ).format(uid=uid, subkeys=subkeys_text)
        return _(
            "About to create a {size}-bit RSA key for {uid}, with {subkeys}."
        ).format(size=request.key_length, uid=uid, subkeys=subkeys_text)
