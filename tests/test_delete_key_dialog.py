"""Tests for the Delete Key dialog — strong confirmation required."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import GPGBackendError, Key, Uid
from pbnightingale.ui.delete_key_dialog import DeleteKeyDialog

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

_PUBLIC_KEY = Key(
    fingerprint="BBBB111122223333444455556666777788889999",
    keyid="5555666677778888",
    algo="1",
    length=2048,
    created=1_700_000_000,
    expires=None,
    trust="f",
    owner_trust="",
    uids=[Uid("Bob Example <bob@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=False,
    can_sign=True,
    can_encrypt=False,
    can_certify=True,
    can_authenticate=False,
)


def test_delete_button_disabled_until_confirmation_checked(qtbot):
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.chkConfirm.setChecked(True)
    assert dialog._ok_button.isEnabled() is True

    dialog._ui.chkConfirm.setChecked(False)
    assert dialog._ok_button.isEnabled() is False


def test_warning_mentions_the_key_id(qtbot):
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    assert _FAKE_KEY.keyid in dialog._ui.lblWarning.text()


def test_dialog_has_no_passphrase_field(qtbot):
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    assert not hasattr(dialog._ui, "txtPassphrase")


def test_delete_succeeds_with_mocked_backend_for_a_secret_key(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def delete_key(self, fingerprint, *, secret):
            calls.append((fingerprint, secret))

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.result() == DeleteKeyDialog.DialogCode.Accepted)
    assert calls == [(_FAKE_KEY.fingerprint, True)]


def test_delete_succeeds_for_a_public_only_key(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def delete_key(self, fingerprint, *, secret):
            calls.append((fingerprint, secret))

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = DeleteKeyDialog([_PUBLIC_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.result() == DeleteKeyDialog.DialogCode.Accepted)
    assert calls == [(_PUBLIC_KEY.fingerprint, False)]


def test_delete_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def delete_key(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.chkConfirm.isEnabled() is True
    assert dialog._ok_button.isEnabled() is True
    assert dialog.result() != DeleteKeyDialog.DialogCode.Accepted


def test_status_label_text_is_selectable(qtbot):
    dialog = DeleteKeyDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse


def test_warning_lists_every_key_id_when_deleting_several(qtbot):
    dialog = DeleteKeyDialog([_FAKE_KEY, _PUBLIC_KEY])
    qtbot.addWidget(dialog)

    text = dialog._ui.lblWarning.text()
    assert "2 keys" in text
    assert _FAKE_KEY.keyid in text
    assert _PUBLIC_KEY.keyid in text


def test_delete_several_keys_deletes_each_one(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def delete_key(self, fingerprint, *, secret):
            calls.append((fingerprint, secret))

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = DeleteKeyDialog([_FAKE_KEY, _PUBLIC_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.result() == DeleteKeyDialog.DialogCode.Accepted)
    assert calls == [(_FAKE_KEY.fingerprint, True), (_PUBLIC_KEY.fingerprint, False)]
    assert dialog.deleted_fingerprints == [
        _FAKE_KEY.fingerprint,
        _PUBLIC_KEY.fingerprint,
    ]


def test_retry_after_a_mid_batch_failure_skips_keys_already_deleted(qtbot, monkeypatch):
    calls = []
    fail = [True]

    class _FlakyBackend:
        def delete_key(self, fingerprint, *, secret):
            calls.append(fingerprint)
            if fingerprint == _PUBLIC_KEY.fingerprint and fail[0]:
                fail[0] = False
                raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FlakyBackend)
    dialog = DeleteKeyDialog([_FAKE_KEY, _PUBLIC_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()
    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog.deleted_fingerprints == [_FAKE_KEY.fingerprint]

    dialog._ui.buttonBox.accepted.emit()
    qtbot.waitUntil(lambda: dialog.result() == DeleteKeyDialog.DialogCode.Accepted)
    assert calls == [
        _FAKE_KEY.fingerprint,
        _PUBLIC_KEY.fingerprint,
        _PUBLIC_KEY.fingerprint,
    ]
