"""Main application window."""

from __future__ import annotations

from email.utils import parseaddr
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStyle,
)

from pbnightingale import i18n, preferences
from pbnightingale.core import activity_log, gpg_backend
from pbnightingale.core.gpg_backend import (
    DownloadedSignature,
    GPGBackendError,
    ImportedKey,
    Key,
    KeySignature,
    RefreshedKey,
)
from pbnightingale.ui import window_state
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.gpg_worker import run_async
from pbnightingale.ui.main_window_ui import Ui_MainWindow


class MainWindow(GeometryMixin, QMainWindow):
    """Top-level window for PBNightingale."""

    def __init__(self) -> None:
        """Build the window, wire up every action, and load the keyring."""
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        # Captured before anything (including a later restoreState()) can
        # change it, so "Reset toolbars" has a pristine layout to go back to.
        self._default_toolbar_state = self.saveState()
        self._pool = QThreadPool(self)
        self._init_geometry(
            "main_window",
            splitters={
                "keys": self._ui.keyListView.splitter,
                "detail": self._ui.keyListView.detailSplitter,
            },
            toolbars=True,
        )

        self._pending_selection: tuple[
            str | None, str | None, str | None, int | None
        ] = (None, None, None, None)
        self._pending_status_message: str | None = None
        self._refresh_progress: QProgressDialog | None = None
        self._signatures_progress: QProgressDialog | None = None
        self._activity_log_dialog = None

        self._connect_signals()
        self._wire_context_menu_actions()
        self._update_action_states()
        # None of these depend on the current selection.
        self._ui.actionTrustRefresh.setEnabled(True)
        self._ui.actionKeyImport.setEnabled(True)
        self._ui.actionServerSearch.setEnabled(True)
        self._ui.actionServerRefresh.setEnabled(True)
        self._apply_toolbar_icon_size()
        activity_log.configure(preferences.get_activity_log_max_entries())
        self.statusBar().showMessage(_("Ready"))
        self.refresh_keys()

    def _apply_toolbar_icon_size(self) -> None:
        """Apply the configured toolbar icon size preference to every toolbar."""
        size_pref = preferences.get_toolbar_icon_size()
        if size_pref == "system":
            px = self.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarIconSize)
        else:
            px = int(size_pref)
        size = QSize(px, px)
        for toolbar in (
            self._ui.toolbarKeys,
            self._ui.toolbarIdentities,
            self._ui.toolbarSubkeys,
            self._ui.toolbarPhotos,
            self._ui.toolbarTrust,
            self._ui.toolbarServers,
            self._ui.toolbarHelp,
        ):
            toolbar.setIconSize(size)

    def _on_reset_toolbars(self) -> None:
        """Restore every toolbar to its default layout and persist that."""
        self.restoreState(self._default_toolbar_state)
        window_state.save_toolbar_state(
            self._geo_state_key, self._default_toolbar_state
        )

    def _restore_geometry(self) -> None:
        """Restore the window/splitters (base class), then column widths."""
        super()._restore_geometry()
        # Not one of GeometryMixin's generic splitters/toolbars knobs: the
        # main key list's column widths need set_keys() told a state was
        # restored (see KeyListView.restore_column_widths()), which a
        # plain dict of QHeaderViews couldn't express.
        header_state = window_state.load_header_state(self._geo_state_key, "keys")
        if header_state is not None:
            self._ui.keyListView.restore_column_widths(header_state)
        sort_state = window_state.load_sort_state(self._geo_state_key, "keys")
        if sort_state is not None:
            self._ui.keyListView.restore_sort_state(*sort_state)

    def _save_geometry(self) -> None:
        """Persist the window/splitters (base class), then column widths and sort order."""
        super()._save_geometry()
        window_state.save_header_state(
            self._geo_state_key, "keys", self._ui.keyListView.save_column_widths()
        )
        window_state.save_sort_state(
            self._geo_state_key, "keys", *self._ui.keyListView.save_sort_state()
        )

    def _connect_signals(self) -> None:
        """Wire every action's ``triggered`` signal, and the key list's own signals, to their handlers."""
        self._ui.actionQuit.triggered.connect(self.close)
        self._ui.actionSettings.triggered.connect(self._on_settings)
        self._ui.actionHelpManual.triggered.connect(self._on_help_manual)
        self._ui.actionAbout.triggered.connect(self._on_about)
        self._ui.actionKeyRefresh.triggered.connect(self.refresh_keys)
        self._ui.actionKeyNew.triggered.connect(self._on_key_new)
        self._ui.actionKeyImport.triggered.connect(self._on_key_import)
        self._ui.actionKeySubkeyAdd.triggered.connect(self._on_key_subkey_add)
        self._ui.actionKeyExpire.triggered.connect(self._on_key_expire)
        self._ui.actionKeyRevoke.triggered.connect(self._on_key_revoke)
        self._ui.actionKeySubkeyExpire.triggered.connect(self._on_key_subkey_expire)
        self._ui.actionKeyUidAdd.triggered.connect(self._on_key_uid_add)
        self._ui.actionKeyUidSetPrimary.triggered.connect(self._on_key_uid_set_primary)
        self._ui.actionKeyUidRevoke.triggered.connect(self._on_key_uid_revoke)
        self._ui.actionKeyPhotoAdd.triggered.connect(self._on_key_photo_add)
        self._ui.actionKeyPhotoRevoke.triggered.connect(self._on_key_photo_revoke)
        self._ui.actionKeyCopyId.triggered.connect(self._on_key_copy_id)
        self._ui.actionKeySubkeyCopyId.triggered.connect(self._on_key_subkey_copy_id)
        self._ui.actionKeyUidCopyEmail.triggered.connect(self._on_key_uid_copy_email)
        self._ui.actionKeyPhotoShow.triggered.connect(self._on_key_photo_show)
        self._ui.actionKeyExport.triggered.connect(self._on_key_export)
        self._ui.actionKeyBackup.triggered.connect(self._on_key_backup)
        self._ui.actionKeyChangePassphrase.triggered.connect(
            self._on_key_change_passphrase
        )
        self._ui.actionKeyDelete.triggered.connect(self._on_key_delete)
        self._ui.actionKeySign.triggered.connect(self._on_key_sign)
        self._ui.actionKeySetOwnerTrust.triggered.connect(self._on_key_set_owner_trust)
        self._ui.actionKeySubkeyRevoke.triggered.connect(self._on_key_subkey_revoke)
        self._ui.actionTrustRefresh.triggered.connect(self._on_trust_refresh)
        self._ui.actionServerSearch.triggered.connect(self._on_server_search)
        self._ui.actionServerPublish.triggered.connect(self._on_server_publish)
        self._ui.actionServerRefresh.triggered.connect(self._on_server_refresh)
        self._ui.actionResetToolbars.triggered.connect(self._on_reset_toolbars)
        self._ui.actionActivityLog.triggered.connect(self._on_activity_log)
        self._ui.keyListView.selectionChanged.connect(self._update_action_states)
        self._ui.keyListView.signaturesRequested.connect(self._on_signatures_requested)
        self._ui.keyListView.downloadUnknownSignaturesRequested.connect(
            self._on_download_unknown_signatures
        )

    def _wire_context_menu_actions(self) -> None:
        """Give the key list view the same QAction instances used by the toolbars/menus, so its context menus never go out of sync with them."""
        # Same QAction instances as the corresponding toolbar, so a context
        # menu entry is never out of sync with the menu bar/toolbar for it —
        # see CODING.md, "Key list & detail view".
        ui = self._ui
        ui.keyListView.set_key_actions(
            [
                ui.actionKeyRefresh,
                ui.actionKeyCopyId,
                ui.actionKeyNew,
                ui.actionKeyExpire,
                ui.actionKeyRevoke,
                ui.actionKeyImport,
                ui.actionKeyExport,
                ui.actionKeyBackup,
                ui.actionKeyChangePassphrase,
                ui.actionKeyDelete,
            ]
        )
        ui.keyListView.set_uid_actions(
            [
                ui.actionKeyUidAdd,
                ui.actionKeyUidCopyEmail,
                ui.actionKeyUidSetPrimary,
                ui.actionKeyUidRevoke,
            ]
        )
        ui.keyListView.set_photo_actions(
            [ui.actionKeyPhotoAdd, ui.actionKeyPhotoShow, ui.actionKeyPhotoRevoke]
        )
        ui.keyListView.set_subkey_actions(
            [
                ui.actionKeySubkeyAdd,
                ui.actionKeySubkeyCopyId,
                ui.actionKeySubkeyExpire,
                ui.actionKeySubkeyRevoke,
            ]
        )

    def _update_action_states(self) -> None:
        """Enable/disable every selection-dependent action to match the key list's current selection."""
        key = self._ui.keyListView.selected_key()
        subkey = self._ui.keyListView.selected_subkey()
        uid = self._ui.keyListView.selected_uid()
        photo = self._ui.keyListView.selected_photo()
        has_secret = key is not None and key.has_secret
        # Copy/view actions are read-only, so available on any selected key
        # regardless of whether its secret part is held.
        self._ui.actionKeyCopyId.setEnabled(key is not None)
        self._ui.actionKeySubkeyCopyId.setEnabled(subkey is not None)
        self._ui.actionKeyUidCopyEmail.setEnabled(uid is not None)
        self._ui.actionKeyPhotoShow.setEnabled(photo is not None)
        self._ui.actionKeyExport.setEnabled(key is not None)
        self._ui.actionKeyBackup.setEnabled(has_secret)
        self._ui.actionKeyChangePassphrase.setEnabled(has_secret)
        self._ui.actionKeyDelete.setEnabled(key is not None)
        self._ui.actionKeySubkeyAdd.setEnabled(has_secret)
        self._ui.actionKeyExpire.setEnabled(has_secret)
        self._ui.actionKeyRevoke.setEnabled(
            has_secret and key is not None and key.trust != "r"
        )
        self._ui.actionKeySubkeyExpire.setEnabled(
            has_secret and subkey is not None and subkey.trust != "r"
        )
        self._ui.actionKeySubkeyRevoke.setEnabled(
            has_secret and subkey is not None and subkey.trust != "r"
        )
        self._ui.actionKeyUidAdd.setEnabled(has_secret)
        self._ui.actionKeyUidSetPrimary.setEnabled(
            has_secret and uid is not None and not uid.revoked and not uid.primary
        )
        valid_uid_count = len(
            [u for u in key.uids if not u.revoked] if key is not None else []
        )
        self._ui.actionKeyUidRevoke.setEnabled(
            has_secret and uid is not None and not uid.revoked and valid_uid_count > 1
        )
        self._ui.actionKeyPhotoAdd.setEnabled(has_secret)
        self._ui.actionKeyPhotoRevoke.setEnabled(
            has_secret and photo is not None and not photo.revoked
        )
        self._ui.actionKeySign.setEnabled(key is not None)
        self._ui.actionKeySetOwnerTrust.setEnabled(key is not None)
        self._ui.actionServerPublish.setEnabled(key is not None)

    def refresh_keys(
        self,
        *,
        status_message: str | None = None,
        select_fingerprint: str | None = None,
    ) -> None:
        """Reload the key list from the keyring in the background.

        Parameters
        ----------
        status_message
            Text to show in the status bar once the reload completes, or
            ``None`` for the default "N key(s) loaded" message.
        select_fingerprint
            Fingerprint to select once reloaded, or ``None`` to restore
            whatever was already selected before the reload.
        """
        if select_fingerprint is not None:
            self._pending_selection = (select_fingerprint, None, None, None)
        else:
            key = self._ui.keyListView.selected_key()
            subkey = self._ui.keyListView.selected_subkey()
            uid = self._ui.keyListView.selected_uid()
            photo = self._ui.keyListView.selected_photo()
            self._pending_selection = (
                key.fingerprint if key is not None else None,
                subkey.keyid if subkey is not None else None,
                uid.value if uid is not None else None,
                photo.index if photo is not None else None,
            )
        self._pending_status_message = status_message
        self.statusBar().showMessage(_("Loading keys…"))
        self._ui.actionKeyRefresh.setEnabled(False)
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().list_keys(),
            on_success=self._on_keys_loaded,
            on_error=self._on_keys_load_failed,
        )

    def _on_keys_loaded(self, keys: list[Key]) -> None:
        """Populate the key list once a background ``refresh_keys()`` call completes with *keys*, restoring any pending selection/status message."""
        self._ui.actionKeyRefresh.setEnabled(True)
        self._ui.keyListView.set_keys(keys)
        fingerprint, subkey_keyid, uid_value, photo_index = self._pending_selection
        if fingerprint is not None:
            self._ui.keyListView.select_key(
                fingerprint, subkey_keyid, uid_value, photo_index
            )
        message = self._pending_status_message
        self._pending_status_message = None
        if message is not None:
            self.statusBar().showMessage(message)
        else:
            self.statusBar().showMessage(_("{n} key(s) loaded").format(n=len(keys)))

    def _on_keys_load_failed(self, exc: Exception) -> None:
        """Report a failed background key-list reload, *exc*, in the status bar."""
        self._ui.actionKeyRefresh.setEnabled(True)
        self.statusBar().showMessage(
            _("Could not load keys: {error}").format(error=str(exc))
        )

    def _on_key_new(self) -> None:
        """Open the New Key wizard and reload the keyring if a key was created."""
        from pbnightingale.ui.new_key_wizard import NewKeyWizard

        wizard = NewKeyWizard(self)
        if wizard.exec() == NewKeyWizard.DialogCode.Accepted:
            self.refresh_keys()

    def _describe_import(
        self, imported: list[ImportedKey]
    ) -> tuple[str | None, str | None]:
        """Build the status-bar message and fingerprint to auto-select for keys just imported via ImportKeyDialog or SearchKeyDialog.

        Parameters
        ----------
        imported
            The keys that were just imported.

        Returns
        -------
        :
            ``(status_message, fingerprint)``, both ``None`` when
            *imported* is empty.
        """
        if not imported:
            return None, None
        if len(imported) == 1:
            entry = imported[0]
            uid = entry.key.uids[0].value if entry.key.uids else entry.key.keyid
            if entry.is_new:
                message = _("Key imported: {uid} ({keyid})").format(
                    uid=uid, keyid=entry.key.keyid
                )
            else:
                message = _("Key already in keyring: {uid} ({keyid})").format(
                    uid=uid, keyid=entry.key.keyid
                )
            return message, entry.key.fingerprint
        new_count = sum(1 for entry in imported if entry.is_new)
        existing_count = len(imported) - new_count
        message = _("{new} new key(s) imported, {existing} already present").format(
            new=new_count, existing=existing_count
        )
        return message, imported[0].key.fingerprint

    def _on_key_import(self) -> None:
        """Open the Import Key dialog and reload the keyring, selecting whatever was imported."""
        from pbnightingale.ui.import_key_dialog import ImportKeyDialog

        dialog = ImportKeyDialog(self)
        if dialog.exec() == ImportKeyDialog.DialogCode.Accepted:
            message, fingerprint = self._describe_import(dialog.imported_keys)
            self.refresh_keys(status_message=message, select_fingerprint=fingerprint)

    def _on_key_subkey_add(self) -> None:
        """Open the Add Subkey dialog for the selected key and reload the keyring if a subkey was added."""
        from pbnightingale.ui.add_subkey_dialog import AddSubkeyDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = AddSubkeyDialog(key.fingerprint, self)
        if dialog.exec() == AddSubkeyDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_expire(self) -> None:
        """Open the Set Expiration dialog for the selected key and reload the keyring if its expiration changed."""
        from pbnightingale.ui.set_expiration_dialog import SetExpirationDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = SetExpirationDialog(key.fingerprint, parent=self)
        if dialog.exec() == SetExpirationDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_subkey_expire(self) -> None:
        """Open the Set Expiration dialog for the selected subkey and reload the keyring if its expiration changed."""
        from pbnightingale.ui.set_expiration_dialog import SetExpirationDialog

        key = self._ui.keyListView.selected_key()
        subkey = self._ui.keyListView.selected_subkey()
        if key is None or subkey is None:
            return
        dialog = SetExpirationDialog(key.fingerprint, subkey, self)
        if dialog.exec() == SetExpirationDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_uid_add(self) -> None:
        """Open the Add User ID dialog for the selected key and reload the keyring if an identity was added."""
        from pbnightingale.ui.add_uid_dialog import AddUidDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = AddUidDialog(key.fingerprint, self)
        if dialog.exec() == AddUidDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_uid_set_primary(self) -> None:
        """Open the Set Primary User ID dialog for the selected identity and reload the keyring if it changed."""
        from pbnightingale.ui.set_primary_uid_dialog import SetPrimaryUidDialog

        key = self._ui.keyListView.selected_key()
        uid = self._ui.keyListView.selected_uid()
        if key is None or uid is None:
            return
        dialog = SetPrimaryUidDialog(key.fingerprint, uid, self)
        if dialog.exec() == SetPrimaryUidDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_uid_revoke(self) -> None:
        """Open the Revoke User ID dialog for the selected identity and reload the keyring if it was revoked."""
        from pbnightingale.ui.revoke_uid_dialog import RevokeUidDialog

        key = self._ui.keyListView.selected_key()
        uid = self._ui.keyListView.selected_uid()
        if key is None or uid is None:
            return
        dialog = RevokeUidDialog(key.fingerprint, uid, self)
        if dialog.exec() == RevokeUidDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_photo_add(self) -> None:
        """Open the Add Photo dialog for the selected key and reload the keyring if a photo was added."""
        from pbnightingale.ui.add_photo_dialog import AddPhotoDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = AddPhotoDialog(key.fingerprint, self)
        if dialog.exec() == AddPhotoDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_photo_revoke(self) -> None:
        """Open the Revoke Photo dialog for the selected photo and reload the keyring if it was revoked."""
        from pbnightingale.ui.revoke_photo_dialog import RevokePhotoDialog

        key = self._ui.keyListView.selected_key()
        photo = self._ui.keyListView.selected_photo()
        if key is None or photo is None:
            return
        dialog = RevokePhotoDialog(key.fingerprint, photo, self)
        if dialog.exec() == RevokePhotoDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_copy_id(self) -> None:
        """Copy the selected key's fingerprint to the clipboard."""
        key = self._ui.keyListView.selected_key()
        if key is not None:
            QApplication.clipboard().setText(key.fingerprint)

    def _on_key_subkey_copy_id(self) -> None:
        """Copy the selected subkey's fingerprint to the clipboard."""
        subkey = self._ui.keyListView.selected_subkey()
        if subkey is not None:
            QApplication.clipboard().setText(subkey.fingerprint)

    def _on_key_uid_copy_email(self) -> None:
        """Copy the selected identity's email address to the clipboard, if it has one."""
        uid = self._ui.keyListView.selected_uid()
        if uid is None:
            return
        _name, email = parseaddr(uid.value)
        if email:
            QApplication.clipboard().setText(email)

    def _on_key_photo_show(self) -> None:
        """Open the selected photo in a full-size viewer."""
        self._ui.keyListView.show_selected_photo()

    def _on_key_sign(self) -> None:
        """Open the Sign Key dialog for the selected key and reload the keyring if a signature was added."""
        from pbnightingale.ui.sign_key_dialog import SignKeyDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = SignKeyDialog(key, self._ui.keyListView.my_keys(), self)
        if dialog.exec() == SignKeyDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_set_owner_trust(self) -> None:
        """Open the Set Owner Trust dialog for the selected key and reload the keyring if its owner trust changed."""
        from pbnightingale.ui.set_owner_trust_dialog import SetOwnerTrustDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = SetOwnerTrustDialog(key, self)
        if dialog.exec() == SetOwnerTrustDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_trust_refresh(self) -> None:
        """Recompute the web of trust for the whole keyring, in the background."""
        self._ui.actionTrustRefresh.setEnabled(False)
        self.statusBar().showMessage(_("Refreshing trust…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().refresh_trust(),
            on_success=self._on_trust_refreshed,
            on_error=self._on_trust_refresh_failed,
        )

    def _on_trust_refreshed(self, _result: None) -> None:
        """Reload the keyring once trust recomputation completes, since it can change keys' computed validity."""
        self._ui.actionTrustRefresh.setEnabled(True)
        # Recomputing trust can change keys' computed validity, so reload
        # to reflect that — its own status messages take over from here
        # rather than a separate "done" message that would just be
        # overwritten right away.
        self.refresh_keys()

    def _on_trust_refresh_failed(self, exc: Exception) -> None:
        """Report a failed trust recomputation, *exc*, in the status bar."""
        self._ui.actionTrustRefresh.setEnabled(True)
        self.statusBar().showMessage(
            _("Could not refresh trust: {error}").format(error=str(exc))
        )

    def _on_server_search(self) -> None:
        """Open the Search Keyserver dialog and reload the keyring, selecting whatever was imported."""
        from pbnightingale.ui.search_key_dialog import SearchKeyDialog

        dialog = SearchKeyDialog(self)
        if dialog.exec() == SearchKeyDialog.DialogCode.Accepted:
            message, fingerprint = self._describe_import(dialog.imported_keys)
            self.refresh_keys(status_message=message, select_fingerprint=fingerprint)

    def _checked_keyservers_or_warn(self, title: str) -> list[str] | None:
        """Return the checked Preferences keyservers, or warn and return ``None``.

        Parameters
        ----------
        title
            The warning dialog's title, matching the action being blocked.

        Returns
        -------
        :
            The checked keyserver URLs, in display order — ``None`` if
            none are checked, after already showing the warning.
        """
        keyservers = preferences.get_checked_keyserver_urls()
        if not keyservers:
            QMessageBox.warning(
                self,
                title,
                _(
                    "No keyserver is checked. Check at least one in "
                    "Preferences → Key Servers."
                ),
            )
            return None
        return keyservers

    def _on_server_publish(self) -> None:
        """Ask which keyservers to publish to, then publish the selected key in the background."""
        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        from pbnightingale.ui.publish_key_dialog import PublishKeyDialog

        dialog = PublishKeyDialog(key.keyid, self)
        if dialog.exec() != PublishKeyDialog.DialogCode.Accepted:
            return
        keyservers = dialog.selected_keyservers()
        self._ui.actionServerPublish.setEnabled(False)
        self.statusBar().showMessage(_("Publishing…"))
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().publish_to_keyservers(
                key.fingerprint, keyservers
            ),
            on_success=self._on_server_published,
            on_error=self._on_server_publish_failed,
        )

    def _on_server_published(self, keyservers: list[str]) -> None:
        """Report a successful keyserver publish in the status bar.

        Parameters
        ----------
        keyservers
            The keyservers the key was actually published to.
        """
        self._ui.actionServerPublish.setEnabled(True)
        self.statusBar().showMessage(
            _("Key published to {keyservers}").format(keyservers=", ".join(keyservers))
        )

    def _on_server_publish_failed(self, exc: Exception) -> None:
        """Report a failed keyserver publish, *exc*, in the status bar."""
        self._ui.actionServerPublish.setEnabled(True)
        self.statusBar().showMessage(
            _("Could not publish key: {error}").format(error=str(exc))
        )

    def _on_server_refresh(self) -> None:
        """Open the Refresh Keys dialog and refresh the chosen key(s) from the keyserver in the background, with a modal progress window."""
        keyservers = self._checked_keyservers_or_warn(_("Refresh Keys"))
        if keyservers is None:
            return
        from pbnightingale.ui.refresh_keys_dialog import RefreshKeysDialog

        key = self._ui.keyListView.selected_key()
        dialog = RefreshKeysDialog(has_selection=key is not None, parent=self)
        if dialog.exec() != RefreshKeysDialog.DialogCode.Accepted:
            return
        fingerprints = None if dialog.refresh_all() else [key.fingerprint]

        self._ui.actionServerRefresh.setEnabled(False)
        # A keyserver round-trip can take a while — a modal progress window
        # makes that wait obvious, unlike every other keyserver/trust
        # action here, which only shows a status-bar line.
        self._refresh_progress = QProgressDialog(
            _("Refreshing keys from keyserver…"), "", 0, 0, self
        )
        self._refresh_progress.setWindowTitle(_("Refresh Keys"))
        self._refresh_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._refresh_progress.setCancelButton(None)
        self._refresh_progress.setMinimumDuration(0)
        self._refresh_progress.show()

        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().refresh_from_keyserver(
                fingerprints=fingerprints, keyservers=keyservers
            ),
            on_success=self._on_server_refreshed,
            on_error=self._on_server_refresh_failed,
        )

    def _on_server_refreshed(self, refreshed: list[RefreshedKey]) -> None:
        """Show the refresh report and reload the keyring once a keyserver refresh completes with *refreshed*."""
        from pbnightingale.ui.refresh_keys_report_dialog import (
            RefreshKeysReportDialog,
        )

        self._ui.actionServerRefresh.setEnabled(True)
        self._close_refresh_progress()
        RefreshKeysReportDialog(refreshed, self).exec()
        # Refreshing can pick up new signatures/UIDs/revocations, so reload
        # — same reasoning as _on_trust_refreshed.
        self.refresh_keys()

    def _on_server_refresh_failed(self, exc: Exception) -> None:
        """Report a failed keyserver refresh, *exc*, in a warning dialog."""
        self._ui.actionServerRefresh.setEnabled(True)
        self._close_refresh_progress()
        QMessageBox.warning(
            self,
            _("Refresh Keys"),
            _("Could not refresh keys: {error}").format(error=str(exc)),
        )

    def _close_refresh_progress(self) -> None:
        """Close and clear the keyserver-refresh progress dialog, if one is showing."""
        if self._refresh_progress is not None:
            self._refresh_progress.close()
            self._refresh_progress = None

    def _on_signatures_requested(self, fingerprint: str) -> None:
        """Load *fingerprint*'s certifications in the background, for the signatures tab."""
        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().list_key_signatures(fingerprint),
            on_success=lambda signatures: self._on_signatures_loaded(
                fingerprint, signatures
            ),
            on_error=self._on_signatures_load_failed,
        )

    def _on_signatures_loaded(
        self, fingerprint: str, signatures: list[KeySignature]
    ) -> None:
        """Populate the signatures tab once ``list_key_signatures()`` completes.

        Parameters
        ----------
        fingerprint
            The key the signatures belong to.
        signatures
            The certifications found on that key's user IDs.
        """
        self._ui.keyListView.set_key_signatures(fingerprint, signatures)

    def _on_signatures_load_failed(self, exc: Exception) -> None:
        """Clear the signatures tab and report a failed load, *exc*, in the status bar."""
        self._ui.keyListView.clear_signatures()
        self.statusBar().showMessage(
            _("Could not load signatures: {error}").format(error=str(exc))
        )

    def _on_download_unknown_signatures(self, identifiers: list[str]) -> None:
        """Fetch each of *identifiers* from the keyserver in the background, with a modal progress window."""
        keyservers = self._checked_keyservers_or_warn(_("Download Unknown Keys"))
        if keyservers is None:
            return
        # Same modal-progress treatment as _on_server_refresh(): a keyserver
        # round-trip per identifier can take a while.
        self._signatures_progress = QProgressDialog(
            _("Downloading unknown keys from keyserver…"), "", 0, 0, self
        )
        self._signatures_progress.setWindowTitle(_("Download Unknown Keys"))
        self._signatures_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._signatures_progress.setCancelButton(None)
        self._signatures_progress.setMinimumDuration(0)
        self._signatures_progress.show()

        run_async(
            self._pool,
            lambda: gpg_backend.default_backend().download_unknown_signatures(
                identifiers, keyservers
            ),
            on_success=self._on_signatures_downloaded,
            on_error=self._on_signatures_download_failed,
        )

    def _on_signatures_downloaded(self, downloaded: list[DownloadedSignature]) -> None:
        """Show the download report and reload the keyring, since a newly-downloaded signer key can now be resolved."""
        from pbnightingale.ui.download_signatures_report_dialog import (
            DownloadSignaturesReportDialog,
        )

        self._close_signatures_progress()
        DownloadSignaturesReportDialog(downloaded, self).exec()
        # A newly-downloaded signer key can now appear in the main list and
        # be resolved on the signatures tab — same reasoning as
        # _on_server_refreshed.
        self.refresh_keys()

    def _on_signatures_download_failed(self, exc: Exception) -> None:
        """Report a failed signature-key download, *exc*, in a warning dialog."""
        self._close_signatures_progress()
        QMessageBox.warning(
            self,
            _("Download Unknown Keys"),
            _("Could not download keys: {error}").format(error=str(exc)),
        )

    def _close_signatures_progress(self) -> None:
        """Close and clear the signature-download progress dialog, if one is showing."""
        if self._signatures_progress is not None:
            self._signatures_progress.close()
            self._signatures_progress = None

    def _on_key_revoke(self) -> None:
        """Open the Revoke Key dialog for the selected key and reload the keyring if it was revoked."""
        from pbnightingale.ui.revoke_key_dialog import RevokeKeyDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = RevokeKeyDialog(key, self)
        if dialog.exec() == RevokeKeyDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_subkey_revoke(self) -> None:
        """Open the Revoke Subkey dialog for the selected subkey and reload the keyring if it was revoked."""
        from pbnightingale.ui.revoke_subkey_dialog import RevokeSubkeyDialog

        key = self._ui.keyListView.selected_key()
        subkey = self._ui.keyListView.selected_subkey()
        if key is None or subkey is None:
            return
        dialog = RevokeSubkeyDialog(key.fingerprint, subkey, self)
        if dialog.exec() == RevokeSubkeyDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_export(self) -> None:
        """Save the selected key's public part to a file chosen by the user."""
        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            _("Export Key"),
            f"{key.keyid}.asc",
            _("ASCII-armored keys (*.asc)"),
        )
        if not path:
            return
        try:
            armored = gpg_backend.default_backend().export_public_key(key.fingerprint)
            Path(path).write_text(armored, encoding="utf-8")
        except (GPGBackendError, OSError) as exc:
            self.statusBar().showMessage(
                _("Could not export key: {error}").format(error=str(exc))
            )
            return
        self.statusBar().showMessage(_("Key exported to {path}").format(path=path))

    def _on_key_backup(self) -> None:
        """Open the Back Up Private Key dialog for the selected key."""
        from pbnightingale.ui.backup_private_key_dialog import BackupPrivateKeyDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        BackupPrivateKeyDialog(key, self).exec()

    def _on_key_change_passphrase(self) -> None:
        """Open the Change Passphrase dialog for the selected key and reload the keyring if it changed."""
        from pbnightingale.ui.change_passphrase_dialog import ChangePassphraseDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = ChangePassphraseDialog(key.fingerprint, self)
        if dialog.exec() == ChangePassphraseDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_key_delete(self) -> None:
        """Open the Delete Key dialog for the selected key and reload the keyring if it was deleted."""
        from pbnightingale.ui.delete_key_dialog import DeleteKeyDialog

        key = self._ui.keyListView.selected_key()
        if key is None:
            return
        dialog = DeleteKeyDialog(key, self)
        if dialog.exec() == DeleteKeyDialog.DialogCode.Accepted:
            self.refresh_keys()

    def _on_settings(self) -> None:
        """Open the Settings dialog and re-apply preferences if settings were saved."""
        from pbnightingale.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._apply_toolbar_icon_size()
            activity_log.configure(preferences.get_activity_log_max_entries())
            if self._activity_log_dialog is not None:
                self._activity_log_dialog.refresh()

    def _on_activity_log(self) -> None:
        """Show the Activity (advanced) window, creating it on first use.

        Non-modal and kept as a single instance for the rest of the
        window's lifetime — repeat activation (menu or F12) just raises
        the existing one rather than creating another.
        """
        if self._activity_log_dialog is None:
            from pbnightingale.ui.activity_log_dialog import ActivityLogDialog

            self._activity_log_dialog = ActivityLogDialog(self)
        self._activity_log_dialog.show()
        self._activity_log_dialog.raise_()
        self._activity_log_dialog.activateWindow()

    def _on_help_manual(self) -> None:
        """Open the online user manual in the interface's current language."""
        lang = i18n.current_language()
        QDesktopServices.openUrl(
            QUrl(f"https://pbnightingale.readthedocs.io/{lang}/latest")
        )

    def _on_about(self) -> None:
        """Open the About dialog."""
        from pbnightingale.ui.about_dialog import AboutDialog

        AboutDialog(self).exec()
