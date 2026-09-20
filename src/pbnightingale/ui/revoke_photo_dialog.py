"""Revoke Photo dialog.

Strong confirmation (a checkbox, not just a button click) before an
irreversible operation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import PhotoUid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.revoke_photo_dialog_ui import Ui_RevokePhotoDialog


class RevokePhotoDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for revoking a photo user ID."""

    def __init__(self, fingerprint: str, photo: PhotoUid, parent=None) -> None:
        """Build the dialog for revoking *photo*.

        Parameters
        ----------
        fingerprint
            The photo's key.
        photo
            The photo to revoke.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._photo = photo
        self._ui = Ui_RevokePhotoDialog()
        self._ui.setupUi(self)
        self._init_geometry("revoke_photo_dialog")
        self._init_key_operation()

        image = QImage.fromData(photo.image)
        pixmap = QPixmap.fromImage(image).scaled(
            96,
            96,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._ui.lblPreview.setPixmap(pixmap)
        self._ui.lblWarning.setText(
            _(
                "You are about to revoke this photo. This cannot be undone: "
                "it will stop being usable everywhere this key is trusted."
            )
        )
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.chkConfirm.toggled.connect(self._ok_button.setEnabled)

        self._ui.buttonBox.accepted.connect(self._on_revoke)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.chkConfirm.setEnabled(enabled)
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.chkConfirm.isChecked())

    def _on_revoke(self) -> None:
        """Revoke the photo via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().revoke_photo_uid(
                self._fingerprint,
                Passphrase(self._ui.txtPassphrase.text()),
                self._photo.index,
            ),
            busy_text=_("Revoking photo…"),
            error_template=_("Could not revoke photo: {error}"),
        )
