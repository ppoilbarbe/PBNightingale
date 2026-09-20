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
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.new_key_wizard_ui import (
    Ui_GeneratePage,
    Ui_IdentityPage,
    Ui_ParametersPage,
    Ui_PassphrasePage,
)


def _looks_like_email(value: str) -> bool:
    """Return whether *value* has the rough shape of an email address.

    Parameters
    ----------
    value
        The candidate string.

    Returns
    -------
    :
        ``True`` if *value* has a non-empty part before ``@`` and a
        domain part containing a dot that doesn't start with one — not a
        full RFC validation, just enough to catch an obviously
        incomplete address.
    """
    user, _sep, domain = value.partition("@")
    return bool(user) and "." in domain and not domain.startswith(".")


class _IdentityPage(QWizardPage):
    """Wizard page collecting the new key's name, email and comment."""

    def __init__(self, parent: QWizard | None = None) -> None:
        """Build the page and wire its completeness check."""
        super().__init__(parent)
        self._ui = Ui_IdentityPage()
        self._ui.setupUi(self)
        self._ui.txtName.textChanged.connect(self.completeChanged)
        self._ui.txtEmail.textChanged.connect(self.completeChanged)

    def isComplete(self) -> bool:
        """Return whether a name and an email-shaped address were entered.

        Returns
        -------
        :
            ``True`` once both fields hold enough to build a valid user ID.
        """
        return bool(self._ui.txtName.text().strip()) and _looks_like_email(
            self._ui.txtEmail.text().strip()
        )

    def name(self) -> str:
        """Return the entered name, stripped of surrounding whitespace."""
        return self._ui.txtName.text().strip()

    def email(self) -> str:
        """Return the entered email address, stripped of surrounding whitespace."""
        return self._ui.txtEmail.text().strip()

    def comment(self) -> str:
        """Return the entered comment, stripped of surrounding whitespace."""
        return self._ui.txtComment.text().strip()


class _ParametersPage(QWizardPage):
    """Wizard page collecting the new key's algorithm and subkey choices."""

    def __init__(self, parent: QWizard | None = None) -> None:
        """Build the page, preselecting the preferred algorithm."""
        super().__init__(parent)
        self._ui = Ui_ParametersPage()
        self._ui.setupUi(self)
        idx = self._ui.cmbAlgorithm.findData(preferences.get_preferred_algorithm())
        if idx >= 0:
            self._ui.cmbAlgorithm.setCurrentIndex(idx)
        self._ui.cmbAlgorithm.currentIndexChanged.connect(self._on_algorithm_changed)
        self._on_algorithm_changed()

    def _on_algorithm_changed(self) -> None:
        """Adjust the key-size and encryption-subkey fields for the selected algorithm.

        ED25519 forces a dedicated encryption subkey, since EdDSA itself
        cannot encrypt.
        """
        is_rsa = self.algorithm() == "RSA"
        self._ui.cmbKeySize.setEnabled(is_rsa)
        # EdDSA cannot itself encrypt: a dedicated Curve25519 subkey is the
        # only way to get encryption capability, so it can't be unchecked.
        self._ui.chkEncryptionSubkey.setEnabled(is_rsa)
        if not is_rsa:
            self._ui.chkEncryptionSubkey.setChecked(True)

    def algorithm(self) -> str:
        """Return the selected algorithm, ``"RSA"`` or ``"ED25519"``."""
        return self._ui.cmbAlgorithm.currentData()

    def key_length(self) -> int:
        """Return the selected RSA key length, in bits."""
        return self._ui.cmbKeySize.currentData()

    def signing_subkey(self) -> bool:
        """Return whether a dedicated signing subkey was requested."""
        return self._ui.chkSigningSubkey.isChecked()

    def encryption_subkey(self) -> bool:
        """Return whether a dedicated encryption subkey was requested."""
        return self._ui.chkEncryptionSubkey.isChecked()


class _PassphrasePage(QWizardPage):
    """Wizard page collecting the new key's optional passphrase."""

    def __init__(self, parent: QWizard | None = None) -> None:
        """Build the page and wire its live strength/match feedback."""
        super().__init__(parent)
        self._ui = Ui_PassphrasePage()
        self._ui.setupUi(self)
        self._ui.txtPassphrase.textChanged.connect(self._on_text_changed)
        self._ui.txtPassphraseConfirm.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self) -> None:
        """Update the mismatch hint and strength meter as the fields change."""
        self._ui.lblMismatch.setVisible(not self._matches())
        self._ui.strengthMeter.set_password(self._ui.txtPassphrase.text())
        self.completeChanged.emit()

    def _matches(self) -> bool:
        """Return whether the passphrase and its confirmation are identical."""
        return self._ui.txtPassphrase.text() == self._ui.txtPassphraseConfirm.text()

    def isComplete(self) -> bool:
        """Return whether the passphrase and its confirmation match.

        Returns
        -------
        :
            ``True`` once both fields hold the same text (including both
            empty, for no passphrase at all).
        """
        return self._matches()

    def passphrase(self) -> Passphrase:
        """Return the entered passphrase, unmodified (empty for none)."""
        return Passphrase(self._ui.txtPassphrase.text())


class _GeneratePage(QWizardPage):
    """Wizard's final page: generates the key and reports progress."""

    def __init__(self, parent: QWizard | None = None) -> None:
        """Build the page and its worker-thread state."""
        super().__init__(parent)
        self._ui = Ui_GeneratePage()
        self._ui.setupUi(self)
        self._pool = QThreadPool(self)
        self._started = False
        self._succeeded = False
        self.generated_key: Key | None = None

    def initializePage(self) -> None:
        """Start key generation the first time this page is shown.

        A no-op on a later call — e.g. navigating back and forward again
        — since ``_started`` is only reset by ``_on_error()``, to allow a
        genuine retry once the user has fixed the inputs.
        """
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
        """Record the generated key and mark the page complete.

        Parameters
        ----------
        key
            The key just generated.
        """
        self.generated_key = key
        self._succeeded = True
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(_("Key created successfully."))
        self.completeChanged.emit()

    def _on_error(self, exc: Exception) -> None:
        """Show the failure and allow a retry.

        Parameters
        ----------
        exc
            The exception raised by the failed generation.
        """
        self._started = False  # allow a retry once the user fixes the inputs
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            _("Could not create the key: {error}").format(error=str(exc))
        )
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        """Return whether the key was generated successfully.

        Returns
        -------
        :
            ``True`` once generation has succeeded — the wizard's Finish
            button stays disabled until then.
        """
        return self._succeeded

    def isFinalPage(self) -> bool:
        """Return ``True`` — this is always the wizard's last page."""
        return True


class NewKeyWizard(GeometryMixin, QWizard):
    """Wizard creating a personal key: identity, parameters, passphrase, then generation.

    Produces a certify-only primary key with signing/encryption subkeys,
    each optional and both proposed by default.
    """

    def __init__(self, parent=None) -> None:
        """Build the wizard and add its four pages in order."""
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
        """The key generated by the final page, or ``None`` before it succeeds."""
        return self._page_generate.generated_key

    def build_request(self) -> NewKeyRequest:
        """Return a ``NewKeyRequest`` built from every page's current input."""
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
        """Return the human-readable summary shown on the generate page.

        Parameters
        ----------
        request
            The key parameters the summary describes.

        Returns
        -------
        :
            A sentence naming the algorithm (and RSA key size), the
            identity, and which subkeys will be created.
        """
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
