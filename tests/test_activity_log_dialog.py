"""Tests for the Activity (advanced) window."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pbnightingale.core import activity_log
from pbnightingale.ui.activity_log_dialog import ActivityLogDialog


def test_is_non_modal(qtbot):
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)

    assert dialog.isModal() is False


def test_prefilled_with_the_existing_history(qtbot):
    activity_log.record("gpg --list-keys")
    activity_log.record("gpg --export")

    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)

    table = dialog._ui.tblActivity
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 2).text() == "gpg --list-keys"
    assert table.item(1, 0).text() == "2"
    assert table.item(1, 2).text() == "gpg --export"


def test_new_commands_are_appended_live(qtbot):
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)

    activity_log.record("gpg --list-keys")

    table = dialog._ui.tblActivity
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "gpg --list-keys"


def test_refresh_reflects_a_shrunk_history(qtbot):
    activity_log.record("first")
    activity_log.record("second")
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)
    assert dialog._ui.tblActivity.rowCount() == 2

    activity_log.configure(1)
    dialog.refresh()

    table = dialog._ui.tblActivity
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "second"
    # The surviving entry keeps its original sequence number (2nd command
    # recorded), not renumbered to 1 just because it's now the only row.
    assert table.item(0, 0).text() == "2"


def test_sequence_number_keeps_incrementing_and_is_not_reset_by_clear(qtbot):
    activity_log.record("first")
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnClearActivity.click()
    activity_log.record("second")
    activity_log.record("third")

    table = dialog._ui.tblActivity
    assert [table.item(row, 0).text() for row in range(table.rowCount())] == [
        "2",
        "3",
    ]


def test_clear_history_button_empties_the_table_and_the_log(qtbot):
    activity_log.record("gpg --list-keys")
    activity_log.record("gpg --export")
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnClearActivity.click()

    assert dialog._ui.tblActivity.rowCount() == 0
    assert activity_log.entries() == []


def test_clear_history_then_new_commands_still_show_up_live(qtbot):
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)
    activity_log.record("gpg --list-keys")

    dialog._ui.btnClearActivity.click()
    activity_log.record("gpg --export")

    table = dialog._ui.tblActivity
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "gpg --export"


def test_ctrl_c_copies_the_selected_command(qtbot):
    activity_log.record("gpg --list-keys")
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tblActivity.setCurrentCell(0, 2)

    dialog._on_copy()

    assert QApplication.clipboard().text() == "gpg --list-keys"


def test_copy_with_no_selection_is_a_noop(qtbot):
    dialog = ActivityLogDialog()
    qtbot.addWidget(dialog)
    QApplication.clipboard().setText("unchanged")

    dialog._on_copy()

    assert QApplication.clipboard().text() == "unchanged"
