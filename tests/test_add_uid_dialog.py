"""Tests for the Add User ID dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.add_uid_dialog import AddUidDialog

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


def test_ok_button_disabled_until_name_and_email_are_valid(qtbot):
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    ok_button = dialog._ok_button

    assert ok_button.isEnabled() is False

    dialog._ui.txtName.setText("Bob Example")
    assert ok_button.isEnabled() is False

    dialog._ui.txtEmail.setText("not-an-email")
    assert ok_button.isEnabled() is False

    dialog._ui.txtEmail.setText("bob@example.com")
    assert ok_button.isEnabled() is True


def test_add_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def add_uid(self, fingerprint, passphrase, *, name, email, comment):
            calls.append((fingerprint, passphrase, name, email, comment))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtName.setText("Bob Example")
    dialog._ui.txtEmail.setText("bob@example.com")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (
        _FAKE_KEY.fingerprint,
        Passphrase(""),
        "Bob Example",
        "bob@example.com",
        "",
    )


def test_successful_add_caches_the_passphrase(qtbot, monkeypatch):
    class _FakeBackend:
        def add_uid(self, fingerprint, passphrase, *, name, email, comment):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtName.setText("Bob Example")
    dialog._ui.txtEmail.setText("bob@example.com")
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("s3cret")


def test_prefills_passphrase_from_the_cache(qtbot):
    passphrase_cache.store(_FAKE_KEY.fingerprint, Passphrase("cached-pass"), 60)

    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == "cached-pass"


def test_add_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def add_uid(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtName.setText("Bob Example")
    dialog._ui.txtEmail.setText("bob@example.com")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtName.isEnabled() is True
    assert dialog.updated_key is None


def test_add_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def add_uid(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtName.setText("Bob Example")
    dialog._ui.txtEmail.setText("bob@example.com")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = AddUidDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
