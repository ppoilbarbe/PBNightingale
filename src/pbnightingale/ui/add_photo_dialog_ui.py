"""UI layout for the Add Photo dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin

# Must match add_photo_dialog.py's _MAX_DIMENSION exactly: the preview
# shows the actual image that will be sent to gpg, at its actual size —
# a smaller label would crop a non-square photo instead of letterboxing it.
MAX_PREVIEW_DIMENSION = 240


class Ui_AddPhotoDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Add Photo"))
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)

        preview_row = QHBoxLayout()
        self.lblPreview = QLabel(dialog)
        self.lblPreview.setFixedSize(MAX_PREVIEW_DIMENSION, MAX_PREVIEW_DIMENSION)
        self.lblPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblPreview.setWordWrap(True)
        self.lblPreview.setStyleSheet("border: 1px solid palette(mid);")
        self.lblPreview.setText(_("No image selected"))
        preview_row.addWidget(self.lblPreview, 0, Qt.AlignmentFlag.AlignVCenter)

        # Button + warning stacked to the right of the preview and vertically
        # centered against it (a leading and trailing addStretch() below),
        # rather than a full-width row of their own underneath — keeps the
        # warning from adding any extra height to the dialog beyond the
        # preview's own. A *minimum* width on the label (not a fixed one)
        # is required for that: an unconstrained word-wrapped QLabel
        # reports a sizeHint from its *unwrapped* width, which made this
        # column (and therefore the whole row) taller than the 240px
        # preview instead of matching it — a floor big enough to bound
        # that initial sizeHint, while the column's own stretch factor
        # below still lets the label grow wider (fewer, longer lines)
        # whenever the dialog itself is wider than its minimum.
        choose_column = QVBoxLayout()
        choose_column.addStretch()
        self.btnChooseImage = QPushButton(_("Choose Image…"), dialog)
        choose_column.addWidget(self.btnChooseImage)
        self.lblResizeWarning = QLabel(dialog)
        self.lblResizeWarning.setWordWrap(True)
        self.lblResizeWarning.setMinimumWidth(240)
        choose_column.addWidget(self.lblResizeWarning)
        choose_column.addStretch()
        preview_row.addLayout(choose_column, 1)
        layout.addLayout(preview_row)

        self._build_passphrase_field(dialog, layout)
        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Add"), ok_enabled=False)
