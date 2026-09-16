"""Tests for the Add Subkey dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.ui.add_subkey_dialog import AddSubkeyDialog

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


def test_defaults_to_preferred_algorithm_and_rsa_key_size_enabled(qtbot):
    from pbnightingale import preferences

    preferences.set_preferred_algorithm("ED25519")
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbAlgorithm.currentData() == "ED25519"
    assert dialog._ui.cmbKeySize.isEnabled() is False


def test_rsa_selection_enables_key_size(qtbot):
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    idx = dialog._ui.cmbAlgorithm.findData("ED25519")
    dialog._ui.cmbAlgorithm.setCurrentIndex(idx)
    assert dialog._ui.cmbKeySize.isEnabled() is False

    idx = dialog._ui.cmbAlgorithm.findData("RSA")
    dialog._ui.cmbAlgorithm.setCurrentIndex(idx)
    assert dialog._ui.cmbKeySize.isEnabled() is True


def test_add_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def add_subkey(self, fingerprint, passphrase, *, usage, algorithm, key_length):
            calls.append((fingerprint, passphrase, usage, algorithm, key_length))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0][0] == _FAKE_KEY.fingerprint


def test_successful_add_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def add_subkey(self, fingerprint, passphrase, *, usage, algorithm, key_length):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == "s3cret"


def test_prefills_passphrase_from_the_cache(qtbot):
    passphrase_cache.store(_FAKE_KEY.fingerprint, "cached-pass", 60)

    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == "cached-pass"


def test_add_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def add_subkey(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.cmbPurpose.isEnabled() is True
    assert dialog.updated_key is None


def test_add_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def add_subkey(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR key_generate 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = AddSubkeyDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
