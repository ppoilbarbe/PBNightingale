"""Tests for the Set Expiration dialog (primary key or one subkey)."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import (
    BadPassphraseError,
    GPGBackendError,
    Key,
    Subkey,
    Uid,
)
from pbnightingale.ui.set_expiration_dialog import SetExpirationDialog

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


def test_primary_key_mode_defaults_to_never_expires(qtbot):
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Set Key Expiration"
    assert dialog._ui.chkNoExpiration.isChecked() is True
    assert dialog._ui.dateExpiration.isEnabled() is False


def test_subkey_mode_mentions_the_subkey_and_defaults_to_never(qtbot):
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Set Subkey Expiration"
    assert _SUBKEY.keyid in dialog._ui.lblExplanation.text()
    assert dialog._ui.chkNoExpiration.isChecked() is True


def test_preselects_an_existing_expiration_date(qtbot):
    expiring_subkey = Subkey(**{**_SUBKEY.__dict__, "expires": 1_893_456_000})

    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint, expiring_subkey)
    qtbot.addWidget(dialog)

    assert dialog._ui.chkNoExpiration.isChecked() is False
    assert dialog._ui.dateExpiration.isEnabled() is True


def test_toggling_no_expiration_enables_and_disables_the_date_field(qtbot):
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.chkNoExpiration.setChecked(False)
    assert dialog._ui.dateExpiration.isEnabled() is True

    dialog._ui.chkNoExpiration.setChecked(True)
    assert dialog._ui.dateExpiration.isEnabled() is False


def test_setting_never_expires_on_the_primary_key(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_key_expiration(self, fingerprint, passphrase, expire):
            calls.append((fingerprint, passphrase, expire))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, "", "0")


def test_setting_a_date_on_the_primary_key(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_key_expiration(self, fingerprint, passphrase, expire):
            calls.append((fingerprint, passphrase, expire))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.chkNoExpiration.setChecked(False)
    dialog._ui.dateExpiration.setDate(QDate(2030, 6, 15))

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, "", "2030-06-15")


def test_setting_a_date_on_a_subkey_targets_the_subkey_fingerprint(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_subkey_expiration(self, fingerprint, passphrase, subkey_fpr, expire):
            calls.append((fingerprint, passphrase, subkey_fpr, expire))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint, _SUBKEY)
    qtbot.addWidget(dialog)
    dialog._ui.chkNoExpiration.setChecked(False)
    dialog._ui.dateExpiration.setDate(QDate(2030, 6, 15))

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (
        _FAKE_KEY.fingerprint,
        "",
        _SUBKEY.fingerprint,
        "2030-06-15",
    )


def test_successful_set_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def set_key_expiration(self, fingerprint, passphrase, expire):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == "s3cret"


def test_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def set_key_expiration(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.chkNoExpiration.isEnabled() is True
    assert dialog.updated_key is None


def test_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def set_key_expiration(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR set_expire 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = SetExpirationDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
