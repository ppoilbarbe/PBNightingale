"""Tests for the Settings dialog (language selection)."""

from __future__ import annotations

from pbnightingale import i18n
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
