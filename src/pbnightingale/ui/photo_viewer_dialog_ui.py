"""UI layout for the Photo Viewer dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
)


class Ui_PhotoViewerDialog:
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Photo"))
        dialog.resize(420, 420)

        layout = QVBoxLayout(dialog)

        self.scrollArea = QScrollArea(dialog)
        # Not resizable: the label stays at the photo's native size, so the
        # scroll area shows it at a true 1:1 zoom and grows scrollbars
        # instead of shrinking the image to fit.
        self.scrollArea.setWidgetResizable(False)
        self.lblPhoto = QLabel()
        self.scrollArea.setWidget(self.lblPhoto)
        layout.addWidget(self.scrollArea)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        layout.addWidget(self.buttonBox)
