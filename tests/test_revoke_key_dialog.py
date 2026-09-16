"""Tests for the Revoke Key dialog — strong confirmation required."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.ui.revoke_key_dialog import RevokeKeyDialog

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


def test_revoke_button_disabled_until_confirmation_checked(qtbot):
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.chkConfirm.setChecked(True)
    assert dialog._ok_button.isEnabled() is True

    dialog._ui.chkConfirm.setChecked(False)
    assert dialog._ok_button.isEnabled() is False


def test_warning_mentions_the_key_id(qtbot):
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    assert _FAKE_KEY.keyid in dialog._ui.lblWarning.text()


def test_revoke_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def revoke_key(self, fingerprint, passphrase):
            calls.append((fingerprint, passphrase))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, "")


def test_successful_revoke_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def revoke_key(self, fingerprint, passphrase):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == "s3cret"


def test_revoke_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def revoke_key(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.chkConfirm.isEnabled() is True
    assert dialog._ok_button.isEnabled() is True
    assert dialog.updated_key is None


def test_revoke_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def revoke_key(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "Incorrect passphrase" in dialog._ui.lblStatus.text())
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = RevokeKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
