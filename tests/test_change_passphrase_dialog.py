"""Tests for the Change Passphrase dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.change_passphrase_dialog import ChangePassphraseDialog

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


def test_ok_button_disabled_until_new_passphrase_matches_and_nonempty(qtbot):
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.txtNewPassphrase.setText("hunter2")
    assert dialog._ok_button.isEnabled() is False
    assert dialog._ui.lblMismatch.isVisible() is True

    dialog._ui.txtNewPassphraseConfirm.setText("hunter2")
    assert dialog._ok_button.isEnabled() is True
    assert dialog._ui.lblMismatch.isVisible() is False


def test_strength_meter_tracks_the_new_passphrase_field(qtbot):
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.txtNewPassphrase.setText("correct horse battery staple")

    assert dialog._ui.strengthMeter._ui.lblBits.text() != "0 bits"


def test_change_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def change_passphrase(self, fingerprint, old_passphrase, new_passphrase):
            calls.append((fingerprint, old_passphrase, new_passphrase))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("old-pass")
    dialog._ui.txtNewPassphrase.setText("new-pass")
    dialog._ui.txtNewPassphraseConfirm.setText("new-pass")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (
        _FAKE_KEY.fingerprint,
        Passphrase("old-pass"),
        Passphrase("new-pass"),
    )


def test_successful_change_caches_the_new_passphrase_not_the_old_one(
    qtbot, monkeypatch
):
    class _FakeBackend:
        def change_passphrase(self, fingerprint, old_passphrase, new_passphrase):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("old-pass")
    dialog._ui.txtNewPassphrase.setText("new-pass")
    dialog._ui.txtNewPassphraseConfirm.setText("new-pass")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("new-pass")


def test_prefills_current_passphrase_from_the_cache(qtbot):
    passphrase_cache.store(_FAKE_KEY.fingerprint, Passphrase("cached-pass"), 60)

    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == "cached-pass"
    assert dialog._ui.txtNewPassphrase.text() == ""


def test_change_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def change_passphrase(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtNewPassphrase.setText("new-pass")
    dialog._ui.txtNewPassphraseConfirm.setText("new-pass")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtPassphrase.isEnabled() is True
    assert dialog._ok_button.isEnabled() is True
    assert dialog.updated_key is None


def test_change_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def change_passphrase(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keyedit.passwd 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.txtNewPassphrase.setText("new-pass")
    dialog._ui.txtNewPassphraseConfirm.setText("new-pass")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect current passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = ChangePassphraseDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
