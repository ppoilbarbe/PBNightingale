"""UI layout for the password strength meter widget."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class Ui_PasswordStrengthMeter:
    def setupUi(self, widget: QWidget) -> None:
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.bar = QProgressBar(widget)
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.bar, 1)

        self.lblBits = QLabel(widget)
        self.lblBits.setMinimumWidth(70)
        layout.addWidget(self.lblBits)
