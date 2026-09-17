"""Settings dialog — interface language."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbnightingale import i18n, preferences
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.settings_dialog_ui import Ui_SettingsDialog


class SettingsDialog(GeometryMixin, QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None) -> None:
        """Build the dialog, pre-filled with the current preferences."""
        super().__init__(parent)
        self._ui = Ui_SettingsDialog()
        self._ui.setupUi(self)
        self._init_geometry("settings_dialog")

        self._ui.cmbLanguage.addItem(_("System default"), userData="")
        for code, name in i18n.available_languages():
            self._ui.cmbLanguage.addItem(f"{name} ({code})", userData=code)
        saved_lang = i18n.get_language_override()
        if saved_lang:
            idx = self._ui.cmbLanguage.findData(saved_lang)
            if idx >= 0:
                self._ui.cmbLanguage.setCurrentIndex(idx)

        self._ui.cmbAlgorithm.addItem(_("RSA"), userData="RSA")
        self._ui.cmbAlgorithm.addItem(
            _("Ed25519 (modern, smaller keys)"), userData="ED25519"
        )
        idx = self._ui.cmbAlgorithm.findData(preferences.get_preferred_algorithm())
        if idx >= 0:
            self._ui.cmbAlgorithm.setCurrentIndex(idx)

        self._ui.cmbIconSize.addItem(_("System default"), userData="system")
        for size in ("16", "24", "32", "48", "64"):
            self._ui.cmbIconSize.addItem(f"{size}x{size}", userData=size)
        idx = self._ui.cmbIconSize.findData(preferences.get_toolbar_icon_size())
        if idx >= 0:
            self._ui.cmbIconSize.setCurrentIndex(idx)

        self._ui.spinPassphraseCache.setValue(
            preferences.get_passphrase_cache_minutes()
        )

        self._ui.buttonBox.accepted.connect(self._save_and_accept)

    def _save_and_accept(self) -> None:
        """Persist every preference field's current value, then close."""
        i18n.set_language_override(self._ui.cmbLanguage.currentData())
        preferences.set_preferred_algorithm(self._ui.cmbAlgorithm.currentData())
        preferences.set_toolbar_icon_size(self._ui.cmbIconSize.currentData())
        preferences.set_passphrase_cache_minutes(self._ui.spinPassphraseCache.value())
        self.accept()
