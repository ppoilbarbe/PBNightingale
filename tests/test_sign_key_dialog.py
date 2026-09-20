"""Tests for the Sign Key dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.sign_key_dialog import SignKeyDialog

_TARGET_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="-",
    owner_trust="",
    uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=False,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)

_MY_KEY = Key(
    fingerprint="BBBB111122223333444455556666777788889999",
    keyid="5555666677778888",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="u",
    uids=[Uid("Bob Example <bob@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


_MY_OTHER_KEY = Key(
    fingerprint="CCCC111122223333444455556666777788889999",
    keyid="9999888877776666",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="u",
    uids=[Uid("Carl Example <carl@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


def test_explanation_mentions_the_target_uid(qtbot):
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    assert _TARGET_KEY.uids[0].value in dialog._ui.lblExplanation.text()


def test_sign_as_combo_lists_certify_capable_own_keys(qtbot):
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbSignAs.count() == 1
    assert dialog._ui.cmbSignAs.currentData() is _MY_KEY


def test_local_only_is_checked_by_default(qtbot):
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    assert dialog._ui.chkLocalOnly.isChecked() is True


def test_ok_disabled_with_a_message_when_no_signing_key_available(qtbot):
    dialog = SignKeyDialog(_TARGET_KEY, [])
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False
    assert "no personal key" in dialog._ui.lblStatus.text()


def test_sign_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def sign_key(
            self,
            fingerprint,
            passphrase,
            *,
            signing_key_fingerprint,
            cert_level,
            local_only,
        ):
            calls.append(
                (
                    fingerprint,
                    passphrase,
                    signing_key_fingerprint,
                    cert_level,
                    local_only,
                )
            )
            return _TARGET_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _TARGET_KEY)
    assert calls[0] == (
        _TARGET_KEY.fingerprint,
        Passphrase("s3cret"),
        _MY_KEY.fingerprint,
        0,
        True,
    )


def test_successful_sign_caches_the_passphrase_under_the_signer(qtbot, monkeypatch):
    class _FakeBackend:
        def sign_key(self, fingerprint, passphrase, **kwargs):
            return _TARGET_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _TARGET_KEY)
    assert passphrase_cache.get(_MY_KEY.fingerprint) == Passphrase("s3cret")
    assert passphrase_cache.get(_TARGET_KEY.fingerprint) is None


def test_switching_signer_prefills_that_signers_cached_passphrase(qtbot):
    passphrase_cache.store(_MY_OTHER_KEY.fingerprint, Passphrase("other-pass"), 60)
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY, _MY_OTHER_KEY])
    qtbot.addWidget(dialog)
    assert dialog._ui.txtPassphrase.text() == ""

    idx = dialog._ui.cmbSignAs.findData(_MY_OTHER_KEY)
    dialog._ui.cmbSignAs.setCurrentIndex(idx)

    assert dialog._ui.txtPassphrase.text() == "other-pass"


def test_sign_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def sign_key(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.cmbSignAs.isEnabled() is True
    assert dialog.updated_key is None


def test_sign_bad_passphrase_shows_friendly_message(qtbot, monkeypatch):
    class _FailingBackend:
        def sign_key(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keyedit.sign-key 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: (
            "Incorrect passphrase for the selected signing key"
            in dialog._ui.lblStatus.text()
        )
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = SignKeyDialog(_TARGET_KEY, [_MY_KEY])
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
