"""Tests for the Set Primary User ID dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.ui.set_primary_uid_dialog import SetPrimaryUidDialog

_UID = Uid("Alice Example <alice@example.com>", revoked=False)

_FAKE_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="",
    uids=[_UID],
    photos=[],
    subkeys=[],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


def test_explanation_mentions_the_uid(qtbot):
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)

    assert _UID.value in dialog._ui.lblExplanation.text()


def test_set_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_primary_uid(self, fingerprint, passphrase, uid):
            calls.append((fingerprint, passphrase, uid))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, "", _UID.value)


def test_successful_set_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def set_primary_uid(self, fingerprint, passphrase, uid):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == "s3cret"


def test_set_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def set_primary_uid(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtPassphrase.isEnabled() is True
    assert dialog.updated_key is None


def test_set_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def set_primary_uid(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = SetPrimaryUidDialog(_FAKE_KEY.fingerprint, _UID)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
