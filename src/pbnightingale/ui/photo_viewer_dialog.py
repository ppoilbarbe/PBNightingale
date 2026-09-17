"""Photo Viewer dialog — shows a photo user ID at its native 1:1 resolution.

Scrollbars appear if it doesn't fit the window. Opened by activating a
photo in the key detail panel — double-click or Enter, both delivered by
Qt's ``itemActivated`` signal, see ``KeyListView._on_photo_activated()``.
"""

from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog

from pbnightingale.core.gpg_backend import PhotoUid
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.photo_viewer_dialog_ui import Ui_PhotoViewerDialog


class PhotoViewerDialog(GeometryMixin, QDialog):
    """Shows one photo user ID at its native 1:1 resolution."""

    def __init__(self, photo: PhotoUid, parent: QDialog | None = None) -> None:
        """Build the dialog, showing *photo* at full size.

        Parameters
        ----------
        photo
            The photo to display.
        parent
            The owning window.
        """
        super().__init__(parent)
        self._ui = Ui_PhotoViewerDialog()
        self._ui.setupUi(self)
        self._init_geometry("photo_viewer_dialog")

        image = QImage.fromData(photo.image)
        self._ui.lblPhoto.setPixmap(QPixmap.fromImage(image))
        self._ui.lblPhoto.resize(image.size())
        self.setWindowTitle(_("Photo (revoked)") if photo.revoked else _("Photo"))

        self._ui.buttonBox.rejected.connect(self.reject)
