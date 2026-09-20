"""Tests for the Add Photo dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.add_photo_dialog import AddPhotoDialog
from pbnightingale.ui.add_photo_dialog_ui import MAX_PREVIEW_DIMENSION
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


def _choose_image(monkeypatch, path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )


def test_ok_button_disabled_until_an_image_is_chosen(qtbot):
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False


def test_choosing_an_image_enables_ok_and_shows_preview(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.btnChooseImage.click()

    assert dialog._ok_button.isEnabled() is True
    assert not dialog._ui.lblPreview.pixmap().isNull()
    assert dialog._jpeg_path is not None
    assert dialog._jpeg_path.exists()


def test_preview_label_is_large_enough_to_show_the_scaled_image_uncropped(qtbot):
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    size = dialog._ui.lblPreview.size()

    assert (size.width(), size.height()) == (
        MAX_PREVIEW_DIMENSION,
        MAX_PREVIEW_DIMENSION,
    )


def test_preview_matches_the_image_actually_sent_to_gpg(qtbot, monkeypatch, tmp_path):
    # make_test_jpeg's fixture is deliberately non-square (24x30) — a
    # cropped preview (the bug this guards against) would otherwise go
    # unnoticed with a square test image.
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.btnChooseImage.click()

    sent = QImage(str(dialog._jpeg_path))
    preview = dialog._ui.lblPreview.pixmap()
    assert (preview.width(), preview.height()) == (sent.width(), sent.height())


def test_choosing_an_invalid_image_shows_error_and_keeps_ok_disabled(
    qtbot, monkeypatch, tmp_path
):
    not_an_image = tmp_path / "not_an_image.png"
    not_an_image.write_bytes(b"nope")
    _choose_image(monkeypatch, not_an_image)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.btnChooseImage.click()

    assert "Could not load image" in dialog._ui.lblStatus.text()
    assert dialog._ok_button.isEnabled() is False


def test_cancelling_the_file_dialog_does_nothing(qtbot, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.btnChooseImage.click()

    assert dialog._ok_button.isEnabled() is False
    assert dialog._jpeg_path is None


def test_add_succeeds_with_mocked_backend(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)
    calls = []

    class _FakeBackend:
        def add_photo_uid(self, fingerprint, passphrase, jpeg_path):
            calls.append((fingerprint, passphrase, jpeg_path))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.btnChooseImage.click()

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0][0] == _FAKE_KEY.fingerprint


def test_successful_add_caches_the_passphrase(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)

    class _FakeBackend:
        def add_photo_uid(self, fingerprint, passphrase, jpeg_path):
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.btnChooseImage.click()
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("s3cret")


def test_add_reports_backend_failure_and_reenables_form(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)

    class _FailingBackend:
        def add_photo_uid(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.btnChooseImage.click()

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.btnChooseImage.isEnabled() is True
    assert dialog.updated_key is None


def test_add_bad_passphrase_shows_friendly_message(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)

    class _FailingBackend:
        def add_photo_uid(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.btnChooseImage.click()

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_status_label_text_is_selectable(qtbot):
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse


def test_rejecting_cleans_up_the_temp_file(qtbot, monkeypatch, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog._ui.btnChooseImage.click()
    temp_path = dialog._jpeg_path
    assert temp_path.exists()

    dialog.reject()

    assert not temp_path.exists()


def test_resize_warning_mentions_the_max_dimension_before_choosing(qtbot):
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    text = dialog._ui.lblResizeWarning.text()

    assert str(MAX_PREVIEW_DIMENSION) in text
    assert "revoked" in text


def test_resize_warning_shows_the_actual_resized_dimensions_once_chosen(
    qtbot, monkeypatch, tmp_path
):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    _choose_image(monkeypatch, jpeg)
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)

    dialog._ui.btnChooseImage.click()

    preview = dialog._ui.lblPreview.pixmap()
    text = dialog._ui.lblResizeWarning.text()
    assert f"{preview.width()}×{preview.height()}" in text
    assert "revoked" in text


def test_button_and_warning_column_fits_within_the_preview_height(qtbot):
    dialog = AddPhotoDialog(_FAKE_KEY.fingerprint)
    qtbot.addWidget(dialog)
    dialog.adjustSize()

    preview_bottom = dialog._ui.lblPreview.geometry().bottom()
    warning_bottom = dialog._ui.lblResizeWarning.geometry().bottom()

    assert warning_bottom <= preview_bottom
