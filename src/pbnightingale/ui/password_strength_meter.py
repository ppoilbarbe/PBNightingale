"""Password strength meter: a colored bar (red for weak, green for
excellent) plus the estimated entropy in bits, meant to be updated on every
keystroke of a *new* passphrase (not one unlocking an existing key — see
``core/password_strength.py``)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pbnightingale.core.password_strength import (
    PasswordQuality,
    evaluate_password_strength,
)
from pbnightingale.ui.password_strength_meter_ui import Ui_PasswordStrengthMeter

# One distinct color per PasswordQuality tier, red to green — unlike
# KeePassXC's own quality bar (gui/styles/StateColorPalette.cpp), which
# this used to mirror exactly and which shares one red between Bad and
# Poor: requested explicitly so all five tiers are visually distinguishable.
_BAR_COLORS = {
    PasswordQuality.BAD: "#C43F31",  # red
    PasswordQuality.POOR: "#E07F16",  # orange
    PasswordQuality.WEAK: "#D4B106",  # yellow
    PasswordQuality.GOOD: "#5EA10E",  # light green
    PasswordQuality.EXCELLENT: "#118F17",  # green
}


def _quality_label(quality: PasswordQuality) -> str:
    return {
        PasswordQuality.BAD: _("Bad"),
        PasswordQuality.POOR: _("Poor"),
        PasswordQuality.WEAK: _("Weak"),
        PasswordQuality.GOOD: _("Good"),
        PasswordQuality.EXCELLENT: _("Excellent"),
    }[quality]


class PasswordStrengthMeter(QWidget):
    """A colored strength bar plus an entropy-in-bits label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_PasswordStrengthMeter()
        self._ui.setupUi(self)
        self.set_password("")

    def set_password(self, password: str) -> None:
        strength = evaluate_password_strength(password)
        self._ui.bar.setValue(max(0, min(round(strength.entropy_bits), 100)))
        color = _BAR_COLORS[strength.quality]
        self._ui.bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )
        self._ui.bar.setToolTip(
            _("Quality: {quality}").format(quality=_quality_label(strength.quality))
        )
        self._ui.lblBits.setText(
            _("{bits} bits").format(bits=round(strength.entropy_bits))
        )
