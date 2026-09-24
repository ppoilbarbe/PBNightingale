"""Tests for the key list & detail view."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QAction

from pbnightingale.core import passphrase_cache
from pbnightingale.core.gpg_backend import Key, KeySignature, PhotoUid, Subkey, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.key_list_view import KeyListView, _lock_icon
from tests.gpg_test_helpers import make_test_jpeg


def _icon_image(icon):
    return icon.pixmap(QSize(32, 32)).toImage()


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

_MY_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=1_800_000_000,
    trust="u",
    owner_trust="m",
    uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
    photos=[],
    subkeys=[_SUBKEY],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)

_OTHER_KEY = Key(
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


_KEY_CHARLIE = Key(
    **{
        **_MY_KEY.__dict__,
        "fingerprint": "CCCC111122223333444455556666777788889999",
        "keyid": "3333000011112222",
        "uids": [Uid("Charlie Example <charlie@example.com>", revoked=False)],
        "expires": 1_900_000_000,
    }
)

_KEY_BOB_SECRET = Key(
    **{
        **_MY_KEY.__dict__,
        "fingerprint": "DDDD111122223333444455556666777788889999",
        "keyid": "1111222233334444",
        "uids": [Uid("Bob Two <bob2@example.com>", revoked=False)],
        "expires": None,
    }
)

# Inserted in this order (Alice, Charlie, Bob) so the un-sorted order is
# distinguishable from a sort-by-name (Alice, Bob, Charlie) or
# sort-by-keyid (Bob, Charlie, Alice) result.
_SORTABLE_KEYS = [_MY_KEY, _KEY_CHARLIE, _KEY_BOB_SECRET]


def _names(group) -> list[str]:
    return [group.child(i).text(0) for i in range(group.childCount())]


def test_no_selection_by_default(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert view._ui.stackDetail.currentWidget() is view._ui.lblNoSelection


def test_set_keys_groups_by_has_secret(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys([_MY_KEY, _OTHER_KEY])

    tree = view._ui.treeKeys
    assert tree.topLevelItem(0).text(0) == "My keys (1)"
    assert tree.topLevelItem(0).child(0).text(2) == "alice@example.com"
    assert tree.topLevelItem(1).text(0) == "Other keys (1)"
    assert tree.topLevelItem(1).child(0).text(2) == "bob@example.com"


def test_key_tree_name_email_columns_use_the_primary_uid(qtbot):
    key = Key(
        **{
            **_MY_KEY.__dict__,
            "uids": [
                Uid("Alice Old <alice.old@example.com>", revoked=False, primary=False),
                Uid("Alice Example <alice@example.com>", revoked=False, primary=True),
            ],
        }
    )
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys([key])

    row = view._ui.treeKeys.topLevelItem(0).child(0)
    assert row.text(0) == "Alice Example"
    assert row.text(2) == "alice@example.com"


def test_my_keys_returns_only_the_has_secret_keys(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert view.my_keys() == []

    view.set_keys([_MY_KEY, _OTHER_KEY])

    assert view.my_keys() == [_MY_KEY]


def test_group_headers_are_not_selectable(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    from PySide6.QtCore import Qt

    header = view._ui.treeKeys.topLevelItem(0)
    assert not header.flags() & Qt.ItemFlag.ItemIsSelectable


def test_selecting_a_key_shows_its_detail(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    item = view._ui.treeKeys.topLevelItem(0).child(0)
    item.setSelected(True)

    ui = view._ui
    assert ui.stackDetail.currentWidget() is not ui.lblNoSelection
    assert ui.lblType.text() == "Personal (secret key available)"
    assert ui.lblFingerprint.text() == (
        "AAAA 1111 2222 3333 4444 5555 6666 7777 8888 9999"
    )
    assert ui.lblAlgorithm.text() == "RSA (1), 4096 bits"
    assert ui.lblTrust.text() == "Ultimate"
    assert ui.lblOwnerTrust.text() == "Marginal"
    assert [ui.lstUids.item(i).text() for i in range(ui.lstUids.count())] == [
        "Alice Example <alice@example.com>"
    ]
    assert ui.treeSubkeys.topLevelItemCount() == 1
    subkey_row = ui.treeSubkeys.topLevelItem(0)
    assert subkey_row.text(0) == "AAAABBBBCCCCDDDD"
    assert subkey_row.text(1) == "Encrypt"
    assert subkey_row.text(2) == "RSA (1)"
    assert subkey_row.text(4) == "Never"
    assert subkey_row.text(5) == "Ultimate"

    assert view.selected_key() is _MY_KEY
    assert view.selected_subkey() is None
    subkey_row.setSelected(True)
    assert view.selected_subkey() is _SUBKEY


def test_copy_fingerprint_button_has_a_visible_focus_style(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert ":focus" in view._ui.btnCopyFingerprint.styleSheet()


def test_key_widgets_have_whats_this_text(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    for widget in (
        view._ui.treeKeys,
        view._ui.lstUids,
        view._ui.lstPhotos,
        view._ui.treeSubkeys,
        view._ui.btnCopyFingerprint,
    ):
        assert widget.whatsThis() != ""


def test_section_lists_share_the_exclusivity_note(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    note = (
        "Only one of the identities, photos and subkeys lists can have a "
        "selection at a time — whichever one currently has focus."
    )
    for widget in (view._ui.lstUids, view._ui.lstPhotos, view._ui.treeSubkeys):
        assert note in widget.whatsThis()


def test_copy_fingerprint_button_copies_the_displayed_text(qtbot):
    from PySide6.QtWidgets import QApplication

    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    view._ui.btnCopyFingerprint.click()

    assert QApplication.clipboard().text() == view._ui.lblFingerprint.text()
    assert QApplication.clipboard().text() == (
        "AAAA 1111 2222 3333 4444 5555 6666 7777 8888 9999"
    )


def test_unknown_creation_date_and_full_capabilities(qtbot):
    key = Key(
        fingerprint="CCCC111122223333444455556666777788889999",
        keyid="6666777788889999",
        algo="22",
        length=256,
        created=0,
        expires=None,
        trust="m",
        owner_trust="",
        uids=[Uid("Carol Example <carol@example.com>", revoked=False)],
        photos=[],
        subkeys=[],
        has_secret=False,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=True,
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    ui = view._ui
    assert ui.lblCreated.text() == "Unknown"
    assert ui.lblTrust.text() == "Marginal"
    assert ui.lblCapabilities.text() == "Certify, Sign, Encrypt, Authenticate"
    assert ui.lblAlgorithm.text() == "EdDSA (22), 256 bits"


def test_unmapped_algo_code_falls_back_to_the_raw_code(qtbot):
    key = Key(
        fingerprint="DDDD111122223333444455556666777788889999",
        keyid="7777888899990000",
        algo="99",
        length=256,
        created=1_700_000_000,
        expires=None,
        trust="u",
        owner_trust="",
        uids=[Uid("Dave Example <dave@example.com>", revoked=False)],
        photos=[],
        subkeys=[],
        has_secret=True,
        can_sign=False,
        can_encrypt=False,
        can_certify=False,
        can_authenticate=False,
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    assert view._ui.lblAlgorithm.text() == "99, 256 bits"


def test_selected_key_and_subkey_are_none_without_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    assert view.selected_key() is None
    assert view.selected_subkey() is None


def test_selection_changed_emitted_on_key_and_subkey_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    seen = []
    view.selectionChanged.connect(lambda: seen.append(True))

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    assert len(seen) == 1

    view._ui.treeSubkeys.topLevelItem(0).setSelected(True)
    assert len(seen) == 2

    view._ui.lstUids.item(0).setSelected(True)
    assert len(seen) == 3


def test_deselecting_returns_to_placeholder(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    item = view._ui.treeKeys.topLevelItem(0).child(0)
    item.setSelected(True)

    item.setSelected(False)

    assert view._ui.stackDetail.currentWidget() is view._ui.lblNoSelection


def test_reloading_keys_resets_selection_to_placeholder(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    view.set_keys([_MY_KEY, _OTHER_KEY])

    assert view._ui.stackDetail.currentWidget() is view._ui.lblNoSelection


def test_select_key_restores_selection_by_fingerprint(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])

    view.select_key(_OTHER_KEY.fingerprint)

    assert view.selected_key() is _OTHER_KEY


def test_select_key_also_restores_subkey_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    view.select_key(_MY_KEY.fingerprint, _SUBKEY.keyid)

    assert view.selected_key() is _MY_KEY
    assert view.selected_subkey() is _SUBKEY


def test_keys_are_sorted_by_name_ascending_by_default(qtbot):
    """No header ever clicked, no previous session to restore from — still sorted, not raw insertion order."""
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys(_SORTABLE_KEYS)

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Alice Example",
        "Bob Two",
        "Charlie Example",
    ]
    header = view._ui.treeKeys.header()
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
    assert view.save_sort_state() == (0, Qt.SortOrder.AscendingOrder.value)


def test_header_click_on_the_active_column_reverses_the_order(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)

    # Name (column 0) is already the active (default) sort — one click on
    # it reverses, it doesn't restart at ascending.
    view._ui.treeKeys.header().sectionClicked.emit(0)

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Charlie Example",
        "Bob Two",
        "Alice Example",
    ]

    view._ui.treeKeys.header().sectionClicked.emit(0)

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Alice Example",
        "Bob Two",
        "Charlie Example",
    ]


def test_header_click_on_a_different_column_sorts_it_ascending(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)

    view._ui.treeKeys.header().sectionClicked.emit(3)  # key ID

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Bob Two",
        "Charlie Example",
        "Alice Example",
    ]


def test_sorting_does_not_reorder_the_groups_themselves(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([*_SORTABLE_KEYS, _OTHER_KEY])

    view._ui.treeKeys.header().sectionClicked.emit(3)

    tree = view._ui.treeKeys
    assert tree.topLevelItem(0).text(0).startswith("My keys")
    assert tree.topLevelItem(1).text(0).startswith("Other keys")


def test_expires_column_sorts_keys_with_no_expiration_last_either_direction(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)
    header = view._ui.treeKeys.header()

    header.sectionClicked.emit(4)  # ascending

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Alice Example",
        "Charlie Example",
        "Bob Two",
    ]

    header.sectionClicked.emit(4)  # descending

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Charlie Example",
        "Alice Example",
        "Bob Two",
    ]


def test_header_click_on_the_lock_column_is_a_no_op(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)
    before = _names(view._ui.treeKeys.topLevelItem(0))
    before_sort_state = view.save_sort_state()

    view._ui.treeKeys.header().sectionClicked.emit(1)

    assert _names(view._ui.treeKeys.topLevelItem(0)) == before
    assert view.save_sort_state() == before_sort_state


def test_save_and_restore_sort_state_round_trip(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)

    view._ui.treeKeys.header().sectionClicked.emit(0)  # ascending -> descending
    saved = view.save_sort_state()
    assert saved == (0, Qt.SortOrder.DescendingOrder.value)

    restored = KeyListView()
    qtbot.addWidget(restored)
    restored.restore_sort_state(*saved)
    restored.set_keys(_SORTABLE_KEYS)

    assert _names(restored._ui.treeKeys.topLevelItem(0)) == [
        "Charlie Example",
        "Bob Two",
        "Alice Example",
    ]


def test_restore_sort_state_rebuilds_a_tree_already_populated(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)

    view.restore_sort_state(3, Qt.SortOrder.AscendingOrder.value)

    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Bob Two",
        "Charlie Example",
        "Alice Example",
    ]


def test_select_key_unknown_fingerprint_is_a_no_op(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    view.select_key("0" * 40)

    assert view.selected_key() is None


def test_select_key_after_reload_survives_a_refresh(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    view.set_keys([_MY_KEY, _OTHER_KEY])
    view.select_key(_MY_KEY.fingerprint)

    assert view.selected_key() is _MY_KEY
    assert view._ui.stackDetail.currentWidget() is not view._ui.lblNoSelection


def test_select_key_also_restores_uid_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    view.select_key(_MY_KEY.fingerprint, uid_value=_MY_KEY.uids[0].value)

    assert view.selected_key() is _MY_KEY
    assert view.selected_uid() == _MY_KEY.uids[0]


def test_uid_list_shows_revoked_status(qtbot):
    key = Key(
        fingerprint="EEEE111122223333444455556666777788889999",
        keyid="8888999900001111",
        algo="1",
        length=4096,
        created=1_700_000_000,
        expires=None,
        trust="u",
        owner_trust="",
        uids=[
            Uid("Erin Example <erin@example.com>", revoked=False),
            Uid("Erin Old <erin.old@example.com>", revoked=True),
            Uid("Erin Work <erin.work@example.com>", revoked=False),
        ],
        photos=[],
        subkeys=[],
        has_secret=True,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=False,
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    ui = view._ui
    assert [ui.lstUids.item(i).text() for i in range(ui.lstUids.count())] == [
        "Erin Example <erin@example.com>",
        "Erin Old <erin.old@example.com> (revoked)",
        "Erin Work <erin.work@example.com>",
    ]

    assert view.selected_uid() is None
    ui.lstUids.item(1).setSelected(True)
    assert view.selected_uid() == key.uids[1]


def test_uid_list_marks_the_primary_identity_with_a_checkmark(qtbot):
    key = Key(
        fingerprint="EEEE111122223333444455556666777788889999",
        keyid="8888999900001111",
        algo="1",
        length=4096,
        created=1_700_000_000,
        expires=None,
        trust="u",
        owner_trust="",
        uids=[
            Uid("Fay Example <fay@example.com>", revoked=False, primary=False),
            Uid("Fay Work <fay.work@example.com>", revoked=False, primary=True),
        ],
        photos=[],
        subkeys=[],
        has_secret=True,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=False,
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    ui = view._ui
    assert [ui.lstUids.item(i).text() for i in range(ui.lstUids.count())] == [
        "Fay Example <fay@example.com>",
        "✓ Fay Work <fay.work@example.com>",
    ]


def _make_full_key(tmp_path) -> Key:
    """A key with a UID, a photo and a subkey — for tests exercising the
    mutual exclusivity between those three sections.
    """
    jpeg = make_test_jpeg(tmp_path / "eve.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    return Key(
        fingerprint="EEEE111122223333444455556666777788889999",
        keyid="1111222233334444",
        algo="1",
        length=4096,
        created=1_700_000_000,
        expires=None,
        trust="u",
        owner_trust="",
        uids=[Uid("Eve Example <eve@example.com>", revoked=False)],
        photos=[photo],
        subkeys=[_SUBKEY],
        has_secret=True,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=False,
    )


def _make_key_with_photos(tmp_path, photos) -> Key:
    return Key(
        fingerprint="FFFF111122223333444455556666777788889999",
        keyid="9999000011112222",
        algo="1",
        length=4096,
        created=1_700_000_000,
        expires=None,
        trust="u",
        owner_trust="",
        uids=[Uid("Frank Example <frank@example.com>", revoked=False)],
        photos=photos,
        subkeys=[],
        has_secret=True,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=False,
    )


def test_photo_list_shows_a_thumbnail_per_photo(qtbot, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    ui = view._ui
    assert ui.lstPhotos.count() == 1
    assert not ui.lstPhotos.item(0).icon().isNull()
    assert ui.lstPhotos.item(0).text() == ""

    assert view.selected_photo() is None
    ui.lstPhotos.item(0).setSelected(True)
    assert view.selected_photo() is photo


def test_revoked_photo_is_labelled(qtbot, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=True)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    assert view._ui.lstPhotos.item(0).text() == "Revoked"


def test_select_key_also_restores_photo_selection(qtbot, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])

    view.select_key(key.fingerprint, photo_index=photo.index)

    assert view.selected_key() is key
    assert view.selected_photo() is photo


# ── Passphrase lock/unlock column ───────────────────────────────────────


def test_lock_column_header_is_empty(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert view._ui.treeKeys.headerItem().text(1) == ""


def test_my_key_without_cached_passphrase_shows_locked_icon(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys([_MY_KEY])

    item = view._ui.treeKeys.topLevelItem(0).child(0)
    assert _icon_image(item.icon(1)) == _icon_image(_lock_icon(False))


def test_my_key_with_cached_passphrase_shows_unlocked_icon(qtbot):
    passphrase_cache.store(_MY_KEY.fingerprint, Passphrase("s3cret"), 60)
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys([_MY_KEY])

    item = view._ui.treeKeys.topLevelItem(0).child(0)
    assert _icon_image(item.icon(1)) == _icon_image(_lock_icon(True))


def test_other_key_has_no_lock_icon(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    view.set_keys([_MY_KEY, _OTHER_KEY])

    item = view._ui.treeKeys.topLevelItem(1).child(0)
    assert item.icon(1).isNull()


def test_double_clicking_lock_column_forgets_the_passphrase(qtbot):
    passphrase_cache.store(_MY_KEY.fingerprint, Passphrase("s3cret"), 60)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    item = view._ui.treeKeys.topLevelItem(0).child(0)

    view._on_key_item_double_clicked(item, 1)

    assert passphrase_cache.get(_MY_KEY.fingerprint) is None
    assert _icon_image(item.icon(1)) == _icon_image(_lock_icon(False))


def test_double_clicking_a_different_column_does_not_forget_the_passphrase(qtbot):
    passphrase_cache.store(_MY_KEY.fingerprint, Passphrase("s3cret"), 60)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    item = view._ui.treeKeys.topLevelItem(0).child(0)

    view._on_key_item_double_clicked(item, 0)

    assert passphrase_cache.get(_MY_KEY.fingerprint) == Passphrase("s3cret")


def test_refresh_lock_icons_reflects_external_cache_changes(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    item = view._ui.treeKeys.topLevelItem(0).child(0)
    assert _icon_image(item.icon(1)) == _icon_image(_lock_icon(False))

    passphrase_cache.store(_MY_KEY.fingerprint, Passphrase("s3cret"), 60)
    view._refresh_lock_icons()

    assert _icon_image(item.icon(1)) == _icon_image(_lock_icon(True))


# ── Context menus (right-click or the 'c' key) ──────────────────────────


def test_key_context_menu_contains_the_key_actions(qtbot, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        KeyListView,
        "_exec_menu",
        lambda self, menu, pos: captured.setdefault("menu", menu),
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    action = QAction("Do key thing")
    view.set_key_actions([action])

    item = view._ui.treeKeys.topLevelItem(0).child(0)
    pos = view._ui.treeKeys.visualItemRect(item).center()
    view._show_key_context_menu(pos)

    menu = captured["menu"]
    assert action in menu.actions()


def test_key_context_menu_is_not_shown_on_a_group_header(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(
        KeyListView, "_exec_menu", lambda self, menu, pos: calls.append(menu)
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    header = view._ui.treeKeys.topLevelItem(0)
    pos = view._ui.treeKeys.visualItemRect(header).center()
    view._show_key_context_menu(pos)

    assert calls == []


def test_uid_context_menu_contains_the_uid_actions(qtbot, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        KeyListView,
        "_exec_menu",
        lambda self, menu, pos: captured.setdefault("menu", menu),
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    action = QAction("Do uid thing")
    view.set_uid_actions([action])

    item = view._ui.lstUids.item(0)
    pos = view._ui.lstUids.visualItemRect(item).center()
    view._show_uid_context_menu(pos)

    menu = captured["menu"]
    assert action in menu.actions()


def test_photo_context_menu_contains_the_photo_actions(qtbot, monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        KeyListView,
        "_exec_menu",
        lambda self, menu, pos: captured.setdefault("menu", menu),
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    action = QAction("Do photo thing")
    view.set_photo_actions([action])

    item = view._ui.lstPhotos.item(0)
    pos = view._ui.lstPhotos.visualItemRect(item).center()
    view._show_photo_context_menu(pos)

    assert captured["menu"].actions() == [action]


def test_show_selected_photo_opens_the_viewer_for_the_selected_photo(
    qtbot, monkeypatch, tmp_path
):
    from pbnightingale.ui.photo_viewer_dialog import PhotoViewerDialog

    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.lstPhotos.item(0).setSelected(True)

    opened = []
    monkeypatch.setattr(
        PhotoViewerDialog, "exec", lambda self: opened.append(self) or 0
    )

    view.show_selected_photo()

    assert len(opened) == 1


def test_show_selected_photo_does_nothing_without_a_selection(qtbot, tmp_path):
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    view.show_selected_photo()  # no photo selected — must not raise


def test_subkey_context_menu_contains_the_subkey_actions(qtbot, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        KeyListView,
        "_exec_menu",
        lambda self, menu, pos: captured.setdefault("menu", menu),
    )
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    action = QAction("Do subkey thing")
    view.set_subkey_actions([action])

    item = view._ui.treeSubkeys.topLevelItem(0)
    pos = view._ui.treeSubkeys.visualItemRect(item).center()
    view._show_subkey_context_menu(pos)

    menu = captured["menu"]
    assert action in menu.actions()


# ── Section exclusivity (UIDs / photos / subkeys) ───────────────────────


def test_focusing_uids_clears_photo_and_subkey_selection(qtbot, tmp_path):
    key = _make_full_key(tmp_path)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.lstPhotos.item(0).setSelected(True)
    view._ui.treeSubkeys.topLevelItem(0).setSelected(True)

    view.eventFilter(view._ui.lstUids, QEvent(QEvent.Type.FocusIn))

    assert view.selected_photo() is None
    assert view.selected_subkey() is None


def test_focusing_subkeys_clears_uid_and_photo_selection(qtbot, tmp_path):
    key = _make_full_key(tmp_path)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.lstUids.item(0).setSelected(True)
    view._ui.lstPhotos.item(0).setSelected(True)

    view.eventFilter(view._ui.treeSubkeys, QEvent(QEvent.Type.FocusIn))

    assert view.selected_uid() is None
    assert view.selected_photo() is None


def test_real_focus_change_triggers_section_exclusivity(qtbot, tmp_path):
    key = _make_full_key(tmp_path)
    view = KeyListView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.lstPhotos.item(0).setSelected(True)

    view._ui.lstUids.setFocus()
    qtbot.waitUntil(lambda: view._ui.lstUids.hasFocus())

    assert view.selected_photo() is None


# ── Photo viewer ─────────────────────────────────────────────────────────


def test_activating_a_photo_opens_the_viewer(qtbot, monkeypatch, tmp_path):
    from pbnightingale.ui.photo_viewer_dialog import PhotoViewerDialog

    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    photo = PhotoUid(index=1, image=jpeg.read_bytes(), revoked=False)
    key = _make_key_with_photos(tmp_path, [photo])
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([key])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    opened = []
    monkeypatch.setattr(
        PhotoViewerDialog, "exec", lambda self: opened.append(self) or 0
    )

    view._ui.lstPhotos.itemActivated.emit(view._ui.lstPhotos.item(0))

    assert len(opened) == 1
    assert not opened[0]._ui.lblPhoto.pixmap().isNull()


# ── Detail panel splitter ────────────────────────────────────────────────


def test_detail_splitter_is_vertical_and_holds_the_three_group_boxes(qtbot):
    from PySide6.QtCore import Qt

    view = KeyListView()
    qtbot.addWidget(view)

    splitter = view.detailSplitter

    assert splitter is view._ui.detailSplitter
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert splitter.count() == 3
    assert splitter.widget(0).findChild(type(view._ui.lstUids)) is view._ui.lstUids
    assert splitter.widget(1).findChild(type(view._ui.lstPhotos)) is view._ui.lstPhotos
    assert (
        splitter.widget(2).findChild(type(view._ui.treeSubkeys)) is view._ui.treeSubkeys
    )


def test_photos_panel_is_resizable_rather_than_height_capped(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert view._ui.lstPhotos.maximumHeight() >= 1_000_000


# ── Lock/unlock column width ─────────────────────────────────────────────


def test_lock_column_is_icon_tight_not_header_default_width(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])

    tree = view._ui.treeKeys
    lock_column_width = tree.columnWidth(1)

    assert lock_column_width == tree.iconSize().width() + 8
    # The actual regression: QHeaderView's own default minimum section
    # size (~38px on most styles) is sized for a sortable text header,
    # not a bare icon, and silently overrides a narrower setColumnWidth()
    # unless minimumSectionSize() is lowered too.
    assert tree.header().minimumSectionSize() <= lock_column_width


# ── Column width persistence ──────────────────────────────────────────────


def test_restore_column_widths_applies_the_saved_state(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.header().resizeSection(0, 321)
    state = view.save_column_widths()

    other = KeyListView()
    qtbot.addWidget(other)
    other.restore_column_widths(state)

    assert other._ui.treeKeys.header().sectionSize(0) == 321


def test_restore_column_widths_keeps_the_header_sortable(qtbot):
    """A header state saved before header-click sorting existed must not un-clickable it back.

    ``QHeaderView.saveState()``/``restoreState()`` round-trips
    ``sectionsClickable``/``sortIndicatorShown`` along with the column
    widths — a real user's on-disk state, saved by an older build where
    neither was ever turned on, would otherwise silently disable header
    clicks again on every subsequent launch. Reported against the real
    running app: clicking a header did nothing at all for a user with a
    pre-existing column-width state.
    """
    from PySide6.QtWidgets import QTreeWidget

    stale_tree = QTreeWidget()
    qtbot.addWidget(stale_tree)
    stale_header = stale_tree.header()
    stale_header.setSectionsClickable(False)
    stale_header.setSortIndicatorShown(False)
    stale_state = stale_header.saveState()

    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys(_SORTABLE_KEYS)

    view.restore_column_widths(stale_state)

    header = view._ui.treeKeys.header()
    assert header.sectionsClickable()
    assert header.isSortIndicatorShown()
    # Name (column 0) is already the default active sort — a click on it
    # reverses the order, proving the click was actually processed.
    header.sectionClicked.emit(0)
    assert _names(view._ui.treeKeys.topLevelItem(0)) == [
        "Charlie Example",
        "Bob Two",
        "Alice Example",
    ]


def test_set_keys_does_not_override_restored_column_widths(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.header().resizeSection(0, 321)
    state = view.save_column_widths()

    other = KeyListView()
    qtbot.addWidget(other)
    other.restore_column_widths(state)
    # A refresh (set_keys() called again) would normally auto-size every
    # column to content — must not undo the just-restored width.
    other.set_keys([_MY_KEY, _OTHER_KEY])

    assert other._ui.treeKeys.header().sectionSize(0) == 321


def test_set_keys_still_auto_sizes_columns_when_nothing_was_restored(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    # A plain resize, never fed through restore_column_widths().
    view._ui.treeKeys.header().resizeSection(0, 321)

    view.set_keys([_MY_KEY, _OTHER_KEY])

    # Without an explicit restore_column_widths() call, a refresh is still
    # free to auto-size columns to content — only a genuinely restored
    # width is protected from that.
    assert view._ui.treeKeys.header().sectionSize(0) != 321


# ── Signatures tab ────────────────────────────────────────────────────────

_SIGNATURES_TAB_INDEX = 1


def test_signatures_not_requested_while_details_tab_is_active(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    seen = []
    view.signaturesRequested.connect(seen.append)

    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    assert seen == []


def test_switching_to_signatures_tab_requests_signatures_for_selected_key(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    seen = []
    view.signaturesRequested.connect(seen.append)

    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    assert seen == [_MY_KEY.fingerprint]
    tree = view._ui.treeSignatures
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(0) == "Loading…"


def test_changing_selection_while_on_signatures_tab_requests_fresh_signatures(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    seen = []
    view.signaturesRequested.connect(seen.append)

    # setCurrentItem() (not setSelected()) — QTreeWidgetItem.setSelected()
    # bypasses SingleSelection's exclusivity, leaving both keys selected.
    view._ui.treeKeys.setCurrentItem(view._ui.treeKeys.topLevelItem(1).child(0))

    assert seen == [_OTHER_KEY.fingerprint]


def test_set_key_signatures_renders_known_and_unknown_signers(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    signatures = [
        KeySignature(
            keyid=_OTHER_KEY.keyid,
            fingerprint=_OTHER_KEY.fingerprint,
            key=_OTHER_KEY,
        ),
        KeySignature(keyid="1234567890ABCDEF", fingerprint=None, key=None),
    ]
    view.set_key_signatures(_MY_KEY.fingerprint, signatures)

    tree = view._ui.treeSignatures
    assert tree.topLevelItemCount() == 2
    known_row = tree.topLevelItem(0)
    assert known_row.text(0) == "Bob Example"
    assert known_row.text(1) == "bob@example.com"
    assert known_row.text(2) == _OTHER_KEY.keyid
    unknown_row = tree.topLevelItem(1)
    assert unknown_row.text(0) == "Unknown locally"
    assert unknown_row.text(1) == ""
    assert unknown_row.text(2) == "1234567890ABCDEF"
    assert view._ui.btnDownloadUnknownSignatures.isEnabled()


def test_set_key_signatures_disables_download_button_when_all_known(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    view.set_key_signatures(
        _MY_KEY.fingerprint,
        [KeySignature(keyid=_OTHER_KEY.keyid, fingerprint=None, key=_OTHER_KEY)],
    )

    assert not view._ui.btnDownloadUnknownSignatures.isEnabled()


def test_set_key_signatures_ignores_a_result_for_a_stale_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)

    # A slow fetch for a key that's no longer selected must not clobber
    # what's shown for the (now different) current selection.
    view.set_key_signatures(
        _OTHER_KEY.fingerprint,
        [KeySignature(keyid=_OTHER_KEY.keyid, fingerprint=None, key=_OTHER_KEY)],
    )

    tree = view._ui.treeSignatures
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(0) == "Loading…"


def test_clicking_download_button_emits_only_unknown_identifiers(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    view.set_key_signatures(
        _MY_KEY.fingerprint,
        [
            KeySignature(keyid=_OTHER_KEY.keyid, fingerprint=None, key=_OTHER_KEY),
            KeySignature(
                keyid="1234567890ABCDEF",
                fingerprint="FFFFEEEEDDDDCCCCBBBBAAAA1111222233334444",
                key=None,
            ),
            KeySignature(keyid="FEDCBA9876543210", fingerprint=None, key=None),
        ],
    )
    seen = []
    view.downloadUnknownSignaturesRequested.connect(seen.append)

    view._ui.btnDownloadUnknownSignatures.click()

    assert seen == [["FFFFEEEEDDDDCCCCBBBBAAAA1111222233334444", "FEDCBA9876543210"]]


def test_clicking_download_button_does_nothing_when_no_unknown_signer(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    view.set_key_signatures(_MY_KEY.fingerprint, [])
    seen = []
    view.downloadUnknownSignaturesRequested.connect(seen.append)

    view._ui.btnDownloadUnknownSignatures.click()

    assert seen == []


def test_deselecting_resets_the_signatures_tab(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    item = view._ui.treeKeys.topLevelItem(0).child(0)
    item.setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    view.set_key_signatures(
        _MY_KEY.fingerprint,
        [KeySignature(keyid="1234567890ABCDEF", fingerprint=None, key=None)],
    )

    item.setSelected(False)

    assert view._ui.treeSignatures.topLevelItemCount() == 0
    assert not view._ui.btnDownloadUnknownSignatures.isEnabled()


def test_clear_signatures_resets_the_tab(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.tabDetail.setCurrentIndex(_SIGNATURES_TAB_INDEX)
    view.set_key_signatures(
        _MY_KEY.fingerprint,
        [KeySignature(keyid="1234567890ABCDEF", fingerprint=None, key=None)],
    )

    view.clear_signatures()

    assert view._ui.treeSignatures.topLevelItemCount() == 0
    assert not view._ui.btnDownloadUnknownSignatures.isEnabled()


def test_signatures_tab_widgets_have_whats_this_text(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)

    assert view._ui.treeSignatures.whatsThis() != ""
    assert view._ui.btnDownloadUnknownSignatures.whatsThis() != ""


# ── Multi-key selection ─────────────────────────────────────────────────


def _select_both(view):
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)


def test_key_list_allows_extended_selection(qtbot):
    from PySide6.QtWidgets import QAbstractItemView

    view = KeyListView()
    qtbot.addWidget(view)

    assert (
        view._ui.treeKeys.selectionMode()
        == QAbstractItemView.SelectionMode.ExtendedSelection
    )


def test_several_selected_keys_report_no_single_selected_key(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])

    _select_both(view)

    assert view.selected_key() is None
    assert view.selected_keys() == [_MY_KEY, _OTHER_KEY]


def test_several_selected_keys_empty_the_detail_panel(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)
    view._ui.treeSubkeys.topLevelItem(0).setSelected(True)
    assert view.selected_subkey() is _SUBKEY

    view._ui.treeKeys.topLevelItem(1).child(0).setSelected(True)

    ui = view._ui
    assert ui.stackDetail.currentWidget() is ui.lblNoSelection
    assert ui.lblNoSelection.text() == "2 keys selected."
    assert ui.treeSubkeys.topLevelItemCount() == 0
    assert ui.lstUids.count() == 0
    assert ui.lblFingerprint.text() == ""
    assert view.selected_subkey() is None
    assert view.selected_uid() is None


def test_placeholder_text_goes_back_to_the_prompt_when_deselected(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    _select_both(view)

    view._ui.treeKeys.clearSelection()

    assert view._ui.lblNoSelection.text() == "Select a key to see its details."


def test_several_selected_keys_do_not_request_signatures(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view._ui.tabDetail.setCurrentIndex(1)
    requested = []
    view.signaturesRequested.connect(requested.append)

    _select_both(view)

    assert requested == [_MY_KEY.fingerprint]
    assert view._ui.treeSignatures.topLevelItemCount() == 0


def test_select_keys_selects_every_given_fingerprint(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    seen = []
    view.selectionChanged.connect(lambda: seen.append(True))

    view.select_keys([_MY_KEY.fingerprint, _OTHER_KEY.fingerprint, "0" * 40])

    assert view.selected_keys() == [_MY_KEY, _OTHER_KEY]
    assert len(seen) == 1


def test_sorting_keeps_a_multi_key_selection(qtbot):
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([*_SORTABLE_KEYS, _OTHER_KEY])
    view.select_keys([_KEY_CHARLIE.fingerprint, _OTHER_KEY.fingerprint])

    view._on_header_section_clicked(0)

    assert {k.fingerprint for k in view.selected_keys()} == {
        _KEY_CHARLIE.fingerprint,
        _OTHER_KEY.fingerprint,
    }


def test_context_menu_on_a_selected_row_keeps_the_multi_selection(qtbot, monkeypatch):
    monkeypatch.setattr(KeyListView, "_exec_menu", lambda self, menu, pos: None)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view.set_key_actions([QAction("Do key thing")])
    _select_both(view)

    item = view._ui.treeKeys.topLevelItem(1).child(0)
    view._show_key_context_menu(view._ui.treeKeys.visualItemRect(item).center())

    assert view.selected_keys() == [_MY_KEY, _OTHER_KEY]


def test_context_menu_on_an_unselected_row_selects_only_it(qtbot, monkeypatch):
    monkeypatch.setattr(KeyListView, "_exec_menu", lambda self, menu, pos: None)
    view = KeyListView()
    qtbot.addWidget(view)
    view.set_keys([_MY_KEY, _OTHER_KEY])
    view.set_key_actions([QAction("Do key thing")])
    view._ui.treeKeys.topLevelItem(0).child(0).setSelected(True)

    item = view._ui.treeKeys.topLevelItem(1).child(0)
    view._show_key_context_menu(view._ui.treeKeys.visualItemRect(item).center())

    assert view.selected_keys() == [_OTHER_KEY]
