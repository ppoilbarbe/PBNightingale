"""UI layout for the Publish Key confirmation dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_PublishKeyDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Publish Key"))
        dialog.setMinimumSize(420, 360)

        layout = QVBoxLayout(dialog)

        self.lblQuestion = QLabel(dialog)
        self.lblQuestion.setWordWrap(True)
        layout.addWidget(self.lblQuestion)

        self.lstKeyservers = QListWidget(dialog)
        # No selection mode and no drag/drop: only each row's own checkbox
        # is interactive here — which servers to publish to, not the list
        # of servers itself (that's Preferences → Key Servers' job).
        self.lstKeyservers.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.lstKeyservers)

        self.lblWarning = QLabel(dialog)
        self.lblWarning.setWordWrap(True)
        layout.addWidget(self.lblWarning)

        self._build_button_box(dialog, layout, ok_text=_("Publish"), ok_enabled=False)
