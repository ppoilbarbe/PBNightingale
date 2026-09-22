"""Settings dialog — interface language."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QListWidgetItem,
)

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
        self._ui.spinActivityLogMaxEntries.setValue(
            preferences.get_activity_log_max_entries()
        )

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._fill_keyservers(preferences.get_keyservers())
        self._ui.lstKeyservers.currentRowChanged.connect(
            self._update_keyserver_buttons_enabled
        )
        self._ui.lstKeyservers.itemChanged.connect(self._update_ok_enabled)
        self._update_keyserver_buttons_enabled()
        self._update_ok_enabled()
        self._ui.btnKeyserverAdd.clicked.connect(self._on_keyserver_add)
        self._ui.btnKeyserverRemove.clicked.connect(self._on_keyserver_remove)
        self._ui.btnKeyserverUp.clicked.connect(self._on_keyserver_move_up)
        self._ui.btnKeyserverDown.clicked.connect(self._on_keyserver_move_down)
        self._ui.btnKeyserverRestoreDefaults.clicked.connect(
            self._on_keyserver_restore_defaults
        )

        self._ui.buttonBox.accepted.connect(self._save_and_accept)

    def _fill_keyservers(self, servers: list[tuple[str, bool]]) -> None:
        """Replace the keyserver list widget's contents with *servers*.

        Parameters
        ----------
        servers
            ``(url, checked)`` pairs, in the order to display.
        """
        self._ui.lstKeyservers.clear()
        for url, checked in servers:
            item = QListWidgetItem(url)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._ui.lstKeyservers.addItem(item)

    def _update_keyserver_buttons_enabled(self) -> None:
        """Enable Remove/Move Up/Move Down only while a row is selected.

        Remove also requires more than one row: the list can never be
        emptied out completely.
        """
        list_widget = self._ui.lstKeyservers
        row = list_widget.currentRow()
        self._ui.btnKeyserverRemove.setEnabled(row >= 0 and list_widget.count() > 1)
        self._ui.btnKeyserverUp.setEnabled(row > 0)
        self._ui.btnKeyserverDown.setEnabled(0 <= row < list_widget.count() - 1)

    def _update_ok_enabled(self) -> None:
        """Enable the dialog's OK button only while at least one keyserver is checked."""
        self._ok_button.setEnabled(any(checked for _url, checked in self._keyservers()))

    def _on_keyserver_add(self) -> None:
        """Prompt for a new keyserver URL and append it, checked."""
        url, ok = QInputDialog.getText(self, _("Add Keyserver"), _("Keyserver URL:"))
        url = url.strip()
        if not ok or not url:
            return
        item = QListWidgetItem(url)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self._ui.lstKeyservers.addItem(item)
        self._ui.lstKeyservers.setCurrentItem(item)
        self._update_keyserver_buttons_enabled()
        self._update_ok_enabled()

    def _on_keyserver_remove(self) -> None:
        """Remove the currently selected keyserver, if any.

        Never empties the list completely — ``_update_keyserver_buttons_
        enabled()`` already keeps Remove disabled with only one row left,
        this is the defensive backstop.
        """
        list_widget = self._ui.lstKeyservers
        row = list_widget.currentRow()
        if row >= 0 and list_widget.count() > 1:
            list_widget.takeItem(row)
        self._update_keyserver_buttons_enabled()
        self._update_ok_enabled()

    def _on_keyserver_move_up(self) -> None:
        """Move the currently selected keyserver one row up."""
        self._swap_keyserver_rows(self._ui.lstKeyservers.currentRow(), -1)

    def _on_keyserver_move_down(self) -> None:
        """Move the currently selected keyserver one row down."""
        self._swap_keyserver_rows(self._ui.lstKeyservers.currentRow(), 1)

    def _swap_keyserver_rows(self, row: int, offset: int) -> None:
        """Swap the keyserver at *row* with its neighbor *offset* rows away.

        Parameters
        ----------
        row
            The row to move.
        offset
            ``-1`` to move it up, ``1`` to move it down.
        """
        list_widget = self._ui.lstKeyservers
        target = row + offset
        if row < 0 or not (0 <= target < list_widget.count()):
            return
        item = list_widget.takeItem(row)
        list_widget.insertItem(target, item)
        list_widget.setCurrentItem(item)

    def _on_keyserver_restore_defaults(self) -> None:
        """Reset the (not-yet-saved) keyserver list back to the built-in defaults."""
        self._fill_keyservers(list(preferences.DEFAULT_KEYSERVERS))
        self._update_keyserver_buttons_enabled()
        self._update_ok_enabled()

    def _keyservers(self) -> list[tuple[str, bool]]:
        """Return the keyserver list widget's current contents.

        Returns
        -------
        :
            ``(url, checked)`` pairs, in display order.
        """
        list_widget = self._ui.lstKeyservers
        return [
            (
                list_widget.item(i).text(),
                list_widget.item(i).checkState() == Qt.CheckState.Checked,
            )
            for i in range(list_widget.count())
        ]

    def _save_and_accept(self) -> None:
        """Persist every preference field's current value, then close."""
        i18n.set_language_override(self._ui.cmbLanguage.currentData())
        preferences.set_preferred_algorithm(self._ui.cmbAlgorithm.currentData())
        preferences.set_toolbar_icon_size(self._ui.cmbIconSize.currentData())
        preferences.set_passphrase_cache_minutes(self._ui.spinPassphraseCache.value())
        preferences.set_activity_log_max_entries(
            self._ui.spinActivityLogMaxEntries.value()
        )
        preferences.set_keyservers(self._keyservers())
        self.accept()
