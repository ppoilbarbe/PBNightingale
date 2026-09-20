"""Add Photo dialog.

Adds a photo user ID to a key already in the keyring (the key must have
its secret part available). The chosen image is scaled down and re-encoded as a small JPEG before being
handed to gpg: a full-resolution photo would bloat the key (and therefore
every copy of it, everywhere it's ever exported to) for no real benefit.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.add_photo_dialog_ui import (
    MAX_PREVIEW_DIMENSION,
    Ui_AddPhotoDialog,
)
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog

# Photo IDs are embedded in the key itself and travel with every copy of
# it — keep them small. 240px on the long side and JPEG quality 85 lands
# comfortably under 10-20 KB for a typical headshot, plenty for the tiny
# preview every OpenPGP tool shows. Shared with add_photo_dialog_ui.py's
# preview label size — see MAX_PREVIEW_DIMENSION's own comment.
_MAX_DIMENSION = MAX_PREVIEW_DIMENSION
_JPEG_QUALITY = 85


class AddPhotoDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for adding a photo user ID to a key."""

    def __init__(self, fingerprint: str, parent=None) -> None:
        """Build the dialog for the key identified by *fingerprint*.

        Parameters
        ----------
        fingerprint
            The key to add the photo to.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._ui = Ui_AddPhotoDialog()
        self._ui.setupUi(self)
        self._init_geometry("add_photo_dialog")
        self._init_key_operation()
        self._jpeg_path: Path | None = None

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.lblResizeWarning.setText(
            _(
                "Images are resized to fit within {max}×{max}px before being "
                "added. Even so, a photo permanently adds to the key's size — "
                "once added, it cannot be deleted, only revoked."
            ).format(max=_MAX_DIMENSION)
        )
        self._ui.btnChooseImage.clicked.connect(self._on_choose_image)
        self._ui.buttonBox.accepted.connect(self._on_add)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _on_choose_image(self) -> None:
        """Prompt for an image file, scale it down, and preview it."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            _("Choose Image"),
            "",
            _("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            self._ui.lblStatus.setText(_("Could not load image."))
            return

        scaled = image.scaled(
            _MAX_DIMENSION,
            _MAX_DIMENSION,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cleanup_temp_file()
        fd, raw_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        self._jpeg_path = Path(raw_path)
        scaled.save(str(self._jpeg_path), "JPEG", _JPEG_QUALITY)

        self._ui.lblPreview.setPixmap(QPixmap.fromImage(scaled))
        self._ui.lblStatus.setText("")
        self._ui.lblResizeWarning.setText(
            _(
                "This image will be resized to {width}×{height}px. Even so, it "
                "permanently adds to the key's size — once added, a photo "
                "cannot be deleted, only revoked."
            ).format(width=scaled.width(), height=scaled.height())
        )
        self._ok_button.setEnabled(True)

    def _cleanup_temp_file(self) -> None:
        """Delete the scaled-down temporary JPEG created by ``_on_choose_image()``."""
        if self._jpeg_path is not None:
            self._jpeg_path.unlink(missing_ok=True)
            self._jpeg_path = None

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.btnChooseImage.setEnabled(enabled)
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._jpeg_path is not None)

    def _on_add(self) -> None:
        """Add the chosen photo to the key via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().add_photo_uid(
                self._fingerprint,
                Passphrase(self._ui.txtPassphrase.text()),
                self._jpeg_path,
            ),
            busy_text=_("Adding photo…"),
            error_template=_("Could not add photo: {error}"),
        )

    def _on_operation_success(self, key: Key) -> None:
        """Clean up the temporary JPEG once the photo has been added.

        Parameters
        ----------
        key
            The updated key, forwarded to the base implementation.
        """
        self._cleanup_temp_file()
        super()._on_operation_success(key)

    def reject(self) -> None:
        """Clean up the temporary JPEG before closing the dialog."""
        self._cleanup_temp_file()
        super().reject()
