"""Tests for the password strength meter widget."""

from __future__ import annotations

from pbnightingale.core.password_strength import PasswordQuality, PasswordStrength
from pbnightingale.ui import password_strength_meter as meter_module
from pbnightingale.ui.password_strength_meter import PasswordStrengthMeter


def test_empty_password_shows_zero_and_bad_color(qtbot):
    meter = PasswordStrengthMeter()
    qtbot.addWidget(meter)

    assert meter._ui.bar.value() == 0
    assert "#C43F31" in meter._ui.bar.styleSheet()
    assert meter._ui.lblBits.text() == "0 bits"


def test_setting_a_strong_password_updates_bar_and_label(qtbot):
    meter = PasswordStrengthMeter()
    qtbot.addWidget(meter)

    meter.set_password(r"4oal-e\_kmTEcdcS?<9;7tlx|ob#!Fi\(7i/]l$-")

    assert meter._ui.bar.value() == 100  # clamped to the bar's maximum
    assert "#118F17" in meter._ui.bar.styleSheet()
    assert "bits" in meter._ui.lblBits.text()
    assert meter._ui.lblBits.text() != "0 bits"


def test_bar_value_tracks_entropy_below_the_cap(qtbot):
    meter = PasswordStrengthMeter()
    qtbot.addWidget(meter)

    meter.set_password("correct horse battery staple")

    from pbnightingale.core.password_strength import evaluate_password_strength

    expected = round(
        evaluate_password_strength("correct horse battery staple").entropy_bits
    )
    assert meter._ui.bar.value() == expected


def test_tooltip_reflects_quality(qtbot):
    meter = PasswordStrengthMeter()
    qtbot.addWidget(meter)

    meter.set_password("")
    assert "Bad" in meter._ui.bar.toolTip()


def test_all_five_quality_tiers_have_distinct_colors():
    colors = list(meter_module._BAR_COLORS.values())

    assert len(colors) == len(PasswordQuality)
    assert len(set(colors)) == len(PasswordQuality)


def test_poor_and_weak_each_use_their_own_color(qtbot, monkeypatch):
    meter = PasswordStrengthMeter()
    qtbot.addWidget(meter)

    monkeypatch.setattr(
        meter_module,
        "evaluate_password_strength",
        lambda password: PasswordStrength(
            entropy_bits=20, quality=PasswordQuality.POOR
        ),
    )
    meter.set_password("x")
    assert "#E07F16" in meter._ui.bar.styleSheet()

    monkeypatch.setattr(
        meter_module,
        "evaluate_password_strength",
        lambda password: PasswordStrength(
            entropy_bits=60, quality=PasswordQuality.WEAK
        ),
    )
    meter.set_password("y")
    assert "#D4B106" in meter._ui.bar.styleSheet()
