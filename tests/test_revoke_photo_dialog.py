"""Tests for the Revoke Photo dialog — strong confirmation required."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import (
    BadPassphraseError,
    GPGBackendError,
    Key,
    PhotoUid,
    Uid,
)
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.revoke_photo_dialog import RevokePhotoDialog
from tests.gpg_test_helpers import make_test_jpeg

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


def _make_photo(tmp_path, index: int = 1) -> PhotoUid:
    jpeg_path = make_test_jpeg(tmp_path / "photo.jpg")
    return PhotoUid(index=index, image=jpeg_path.read_bytes(), revoked=False)


def test_revoke_button_disabled_until_confirmation_checked(qtbot, tmp_path):
    photo = _make_photo(tmp_path)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.chkConfirm.setChecked(True)
    assert dialog._ok_button.isEnabled() is True

    dialog._ui.chkConfirm.setChecked(False)
    assert dialog._ok_button.isEnabled() is False


def test_preview_shows_the_photo(qtbot, tmp_path):
    photo = _make_photo(tmp_path)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)

    assert not dialog._ui.lblPreview.pixmap().isNull()


def test_revoke_succeeds_with_mocked_backend(qtbot, monkeypatch, tmp_path):
    photo = _make_photo(tmp_path)
    calls = []

    class _FakeBackend:
        def revoke_photo_uid(self, fingerprint, passphrase, photo_index):
            calls.append((fingerprint, passphrase, photo_index))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, Passphrase(""), photo.index)


def test_successful_revoke_caches_the_passphrase(qtbot, monkeypatch, tmp_path):
    photo = _make_photo(tmp_path)

    class _FakeBackend:
        def revoke_photo_uid(self, fingerprint, passphrase, photo_index):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("s3cret")


def test_revoke_reports_backend_failure_and_reenables_form(
    qtbot, monkeypatch, tmp_path
):
    photo = _make_photo(tmp_path)

    class _FailingBackend:
        def revoke_photo_uid(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.chkConfirm.isEnabled() is True
    assert dialog._ok_button.isEnabled() is True
    assert dialog.updated_key is None


def test_revoke_bad_passphrase_shows_friendly_message(qtbot, monkeypatch, tmp_path):
    photo = _make_photo(tmp_path)

    class _FailingBackend:
        def revoke_photo_uid(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keyedit.revoke.uid 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)
    dialog._ui.chkConfirm.setChecked(True)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot, tmp_path):
    photo = _make_photo(tmp_path)
    dialog = RevokePhotoDialog(_FAKE_KEY.fingerprint, photo)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
