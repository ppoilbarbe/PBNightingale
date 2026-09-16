"""Tests for the Photo Viewer dialog."""

from __future__ import annotations

from pbnightingale.core.gpg_backend import PhotoUid
from pbnightingale.ui.photo_viewer_dialog import PhotoViewerDialog
from tests.gpg_test_helpers import make_test_jpeg


def _make_photo(tmp_path, *, revoked: bool = False) -> PhotoUid:
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    return PhotoUid(index=1, image=jpeg.read_bytes(), revoked=revoked)


def test_shows_the_photo_at_its_native_size(qtbot, tmp_path):
    photo = _make_photo(tmp_path)

    dialog = PhotoViewerDialog(photo)
    qtbot.addWidget(dialog)

    pixmap = dialog._ui.lblPhoto.pixmap()
    assert not pixmap.isNull()
    assert dialog._ui.lblPhoto.size() == pixmap.size()


def test_title_is_plain_for_a_non_revoked_photo(qtbot, tmp_path):
    photo = _make_photo(tmp_path)

    dialog = PhotoViewerDialog(photo)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Photo"


def test_title_mentions_revocation(qtbot, tmp_path):
    photo = _make_photo(tmp_path, revoked=True)

    dialog = PhotoViewerDialog(photo)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Photo (revoked)"


def test_close_button_rejects_the_dialog(qtbot, tmp_path):
    photo = _make_photo(tmp_path)

    dialog = PhotoViewerDialog(photo)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.rejected.emit()

    assert dialog.result() == PhotoViewerDialog.DialogCode.Rejected
