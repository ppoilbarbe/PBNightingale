"""Tests for the Settings dialog (language selection)."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale import i18n, preferences
from pbnightingale.ui.settings_dialog import SettingsDialog


def test_language_combo_lists_system_default_and_available_languages(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    combo = dialog._ui.cmbLanguage
    assert combo.itemData(0) == ""
    codes = {combo.itemData(i) for i in range(1, combo.count())}
    assert codes == {code for code, _name in i18n.available_languages()}


def test_accept_persists_selected_language(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    idx = dialog._ui.cmbLanguage.findData("fr")
    dialog._ui.cmbLanguage.setCurrentIndex(idx)

    dialog._ui.buttonBox.accepted.emit()

    assert i18n.get_language_override() == "fr"


def test_cancel_does_not_persist_language(qtbot):
    i18n.set_language_override("")
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    idx = dialog._ui.cmbLanguage.findData("fr")
    dialog._ui.cmbLanguage.setCurrentIndex(idx)

    dialog._ui.buttonBox.rejected.emit()

    assert i18n.get_language_override() == ""


def test_preselects_saved_language_override(qtbot):
    i18n.set_language_override("fr")

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbLanguage.currentData() == "fr"


def test_algorithm_combo_defaults_to_rsa(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbAlgorithm.currentData() == "RSA"


def test_accept_persists_selected_algorithm(qtbot):
    from pbnightingale import preferences

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    idx = dialog._ui.cmbAlgorithm.findData("ED25519")
    dialog._ui.cmbAlgorithm.setCurrentIndex(idx)

    dialog._ui.buttonBox.accepted.emit()

    assert preferences.get_preferred_algorithm() == "ED25519"


def test_preselects_saved_algorithm_preference(qtbot):
    from pbnightingale import preferences

    preferences.set_preferred_algorithm("ED25519")

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbAlgorithm.currentData() == "ED25519"


def test_icon_size_combo_lists_system_and_pixel_sizes(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    combo = dialog._ui.cmbIconSize
    sizes = [combo.itemData(i) for i in range(combo.count())]
    assert sizes == ["system", "16", "24", "32", "48", "64"]


def test_icon_size_combo_defaults_to_system(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbIconSize.currentData() == "system"


def test_accept_persists_selected_icon_size(qtbot):
    from pbnightingale import preferences

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    idx = dialog._ui.cmbIconSize.findData("32")
    dialog._ui.cmbIconSize.setCurrentIndex(idx)

    dialog._ui.buttonBox.accepted.emit()

    assert preferences.get_toolbar_icon_size() == "32"


def test_preselects_saved_icon_size_preference(qtbot):
    from pbnightingale import preferences

    preferences.set_toolbar_icon_size("48")

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbIconSize.currentData() == "48"


def test_passphrase_cache_spinbox_defaults_to_ten(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.spinPassphraseCache.value() == 10


def test_accept_persists_passphrase_cache_minutes(qtbot):
    from pbnightingale import preferences

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.spinPassphraseCache.setValue(30)

    dialog._ui.buttonBox.accepted.emit()

    assert preferences.get_passphrase_cache_minutes() == 30


def test_preselects_saved_passphrase_cache_preference(qtbot):
    from pbnightingale import preferences

    preferences.set_passphrase_cache_minutes(0)

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.spinPassphraseCache.value() == 0


def test_activity_log_max_entries_spinbox_defaults_to_fifty(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.spinActivityLogMaxEntries.value() == 50


def test_accept_persists_activity_log_max_entries(qtbot):
    from pbnightingale import preferences

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.spinActivityLogMaxEntries.setValue(200)

    dialog._ui.buttonBox.accepted.emit()

    assert preferences.get_activity_log_max_entries() == 200


def test_preselects_saved_activity_log_max_entries_preference(qtbot):
    from pbnightingale import preferences

    preferences.set_activity_log_max_entries(10)

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.spinActivityLogMaxEntries.value() == 10


def test_keyserver_list_prefilled_with_the_default_list(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    list_widget = dialog._ui.lstKeyservers
    servers = [
        (list_widget.item(i).text(), list_widget.item(i).checkState())
        for i in range(list_widget.count())
    ]
    assert servers == [
        (url, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        for url, checked in preferences.DEFAULT_KEYSERVERS
    ]


def test_keyserver_move_buttons_disabled_without_a_selection(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.btnKeyserverRemove.isEnabled() is False
    assert dialog._ui.btnKeyserverUp.isEnabled() is False
    assert dialog._ui.btnKeyserverDown.isEnabled() is False


def test_keyserver_move_up_button_disabled_on_first_row(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    dialog._ui.lstKeyservers.setCurrentRow(0)

    assert dialog._ui.btnKeyserverUp.isEnabled() is False
    assert dialog._ui.btnKeyserverDown.isEnabled() is True


def test_keyserver_move_down_button_disabled_on_last_row(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    dialog._ui.lstKeyservers.setCurrentRow(dialog._ui.lstKeyservers.count() - 1)

    assert dialog._ui.btnKeyserverDown.isEnabled() is False
    assert dialog._ui.btnKeyserverUp.isEnabled() is True


def test_keyserver_move_up_swaps_with_the_previous_row(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    list_widget = dialog._ui.lstKeyservers
    second_url = list_widget.item(1).text()
    list_widget.setCurrentRow(1)

    dialog._ui.btnKeyserverUp.click()

    assert list_widget.item(0).text() == second_url
    assert list_widget.currentRow() == 0


def test_keyserver_move_down_swaps_with_the_next_row(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    list_widget = dialog._ui.lstKeyservers
    first_url = list_widget.item(0).text()
    list_widget.setCurrentRow(0)

    dialog._ui.btnKeyserverDown.click()

    assert list_widget.item(1).text() == first_url
    assert list_widget.currentRow() == 1


def test_keyserver_remove_deletes_the_selected_row(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    list_widget = dialog._ui.lstKeyservers
    before = list_widget.count()
    list_widget.setCurrentRow(0)

    dialog._ui.btnKeyserverRemove.click()

    assert list_widget.count() == before - 1


def test_keyserver_add_appends_a_checked_entry(qtbot, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: ("hkps://new.example", True)),
    )
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    list_widget = dialog._ui.lstKeyservers
    before = list_widget.count()

    dialog._ui.btnKeyserverAdd.click()

    assert list_widget.count() == before + 1
    new_item = list_widget.item(list_widget.count() - 1)
    assert new_item.text() == "hkps://new.example"
    assert new_item.checkState() == Qt.CheckState.Checked


def test_keyserver_add_cancelled_leaves_the_list_untouched(qtbot, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False))
    )
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    before = dialog._ui.lstKeyservers.count()

    dialog._ui.btnKeyserverAdd.click()

    assert dialog._ui.lstKeyservers.count() == before


def test_keyserver_restore_defaults_resets_the_in_dialog_list(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.lstKeyservers.setCurrentRow(0)
    dialog._ui.btnKeyserverRemove.click()
    assert dialog._ui.lstKeyservers.count() == len(preferences.DEFAULT_KEYSERVERS) - 1

    dialog._ui.btnKeyserverRestoreDefaults.click()

    assert dialog._keyservers() == list(preferences.DEFAULT_KEYSERVERS)


def test_accept_persists_the_keyserver_list(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.lstKeyservers.setCurrentRow(0)
    dialog._ui.btnKeyserverRemove.click()

    dialog._ui.buttonBox.accepted.emit()

    assert preferences.get_keyservers() == list(preferences.DEFAULT_KEYSERVERS)[1:]


def test_cancel_does_not_persist_the_keyserver_list(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.lstKeyservers.setCurrentRow(0)
    dialog._ui.btnKeyserverRemove.click()

    dialog._ui.buttonBox.rejected.emit()

    assert preferences.get_keyservers() == list(preferences.DEFAULT_KEYSERVERS)


def test_keyserver_remove_disabled_with_only_one_server_left(qtbot):
    preferences.set_keyservers([("hkps://a.example", True)])
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.lstKeyservers.setCurrentRow(0)

    assert dialog._ui.btnKeyserverRemove.isEnabled() is False


def test_keyserver_remove_is_a_no_op_with_only_one_server_left(qtbot):
    preferences.set_keyservers([("hkps://a.example", True)])
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog._ui.lstKeyservers.setCurrentRow(0)

    dialog._ui.btnKeyserverRemove.click()

    assert dialog._ui.lstKeyservers.count() == 1


def test_ok_button_disabled_when_no_keyserver_is_checked(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", False), ("hkps://b.example", False)]
    )

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False


def test_ok_button_enabled_when_at_least_one_keyserver_is_checked(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is True


def test_ok_button_toggles_as_the_last_checked_server_is_unchecked(qtbot):
    preferences.set_keyservers([("hkps://a.example", True)])
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    assert dialog._ok_button.isEnabled() is True

    dialog._ui.lstKeyservers.item(0).setCheckState(Qt.CheckState.Unchecked)

    assert dialog._ok_button.isEnabled() is False

    dialog._ui.lstKeyservers.item(0).setCheckState(Qt.CheckState.Checked)

    assert dialog._ok_button.isEnabled() is True


def test_ok_button_updates_after_restore_defaults(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", False), ("hkps://b.example", False)]
    )
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    assert dialog._ok_button.isEnabled() is False

    dialog._ui.btnKeyserverRestoreDefaults.click()

    assert dialog._ok_button.isEnabled() is True
