"""Tests for the Revoke Subkey dialog — strong confirmation required."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import (
    BadPassphraseError,
    GPGBackendError,
    Key,
    Subkey,
    Uid,
)
from pbnightingale.ui.revoke_subkey_dialog import RevokeSubkeyDialog

_SUBKEY = Subkey(
    keyid="AAAABBBBCCCCDDDD",
    fingerprint="1111222233334444555566667777888899990000",
    algo="1",
    length=2048,
    created=1_700_000_000,
    expires=None,
    trust="u",
    can_sign=False,
    can_encrypt=True,
    can_certify=False,
    can_authenticate=False,
)

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
    subkeys=[_SUBKEY],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


def test_revoke_button_disabled_until_confirmation_checked(qtbot):
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.chkConfirm.setChecked(True)
    assert dialog._ok_button.isEnabled() is True

    dialog._ui.chkConfirm.setChecked(False)
    assert dialog._ok_button.isEnabled() is False


def test_warning_mentions_the_subkey_id(qtbot):
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)

    assert _SUBKEY.keyid in dialog._ui.lblWarning.text()


def test_revoke_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def revoke_subkey(self, fingerprint, subkey_keyid, passphrase):
            calls.append((fingerprint, subkey_keyid, passphrase))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, _SUBKEY.keyid, "")


def test_successful_revoke_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def revoke_subkey(self, fingerprint, subkey_keyid, passphrase):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == "s3cret"


def test_revoke_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def revoke_subkey(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.chkConfirm.isEnabled() is True
    assert dialog._ok_button.isEnabled() is True
    assert dialog.updated_key is None


def test_revoke_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def revoke_subkey(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = RevokeSubkeyDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
