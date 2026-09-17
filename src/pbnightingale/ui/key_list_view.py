"""Key list & detail view — the main window's central widget."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from email.utils import parseaddr

from PySide6.QtCore import QByteArray, QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from pbnightingale.core import passphrase_cache
from pbnightingale.core.gpg_backend import Key, KeySignature, PhotoUid, Subkey, Uid
from pbnightingale.resources import path as _resource
from pbnightingale.ui.key_list_view_ui import Ui_KeyListView

_KEY_ROLE = Qt.ItemDataRole.UserRole
_SUBKEY_ROLE = Qt.ItemDataRole.UserRole + 1
_UID_ROLE = Qt.ItemDataRole.UserRole + 2
_PHOTO_ROLE = Qt.ItemDataRole.UserRole + 3
_SIGNATURE_ROLE = Qt.ItemDataRole.UserRole + 4

# Index of the "Signatures" tab within Ui_KeyListView.tabDetail — see
# key_list_view_ui.py's _setup_detail_stack().
_SIGNATURES_TAB_INDEX = 1

# Between "Name" and "Email" — see key_list_view_ui.py's header labels.
_LOCK_COLUMN = 1

# How often the key list re-checks the passphrase cache on its own, so a
# key's lock icon still flips back to "locked" after its cached passphrase
# expires even if nothing else (a reload, a dialog) happens to redraw the
# row in the meantime.
_LOCK_ICON_REFRESH_MS = 30_000


def _parse_uid(uid: str) -> tuple[str, str]:
    """Split a GPG UID string ("Name (Comment) <email>") into (name, email)."""
    name, email = parseaddr(uid)
    return name or uid, email


def _display_name_email(key: Key) -> tuple[str, str]:
    """Return (name, email) for *key*'s primary UID (or its first, or "")."""
    display_uid = next((u for u in key.uids if u.primary), None) or (
        key.uids[0] if key.uids else None
    )
    return _parse_uid(display_uid.value) if display_uid else ("", "")


# Sortable columns of the main key list — see key_list_view_ui.py's header
# labels. Column 1 (the lock icon) has no header text and isn't sortable.
_NAME_COLUMN = 0
_EMAIL_COLUMN = 2
_KEYID_COLUMN = 3
_EXPIRES_COLUMN = 4


def _sort_value(column: int, key: Key):
    """Return *key*'s sort key for *column*, one of the ``_*_COLUMN`` constants."""
    if column == _NAME_COLUMN:
        return _display_name_email(key)[0].casefold()
    if column == _EMAIL_COLUMN:
        return _display_name_email(key)[1].casefold()
    if column == _KEYID_COLUMN:
        return key.keyid
    return 0


def _sorted_keys(column: int, order: Qt.SortOrder, keys: list[Key]) -> list[Key]:
    """Sort *keys* by *column*, in *order* — the ordering within one key-list group.

    A key with no expiration date always sorts last in the "Expires"
    column, in either direction: "never" isn't a point on the timeline, so
    reversing the sort shouldn't move it to the front.
    """
    reverse = order == Qt.SortOrder.DescendingOrder
    if column == _EXPIRES_COLUMN:
        dated = sorted(
            (k for k in keys if k.expires is not None),
            key=lambda k: k.expires,
            reverse=reverse,
        )
        return dated + [k for k in keys if k.expires is None]
    return sorted(keys, key=lambda k: _sort_value(column, k), reverse=reverse)


_PRIMARY_UID_MARK = "✓ "  # ✓ — see CODING.md, "Editable user IDs"


def _format_uid_label(uid: Uid) -> str:
    """Return *uid*'s display text: revoked/primary markers plus its value."""
    label = _("{uid} (revoked)").format(uid=uid.value) if uid.revoked else uid.value
    return _PRIMARY_UID_MARK + label if uid.primary else label


def _photo_icon(photo: PhotoUid) -> QIcon:
    """Decode *photo*'s raw JPEG bytes into a displayable icon."""
    image = QImage.fromData(photo.image)
    return QIcon(QPixmap.fromImage(image))


def _signature_item(signature: KeySignature) -> QTreeWidgetItem:
    """Build one Signatures-tab row for *signature*.

    A known signer is shown the same way as the main key list on the
    left (name/email/key ID/expiry); an unknown one only carries its
    identifier, per ``KeySignature``'s docstring.
    """
    if signature.key is not None:
        key = signature.key
        display_uid = next((u for u in key.uids if u.primary), None) or (
            key.uids[0] if key.uids else None
        )
        name, email = _parse_uid(display_uid.value) if display_uid else ("", "")
        item = QTreeWidgetItem([name, email, key.keyid, _format_expires(key.expires)])
    else:
        identifier = signature.fingerprint or signature.keyid
        item = QTreeWidgetItem([_("Unknown locally"), "", identifier, ""])
    item.setData(0, _SIGNATURE_ROLE, signature)
    return item


def _lock_icon(passphrase_known: bool) -> QIcon:
    """Return the open or closed padlock icon for *passphrase_known*."""
    name = "unlocked-black.svg" if passphrase_known else "locked-black.svg"
    return QIcon(_resource(name))


def _current_item_pos(widget: QListWidget | QTreeWidget) -> QPoint:
    """Return where to pop up a context menu triggered by the ``C`` key.

    Unlike a mouse click, ``C`` carries no position of its own: this is
    the center of the current item, or the widget's own center if there
    isn't one.
    """
    item = widget.currentItem()
    if item is not None:
        rect = widget.visualItemRect(item)
        if rect.isValid():
            return rect.center()
    return widget.rect().center()


def _format_fingerprint(fingerprint: str) -> str:
    """Group a fingerprint into 4-char blocks, the conventional GPG display."""
    return " ".join(fingerprint[i : i + 4] for i in range(0, len(fingerprint), 4))


# RFC 4880 public-key algorithm IDs, as reported (as strings) by gpg's
# machine-readable `--with-colons` output. Names are universal abbreviations,
# not translated (same as every GPG-aware tool, in any language).
_ALGO_NAMES = {
    "1": "RSA",
    "2": "RSA",
    "3": "RSA",
    "16": "ElGamal",
    "17": "DSA",
    "18": "ECDH",
    "19": "ECDSA",
    "22": "EdDSA",
}


def _format_algo(algo: str) -> str:
    """Return *algo* (a gpg RFC 4880 algorithm ID) as a display name.

    Renders as ``"Name (id)"`` for a known one (see ``_ALGO_NAMES``), or
    just the raw ID otherwise.
    """
    name = _ALGO_NAMES.get(algo)
    return f"{name} ({algo})" if name else algo


def _format_date(timestamp: int) -> str:
    """Format a gpg Unix *timestamp* as ``YYYY-MM-DD``, or "Unknown" for 0."""
    if not timestamp:
        return _("Unknown")
    # Naive/local on purpose: this is a display-only conversion of a GPG
    # timestamp for the user's own wall clock, never stored or compared.
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")  # noqa: DTZ006


def _format_expires(timestamp: int | None) -> str:
    """Format an expiration *timestamp*, or "Never" for ``None``."""
    if timestamp is None:
        return _("Never")
    return _format_date(timestamp)


def _format_capabilities(entry: Key | Subkey) -> str:
    """Return *entry*'s usable capabilities as a comma-separated list."""
    labels = []
    if entry.can_certify:
        labels.append(_("Certify"))
    if entry.can_sign:
        labels.append(_("Sign"))
    if entry.can_encrypt:
        labels.append(_("Encrypt"))
    if entry.can_authenticate:
        labels.append(_("Authenticate"))
    return ", ".join(labels) if labels else _("None")


def _trust_label(code: str) -> str:
    """Translate a gpg trust/validity one-letter *code* to a display label."""
    labels = {
        "u": _("Ultimate"),
        "f": _("Full"),
        "m": _("Marginal"),
        "n": _("None"),
        "q": _("Undefined"),
        "-": _("Undefined"),
        "e": _("Expired"),
        "r": _("Revoked"),
        "d": _("Disabled"),
        "i": _("Invalid"),
        "o": _("Unknown"),
    }
    return labels.get(code, code)


class KeyListView(QWidget):
    """Lists keyring keys (grouped by ``has_secret``) with a detail panel for the current selection."""

    selectionChanged = Signal()
    signaturesRequested = Signal(str)
    downloadUnknownSignaturesRequested = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the (initially empty) list and detail panel.

        Wires up every internal signal: selection, context menus, section
        exclusivity, and the lock-icon refresh timer.
        """
        super().__init__(parent)
        self._ui = Ui_KeyListView()
        self._ui.setupUi(self)
        self._ui.treeKeys.itemSelectionChanged.connect(self._on_selection_changed)
        self._ui.treeSubkeys.itemSelectionChanged.connect(self.selectionChanged)
        self._ui.lstUids.itemSelectionChanged.connect(self.selectionChanged)
        self._ui.lstPhotos.itemSelectionChanged.connect(self.selectionChanged)
        self._ui.btnCopyFingerprint.clicked.connect(self._on_copy_fingerprint)
        self._ui.treeKeys.itemDoubleClicked.connect(self._on_key_item_double_clicked)
        self._ui.treeKeys.header().sectionClicked.connect(
            self._on_header_section_clicked
        )
        self._ui.lstPhotos.itemActivated.connect(self._on_photo_activated)
        self._ui.tabDetail.currentChanged.connect(self._on_detail_tab_changed)
        self._ui.btnDownloadUnknownSignatures.clicked.connect(
            self._on_download_unknown_signatures_clicked
        )
        self._my_keys: list[Key] = []
        self._keys: list[Key] = []
        self._current_signatures: list[KeySignature] = []
        # Sorted by name, ascending, until a header click or a restored
        # previous session's choice (restore_sort_state()) says otherwise —
        # there's always an active sort, never raw keyring insertion order.
        self._sort_column: int = _NAME_COLUMN
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._ui.treeKeys.header().setSortIndicator(self._sort_column, self._sort_order)
        # Set once column widths are restored from a previous session (see
        # restore_column_widths()) — set_keys() then stops auto-sizing
        # columns to content on every refresh, which would otherwise
        # silently undo the restored widths the very first time the
        # keyring reloads.
        self._columns_restored = False
        self._ui.stackDetail.setCurrentWidget(self._ui.lblNoSelection)

        # Filled in by MainWindow via set_key_actions()/etc — the same
        # QAction instances as the corresponding toolbar/menu, so toggling
        # one toggles all three.
        self._key_actions: list[QAction] = []
        self._uid_actions: list[QAction] = []
        self._photo_actions: list[QAction] = []
        self._subkey_actions: list[QAction] = []

        for widget, handler in (
            (self._ui.treeKeys, self._show_key_context_menu),
            (self._ui.lstUids, self._show_uid_context_menu),
            (self._ui.lstPhotos, self._show_photo_context_menu),
            (self._ui.treeSubkeys, self._show_subkey_context_menu),
        ):
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(handler)
            shortcut = QShortcut(QKeySequence("C"), widget)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(
                lambda w=widget, h=handler: h(_current_item_pos(w))
            )

        # Only one of these three sections is ever selected at a time — the
        # one currently focused (see CODING.md); the other two lose their
        # selection as soon as a section gains focus, not just when the
        # user actively picks something in it (e.g. Tab-ing back into a
        # section that still remembers an old selection).
        for widget in (self._ui.lstUids, self._ui.lstPhotos, self._ui.treeSubkeys):
            widget.installEventFilter(self)

        self._lock_icon_timer = QTimer(self)
        self._lock_icon_timer.setInterval(_LOCK_ICON_REFRESH_MS)
        self._lock_icon_timer.timeout.connect(self._refresh_lock_icons)
        self._lock_icon_timer.start()

    @property
    def splitter(self):
        """The key-list/detail-panel splitter, for geometry persistence."""
        return self._ui.splitter

    @property
    def detailSplitter(self):
        """The identities/photos/subkeys splitter, for geometry persistence."""
        return self._ui.detailSplitter

    def save_column_widths(self) -> QByteArray:
        """Return the main key list's current column widths (and order).

        For geometry persistence — see ``restore_column_widths()``.
        """
        return self._ui.treeKeys.header().saveState()

    def restore_column_widths(self, state: QByteArray) -> None:
        """Apply previously-saved column widths to the main key list.

        Also stops ``set_keys()`` from auto-sizing columns to content on
        the next refresh — that would otherwise immediately undo this.
        """
        header = self._ui.treeKeys.header()
        header.restoreState(state)
        # QHeaderView.restoreState() also overwrites sectionsClickable and
        # sortIndicatorShown with whatever they were when *state* was
        # saved — for anyone who already used the app (and so has a
        # column-width state on disk) from before header-click sorting
        # existed, that silently turns header clicks back into a no-op on
        # every subsequent launch. Re-apply key_list_view_ui.py's own
        # setup unconditionally, after the restore, not before.
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self._columns_restored = True

    def save_sort_state(self) -> tuple[int, int]:
        """Return the main key list's current (column, order) sort state.

        Returns
        -------
        :
            ``(column, order)``, with *order* a ``Qt.SortOrder`` value.
        """
        return self._sort_column, self._sort_order.value

    def restore_sort_state(self, column: int, order: int) -> None:
        """Apply a previously-saved (column, order) sort state.

        Parameters
        ----------
        column
            The column to sort by.
        order
            The sort direction, as a ``Qt.SortOrder`` value.
        """
        self._sort_column = column
        self._sort_order = Qt.SortOrder(order)
        self._ui.treeKeys.header().setSortIndicator(column, self._sort_order)
        if self._keys:
            self._rebuild_tree(preserve_selection=True)

    def selected_key(self) -> Key | None:
        """Report the currently selected key.

        Returns
        -------
        :
            The selected key, or ``None`` if none is selected.
        """
        items = self._ui.treeKeys.selectedItems()
        return items[0].data(0, _KEY_ROLE) if items else None

    def selected_subkey(self) -> Subkey | None:
        """Report the currently selected subkey.

        Returns
        -------
        :
            The selected subkey, or ``None`` if none is selected.
        """
        items = self._ui.treeSubkeys.selectedItems()
        return items[0].data(0, _SUBKEY_ROLE) if items else None

    def selected_uid(self) -> Uid | None:
        """Report the currently selected user ID.

        Returns
        -------
        :
            The selected UID, or ``None`` if none is selected.
        """
        items = self._ui.lstUids.selectedItems()
        return items[0].data(_UID_ROLE) if items else None

    def selected_photo(self) -> PhotoUid | None:
        """Report the currently selected photo.

        Returns
        -------
        :
            The selected photo, or ``None`` if none is selected.
        """
        items = self._ui.lstPhotos.selectedItems()
        return items[0].data(_PHOTO_ROLE) if items else None

    def select_key(
        self,
        fingerprint: str,
        subkey_keyid: str | None = None,
        uid_value: str | None = None,
        photo_index: int | None = None,
    ) -> None:
        """Re-select a key by identifier.

        Used e.g. to restore the selection after ``set_keys()`` reloaded
        the list following an operation on that key. A no-op if
        *fingerprint* isn't found (e.g. the key was deleted).

        Parameters
        ----------
        fingerprint
            The key to re-select.
        subkey_keyid
            If given, also re-select this subkey of that key.
        uid_value
            If given, also re-select this user ID of that key.
        photo_index
            If given, also re-select this photo of that key.
        """
        for i in range(self._ui.treeKeys.topLevelItemCount()):
            group = self._ui.treeKeys.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                key = item.data(0, _KEY_ROLE)
                if key is not None and key.fingerprint == fingerprint:
                    self._ui.treeKeys.setCurrentItem(item)
                    if subkey_keyid is not None:
                        self._select_subkey(subkey_keyid)
                    if uid_value is not None:
                        self._select_uid(uid_value)
                    if photo_index is not None:
                        self._select_photo(photo_index)
                    return

    def _select_subkey(self, subkey_keyid: str) -> None:
        """Re-select the subkey identified by *subkey_keyid*, if found."""
        tree = self._ui.treeSubkeys
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            subkey = item.data(0, _SUBKEY_ROLE)
            if subkey is not None and subkey.keyid == subkey_keyid:
                tree.setCurrentItem(item)
                return

    def _select_uid(self, uid_value: str) -> None:
        """Re-select the user ID whose value is *uid_value*, if found."""
        lst = self._ui.lstUids
        for i in range(lst.count()):
            item = lst.item(i)
            uid = item.data(_UID_ROLE)
            if uid is not None and uid.value == uid_value:
                lst.setCurrentItem(item)
                return

    def _select_photo(self, photo_index: int) -> None:
        """Re-select the photo at *photo_index* (1-based), if found."""
        lst = self._ui.lstPhotos
        for i in range(lst.count()):
            item = lst.item(i)
            photo = item.data(_PHOTO_ROLE)
            if photo is not None and photo.index == photo_index:
                lst.setCurrentItem(item)
                return

    def _on_copy_fingerprint(self) -> None:
        """Copy the currently displayed fingerprint to the clipboard."""
        QApplication.clipboard().setText(self._ui.lblFingerprint.text())

    # ── Section exclusivity (UIDs / photos / subkeys) ───────────────────

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Clear the other two sections' selection when one gains focus.

        Applies to the UIDs/photos/subkeys widgets — see the "Section
        exclusivity" note in ``__init__``.

        Parameters
        ----------
        watched
            The widget that raised *event*.
        event
            The event being filtered; only ``FocusIn`` triggers anything
            here.

        Returns
        -------
        :
            Whatever the base class implementation returns — this filter
            never consumes the event itself.
        """
        if event.type() == QEvent.Type.FocusIn:
            others = {
                self._ui.lstUids: (self._ui.lstPhotos, self._ui.treeSubkeys),
                self._ui.lstPhotos: (self._ui.lstUids, self._ui.treeSubkeys),
                self._ui.treeSubkeys: (self._ui.lstUids, self._ui.lstPhotos),
            }.get(watched)
            if others is not None:
                for other in others:
                    other.clearSelection()
        return super().eventFilter(watched, event)

    # ── Context menus (right-click or the 'c' key) ──────────────────────

    def set_key_actions(self, actions: Sequence[QAction]) -> None:
        """Register the actions shown in the key list's context menu.

        Parameters
        ----------
        actions
            The same QAction instances used by the corresponding
            toolbar/menu, so a context-menu entry never falls out of sync
            with them.
        """
        self._key_actions = list(actions)

    def set_uid_actions(self, actions: Sequence[QAction]) -> None:
        """Register the actions shown in the user ID list's context menu.

        Parameters
        ----------
        actions
            The same QAction instances used by the corresponding
            toolbar/menu.
        """
        self._uid_actions = list(actions)

    def set_photo_actions(self, actions: Sequence[QAction]) -> None:
        """Register the actions shown in the photo list's context menu.

        Parameters
        ----------
        actions
            The same QAction instances used by the corresponding
            toolbar/menu.
        """
        self._photo_actions = list(actions)

    def set_subkey_actions(self, actions: Sequence[QAction]) -> None:
        """Register the actions shown in the subkey list's context menu.

        Parameters
        ----------
        actions
            The same QAction instances used by the corresponding
            toolbar/menu.
        """
        self._subkey_actions = list(actions)

    def _show_context_menu(
        self,
        widget: QListWidget | QTreeWidget,
        pos: QPoint,
        actions: Sequence[QAction],
    ) -> None:
        """Select the item under *pos* in *widget* and pop up *actions*.

        Parameters
        ----------
        widget
            The list/tree the context menu was requested on.
        pos
            The position, in *widget*'s own coordinates, the menu was
            requested at (a right-click, or the ``C`` keyboard shortcut).
        actions
            The actions to show; a no-op when empty.
        """
        item = widget.itemAt(pos)
        if item is None:
            return
        widget.setCurrentItem(item)
        if not actions:
            return
        menu = QMenu(self)
        for action in actions:
            menu.addAction(action)
        self._exec_menu(menu, widget.mapToGlobal(pos))

    def _exec_menu(self, menu: QMenu, global_pos: QPoint) -> None:
        """Show *menu* modally at *global_pos*.

        A thin, overridable wrapper around the actual modal call: tests
        monkeypatch this instead of ``QMenu.exec()`` itself, which (unlike
        overriding ``exec()`` on a Python-defined ``QDialog`` subclass
        elsewhere in this codebase) doesn't reliably intercept the real
        call — verified the hard way, as a real popup with no one to
        dismiss it hangs a headless/offscreen test run forever.

        Parameters
        ----------
        menu
            The menu to show.
        global_pos
            Where to show it, in global screen coordinates.
        """
        menu.exec(global_pos)

    def _show_key_context_menu(self, pos: QPoint) -> None:
        """Pop up the key context menu at *pos*, if a real key row (not a group header) is under it."""
        item = self._ui.treeKeys.itemAt(pos)
        if item is None or item.data(0, _KEY_ROLE) is None:
            return
        self._show_context_menu(self._ui.treeKeys, pos, self._key_actions)

    def _show_uid_context_menu(self, pos: QPoint) -> None:
        """Pop up the user ID context menu at *pos*."""
        self._show_context_menu(self._ui.lstUids, pos, self._uid_actions)

    def _show_photo_context_menu(self, pos: QPoint) -> None:
        """Pop up the photo context menu at *pos*."""
        self._show_context_menu(self._ui.lstPhotos, pos, self._photo_actions)

    def _show_subkey_context_menu(self, pos: QPoint) -> None:
        """Pop up the subkey context menu at *pos*."""
        self._show_context_menu(self._ui.treeSubkeys, pos, self._subkey_actions)

    # ── Photo viewer ─────────────────────────────────────────────────────

    def _on_photo_activated(self, item: QListWidgetItem) -> None:
        """Open the photo viewer for *item*.

        ``itemActivated`` already covers both a double-click and pressing
        Enter/Return on the current item — no separate key handling needed.

        Parameters
        ----------
        item
            The activated photo list item.
        """
        photo = item.data(_PHOTO_ROLE)
        if photo is not None:
            self._open_photo_viewer(photo)

    def show_selected_photo(self) -> None:
        """Open the photo viewer for the currently selected photo.

        The "Show" menu/toolbar/context-menu action; same effect as
        activating the currently selected photo (double-click or Enter).
        """
        photo = self.selected_photo()
        if photo is not None:
            self._open_photo_viewer(photo)

    def _open_photo_viewer(self, photo: PhotoUid) -> None:
        """Open a modal ``PhotoViewerDialog`` showing *photo*."""
        from pbnightingale.ui.photo_viewer_dialog import PhotoViewerDialog

        PhotoViewerDialog(photo, self).exec()

    # ── Passphrase lock/unlock column ───────────────────────────────────

    def _on_key_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Forget *item*'s cached passphrase on a double-click of its unlocked lock icon; a no-op everywhere else.

        Parameters
        ----------
        item
            The double-clicked row.
        column
            The clicked column index; only ``_LOCK_COLUMN`` does anything.
        """
        if column != _LOCK_COLUMN:
            return
        key = item.data(0, _KEY_ROLE)
        if key is None or not key.has_secret:
            return
        if passphrase_cache.get(key.fingerprint) is None:
            return
        passphrase_cache.forget(key.fingerprint)
        item.setIcon(_LOCK_COLUMN, _lock_icon(passphrase_known=False))

    def _refresh_lock_icons(self) -> None:
        """Re-check the passphrase cache and redraw every key's lock icon.

        Run periodically by ``_lock_icon_timer`` so an icon still flips
        back to "locked" once its cache entry expires on its own.
        """
        tree = self._ui.treeKeys
        for i in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                key = item.data(0, _KEY_ROLE)
                if key is not None and key.has_secret:
                    item.setIcon(
                        _LOCK_COLUMN,
                        _lock_icon(passphrase_cache.get(key.fingerprint) is not None),
                    )

    def my_keys(self) -> list[Key]:
        """Return the personal keys (``has_secret``) from the last ``set_keys()`` call.

        E.g. to populate "sign as" choices without a redundant
        synchronous keyring listing.
        """
        return list(self._my_keys)

    def set_keys(self, keys: list[Key]) -> None:
        """Rebuild the whole key list from a fresh keyring listing.

        Splits it into "My keys" (``has_secret``) and "Other keys"
        groups, and re-runs selection-dependent state (detail panel,
        lock icons).

        Parameters
        ----------
        keys
            The full keyring listing, as returned by
            ``GPGBackend.list_keys()``.
        """
        self._keys = keys
        self._rebuild_tree()

    def _on_header_section_clicked(self, column: int) -> None:
        """Sort the keys within each group by *column*; toggle order on a repeat click.

        The "My keys"/"Other keys" groups themselves never reorder — only
        the keys within each one, per key_list_view_ui.py's own note on
        why native ``QTreeWidget`` sorting isn't used here.

        Parameters
        ----------
        column
            The clicked header section; a no-op for the header-less lock
            icon column (``_LOCK_COLUMN``).
        """
        if column == _LOCK_COLUMN:
            return
        if column == self._sort_column:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder
        self._ui.treeKeys.header().setSortIndicator(column, self._sort_order)
        self._rebuild_tree(preserve_selection=True)

    def _rebuild_tree(self, *, preserve_selection: bool = False) -> None:
        """Rebuild the "My keys"/"Other keys" groups from ``self._keys``.

        Applies the current sort column/order within each group.

        Parameters
        ----------
        preserve_selection
            Whether to re-select the currently selected key afterwards.
            Only for a local re-sort — a fresh ``set_keys()`` keyring
            reload always resets the selection to the placeholder, as
            before (callers re-select explicitly when appropriate, e.g.
            via ``select_key()``).
        """
        current = self.selected_key() if preserve_selection else None
        self._ui.treeKeys.clear()
        mine = [k for k in self._keys if k.has_secret]
        others = [k for k in self._keys if not k.has_secret]
        self._my_keys = mine
        mine = _sorted_keys(self._sort_column, self._sort_order, mine)
        others = _sorted_keys(self._sort_column, self._sort_order, others)
        self._add_group(_("My keys ({n})").format(n=len(mine)), mine)
        self._add_group(_("Other keys ({n})").format(n=len(others)), others)
        self._ui.treeKeys.expandAll()
        if not self._columns_restored:
            # Only until a real width has been restored from a previous
            # session (or set once by this same block) — otherwise this
            # would silently undo a restored or user-resized column on
            # every subsequent refresh.
            for column in range(self._ui.treeKeys.columnCount()):
                self._ui.treeKeys.resizeColumnToContents(column)
        # resizeColumnToContents() over-sizes this header-less, icon-only
        # column on some styles (padding meant for a sortable text header,
        # not a bare icon) — clamp it to just the icon plus a small margin.
        # Unconditional: this column is never meant to be freely resizable.
        self._ui.treeKeys.setColumnWidth(
            _LOCK_COLUMN, self._ui.treeKeys.iconSize().width() + 8
        )
        if current is not None:
            self.select_key(current.fingerprint)
        self._on_selection_changed()

    def _add_group(self, label: str, keys: list[Key]) -> None:
        """Add a bold, non-selectable group header row, then its children.

        The header is titled *label*, followed by one child row per
        entry in *keys*.

        Parameters
        ----------
        label
            The group header's text, e.g. ``"My keys (3)"``.
        keys
            The keys to list under it.
        """
        group = QTreeWidgetItem([label])
        bold = group.font(0)
        bold.setBold(True)
        group.setFont(0, bold)
        group.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._ui.treeKeys.addTopLevelItem(group)
        for key in keys:
            name, email = _display_name_email(key)
            item = QTreeWidgetItem(
                [name, "", email, key.keyid, _format_expires(key.expires)]
            )
            item.setData(0, _KEY_ROLE, key)
            if key.has_secret:
                item.setIcon(
                    _LOCK_COLUMN,
                    _lock_icon(passphrase_cache.get(key.fingerprint) is not None),
                )
            group.addChild(item)

    def _on_selection_changed(self) -> None:
        """React to a change of the selected key.

        Shows its detail panel (or the empty placeholder), refreshes the
        Signatures tab if it's active, and re-emits ``selectionChanged``
        for ``MainWindow``.
        """
        key = self.selected_key()
        if key is None:
            self._ui.stackDetail.setCurrentWidget(self._ui.lblNoSelection)
            self._reset_signatures()
            self.selectionChanged.emit()
            return
        self._show_key(key)
        self._ui.stackDetail.setCurrentIndex(1)
        self._maybe_request_signatures()
        self.selectionChanged.emit()

    # ── Signatures tab ───────────────────────────────────────────────────

    def _on_detail_tab_changed(self, _index: int) -> None:
        """Request the current key's signatures if the Signatures tab was just switched to."""
        self._maybe_request_signatures()

    def _maybe_request_signatures(self) -> None:
        """Emit ``signaturesRequested`` for the selected key.

        A no-op unless the Signatures tab is the active one, and a key
        is selected.
        """
        if self._ui.tabDetail.currentIndex() != _SIGNATURES_TAB_INDEX:
            return
        key = self.selected_key()
        if key is None:
            return
        tree = self._ui.treeSignatures
        tree.clear()
        placeholder = QTreeWidgetItem([_("Loading…"), "", "", ""])
        placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
        tree.addTopLevelItem(placeholder)
        self._current_signatures = []
        self._ui.btnDownloadUnknownSignatures.setEnabled(False)
        self.signaturesRequested.emit(key.fingerprint)

    def _reset_signatures(self) -> None:
        """Clear the Signatures tab back to its empty state."""
        self._ui.treeSignatures.clear()
        self._current_signatures = []
        self._ui.btnDownloadUnknownSignatures.setEnabled(False)

    def clear_signatures(self) -> None:
        """Reset the Signatures tab.

        E.g. after an asynchronous ``list_key_signatures()`` fetch
        failed, so it doesn't keep showing "Loading…" forever.
        """
        self._reset_signatures()

    def set_key_signatures(
        self, fingerprint: str, signatures: list[KeySignature]
    ) -> None:
        """Populate the Signatures tab.

        Called back once an asynchronous ``list_key_signatures()`` fetch
        completes. Ignored if the selection has since moved to a
        different key.

        Parameters
        ----------
        fingerprint
            The key *signatures* was fetched for.
        signatures
            The certifications found on that key's user IDs.
        """
        key = self.selected_key()
        if key is None or key.fingerprint != fingerprint:
            return
        self._current_signatures = signatures
        tree = self._ui.treeSignatures
        tree.clear()
        for signature in signatures:
            tree.addTopLevelItem(_signature_item(signature))
        for column in range(tree.columnCount()):
            tree.resizeColumnToContents(column)
        self._ui.btnDownloadUnknownSignatures.setEnabled(
            any(signature.key is None for signature in signatures)
        )

    def _on_download_unknown_signatures_clicked(self) -> None:
        """Emit ``downloadUnknownSignaturesRequested`` for every signer currently shown as unknown locally, if any."""
        identifiers = [
            signature.fingerprint or signature.keyid
            for signature in self._current_signatures
            if signature.key is None
        ]
        if identifiers:
            self.downloadUnknownSignaturesRequested.emit(identifiers)

    def _show_key(self, key: Key) -> None:
        """Populate every detail-panel field (labels, UIDs, photos, subkeys) from *key*."""
        ui = self._ui
        ui.lblType.setText(
            _("Personal (secret key available)") if key.has_secret else _("Public only")
        )
        ui.lblFingerprint.setText(_format_fingerprint(key.fingerprint))
        ui.lblAlgorithm.setText(f"{_format_algo(key.algo)}, {key.length} bits")
        ui.lblCapabilities.setText(_format_capabilities(key))
        ui.lblCreated.setText(_format_date(key.created))
        ui.lblExpires.setText(_format_expires(key.expires))
        ui.lblTrust.setText(_trust_label(key.trust))
        ui.lblOwnerTrust.setText(_trust_label(key.owner_trust))

        ui.lstUids.clear()
        for uid in key.uids:
            item = QListWidgetItem(_format_uid_label(uid))
            item.setData(_UID_ROLE, uid)
            ui.lstUids.addItem(item)

        ui.lstPhotos.clear()
        for photo in key.photos:
            item = QListWidgetItem(
                _photo_icon(photo), _("Revoked") if photo.revoked else ""
            )
            item.setData(_PHOTO_ROLE, photo)
            ui.lstPhotos.addItem(item)

        ui.treeSubkeys.clear()
        for sub in key.subkeys:
            item = QTreeWidgetItem(
                [
                    sub.keyid,
                    _format_capabilities(sub),
                    _format_algo(sub.algo),
                    _format_date(sub.created),
                    _format_expires(sub.expires),
                    _trust_label(sub.trust),
                ]
            )
            item.setData(0, _SUBKEY_ROLE, sub)
            ui.treeSubkeys.addTopLevelItem(item)
