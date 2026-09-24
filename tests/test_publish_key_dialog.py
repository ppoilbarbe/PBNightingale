"""Tests for the Publish Key dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale import preferences
from pbnightingale.ui.publish_key_dialog import PublishKeyDialog


def test_question_names_the_key(qtbot):
    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert "4444555566667777" in dialog._ui.lblQuestion.text()


def test_warning_sentence_is_kept(qtbot):
    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert "cannot" in dialog._ui.lblWarning.text()
    assert "revoked" in dialog._ui.lblWarning.text()


def test_lists_every_configured_keyserver_prechecking_the_checked_ones(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", True), ("hkps://b.example", False)]
    )

    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    list_widget = dialog._ui.lstKeyservers
    servers = [
        (list_widget.item(i).text(), list_widget.item(i).checkState())
        for i in range(list_widget.count())
    ]
    assert servers == [
        ("hkps://a.example", Qt.CheckState.Checked),
        ("hkps://b.example", Qt.CheckState.Unchecked),
    ]


def test_list_is_not_selectable(qtbot):
    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    from PySide6.QtWidgets import QAbstractItemView

    assert (
        dialog._ui.lstKeyservers.selectionMode()
        == QAbstractItemView.SelectionMode.NoSelection
    )


def test_ok_button_reflects_default_checked_state(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", True), ("hkps://b.example", False)]
    )

    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is True


def test_ok_button_disabled_when_nothing_is_checked(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", False), ("hkps://b.example", False)]
    )

    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False


def test_ok_button_toggles_as_checkboxes_change(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", False), ("hkps://b.example", False)]
    )
    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)
    assert dialog._ok_button.isEnabled() is False

    dialog._ui.lstKeyservers.item(0).setCheckState(Qt.CheckState.Checked)

    assert dialog._ok_button.isEnabled() is True

    dialog._ui.lstKeyservers.item(0).setCheckState(Qt.CheckState.Unchecked)

    assert dialog._ok_button.isEnabled() is False


def test_selected_keyservers_returns_only_checked_ones_in_order(qtbot):
    preferences.set_keyservers(
        [
            ("hkps://a.example", False),
            ("hkps://b.example", True),
            ("hkps://c.example", True),
        ]
    )

    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert dialog.selected_keyservers() == ["hkps://b.example", "hkps://c.example"]


def test_ok_button_disabled_with_no_keyservers_configured(qtbot):
    preferences.set_keyservers([])

    dialog = PublishKeyDialog(["4444555566667777"])
    qtbot.addWidget(dialog)

    assert dialog._ui.lstKeyservers.count() == 0
    assert dialog._ok_button.isEnabled() is False


def test_question_lists_every_key_id_for_several_keys(qtbot):
    dialog = PublishKeyDialog(["4444555566667777", "5555666677778888"])
    qtbot.addWidget(dialog)

    assert dialog._ui.lblQuestion.text() == (
        "Publish these 2 keys (4444555566667777, 5555666677778888) to:"
    )
