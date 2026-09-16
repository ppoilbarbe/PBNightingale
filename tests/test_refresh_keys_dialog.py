"""Tests for the Refresh Keys (from keyserver) confirmation dialog."""

from __future__ import annotations

from pbnightingale.ui.refresh_keys_dialog import RefreshKeysDialog


def test_selected_key_option_is_checked_and_enabled_with_a_selection(qtbot):
    dialog = RefreshKeysDialog(has_selection=True)
    qtbot.addWidget(dialog)

    assert dialog._ui.radioSelected.isEnabled() is True
    assert dialog._ui.radioSelected.isChecked() is True
    assert dialog.refresh_all() is False


def test_selected_key_option_is_disabled_without_a_selection(qtbot):
    dialog = RefreshKeysDialog(has_selection=False)
    qtbot.addWidget(dialog)

    assert dialog._ui.radioSelected.isEnabled() is False
    assert dialog._ui.radioAll.isChecked() is True
    assert dialog.refresh_all() is True


def test_choosing_all_keys_flips_refresh_all(qtbot):
    dialog = RefreshKeysDialog(has_selection=True)
    qtbot.addWidget(dialog)

    dialog._ui.radioAll.setChecked(True)

    assert dialog.refresh_all() is True


def test_reject_sets_the_dialog_result(qtbot):
    dialog = RefreshKeysDialog(has_selection=True)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.rejected.emit()

    assert dialog.result() == RefreshKeysDialog.DialogCode.Rejected


def test_accept_sets_the_dialog_result(qtbot):
    dialog = RefreshKeysDialog(has_selection=True)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    assert dialog.result() == RefreshKeysDialog.DialogCode.Accepted
