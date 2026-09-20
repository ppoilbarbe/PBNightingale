"""Tests for the personal key creation wizard."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import GPGBackendError, Key, NewKeyRequest, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.new_key_wizard import NewKeyWizard
from tests.gpg_test_helpers import generate_test_key

_FAKE_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="",
    uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


def _fill_identity(
    wizard: NewKeyWizard, name="Alice Example", email="alice@example.com"
):
    wizard._page_identity._ui.txtName.setText(name)
    wizard._page_identity._ui.txtEmail.setText(email)


def test_identity_page_incomplete_until_name_and_valid_email(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    page = wizard._page_identity

    assert page.isComplete() is False

    page._ui.txtName.setText("Alice Example")
    assert page.isComplete() is False  # email still missing

    page._ui.txtEmail.setText("not-an-email")
    assert page.isComplete() is False  # no domain dot

    page._ui.txtEmail.setText("alice@example.com")
    assert page.isComplete() is True


def test_passphrase_page_requires_matching_values(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.setCurrentId(wizard.pageIds()[2])  # the passphrase page itself
    page = wizard._page_passphrase

    assert page.isComplete() is True  # both empty: no passphrase, valid

    page._ui.txtPassphrase.setText("hunter2")
    assert page.isComplete() is False
    assert page._ui.lblMismatch.isVisible() is True

    page._ui.txtPassphraseConfirm.setText("hunter2")
    assert page.isComplete() is True
    assert page._ui.lblMismatch.isVisible() is False


def test_build_request_collects_fields_from_all_pages(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    _fill_identity(wizard, "Bob Example", "bob@example.com")
    wizard._page_identity._ui.txtComment.setText("work")
    wizard._page_parameters._ui.cmbKeySize.setCurrentIndex(0)  # 2048
    wizard._page_parameters._ui.chkEncryptionSubkey.setChecked(False)
    wizard._page_passphrase._ui.txtPassphrase.setText("s3cret")
    wizard._page_passphrase._ui.txtPassphraseConfirm.setText("s3cret")

    request = wizard.build_request()

    assert request == NewKeyRequest(
        name="Bob Example",
        email="bob@example.com",
        comment="work",
        key_length=2048,
        passphrase=Passphrase("s3cret"),
        signing_subkey=True,
        encryption_subkey=False,
    )


def test_parameters_page_defaults_to_preferred_algorithm(qtbot):
    from pbnightingale import preferences

    preferences.set_preferred_algorithm("ED25519")
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)

    assert wizard._page_parameters.algorithm() == "ED25519"


def test_selecting_ed25519_forces_and_disables_encryption_subkey(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    page = wizard._page_parameters
    page._ui.chkEncryptionSubkey.setChecked(False)

    idx = page._ui.cmbAlgorithm.findData("ED25519")
    page._ui.cmbAlgorithm.setCurrentIndex(idx)

    assert page._ui.chkEncryptionSubkey.isChecked() is True
    assert page._ui.chkEncryptionSubkey.isEnabled() is False
    assert page._ui.cmbKeySize.isEnabled() is False


def test_switching_back_to_rsa_reenables_key_size_and_encryption_checkbox(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    page = wizard._page_parameters
    idx_ed = page._ui.cmbAlgorithm.findData("ED25519")
    page._ui.cmbAlgorithm.setCurrentIndex(idx_ed)

    idx_rsa = page._ui.cmbAlgorithm.findData("RSA")
    page._ui.cmbAlgorithm.setCurrentIndex(idx_rsa)

    assert page._ui.chkEncryptionSubkey.isEnabled() is True
    assert page._ui.cmbKeySize.isEnabled() is True


def test_summary_text_for_ed25519_mentions_no_bit_size(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    request = NewKeyRequest(
        name="Carol", email="carol@example.com", algorithm="ED25519"
    )

    text = wizard.summary_text(request)

    assert "Ed25519" in text
    assert "bit" not in text


def test_summary_text_lists_requested_subkeys(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    request = NewKeyRequest(name="Carol", email="carol@example.com")

    text = wizard.summary_text(request)

    assert "Carol <carol@example.com>" in text
    assert "signing subkey" in text
    assert "encryption subkey" in text
    assert " and " in text


def test_summary_text_with_a_single_subkey_has_no_and(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    request = NewKeyRequest(
        name="Carol", email="carol@example.com", encryption_subkey=False
    )

    text = wizard.summary_text(request)

    assert "signing subkey" in text
    assert "encryption subkey" not in text
    assert " and " not in text


def test_summary_text_without_subkeys(qtbot):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    request = NewKeyRequest(
        name="Carol",
        email="carol@example.com",
        signing_subkey=False,
        encryption_subkey=False,
    )

    text = wizard.summary_text(request)

    assert "no additional subkeys" in text


def test_generate_page_succeeds_with_mocked_backend(qtbot, monkeypatch):
    class _FakeBackend:
        def generate_key(self, request: NewKeyRequest) -> Key:
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    _fill_identity(wizard)

    wizard.show()
    wizard.setCurrentId(wizard.pageIds()[-1])  # jump straight to the Generate page

    qtbot.waitUntil(lambda: wizard._page_generate.isComplete())
    assert wizard.generated_key is _FAKE_KEY
    assert "successfully" in wizard._page_generate._ui.lblStatus.text()


def test_generate_page_reports_backend_failure_and_allows_retry(qtbot, monkeypatch):
    class _FailingBackend:
        def generate_key(self, request: NewKeyRequest) -> Key:
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    _fill_identity(wizard)

    page = wizard._page_generate
    wizard.show()
    wizard.setCurrentId(wizard.pageIds()[-1])

    qtbot.waitUntil(lambda: "boom" in page._ui.lblStatus.text())
    assert page.isComplete() is False
    flags = page._ui.lblStatus.textInteractionFlags()
    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse

    # Retrying (re-entering the page) must attempt generation again.
    monkeypatch.setattr(
        gpg_backend,
        "default_backend",
        lambda: type("B", (), {"generate_key": staticmethod(lambda r: _FAKE_KEY)})(),
    )
    page.initializePage()

    qtbot.waitUntil(lambda: page.isComplete())
    assert wizard.generated_key is _FAKE_KEY


def test_generate_page_ignores_reinitialization_after_success(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def generate_key(self, request: NewKeyRequest) -> Key:
            calls.append(request)
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    _fill_identity(wizard)
    wizard.show()
    wizard.setCurrentId(wizard.pageIds()[-1])
    qtbot.waitUntil(lambda: wizard._page_generate.isComplete())

    wizard._page_generate.initializePage()  # e.g. Back then Next after success

    assert len(calls) == 1
    assert wizard._page_generate.isFinalPage() is True


def test_wizard_generates_a_real_key_end_to_end(qtbot, gnupg_home):
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)
    _fill_identity(wizard, "Dave Example", "dave@example.com")
    monkeypatch_key_length = 1024
    wizard._page_parameters.key_length = lambda: monkeypatch_key_length

    wizard.show()
    wizard.setCurrentId(wizard.pageIds()[-1])

    qtbot.waitUntil(lambda: wizard._page_generate.isComplete(), timeout=15000)
    key = wizard.generated_key
    assert key is not None
    assert [uid.value for uid in key.uids] == ["Dave Example <dave@example.com>"]
    assert key.has_secret is True
    assert len(key.subkeys) == 2

    from pbnightingale.core.gpg_backend import default_backend

    assert any(k.fingerprint == key.fingerprint for k in default_backend().list_keys())


def test_new_key_action_reachable_regardless_of_existing_keys(qtbot, gnupg_home):
    generate_test_key(gnupg_home)
    wizard = NewKeyWizard()
    qtbot.addWidget(wizard)

    assert wizard._page_identity.isComplete() is False
