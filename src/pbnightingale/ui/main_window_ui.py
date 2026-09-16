"""UI layout for the main window: actions, toolbars, menus, status bar."""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenuBar, QStatusBar, QToolBar, QWhatsThis

from pbnightingale.resources import path as _resource
from pbnightingale.ui.key_list_view import KeyListView


class Ui_MainWindow:
    def setupUi(self, window: QMainWindow) -> None:
        window.setMinimumSize(900, 600)
        window.resize(1100, 700)
        window.setWindowTitle("PBNightingale")

        self._setup_actions(window)
        self._setup_statusbar(window)
        self._setup_central_widget(window)
        self._setup_toolbars(window)
        self._setup_menubar(window)

    # ── Central widget ───────────────────────────────────────────────────

    def _setup_central_widget(self, window: QMainWindow) -> None:
        self.keyListView = KeyListView(window)
        window.setCentralWidget(self.keyListView)

    # ── Actions ──────────────────────────────────────────────────────────

    def _setup_actions(self, window: QMainWindow) -> None:
        self._setup_general_actions(window)
        self._setup_key_actions(window)
        self._setup_trust_actions(window)
        self._setup_server_actions(window)

    def _setup_general_actions(self, window: QMainWindow) -> None:
        self.actionSettings = QAction(
            QIcon(_resource("preferences-system.svg")), _("Settings…"), window
        )
        self.actionSettings.setToolTip(_("Open settings"))
        self.actionSettings.setStatusTip(_("Configure the interface language"))
        self.actionSettings.setWhatsThis(
            _(
                "Configure the interface language, the default algorithm "
                "for new keys, the toolbar icon size, and how long a "
                "passphrase you enter is remembered before it's forgotten "
                "again."
            )
        )

        self.actionQuit = QAction(QIcon(_resource("quit.svg")), _("Quit"), window)
        self.actionQuit.setShortcut(QKeySequence("Ctrl+Q"))
        self.actionQuit.setToolTip(_("Quit PBNightingale"))
        self.actionQuit.setStatusTip(_("Exit the application"))
        self.actionQuit.setWhatsThis(
            _(
                "Closes PBNightingale. There is nothing to save first — "
                "every change is applied directly to your GPG keyring as "
                "you make it, so no operation already done is undone by "
                "quitting."
            )
        )

        self.actionAbout = QAction(
            QIcon(_resource("help-about.svg")), _("About PBNightingale"), window
        )
        self.actionAbout.setToolTip(_("About this application"))
        self.actionAbout.setStatusTip(_("Show version and license information"))
        self.actionAbout.setWhatsThis(
            _(
                "Shows the application's version, author and license "
                "(GPLv3 for the code; the bundled icons are separately "
                "licensed under CC BY-NC-SA 4.0)."
            )
        )

        self.actionResetToolbars = QAction(
            QIcon(_resource("previous.svg")), _("Reset toolbars"), window
        )
        self.actionResetToolbars.setStatusTip(
            _("Restore the default toolbar positions and visibility")
        )
        self.actionResetToolbars.setWhatsThis(
            _(
                "Restores every toolbar to its position, order and "
                "visibility from the very first run — handy after moving "
                "or hiding one by accident."
            )
        )

        # QWhatsThis.createAction() already wires up the standard "click
        # here, then click a widget" behavior (and its own translated text/
        # shortcut, via Qt's own base translations) — only the icon is ours.
        self.actionWhatsThis = QWhatsThis.createAction(window)
        self.actionWhatsThis.setIcon(QIcon(_resource("help-contextual.svg")))

    def _setup_key_actions(self, window: QMainWindow) -> None:
        self.actionKeyRefresh = QAction(
            QIcon(_resource("view-refresh.svg")), _("Refresh"), window
        )
        self.actionKeyRefresh.setShortcut(QKeySequence("F5"))
        self.actionKeyRefresh.setStatusTip(_("Reload the key list from the keyring"))
        self.actionKeyRefresh.setWhatsThis(
            _(
                "Reloads the key list from your GPG keyring, picking up "
                "any change made outside PBNightingale (e.g. via the gpg "
                "command line)."
            )
        )

        self.actionKeyNew = QAction(
            QIcon(_resource("key-new.svg")), _("New key…"), window
        )
        self.actionKeyNew.setStatusTip(_("Create a new personal key pair"))
        self.actionKeyNew.setWhatsThis(
            _(
                "Opens the wizard to generate a brand-new personal key "
                "pair (RSA or Ed25519), including its own passphrase."
            )
        )

        self.actionKeySubkeyAdd = QAction(
            QIcon(_resource("subkey-add.svg")), _("Add subkey…"), window
        )
        self.actionKeySubkeyAdd.setStatusTip(
            _("Add a signing, encryption or authentication subkey")
        )
        self.actionKeySubkeyAdd.setWhatsThis(
            _(
                "Adds a new subkey to the selected personal key, for "
                "signing, encryption or authentication — useful for "
                "giving each purpose its own key without touching the "
                "primary one."
            )
        )

        self.actionKeyExpire = QAction(
            QIcon(_resource("key-expire.svg")), _("Set key expiration…"), window
        )
        self.actionKeyExpire.setStatusTip(_("Set this key's expiration date"))
        self.actionKeyExpire.setWhatsThis(
            _("Sets or removes the selected key's own expiration date.")
        )

        self.actionKeyRevoke = QAction(
            QIcon(_resource("key-revoke.svg")), _("Revoke key…"), window
        )
        self.actionKeyRevoke.setStatusTip(_("Revoke this key (requires confirmation)"))
        self.actionKeyRevoke.setWhatsThis(
            _(
                "Permanently revokes the selected personal key itself, "
                "marking it untrustworthy from now on. This cannot be "
                "undone — the key still exists, but should no longer be "
                "used or trusted."
            )
        )

        self.actionKeySubkeyExpire = QAction(
            QIcon(_resource("subkey-expire.svg")), _("Set subkey expiration…"), window
        )
        self.actionKeySubkeyExpire.setStatusTip(
            _("Set the selected subkey's expiration date")
        )
        self.actionKeySubkeyExpire.setWhatsThis(
            _(
                "Sets or removes the selected subkey's expiration date, "
                "independently of the primary key's own expiration."
            )
        )

        self.actionKeyUidAdd = QAction(
            QIcon(_resource("user-add.svg")), _("Add user ID…"), window
        )
        self.actionKeyUidAdd.setStatusTip(_("Add a new identity (name and email)"))
        self.actionKeyUidAdd.setWhatsThis(
            _(
                "Adds another identity (name and email address) to the "
                "selected personal key — e.g. a second address you also "
                "want this key to vouch for."
            )
        )

        self.actionKeyUidSetPrimary = QAction(
            QIcon(_resource("user-default.svg")), _("Set as primary…"), window
        )
        self.actionKeyUidSetPrimary.setStatusTip(
            _("Set the selected user ID as the primary identity")
        )
        self.actionKeyUidSetPrimary.setWhatsThis(
            _(
                "Marks the selected identity as the key's primary one — "
                "the identity other tools show by default for this key."
            )
        )

        self.actionKeyUidRevoke = QAction(
            QIcon(_resource("user-delete.svg")), _("Revoke user ID…"), window
        )
        self.actionKeyUidRevoke.setStatusTip(
            _("Revoke the selected user ID (requires confirmation)")
        )
        self.actionKeyUidRevoke.setWhatsThis(
            _(
                "Permanently revokes the selected identity. At least one "
                "non-revoked identity must remain on the key."
            )
        )

        self.actionKeyPhotoAdd = QAction(
            QIcon(_resource("photo-add.svg")), _("Add photo…"), window
        )
        self.actionKeyPhotoAdd.setStatusTip(_("Add a photo user ID"))
        self.actionKeyPhotoAdd.setWhatsThis(
            _(
                "Attaches a photo to the selected personal key, as an "
                "extra (visual) identity."
            )
        )

        self.actionKeyPhotoRevoke = QAction(
            QIcon(_resource("photo-delete.svg")), _("Revoke photo…"), window
        )
        self.actionKeyPhotoRevoke.setStatusTip(
            _("Revoke the selected photo (requires confirmation)")
        )
        self.actionKeyPhotoRevoke.setWhatsThis(
            _("Permanently revokes the selected photo.")
        )

        self.actionKeyImport = QAction(
            QIcon(_resource("key-import.svg")), _("Import…"), window
        )
        self.actionKeyImport.setStatusTip(_("Import a key from a file or a keyserver"))
        self.actionKeyImport.setWhatsThis(
            _(
                "Imports a key from a local file, or fetches one from a "
                "keyserver by fingerprint, key ID or email address."
            )
        )

        self.actionKeyExport = QAction(
            QIcon(_resource("key-export.svg")), _("Export…"), window
        )
        self.actionKeyExport.setStatusTip(_("Export the selected key to a file"))
        self.actionKeyExport.setWhatsThis(
            _(
                "Saves the selected key's public part to a file, to share "
                "with someone else. Does not include any private key "
                "material."
            )
        )

        self.actionKeyBackup = QAction(
            QIcon(_resource("key-backup.svg")), _("Back up private key…"), window
        )
        self.actionKeyBackup.setStatusTip(
            _("Export the selected key's private key material to a file")
        )
        self.actionKeyBackup.setWhatsThis(
            _(
                "Saves the selected key's full private key material to a "
                "file — a real backup, unlike Export. Requires the key's "
                "passphrase; anyone with this file and its passphrase can "
                "fully impersonate the key."
            )
        )

        self.actionKeyChangePassphrase = QAction(
            QIcon(_resource("password-change.svg")), _("Change passphrase…"), window
        )
        self.actionKeyChangePassphrase.setStatusTip(
            _("Change the passphrase protecting this key's private key material")
        )
        self.actionKeyChangePassphrase.setWhatsThis(
            _(
                "Changes the passphrase protecting the selected key's "
                "private key material. Requires the current passphrase."
            )
        )

        self.actionKeyDelete = QAction(
            QIcon(_resource("key-delete.svg")), _("Delete…"), window
        )
        self.actionKeyDelete.setStatusTip(_("Delete the selected key"))
        self.actionKeyDelete.setWhatsThis(
            _(
                "Permanently removes the selected key from your keyring, "
                "including any private key material. Requires strong "
                "confirmation, since this cannot be undone — unlike "
                "revoking, the key won't exist at all afterwards."
            )
        )

        # ── Copy / view — read-only, so available on any key regardless of
        # whether its secret part is held ──────────────────────────────
        copy_icon = QIcon(_resource("edit-copy.svg"))

        self.actionKeyCopyId = QAction(copy_icon, _("Copy ID"), window)
        self.actionKeyCopyId.setStatusTip(
            _("Copy the selected key's fingerprint to the clipboard")
        )
        self.actionKeyCopyId.setWhatsThis(
            _("Copies the selected key's full fingerprint to the clipboard.")
        )

        self.actionKeySubkeyCopyId = QAction(copy_icon, _("Copy ID"), window)
        self.actionKeySubkeyCopyId.setStatusTip(
            _("Copy the selected subkey's fingerprint to the clipboard")
        )
        self.actionKeySubkeyCopyId.setWhatsThis(
            _("Copies the selected subkey's full fingerprint to the clipboard.")
        )

        self.actionKeyUidCopyEmail = QAction(copy_icon, _("Copy email"), window)
        self.actionKeyUidCopyEmail.setStatusTip(
            _("Copy the selected identity's email address to the clipboard")
        )
        self.actionKeyUidCopyEmail.setWhatsThis(
            _(
                "Copies the selected identity's email address to the "
                "clipboard, if it has one."
            )
        )

        self.actionKeyPhotoShow = QAction(
            QIcon(_resource("view.svg")), _("Show"), window
        )
        self.actionKeyPhotoShow.setStatusTip(_("View the selected photo full-size"))
        self.actionKeyPhotoShow.setWhatsThis(
            _(
                "Opens the selected photo in a viewer, at full size — same "
                "as double-clicking it."
            )
        )

    def _setup_trust_actions(self, window: QMainWindow) -> None:
        self.actionKeySign = QAction(
            QIcon(_resource("key-sign.svg")), _("Sign key…"), window
        )
        self.actionKeySign.setStatusTip(_("Sign another key to build the web of trust"))
        self.actionKeySign.setWhatsThis(
            _(
                "Signs the selected key with one of your own keys, "
                "vouching that its identity binding is genuine — the "
                "basis of the web of trust."
            )
        )

        self.actionKeySetOwnerTrust = QAction(
            QIcon(_resource("trust-set.svg")), _("Set owner trust…"), window
        )
        self.actionKeySetOwnerTrust.setStatusTip(
            _("Set how much you trust this key's owner to certify others")
        )
        self.actionKeySetOwnerTrust.setWhatsThis(
            _(
                "Sets how much you personally trust the selected key's "
                "owner to correctly vouch for other people's keys. This "
                "is a private, local judgment — it isn't published "
                "anywhere."
            )
        )

        self.actionKeySubkeyRevoke = QAction(
            QIcon(_resource("subkey-revoke.svg")), _("Revoke subkey…"), window
        )
        self.actionKeySubkeyRevoke.setStatusTip(
            _("Revoke a subkey (requires confirmation)")
        )
        self.actionKeySubkeyRevoke.setWhatsThis(
            _(
                "Permanently revokes the selected subkey. Unlike revoking "
                "the whole key, the primary key and its other subkeys "
                "remain usable."
            )
        )

        self.actionTrustRefresh = QAction(
            QIcon(_resource("trust-refresh.svg")), _("Refresh trust"), window
        )
        self.actionTrustRefresh.setStatusTip(_("Recompute the web of trust"))
        self.actionTrustRefresh.setWhatsThis(
            _(
                "Recomputes every key's validity from its current "
                "signatures — useful after signing a key, or importing "
                "new signatures, since validity isn't recalculated "
                "automatically."
            )
        )

    def _setup_server_actions(self, window: QMainWindow) -> None:
        self.actionServerSearch = QAction(
            QIcon(_resource("server-search.svg")), _("Search…"), window
        )
        self.actionServerSearch.setStatusTip(
            _("Search a keyserver by fingerprint, key ID or email")
        )
        self.actionServerSearch.setWhatsThis(
            _(
                "Searches a keyserver by name, email address, fingerprint "
                "or key ID, and lets you import one of the matching keys."
            )
        )

        self.actionServerPublish = QAction(
            QIcon(_resource("server-publish.svg")), _("Publish…"), window
        )
        self.actionServerPublish.setStatusTip(
            _("Publish the selected key to a keyserver")
        )
        self.actionServerPublish.setWhatsThis(
            _(
                "Publishes the selected key to a keyserver, making it "
                "publicly retrievable by anyone. A published key "
                "generally cannot be fully removed again afterwards, only "
                "revoked."
            )
        )

        self.actionServerRefresh = QAction(
            QIcon(_resource("server-refresh.svg")), _("Refresh"), window
        )
        self.actionServerRefresh.setStatusTip(_("Refresh keys from their keyserver"))
        self.actionServerRefresh.setWhatsThis(
            _(
                "Re-downloads the selected key, or every key in your "
                "keyring, from its keyserver, picking up new signatures, "
                "identities or revocations."
            )
        )

    # ── Status bar ───────────────────────────────────────────────────────

    def _setup_statusbar(self, window: QMainWindow) -> None:
        self.statusbar = QStatusBar(window)
        window.setStatusBar(self.statusbar)

    # ── Toolbars — one per functional theme ─────────────────────────────

    def _setup_toolbars(self, window: QMainWindow) -> None:
        self.toolbarKeys = QToolBar(_("Keys"), window)
        self.toolbarKeys.setObjectName("toolbarKeys")
        self.toolbarKeys.addAction(self.actionKeyRefresh)
        self.toolbarKeys.addSeparator()
        self.toolbarKeys.addAction(self.actionKeyCopyId)
        self.toolbarKeys.addAction(self.actionKeyNew)
        self.toolbarKeys.addAction(self.actionKeyExpire)
        self.toolbarKeys.addAction(self.actionKeyRevoke)
        self.toolbarKeys.addAction(self.actionKeyImport)
        self.toolbarKeys.addAction(self.actionKeyExport)
        self.toolbarKeys.addAction(self.actionKeyBackup)
        self.toolbarKeys.addAction(self.actionKeyChangePassphrase)
        self.toolbarKeys.addAction(self.actionKeyDelete)
        window.addToolBar(self.toolbarKeys)

        self.toolbarIdentities = QToolBar(_("Identities"), window)
        self.toolbarIdentities.setObjectName("toolbarIdentities")
        self.toolbarIdentities.addAction(self.actionKeyUidAdd)
        self.toolbarIdentities.addAction(self.actionKeyUidCopyEmail)
        self.toolbarIdentities.addAction(self.actionKeyUidSetPrimary)
        self.toolbarIdentities.addAction(self.actionKeyUidRevoke)
        window.addToolBar(self.toolbarIdentities)

        self.toolbarSubkeys = QToolBar(_("Subkeys"), window)
        self.toolbarSubkeys.setObjectName("toolbarSubkeys")
        self.toolbarSubkeys.addAction(self.actionKeySubkeyAdd)
        self.toolbarSubkeys.addAction(self.actionKeySubkeyCopyId)
        self.toolbarSubkeys.addAction(self.actionKeySubkeyExpire)
        self.toolbarSubkeys.addAction(self.actionKeySubkeyRevoke)
        window.addToolBar(self.toolbarSubkeys)

        self.toolbarPhotos = QToolBar(_("Photos"), window)
        self.toolbarPhotos.setObjectName("toolbarPhotos")
        self.toolbarPhotos.addAction(self.actionKeyPhotoAdd)
        self.toolbarPhotos.addAction(self.actionKeyPhotoShow)
        self.toolbarPhotos.addAction(self.actionKeyPhotoRevoke)
        window.addToolBar(self.toolbarPhotos)

        self.toolbarTrust = QToolBar(_("Trust"), window)
        self.toolbarTrust.setObjectName("toolbarTrust")
        self.toolbarTrust.addAction(self.actionKeySign)
        self.toolbarTrust.addAction(self.actionKeySetOwnerTrust)
        self.toolbarTrust.addAction(self.actionTrustRefresh)
        window.addToolBar(self.toolbarTrust)

        self.toolbarServers = QToolBar(_("Keyservers"), window)
        self.toolbarServers.setObjectName("toolbarServers")
        self.toolbarServers.addAction(self.actionServerSearch)
        self.toolbarServers.addAction(self.actionServerPublish)
        self.toolbarServers.addAction(self.actionServerRefresh)
        window.addToolBar(self.toolbarServers)

        self.toolbarHelp = QToolBar(_("Help"), window)
        self.toolbarHelp.setObjectName("toolbarHelp")
        self.toolbarHelp.addAction(self.actionWhatsThis)
        window.addToolBar(self.toolbarHelp)

    # ── Menu bar ─────────────────────────────────────────────────────────

    def _setup_menubar(self, window: QMainWindow) -> None:
        menubar = QMenuBar(window)
        window.setMenuBar(menubar)

        menu_file = menubar.addMenu(_("File"))
        menu_file.addAction(self.actionQuit)

        menu_edit = menubar.addMenu(_("Edit"))
        menu_edit.addAction(self.actionSettings)

        menu_keys = menubar.addMenu(_("Keys"))
        menu_keys.addAction(self.actionKeyRefresh)
        menu_keys.addSeparator()
        menu_keys.addAction(self.actionKeyCopyId)
        menu_keys.addAction(self.actionKeyNew)
        menu_keys.addAction(self.actionKeyExpire)
        menu_keys.addAction(self.actionKeyRevoke)
        menu_keys.addSeparator()
        menu_keys.addAction(self.actionKeySubkeyAdd)
        menu_keys.addAction(self.actionKeySubkeyCopyId)
        menu_keys.addAction(self.actionKeySubkeyExpire)
        menu_keys.addAction(self.actionKeySubkeyRevoke)
        menu_keys.addSeparator()
        menu_keys.addAction(self.actionKeyImport)
        menu_keys.addAction(self.actionKeyExport)
        menu_keys.addAction(self.actionKeyBackup)
        menu_keys.addAction(self.actionKeyChangePassphrase)
        menu_keys.addSeparator()
        menu_keys.addAction(self.actionKeyDelete)

        menu_identities = menubar.addMenu(_("Identities"))
        menu_identities.addAction(self.actionKeyUidAdd)
        menu_identities.addAction(self.actionKeyUidCopyEmail)
        menu_identities.addAction(self.actionKeyUidSetPrimary)
        menu_identities.addAction(self.actionKeyUidRevoke)
        menu_identities.addSeparator()
        menu_identities.addAction(self.actionKeyPhotoAdd)
        menu_identities.addAction(self.actionKeyPhotoShow)
        menu_identities.addAction(self.actionKeyPhotoRevoke)

        menu_trust = menubar.addMenu(_("Trust"))
        menu_trust.addAction(self.actionKeySign)
        menu_trust.addAction(self.actionKeySetOwnerTrust)
        menu_trust.addAction(self.actionTrustRefresh)

        menu_servers = menubar.addMenu(_("Keyservers"))
        menu_servers.addAction(self.actionServerSearch)
        menu_servers.addAction(self.actionServerPublish)
        menu_servers.addAction(self.actionServerRefresh)

        menu_view = menubar.addMenu(_("View"))
        self.menuToolbars = menu_view.addMenu(_("Toolbars"))
        self.menuToolbars.addAction(self.toolbarKeys.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarIdentities.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarSubkeys.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarPhotos.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarTrust.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarServers.toggleViewAction())
        self.menuToolbars.addAction(self.toolbarHelp.toggleViewAction())
        menu_view.addAction(self.actionResetToolbars)

        menu_help = menubar.addMenu(_("Help"))
        menu_help.addAction(self.actionWhatsThis)
        menu_help.addSeparator()
        menu_help.addAction(self.actionAbout)
