"""UI layout for the key list & detail view (the main window's central widget)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


def _section_exclusivity_note() -> str:
    return _(
        "Only one of the identities, photos and subkeys lists can have a "
        "selection at a time — whichever one currently has focus."
    )


class Ui_KeyListView:
    def setupUi(self, widget: QWidget) -> None:
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, widget)
        layout.addWidget(self.splitter)

        self._setup_key_tree()
        self._setup_detail_stack()

        self.splitter.addWidget(self.treeKeys)
        self.splitter.addWidget(self.stackDetail)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([360, 640])

    # ── Key tree (left pane) ─────────────────────────────────────────────

    def _setup_key_tree(self) -> None:
        self.treeKeys = QTreeWidget(self.splitter)
        # Explicit rather than the style default (QSize(-1, -1), "ask the
        # style") so the lock/unlock column's width can be computed from a
        # known value below — see KeyListView.set_keys().
        self.treeKeys.setIconSize(QSize(16, 16))
        # QHeaderView's own default minimum (~38px on most styles) is
        # sized for a sortable text header, not a bare icon — without
        # lowering it, the header-less lock/unlock column can't be made
        # icon-tight no matter what KeyListView.set_keys() sets its width
        # to afterwards.
        self.treeKeys.header().setMinimumSectionSize(24)
        self.treeKeys.setColumnCount(5)
        # Column 1 (between Name and Email) carries only the passphrase
        # lock/unlock icon — no header text, see KeyListView._refresh_lock_icons().
        self.treeKeys.setHeaderLabels(
            [_("Name"), "", _("Email"), _("Key ID"), _("Expires")]
        )
        self.treeKeys.setRootIsDecorated(True)
        # Several keys can be selected at once (Ctrl/Shift-click): only the
        # actions applying identically to all of them stay enabled then,
        # and the detail panel is emptied — see KeyListView.selected_keys().
        self.treeKeys.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        # Sorting is applied manually within each "My keys"/"Other keys"
        # group (see KeyListView._on_header_section_clicked()) rather than
        # via QTreeWidget.setSortingEnabled(), which would sort the two
        # top-level group rows themselves along with their children.
        self.treeKeys.header().setSectionsClickable(True)
        self.treeKeys.header().setSortIndicatorShown(True)
        self.treeKeys.setToolTip(_("Keys in your keyring"))
        self.treeKeys.setWhatsThis(
            _(
                'Lists every key in your keyring, grouped into "My keys" '
                '(a secret key is available) and "Other keys" (public '
                "only). The unlabeled column between Name and Email shows "
                "whether a personal key's passphrase is currently "
                "remembered: unlocked if so, locked otherwise. "
                "Double-click that icon to forget a remembered passphrase. "
                "Click a column header to sort the keys within each group "
                "by that column; click it again to reverse the order. "
                "Ctrl-click or Shift-click to select several keys at once: "
                "only the actions applying to all of them with the same "
                "options stay available then."
            )
        )

    # ── Detail pane (right pane) ─────────────────────────────────────────

    def _setup_detail_stack(self) -> None:
        self.stackDetail = QStackedWidget(self.splitter)

        self.lblNoSelection = QLabel(_("Select a key to see its details."))
        self.lblNoSelection.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblNoSelection.setWordWrap(True)
        self.stackDetail.addWidget(self.lblNoSelection)

        self.tabDetail = QTabWidget(self.stackDetail)
        self.tabDetail.addTab(self._make_detail_page(), _("Details"))
        self.tabDetail.addTab(self._make_signatures_page(), _("Signatures"))
        self.stackDetail.addWidget(self.tabDetail)

    def _make_detail_page(self) -> QWidget:
        page = QWidget(self.tabDetail)
        layout = QVBoxLayout(page)

        form = QFormLayout()
        self.lblType = QLabel(page)
        form.addRow(_("Type:"), self.lblType)
        fingerprint_row = QHBoxLayout()
        self.lblFingerprint = QLabel(page)
        self.lblFingerprint.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        fingerprint_row.addWidget(self.lblFingerprint)
        self.btnCopyFingerprint = QPushButton(_("Copy"), page)
        self.btnCopyFingerprint.setToolTip(_("Copy the fingerprint to the clipboard"))
        # A thicker, more visible focus border than the platform default —
        # palette(highlight) rather than a fixed color, so it stays correct
        # in both light and dark themes.
        self.btnCopyFingerprint.setStyleSheet(
            "QPushButton:focus { border: 2px solid palette(highlight); }"
        )
        self.btnCopyFingerprint.setWhatsThis(
            _(
                "Copies the fingerprint shown above (grouped in 4-character "
                "blocks) to the clipboard."
            )
        )
        fingerprint_row.addWidget(self.btnCopyFingerprint)
        fingerprint_row.addStretch()
        form.addRow(_("Fingerprint:"), fingerprint_row)
        self.lblAlgorithm = QLabel(page)
        form.addRow(_("Algorithm:"), self.lblAlgorithm)
        self.lblCapabilities = QLabel(page)
        form.addRow(_("Capabilities:"), self.lblCapabilities)
        self.lblCreated = QLabel(page)
        form.addRow(_("Created:"), self.lblCreated)
        self.lblExpires = QLabel(page)
        form.addRow(_("Expires:"), self.lblExpires)
        self.lblTrust = QLabel(page)
        form.addRow(_("Validity:"), self.lblTrust)
        self.lblOwnerTrust = QLabel(page)
        form.addRow(_("Owner trust:"), self.lblOwnerTrust)
        layout.addLayout(form)

        self.detailSplitter = QSplitter(Qt.Orientation.Vertical, page)
        layout.addWidget(self.detailSplitter)

        grpUids = QGroupBox(_("User IDs"), self.detailSplitter)
        grpUidsLayout = QVBoxLayout(grpUids)
        self.lstUids = QListWidget(grpUids)
        self.lstUids.setWhatsThis(
            _(
                "The identities (names and email addresses) attached to "
                "the selected key. A checkmark (✓) marks the current "
                "primary identity."
            )
            + " "
            + _section_exclusivity_note()
        )
        grpUidsLayout.addWidget(self.lstUids)
        self.detailSplitter.addWidget(grpUids)

        grpPhotos = QGroupBox(_("Photos"), self.detailSplitter)
        grpPhotosLayout = QVBoxLayout(grpPhotos)
        self.lstPhotos = QListWidget(grpPhotos)
        self.lstPhotos.setViewMode(QListView.ViewMode.IconMode)
        self.lstPhotos.setIconSize(QSize(64, 64))
        self.lstPhotos.setResizeMode(QListView.ResizeMode.Adjust)
        self.lstPhotos.setMovement(QListView.Movement.Static)
        self.lstPhotos.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.lstPhotos.setWhatsThis(
            _(
                "The photos attached to the selected key. Double-click a "
                "photo, or press Enter on it, to view it at its full size."
            )
            + " "
            + _section_exclusivity_note()
        )
        grpPhotosLayout.addWidget(self.lstPhotos)
        self.detailSplitter.addWidget(grpPhotos)

        grpSubkeys = QGroupBox(_("Subkeys"), self.detailSplitter)
        grpSubkeysLayout = QVBoxLayout(grpSubkeys)
        self.treeSubkeys = QTreeWidget(grpSubkeys)
        self.treeSubkeys.setColumnCount(6)
        self.treeSubkeys.setHeaderLabels(
            [
                _("Key ID"),
                _("Capabilities"),
                _("Algorithm"),
                _("Created"),
                _("Expires"),
                _("Status"),
            ]
        )
        self.treeSubkeys.setRootIsDecorated(False)
        self.treeSubkeys.setSelectionMode(
            self.treeSubkeys.SelectionMode.SingleSelection
        )
        self.treeSubkeys.setWhatsThis(
            _(
                "The subkeys attached to the selected key — separate "
                "signing, encryption or authentication keys bound to it."
            )
            + " "
            + _section_exclusivity_note()
        )
        grpSubkeysLayout.addWidget(self.treeSubkeys)
        self.detailSplitter.addWidget(grpSubkeys)

        # Photos default to less space than the other two — a photo's own
        # QListWidget caps its icon size (64px) well below a typical UID/
        # subkey row count, so it rarely needs as much room.
        self.detailSplitter.setStretchFactor(0, 2)
        self.detailSplitter.setStretchFactor(1, 1)
        self.detailSplitter.setStretchFactor(2, 2)

        return page

    def _make_signatures_page(self) -> QWidget:
        page = QWidget(self.tabDetail)
        layout = QVBoxLayout(page)

        self.treeSignatures = QTreeWidget(page)
        self.treeSignatures.setColumnCount(4)
        self.treeSignatures.setHeaderLabels(
            [_("Name"), _("Email"), _("Key ID"), _("Expires")]
        )
        self.treeSignatures.setRootIsDecorated(False)
        self.treeSignatures.setSelectionMode(
            self.treeSignatures.SelectionMode.SingleSelection
        )
        self.treeSignatures.setWhatsThis(
            _(
                "Every key that has certified (signed) the selected key's "
                "user IDs. A signer already in your keyring is shown the "
                "same way as in the list on the left; one gpg cannot "
                'resolve locally is shown as "Unknown locally" with only '
                "its identifier."
            )
        )
        layout.addWidget(self.treeSignatures)

        self.btnDownloadUnknownSignatures = QPushButton(
            _("Download Unknown Keys"), page
        )
        self.btnDownloadUnknownSignatures.setWhatsThis(
            _(
                "Fetches every signing key not already in your keyring "
                "from the keyserver, then reports which ones were found."
            )
        )
        layout.addWidget(self.btnDownloadUnknownSignatures)

        return page
