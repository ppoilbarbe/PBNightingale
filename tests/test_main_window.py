"""Tests for the main window: menus, toolbars, status bar."""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QToolBar

from pbnightingale.core.gpg_backend import (
    DownloadedSignature,
    Key,
    KeySignature,
    PhotoUid,
    Subkey,
    Uid,
)
from pbnightingale.ui.main_window import MainWindow
from tests.gpg_test_helpers import generate_test_key, make_test_jpeg

_SUBKEY = Subkey(
    keyid="AAAABBBBCCCCDDDD",
    fingerprint="1111222233334444555566667777888899990000",
    algo="1",
    length=2048,
    created=1_700_000_000,
    expires=None,
    trust="u",
    can_sign=False,
    can_encrypt=True,
    can_certify=False,
    can_authenticate=False,
)

_PERSONAL_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="",
    uids=[
        Uid("Alice Example <alice@example.com>", revoked=False),
        Uid("Alice Example <alice@work.example.com>", revoked=False),
    ],
    photos=[],
    subkeys=[_SUBKEY],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)

_PUBLIC_KEY = Key(
    fingerprint="BBBB111122223333444455556666777788889999",
    keyid="5555666677778888",
    algo="1",
    length=2048,
    created=1_700_000_000,
    expires=None,
    trust="f",
    owner_trust="",
    uids=[Uid("Bob Example <bob@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=False,
    can_sign=True,
    can_encrypt=False,
    can_certify=True,
    can_authenticate=False,
)


def _make_window_with_keys(qtbot, monkeypatch, keys):
    from pbnightingale.core import gpg_backend

    class _FakeBackend:
        def list_keys(self):
            return keys

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    window = MainWindow()
    qtbot.addWidget(window)
    tree = window._ui.keyListView._ui.treeKeys
    qtbot.waitUntil(lambda: tree.topLevelItem(0) is not None)
    return window


def test_window_title(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "PBNightingale"


def test_status_bar_reports_key_count_once_loaded(qtbot, gnupg_home):
    generate_test_key(gnupg_home)
    window = MainWindow()
    qtbot.addWidget(window)

    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "1 key(s) loaded")


def test_one_toolbar_per_theme(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    toolbars = window.findChildren(QToolBar)

    assert {t.objectName() for t in toolbars} == {
        "toolbarKeys",
        "toolbarIdentities",
        "toolbarSubkeys",
        "toolbarPhotos",
        "toolbarTrust",
        "toolbarServers",
        "toolbarHelp",
    }
    assert {t.windowTitle() for t in toolbars} == {
        "Keys",
        "Identities",
        "Subkeys",
        "Photos",
        "Trust",
        "Keyservers",
        "Help",
    }


def test_toolbar_icons_are_svg_resources(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    for toolbar in window.findChildren(QToolBar):
        for action in toolbar.actions():
            if action.isSeparator():
                continue
            assert not action.icon().isNull()


_ACTION_NAMES = [
    "actionAbout",
    "actionHelpManual",
    "actionKeyBackup",
    "actionKeyChangePassphrase",
    "actionKeyCopyId",
    "actionKeyDelete",
    "actionKeyExpire",
    "actionKeyExport",
    "actionKeyImport",
    "actionKeyNew",
    "actionKeyPhotoAdd",
    "actionKeyPhotoRevoke",
    "actionKeyPhotoShow",
    "actionKeyRefresh",
    "actionKeyRevoke",
    "actionKeySetOwnerTrust",
    "actionKeySign",
    "actionKeySubkeyAdd",
    "actionKeySubkeyCopyId",
    "actionKeySubkeyExpire",
    "actionKeySubkeyRevoke",
    "actionKeyUidAdd",
    "actionKeyUidCopyEmail",
    "actionKeyUidRevoke",
    "actionKeyUidSetPrimary",
    "actionQuit",
    "actionResetToolbars",
    "actionServerPublish",
    "actionServerRefresh",
    "actionServerSearch",
    "actionSettings",
    "actionTrustRefresh",
]


def test_every_action_has_whats_this_text(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    for name in _ACTION_NAMES:
        action = getattr(window._ui, name)
        assert action.whatsThis() != "", name


_EXPECTED_SHORTCUTS = {
    "actionSettings": "Ctrl+,",
    "actionQuit": "Ctrl+Q",
    "actionHelpManual": "F1",
    "actionKeyRefresh": "F5",
    "actionKeyNew": "Ctrl+N",
    "actionKeyImport": "Ctrl+O",
    "actionKeyExport": "Ctrl+E",
    "actionKeyBackup": "Ctrl+Shift+E",
    "actionKeyDelete": "Del",
    "actionTrustRefresh": "Shift+F5",
    "actionServerRefresh": "Ctrl+F5",
}


def test_actions_have_the_expected_shortcuts(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    for name, shortcut in _EXPECTED_SHORTCUTS.items():
        action = getattr(window._ui, name)
        assert action.shortcut() == QKeySequence(shortcut), name


def test_action_shortcuts_are_globally_unique(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    seen: dict[str, str] = {}
    for action in window.findChildren(QAction):
        shortcut = action.shortcut()
        if shortcut.isEmpty():
            continue
        key = shortcut.toString()
        name = action.objectName() or action.text()
        assert key not in seen, (
            f"{name!r} reuses {key!r} already bound to {seen[key]!r}"
        )
        seen[key] = name


def test_menu_bar_has_expected_top_level_menus(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    titles = [action.text() for action in window.menuBar().actions()]

    assert titles == [
        "File",
        "Edit",
        "Keys",
        "Identities",
        "Trust",
        "Keyservers",
        "View",
        "Help",
    ]


def test_view_menu_toggles_toolbar_visibility(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window._ui.toolbarKeys.isVisible() is True

    window._ui.toolbarKeys.toggleViewAction().trigger()

    assert window._ui.toolbarKeys.isVisible() is False


def test_reset_toolbars_action_is_not_on_any_toolbar(qtbot):
    from PySide6.QtWidgets import QToolBar

    window = MainWindow()
    qtbot.addWidget(window)

    for toolbar in window.findChildren(QToolBar):
        assert window._ui.actionResetToolbars not in toolbar.actions()


def test_reset_toolbars_restores_hidden_toolbar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window._ui.toolbarKeys.setVisible(False)

    window._ui.actionResetToolbars.trigger()

    assert window._ui.toolbarKeys.isVisible() is True


def test_toolbar_visibility_persists_across_instances(qtbot):
    first = MainWindow()
    qtbot.addWidget(first)
    first.show()
    first._ui.toolbarKeys.setVisible(False)
    first.close()

    second = MainWindow()
    qtbot.addWidget(second)
    second.show()

    assert second._ui.toolbarKeys.isVisible() is False


def test_reset_toolbars_persists_the_default_layout(qtbot):
    first = MainWindow()
    qtbot.addWidget(first)
    first.show()
    first._ui.toolbarKeys.setVisible(False)
    first._ui.actionResetToolbars.trigger()
    first.close()

    second = MainWindow()
    qtbot.addWidget(second)
    second.show()

    assert second._ui.toolbarKeys.isVisible() is True


def test_quit_action_closes_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window._ui.actionQuit.trigger()

    assert window.isVisible() is False


def test_toolbar_icons_use_system_size_by_default(qtbot):
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QStyle

    window = MainWindow()
    qtbot.addWidget(window)

    px = window.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarIconSize)
    assert window._ui.toolbarKeys.iconSize() == QSize(px, px)


def test_toolbar_icons_use_the_preferred_size(qtbot):
    from PySide6.QtCore import QSize

    from pbnightingale import preferences

    preferences.set_toolbar_icon_size("32")

    window = MainWindow()
    qtbot.addWidget(window)

    for toolbar in (
        window._ui.toolbarKeys,
        window._ui.toolbarIdentities,
        window._ui.toolbarSubkeys,
        window._ui.toolbarPhotos,
        window._ui.toolbarTrust,
        window._ui.toolbarServers,
        window._ui.toolbarHelp,
    ):
        assert toolbar.iconSize() == QSize(32, 32)


def test_accepting_settings_reapplies_the_icon_size(qtbot, monkeypatch):
    from PySide6.QtCore import QSize

    from pbnightingale import preferences
    from pbnightingale.ui.settings_dialog import SettingsDialog

    window = MainWindow()
    qtbot.addWidget(window)

    preferences.set_toolbar_icon_size("64")
    monkeypatch.setattr(
        SettingsDialog, "exec", lambda self: SettingsDialog.DialogCode.Accepted
    )

    window._ui.actionSettings.trigger()

    assert window._ui.toolbarKeys.iconSize() == QSize(64, 64)


def test_cancelling_settings_does_not_reapply_the_icon_size(qtbot, monkeypatch):
    from PySide6.QtCore import QSize

    from pbnightingale import preferences
    from pbnightingale.ui.settings_dialog import SettingsDialog

    window = MainWindow()
    qtbot.addWidget(window)
    before = window._ui.toolbarKeys.iconSize()

    preferences.set_toolbar_icon_size("64")
    monkeypatch.setattr(
        SettingsDialog, "exec", lambda self: SettingsDialog.DialogCode.Rejected
    )

    window._ui.actionSettings.trigger()

    assert window._ui.toolbarKeys.iconSize() == before
    assert before != QSize(64, 64)


def test_on_settings_opens_settings_dialog(qtbot, monkeypatch):
    from pbnightingale.ui.settings_dialog import SettingsDialog

    window = MainWindow()
    qtbot.addWidget(window)

    called = []
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: called.append(True))

    window._ui.actionSettings.trigger()

    assert called == [True]


def test_on_about_opens_about_dialog(qtbot, monkeypatch):
    from pbnightingale.ui.about_dialog import AboutDialog

    window = MainWindow()
    qtbot.addWidget(window)

    called = []
    monkeypatch.setattr(AboutDialog, "exec", lambda self: called.append(True))

    window._ui.actionAbout.trigger()

    assert called == [True]


def test_on_help_manual_opens_the_online_manual(qtbot, monkeypatch):
    from pbnightingale.ui import main_window as main_window_module

    window = MainWindow()
    qtbot.addWidget(window)

    monkeypatch.setattr(main_window_module.i18n, "current_language", lambda: "fr")
    opened = []
    monkeypatch.setattr(
        main_window_module.QDesktopServices, "openUrl", lambda url: opened.append(url)
    )

    window._ui.actionHelpManual.trigger()

    assert len(opened) == 1
    assert opened[0].toString() == "https://pbnightingale.readthedocs.io/fr/latest"


def test_help_manual_action_is_first_in_the_help_menu(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    help_menu = window.menuBar().actions()[-1].menu()
    actions = [a for a in help_menu.actions() if not a.isSeparator()]
    assert actions[0] is window._ui.actionHelpManual
    assert not window._ui.actionHelpManual.icon().isNull()


def test_whats_this_action_uses_the_contextual_help_icon(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    action = window._ui.actionWhatsThis
    assert not action.icon().isNull()
    assert action.isCheckable()
    assert action in window._ui.toolbarHelp.actions()


def test_whats_this_action_is_in_the_help_menu(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    help_menu = window.menuBar().actions()[-1].menu()
    assert window._ui.actionWhatsThis in help_menu.actions()
    assert window._ui.actionAbout in help_menu.actions()


def test_help_toolbar_visibility_is_toggleable_from_the_view_menu(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert (
        window._ui.toolbarHelp.toggleViewAction() in window._ui.menuToolbars.actions()
    )


def test_loads_keys_into_key_list_view_on_startup(qtbot, gnupg_home):
    generate_test_key(gnupg_home, with_subkey=True)
    window = MainWindow()
    qtbot.addWidget(window)

    tree = window._ui.keyListView._ui.treeKeys
    qtbot.waitUntil(
        lambda: (
            tree.topLevelItem(0) is not None and tree.topLevelItem(0).childCount() == 1
        )
    )

    assert tree.topLevelItem(0).text(0) == "My keys (1)"
    assert tree.topLevelItem(1).text(0) == "Other keys (0)"


def test_refresh_action_reloads_keys(qtbot, gnupg_home):
    window = MainWindow()
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window._ui.actionKeyRefresh.isEnabled())

    generate_test_key(gnupg_home)
    window._ui.actionKeyRefresh.trigger()

    tree = window._ui.keyListView._ui.treeKeys
    qtbot.waitUntil(lambda: tree.topLevelItem(0).childCount() == 1)


def test_on_key_new_opens_wizard_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.new_key_wizard import NewKeyWizard

    window = MainWindow()
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window._ui.actionKeyRefresh.isEnabled())

    opened = []
    monkeypatch.setattr(
        NewKeyWizard,
        "exec",
        lambda self: (opened.append(True), NewKeyWizard.DialogCode.Accepted)[1],
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyNew.trigger()

    assert opened == [True]
    assert refreshed == [True]


def test_on_key_new_does_not_refresh_when_wizard_cancelled(qtbot, monkeypatch):
    from pbnightingale.ui.new_key_wizard import NewKeyWizard

    window = MainWindow()
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window._ui.actionKeyRefresh.isEnabled())

    monkeypatch.setattr(
        NewKeyWizard, "exec", lambda self: NewKeyWizard.DialogCode.Rejected
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyNew.trigger()

    assert refreshed == []


def test_key_actions_disabled_without_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionKeyExport.isEnabled() is False
    assert window._ui.actionKeyBackup.isEnabled() is False
    assert window._ui.actionKeyChangePassphrase.isEnabled() is False
    assert window._ui.actionKeyDelete.isEnabled() is False
    assert window._ui.actionKeySubkeyAdd.isEnabled() is False
    assert window._ui.actionKeySubkeyRevoke.isEnabled() is False


def test_key_actions_enabled_for_personal_key_with_subkey_selected(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    assert window._ui.actionKeyExport.isEnabled() is True
    assert window._ui.actionKeyBackup.isEnabled() is True
    assert window._ui.actionKeyChangePassphrase.isEnabled() is True
    assert window._ui.actionKeyDelete.isEnabled() is True
    assert window._ui.actionKeySubkeyAdd.isEnabled() is True
    assert (
        window._ui.actionKeySubkeyRevoke.isEnabled() is False
    )  # no subkey selected yet

    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)
    assert window._ui.actionKeySubkeyRevoke.isEnabled() is True


def test_key_actions_for_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionKeyExport.isEnabled() is True
    assert window._ui.actionKeyBackup.isEnabled() is False
    assert window._ui.actionKeyChangePassphrase.isEnabled() is False
    assert window._ui.actionKeyDelete.isEnabled() is True
    assert window._ui.actionKeySubkeyAdd.isEnabled() is False
    assert window._ui.actionKeySubkeyRevoke.isEnabled() is False


def test_key_list_view_context_menus_share_the_toolbar_actions(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    ui = window._ui
    key_view = ui.keyListView

    assert key_view._key_actions == [
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
    assert key_view._uid_actions == [
        ui.actionKeyUidAdd,
        ui.actionKeyUidCopyEmail,
        ui.actionKeyUidSetPrimary,
        ui.actionKeyUidRevoke,
    ]
    assert key_view._photo_actions == [
        ui.actionKeyPhotoAdd,
        ui.actionKeyPhotoShow,
        ui.actionKeyPhotoRevoke,
    ]
    assert key_view._subkey_actions == [
        ui.actionKeySubkeyAdd,
        ui.actionKeySubkeyCopyId,
        ui.actionKeySubkeyExpire,
        ui.actionKeySubkeyRevoke,
    ]


def test_copy_view_actions_disabled_without_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionKeyCopyId.isEnabled() is False
    assert window._ui.actionKeySubkeyCopyId.isEnabled() is False
    assert window._ui.actionKeyUidCopyEmail.isEnabled() is False
    assert window._ui.actionKeyPhotoShow.isEnabled() is False


def test_copy_id_and_copy_email_are_enabled_for_a_public_only_key(qtbot, monkeypatch):
    # Read-only, so unlike the "my keys" actions (Add/Revoke/…), these apply
    # to any key, not just one whose secret part is held.
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)
    assert window._ui.actionKeyCopyId.isEnabled() is True
    key_view._ui.lstUids.item(0).setSelected(True)
    assert window._ui.actionKeyUidCopyEmail.isEnabled() is True


def test_on_key_copy_id_copies_the_fingerprint(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    window._ui.actionKeyCopyId.trigger()

    assert QApplication.clipboard().text() == _PERSONAL_KEY.fingerprint


def test_on_key_subkey_copy_id_copies_the_fingerprint(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)

    window._ui.actionKeySubkeyCopyId.trigger()

    assert QApplication.clipboard().text() == _SUBKEY.fingerprint


def test_on_key_uid_copy_email_copies_the_address(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    window._ui.actionKeyUidCopyEmail.trigger()

    assert QApplication.clipboard().text() == "alice@example.com"


def test_on_key_photo_show_opens_the_viewer(qtbot, monkeypatch, tmp_path):
    from pbnightingale.ui.photo_viewer_dialog import PhotoViewerDialog

    key = _personal_key_with_photo(tmp_path)
    window = _make_window_with_keys(qtbot, monkeypatch, [key])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstPhotos.item(0).setSelected(True)

    opened = []
    monkeypatch.setattr(
        PhotoViewerDialog, "exec", lambda self: opened.append(self) or 0
    )

    window._ui.actionKeyPhotoShow.trigger()

    assert len(opened) == 1


def test_key_revoke_disabled_without_any_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionKeyRevoke.isEnabled() is False


def test_key_revoke_enabled_for_personal_key_selected(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    assert window._ui.actionKeyRevoke.isEnabled() is True


def test_key_revoke_disabled_for_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionKeyRevoke.isEnabled() is False


def test_on_key_revoke_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.revoke_key_dialog import RevokeKeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        RevokeKeyDialog, "exec", lambda self: RevokeKeyDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyRevoke.trigger()

    assert refreshed == [True]


def test_expiration_actions_enabled_for_personal_key_with_subkey_selected(
    qtbot, monkeypatch
):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    assert window._ui.actionKeyExpire.isEnabled() is True
    assert window._ui.actionKeySubkeyExpire.isEnabled() is False  # no subkey yet

    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)
    assert window._ui.actionKeySubkeyExpire.isEnabled() is True


def test_expiration_actions_for_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionKeyExpire.isEnabled() is False
    assert window._ui.actionKeySubkeyExpire.isEnabled() is False


def test_on_key_expire_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.set_expiration_dialog import SetExpirationDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        SetExpirationDialog,
        "exec",
        lambda self: SetExpirationDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyExpire.trigger()

    assert refreshed == [True]


def test_on_key_subkey_expire_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.set_expiration_dialog import SetExpirationDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)

    monkeypatch.setattr(
        SetExpirationDialog,
        "exec",
        lambda self: SetExpirationDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeySubkeyExpire.trigger()

    assert refreshed == [True]


def test_uid_actions_enabled_for_personal_key_with_uid_selected(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    assert window._ui.actionKeyUidAdd.isEnabled() is True
    assert window._ui.actionKeyUidSetPrimary.isEnabled() is False  # no uid selected yet
    assert window._ui.actionKeyUidRevoke.isEnabled() is False

    key_view._ui.lstUids.item(0).setSelected(True)
    assert window._ui.actionKeyUidSetPrimary.isEnabled() is True
    assert window._ui.actionKeyUidRevoke.isEnabled() is True  # two valid uids


def test_uid_set_primary_disabled_when_the_selected_uid_is_already_primary(
    qtbot, monkeypatch
):
    import dataclasses

    primary_uid, other_uid = _PERSONAL_KEY.uids
    key = Key(
        **{
            **_PERSONAL_KEY.__dict__,
            "uids": [dataclasses.replace(primary_uid, primary=True), other_uid],
        }
    )
    window = _make_window_with_keys(qtbot, monkeypatch, [key])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    assert key_view.selected_uid().primary is True
    assert window._ui.actionKeyUidSetPrimary.isEnabled() is False


def test_uid_revoke_disabled_when_it_is_the_last_valid_uid(qtbot, monkeypatch):
    single_uid_key = Key(**{**_PERSONAL_KEY.__dict__, "uids": [_PERSONAL_KEY.uids[0]]})
    window = _make_window_with_keys(qtbot, monkeypatch, [single_uid_key])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    assert window._ui.actionKeyUidSetPrimary.isEnabled() is True
    assert window._ui.actionKeyUidRevoke.isEnabled() is False


def test_uid_actions_for_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    assert window._ui.actionKeyUidAdd.isEnabled() is False
    assert window._ui.actionKeyUidSetPrimary.isEnabled() is False
    assert window._ui.actionKeyUidRevoke.isEnabled() is False


def _personal_key_with_photo(tmp_path) -> Key:
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    return Key(**{**_PERSONAL_KEY.__dict__, "photos": [photo]})


def test_photo_actions_enabled_for_personal_key_with_photo_selected(
    qtbot, monkeypatch, tmp_path
):
    key = _personal_key_with_photo(tmp_path)
    window = _make_window_with_keys(qtbot, monkeypatch, [key])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    assert window._ui.actionKeyPhotoAdd.isEnabled() is True
    assert window._ui.actionKeyPhotoRevoke.isEnabled() is False  # no photo selected yet

    key_view._ui.lstPhotos.item(0).setSelected(True)
    assert window._ui.actionKeyPhotoRevoke.isEnabled() is True


def test_photo_actions_for_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionKeyPhotoAdd.isEnabled() is False
    assert window._ui.actionKeyPhotoRevoke.isEnabled() is False


def test_on_key_photo_add_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.add_photo_dialog import AddPhotoDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        AddPhotoDialog, "exec", lambda self: AddPhotoDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyPhotoAdd.trigger()

    assert refreshed == [True]


def test_on_key_photo_revoke_opens_dialog_and_refreshes_on_accept(
    qtbot, monkeypatch, tmp_path
):
    from pbnightingale.ui.revoke_photo_dialog import RevokePhotoDialog

    key = _personal_key_with_photo(tmp_path)
    window = _make_window_with_keys(qtbot, monkeypatch, [key])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstPhotos.item(0).setSelected(True)

    monkeypatch.setattr(
        RevokePhotoDialog,
        "exec",
        lambda self: RevokePhotoDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyPhotoRevoke.trigger()

    assert refreshed == [True]


def test_on_key_uid_add_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.add_uid_dialog import AddUidDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        AddUidDialog, "exec", lambda self: AddUidDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyUidAdd.trigger()

    assert refreshed == [True]


def test_on_key_uid_set_primary_opens_dialog_and_refreshes_on_accept(
    qtbot, monkeypatch
):
    from pbnightingale.ui.set_primary_uid_dialog import SetPrimaryUidDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    monkeypatch.setattr(
        SetPrimaryUidDialog,
        "exec",
        lambda self: SetPrimaryUidDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyUidSetPrimary.trigger()

    assert refreshed == [True]


def test_on_key_uid_revoke_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.revoke_uid_dialog import RevokeUidDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    monkeypatch.setattr(
        RevokeUidDialog, "exec", lambda self: RevokeUidDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyUidRevoke.trigger()

    assert refreshed == [True]


def test_uid_add_keeps_the_key_and_uid_selected_after_refresh(qtbot, monkeypatch):
    from pbnightingale.ui.add_uid_dialog import AddUidDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.lstUids.item(0).setSelected(True)

    monkeypatch.setattr(
        AddUidDialog, "exec", lambda self: AddUidDialog.DialogCode.Accepted
    )

    window._ui.actionKeyUidAdd.trigger()

    qtbot.waitUntil(lambda: key_view.selected_uid() is not None)
    assert key_view.selected_key().fingerprint == _PERSONAL_KEY.fingerprint
    assert key_view.selected_uid() == _PERSONAL_KEY.uids[0]


def test_on_key_subkey_add_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.add_subkey_dialog import AddSubkeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        AddSubkeyDialog, "exec", lambda self: AddSubkeyDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeySubkeyAdd.trigger()

    assert refreshed == [True]


def test_on_key_subkey_revoke_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.revoke_subkey_dialog import RevokeSubkeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)

    monkeypatch.setattr(
        RevokeSubkeyDialog, "exec", lambda self: RevokeSubkeyDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeySubkeyRevoke.trigger()

    assert refreshed == [True]


def test_on_key_change_passphrase_opens_dialog_and_refreshes_on_accept(
    qtbot, monkeypatch
):
    from pbnightingale.ui.change_passphrase_dialog import ChangePassphraseDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        ChangePassphraseDialog,
        "exec",
        lambda self: ChangePassphraseDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyChangePassphrase.trigger()

    assert refreshed == [True]


def test_on_key_change_passphrase_does_nothing_without_a_selection(qtbot, monkeypatch):
    from pbnightingale.ui.change_passphrase_dialog import ChangePassphraseDialog

    window = MainWindow()
    qtbot.addWidget(window)
    called = []
    monkeypatch.setattr(
        ChangePassphraseDialog, "exec", lambda self: called.append(True)
    )

    window._ui.actionKeyChangePassphrase.trigger()

    assert called == []


def test_subkey_add_keeps_the_key_selected_after_refresh(qtbot, monkeypatch):
    from pbnightingale.ui.add_subkey_dialog import AddSubkeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    monkeypatch.setattr(
        AddSubkeyDialog, "exec", lambda self: AddSubkeyDialog.DialogCode.Accepted
    )

    window._ui.actionKeySubkeyAdd.trigger()

    qtbot.waitUntil(lambda: key_view.selected_key() is not None)
    assert key_view.selected_key().fingerprint == _PERSONAL_KEY.fingerprint


def test_revoke_keeps_the_key_and_subkey_selected_after_refresh(qtbot, monkeypatch):
    from pbnightingale.ui.revoke_subkey_dialog import RevokeSubkeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.treeSubkeys.topLevelItem(0).setSelected(True)

    monkeypatch.setattr(
        RevokeSubkeyDialog,
        "exec",
        lambda self: RevokeSubkeyDialog.DialogCode.Accepted,
    )

    window._ui.actionKeySubkeyRevoke.trigger()

    qtbot.waitUntil(lambda: key_view.selected_subkey() is not None)
    assert key_view.selected_key().fingerprint == _PERSONAL_KEY.fingerprint
    assert key_view.selected_subkey().keyid == _SUBKEY.keyid


def test_manual_refresh_keeps_the_selected_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    window._ui.actionKeyRefresh.trigger()

    qtbot.waitUntil(lambda: key_view.selected_key() is not None)
    assert key_view.selected_key().fingerprint == _PERSONAL_KEY.fingerprint


def test_on_key_export_writes_file_and_shows_status(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    out_path = tmp_path / "exported.asc"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "")),
    )

    from pbnightingale.core import gpg_backend

    class _FakeBackend:
        def export_public_key(self, fingerprint):
            return "ARMORED-DATA"

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    window._ui.actionKeyExport.trigger()

    assert out_path.read_text(encoding="utf-8") == "ARMORED-DATA"
    assert window.statusBar().currentMessage() == f"Key exported to {out_path}"


def test_on_key_export_cancelled_dialog_does_nothing(qtbot, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    window.statusBar().clearMessage()

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )

    window._ui.actionKeyExport.trigger()

    assert window.statusBar().currentMessage() == ""


def test_on_key_export_backend_failure_shows_status(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    out_path = tmp_path / "exported.asc"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "")),
    )

    from pbnightingale.core import gpg_backend

    class _FailingBackend:
        def export_public_key(self, fingerprint):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)

    window._ui.actionKeyExport.trigger()

    assert window.statusBar().currentMessage() == "Could not export key: boom"


def test_on_key_backup_opens_dialog_for_the_selected_key(qtbot, monkeypatch):
    from pbnightingale.ui.backup_private_key_dialog import BackupPrivateKeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    opened_with = []
    original_init = BackupPrivateKeyDialog.__init__

    def _fake_init(self, key, parent=None):
        opened_with.append(key)
        original_init(self, key, parent)

    monkeypatch.setattr(BackupPrivateKeyDialog, "__init__", _fake_init)
    monkeypatch.setattr(BackupPrivateKeyDialog, "exec", lambda self: None)

    window._ui.actionKeyBackup.trigger()

    assert opened_with == [_PERSONAL_KEY]


def test_on_key_backup_does_nothing_without_a_selection(qtbot, monkeypatch):
    from pbnightingale.ui.backup_private_key_dialog import BackupPrivateKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)
    called = []
    monkeypatch.setattr(
        BackupPrivateKeyDialog, "exec", lambda self: called.append(True)
    )

    window._ui.actionKeyBackup.trigger()

    assert called == []


def test_on_key_delete_opens_dialog_for_the_selected_key(qtbot, monkeypatch):
    from pbnightingale.ui.delete_key_dialog import DeleteKeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    opened_with = []
    original_init = DeleteKeyDialog.__init__

    def _fake_init(self, key, parent=None):
        opened_with.append(key)
        original_init(self, key, parent)

    monkeypatch.setattr(DeleteKeyDialog, "__init__", _fake_init)
    monkeypatch.setattr(
        DeleteKeyDialog, "exec", lambda self: DeleteKeyDialog.DialogCode.Rejected
    )

    window._ui.actionKeyDelete.trigger()

    assert opened_with == [_PERSONAL_KEY]


def test_on_key_delete_does_nothing_without_a_selection(qtbot, monkeypatch):
    from pbnightingale.ui.delete_key_dialog import DeleteKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)
    called = []
    monkeypatch.setattr(DeleteKeyDialog, "exec", lambda self: called.append(True))

    window._ui.actionKeyDelete.trigger()

    assert called == []


def test_on_key_delete_refreshes_keys_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.delete_key_dialog import DeleteKeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    monkeypatch.setattr(
        DeleteKeyDialog, "exec", lambda self: DeleteKeyDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeyDelete.trigger()

    assert refreshed == [True]


def test_key_load_failure_shows_error_in_status_bar(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    def _boom():
        raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _boom)
    window = MainWindow()
    qtbot.addWidget(window)

    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage() == "Could not load keys: boom"
    )


def test_trust_refresh_enabled_without_any_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionTrustRefresh.isEnabled() is True


def test_key_import_enabled_without_any_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionKeyImport.isEnabled() is True


def test_sign_and_owner_trust_actions_disabled_without_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionKeySign.isEnabled() is False
    assert window._ui.actionKeySetOwnerTrust.isEnabled() is False


def test_sign_and_owner_trust_actions_enabled_for_a_public_only_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    key_view = window._ui.keyListView

    key_view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionKeySign.isEnabled() is True
    assert window._ui.actionKeySetOwnerTrust.isEnabled() is True


def test_on_key_sign_opens_dialog_and_refreshes_on_accept(qtbot, monkeypatch):
    from pbnightingale.ui.sign_key_dialog import SignKeyDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    monkeypatch.setattr(
        SignKeyDialog, "exec", lambda self: SignKeyDialog.DialogCode.Accepted
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeySign.trigger()

    assert refreshed == [True]


def test_on_key_set_owner_trust_opens_dialog_and_refreshes_on_accept(
    qtbot, monkeypatch
):
    from pbnightingale.ui.set_owner_trust_dialog import SetOwnerTrustDialog

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    monkeypatch.setattr(
        SetOwnerTrustDialog,
        "exec",
        lambda self: SetOwnerTrustDialog.DialogCode.Accepted,
    )
    refreshed = []
    monkeypatch.setattr(window, "refresh_keys", lambda: refreshed.append(True))

    window._ui.actionKeySetOwnerTrust.trigger()

    assert refreshed == [True]


def test_on_trust_refresh_calls_backend_and_reloads_keys(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    calls = []

    class _FakeBackend:
        def refresh_trust(self):
            calls.append(True)

        def list_keys(self):
            return [_PUBLIC_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    window._ui.actionTrustRefresh.trigger()

    qtbot.waitUntil(lambda: calls == [True])
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "1 key(s) loaded")
    assert window._ui.actionTrustRefresh.isEnabled() is True


def test_on_trust_refresh_failure_shows_status_and_reenables(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])

    class _FailingBackend:
        def refresh_trust(self):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)

    window._ui.actionTrustRefresh.trigger()

    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage() == "Could not refresh trust: boom"
    )
    assert window._ui.actionTrustRefresh.isEnabled() is True


def test_on_key_import_reports_a_newly_imported_key_and_selects_it(qtbot, monkeypatch):
    from pbnightingale.core.gpg_backend import ImportedKey
    from pbnightingale.ui.import_key_dialog import ImportKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)

    def _fake_exec(self):
        self.imported_keys = [ImportedKey(key=_PUBLIC_KEY, is_new=True)]
        return ImportKeyDialog.DialogCode.Accepted

    monkeypatch.setattr(ImportKeyDialog, "exec", _fake_exec)
    calls = []
    monkeypatch.setattr(window, "refresh_keys", lambda **kwargs: calls.append(kwargs))

    window._ui.actionKeyImport.trigger()

    assert calls == [
        {
            "status_message": "Key imported: Bob Example <bob@example.com> "
            "(5555666677778888)",
            "select_fingerprint": _PUBLIC_KEY.fingerprint,
        }
    ]


def test_on_key_import_reports_an_already_present_key(qtbot, monkeypatch):
    from pbnightingale.core.gpg_backend import ImportedKey
    from pbnightingale.ui.import_key_dialog import ImportKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)

    def _fake_exec(self):
        self.imported_keys = [ImportedKey(key=_PUBLIC_KEY, is_new=False)]
        return ImportKeyDialog.DialogCode.Accepted

    monkeypatch.setattr(ImportKeyDialog, "exec", _fake_exec)
    calls = []
    monkeypatch.setattr(window, "refresh_keys", lambda **kwargs: calls.append(kwargs))

    window._ui.actionKeyImport.trigger()

    assert calls == [
        {
            "status_message": "Key already in keyring: Bob Example "
            "<bob@example.com> (5555666677778888)",
            "select_fingerprint": _PUBLIC_KEY.fingerprint,
        }
    ]


def test_on_key_import_with_several_keys_reports_counts(qtbot, monkeypatch):
    from pbnightingale.core.gpg_backend import ImportedKey
    from pbnightingale.ui.import_key_dialog import ImportKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)

    def _fake_exec(self):
        self.imported_keys = [
            ImportedKey(key=_PUBLIC_KEY, is_new=True),
            ImportedKey(key=_PERSONAL_KEY, is_new=False),
        ]
        return ImportKeyDialog.DialogCode.Accepted

    monkeypatch.setattr(ImportKeyDialog, "exec", _fake_exec)
    calls = []
    monkeypatch.setattr(window, "refresh_keys", lambda **kwargs: calls.append(kwargs))

    window._ui.actionKeyImport.trigger()

    assert calls == [
        {
            "status_message": "1 new key(s) imported, 1 already present",
            "select_fingerprint": _PUBLIC_KEY.fingerprint,
        }
    ]


def test_refresh_keys_with_status_message_and_select_fingerprint_overrides_defaults(
    qtbot, monkeypatch
):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY, _PUBLIC_KEY])

    window.refresh_keys(
        status_message="One-off message",
        select_fingerprint=_PUBLIC_KEY.fingerprint,
    )

    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "One-off message")
    key = window._ui.keyListView.selected_key()
    assert key is not None
    assert key.fingerprint == _PUBLIC_KEY.fingerprint


def test_refresh_keys_status_message_does_not_leak_into_next_refresh(
    qtbot, monkeypatch
):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])

    window.refresh_keys(status_message="One-off message")
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "One-off message")

    window.refresh_keys()

    qtbot.waitUntil(lambda: "loaded" in window.statusBar().currentMessage())
    assert window.statusBar().currentMessage() == "1 key(s) loaded"


def test_server_search_and_refresh_enabled_without_any_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionServerSearch.isEnabled() is True
    assert window._ui.actionServerRefresh.isEnabled() is True


def test_server_publish_disabled_without_selection(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._ui.actionServerPublish.isEnabled() is False


def test_server_publish_enabled_for_a_selected_key(qtbot, monkeypatch):
    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])

    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    assert window._ui.actionServerPublish.isEnabled() is True


def test_on_server_search_reports_the_imported_key_and_selects_it(qtbot, monkeypatch):
    from pbnightingale.core.gpg_backend import ImportedKey
    from pbnightingale.ui.search_key_dialog import SearchKeyDialog

    window = MainWindow()
    qtbot.addWidget(window)

    def _fake_exec(self):
        self.imported_keys = [ImportedKey(key=_PUBLIC_KEY, is_new=True)]
        return SearchKeyDialog.DialogCode.Accepted

    monkeypatch.setattr(SearchKeyDialog, "exec", _fake_exec)
    calls = []
    monkeypatch.setattr(window, "refresh_keys", lambda **kwargs: calls.append(kwargs))

    window._ui.actionServerSearch.trigger()

    assert calls == [
        {
            "status_message": "Key imported: Bob Example <bob@example.com> "
            "(5555666677778888)",
            "select_fingerprint": _PUBLIC_KEY.fingerprint,
        }
    ]


def test_on_server_publish_asks_for_confirmation_and_calls_backend(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)
    calls = []

    class _FakeBackend:
        def publish_to_keyserver(self, fingerprint):
            calls.append(fingerprint)

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    window._ui.actionServerPublish.trigger()

    qtbot.waitUntil(lambda: calls == [_PUBLIC_KEY.fingerprint])
    qtbot.waitUntil(lambda: "published" in window.statusBar().currentMessage().lower())
    assert window._ui.actionServerPublish.isEnabled() is True


def test_on_server_publish_does_nothing_without_confirmation(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)
    calls = []

    class _FakeBackend:
        def publish_to_keyserver(self, fingerprint):
            calls.append(fingerprint)

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )

    window._ui.actionServerPublish.trigger()

    assert calls == []


def test_on_server_publish_failure_shows_status_and_reenables(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    class _FailingBackend:
        def publish_to_keyserver(self, fingerprint):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    window._ui.actionServerPublish.trigger()

    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage() == "Could not publish key: boom"
    )
    assert window._ui.actionServerPublish.isEnabled() is True


def _accept_refresh_dialogs(monkeypatch):
    """Auto-accept the confirm-scope and report dialogs `_on_server_refresh()`
    opens, so a test driving it through `actionServerRefresh.trigger()`
    doesn't hang on a real modal event loop."""
    from pbnightingale.ui.refresh_keys_dialog import RefreshKeysDialog
    from pbnightingale.ui.refresh_keys_report_dialog import RefreshKeysReportDialog

    monkeypatch.setattr(
        RefreshKeysDialog, "exec", lambda self: RefreshKeysDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(
        RefreshKeysReportDialog,
        "exec",
        lambda self: RefreshKeysReportDialog.DialogCode.Accepted,
    )


def test_on_server_refresh_calls_backend_and_reloads_keys(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    _accept_refresh_dialogs(monkeypatch)
    calls = []

    class _FakeBackend:
        def refresh_from_keyserver(self, fingerprints=None):
            calls.append(fingerprints)
            return []

        def list_keys(self):
            return [_PUBLIC_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    window._ui.actionServerRefresh.trigger()

    # No key selected — the confirm dialog defaults to "every key".
    qtbot.waitUntil(lambda: calls == [None])
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "1 key(s) loaded")
    assert window._ui.actionServerRefresh.isEnabled() is True


def test_on_server_refresh_with_a_selection_refreshes_only_that_key(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    window._ui.keyListView._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)
    _accept_refresh_dialogs(monkeypatch)
    calls = []

    class _FakeBackend:
        def refresh_from_keyserver(self, fingerprints=None):
            calls.append(fingerprints)
            return []

        def list_keys(self):
            return [_PUBLIC_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    window._ui.actionServerRefresh.trigger()

    qtbot.waitUntil(lambda: calls == [[_PUBLIC_KEY.fingerprint]])


def test_on_server_refresh_failure_shows_status_and_reenables(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PUBLIC_KEY])
    _accept_refresh_dialogs(monkeypatch)
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: warnings.append(a[1:])),
    )

    class _FailingBackend:
        def refresh_from_keyserver(self, fingerprints=None):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)

    window._ui.actionServerRefresh.trigger()

    qtbot.waitUntil(lambda: len(warnings) == 1)
    assert "Could not refresh keys: boom" in warnings[0][1]
    assert window._ui.actionServerRefresh.isEnabled() is True


_SIGNATURES_TAB_INDEX = 1


def test_signatures_requested_calls_backend_and_populates_tab(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY, _PUBLIC_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    calls = []

    class _FakeBackend:
        def list_key_signatures(self, fingerprint):
            calls.append(fingerprint)
            return [
                KeySignature(keyid=_PUBLIC_KEY.keyid, fingerprint=None, key=_PUBLIC_KEY)
            ]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    key_view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    qtbot.waitUntil(lambda: calls == [_PERSONAL_KEY.fingerprint])
    sig_tree = key_view._ui.treeSignatures
    qtbot.waitUntil(lambda: sig_tree.topLevelItemCount() == 1)
    assert sig_tree.topLevelItem(0).text(0) == "Bob Example"


def test_signatures_load_failure_shows_status_and_clears_tab(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    class _FailingBackend:
        def list_key_signatures(self, fingerprint):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)

    key_view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage() == "Could not load signatures: boom"
    )
    assert key_view._ui.treeSignatures.topLevelItemCount() == 0


def _accept_download_signatures_report_dialog(monkeypatch):
    from pbnightingale.ui.download_signatures_report_dialog import (
        DownloadSignaturesReportDialog,
    )

    monkeypatch.setattr(
        DownloadSignaturesReportDialog,
        "exec",
        lambda self: DownloadSignaturesReportDialog.DialogCode.Accepted,
    )


def test_on_download_unknown_signatures_calls_backend_and_reloads_keys(
    qtbot, monkeypatch
):
    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY, _PUBLIC_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    key_view.set_key_signatures(
        _PERSONAL_KEY.fingerprint,
        [KeySignature(keyid="1234567890ABCDEF", fingerprint=None, key=None)],
    )
    _accept_download_signatures_report_dialog(monkeypatch)
    calls = []

    class _FakeBackend:
        def download_unknown_signatures(self, identifiers):
            calls.append(identifiers)
            return [DownloadedSignature("1234567890ABCDEF", _PUBLIC_KEY)]

        def list_keys(self):
            return [_PERSONAL_KEY, _PUBLIC_KEY]

        def list_key_signatures(self, fingerprint):
            # Reselecting the key after refresh_keys() re-triggers the
            # Signatures tab's own fetch, still on the same backend.
            return [
                KeySignature(keyid=_PUBLIC_KEY.keyid, fingerprint=None, key=_PUBLIC_KEY)
            ]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    key_view._ui.btnDownloadUnknownSignatures.click()

    qtbot.waitUntil(lambda: calls == [["1234567890ABCDEF"]])
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "2 key(s) loaded")


def test_on_download_unknown_signatures_failure_shows_warning(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pbnightingale.core import gpg_backend

    window = _make_window_with_keys(qtbot, monkeypatch, [_PERSONAL_KEY])
    key_view = window._ui.keyListView
    key_view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    key_view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    key_view.set_key_signatures(
        _PERSONAL_KEY.fingerprint,
        [KeySignature(keyid="1234567890ABCDEF", fingerprint=None, key=None)],
    )
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: warnings.append(a[1:])),
    )

    class _FailingBackend:
        def download_unknown_signatures(self, identifiers):
            raise gpg_backend.GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)

    key_view._ui.btnDownloadUnknownSignatures.click()

    qtbot.waitUntil(lambda: len(warnings) == 1)
    assert "Could not download keys: boom" in warnings[0][1]


def test_key_list_column_widths_persist_across_instances(qtbot, monkeypatch):
    from pbnightingale.core import gpg_backend

    class _FakeBackend:
        def list_keys(self):
            return [_PERSONAL_KEY, _PUBLIC_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)

    first = MainWindow()
    qtbot.addWidget(first)
    first.show()
    first_tree = first._ui.keyListView._ui.treeKeys
    qtbot.waitUntil(lambda: first_tree.topLevelItem(0) is not None)
    qtbot.waitUntil(lambda: first_tree.topLevelItem(0).child(0) is not None)
    first_tree.header().resizeSection(0, 321)
    first.close()

    second = MainWindow()
    qtbot.addWidget(second)
    second.show()
    second_tree = second._ui.keyListView._ui.treeKeys
    qtbot.waitUntil(lambda: second_tree.topLevelItem(0) is not None)
    qtbot.waitUntil(lambda: second_tree.topLevelItem(0).child(0) is not None)

    # The width must survive set_keys() re-populating the tree after the
    # restore, not just the restore itself — see KeyListView.
    # restore_column_widths().
    assert second_tree.header().sectionSize(0) == 321
