"""Tests for the Import Key dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QSizePolicy

from pbnightingale import preferences
from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import (
    GPGBackendError,
    ImportedKey,
    ImportPreview,
    Key,
    Uid,
)
from pbnightingale.ui.import_key_dialog import ImportKeyDialog

_NEW_CANDIDATE = ImportPreview(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    uids=["Alice Example <alice@example.com>"],
    is_new=True,
)

_EXISTING_CANDIDATE = ImportPreview(
    fingerprint="BBBB111122223333444455556666777788889999",
    keyid="5555666677778888",
    uids=["Bob Example <bob@example.com>"],
    is_new=False,
)

_IMPORTED_KEY = ImportedKey(
    key=Key(
        fingerprint=_NEW_CANDIDATE.fingerprint,
        keyid=_NEW_CANDIDATE.keyid,
        algo="1",
        length=4096,
        created=1_700_000_000,
        expires=None,
        trust="-",
        owner_trust="",
        uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
        photos=[],
        subkeys=[],
        has_secret=False,
        can_sign=True,
        can_encrypt=True,
        can_certify=True,
        can_authenticate=False,
    ),
    is_new=True,
)


def _tree_items(dialog):
    tree = dialog._ui.treeCandidates
    return [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]


def test_import_from_file_tab_requires_a_file_first(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)

    dialog._ui.btnCheck.click()

    assert "Choose a file" in dialog._ui.lblStatus.text()


def test_browse_sets_the_chosen_file_path(qtbot, monkeypatch, tmp_path):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(key_file), "")),
    )
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnBrowse.click()

    assert dialog._ui.txtFilePath.text() == str(key_file)


def test_cancelling_the_file_dialog_leaves_the_path_empty(qtbot, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnBrowse.click()

    assert dialog._ui.txtFilePath.text() == ""


def test_import_from_keyserver_tab_requires_a_query_first(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnCheck.click()

    assert "Enter a fingerprint" in dialog._ui.lblStatus.text()


def test_import_from_keyserver_tab_is_shown_first(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.tabs.currentIndex() == 0
    assert dialog._ui.tabs.tabText(0) == "From keyserver"
    assert dialog._ui.tabs.tabText(1) == "From file"


def test_tabs_have_a_fixed_vertical_size_policy(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.tabs.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed


def test_resizing_taller_grows_the_candidate_tree_not_the_tabs(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog.resize(520, 420)
    dialog.show()
    qtbot.waitExposed(dialog)
    tabs_height_before = dialog._ui.tabs.height()
    tree_height_before = dialog._ui.treeCandidates.height()

    dialog.resize(520, 800)
    qtbot.wait(0)

    assert dialog._ui.tabs.height() == tabs_height_before
    assert dialog._ui.treeCandidates.height() > tree_height_before


def test_check_from_file_populates_the_candidate_tree(qtbot, monkeypatch, tmp_path):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")
    calls = []

    class _FakeBackend:
        def preview_import_from_file(self, path):
            calls.append(path)
            return [_NEW_CANDIDATE]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))

    dialog._ui.btnCheck.click()

    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 1)
    assert calls == [str(key_file)]
    item = _tree_items(dialog)[0]
    assert item.text(0) == "Alice Example <alice@example.com>"
    assert item.text(1) == _NEW_CANDIDATE.keyid
    assert item.text(3) == ""  # new key: no "already in keyring" status
    assert dialog._ui.tabs.isEnabled() is False
    assert dialog._ui.btnCheck.isEnabled() is False


def test_new_candidate_defaults_unchecked_existing_candidate_defaults_checked(
    qtbot, monkeypatch, tmp_path
):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")

    class _FakeBackend:
        def preview_import_from_file(self, path):
            return [_NEW_CANDIDATE, _EXISTING_CANDIDATE]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))

    dialog._ui.btnCheck.click()

    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 2)
    new_item, existing_item = _tree_items(dialog)
    assert new_item.checkState(0) == Qt.CheckState.Unchecked
    assert existing_item.checkState(0) == Qt.CheckState.Checked
    assert existing_item.text(3) == "Already in keyring"


def test_import_button_disabled_until_a_candidate_is_checked(
    qtbot, monkeypatch, tmp_path
):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")

    class _FakeBackend:
        def preview_import_from_file(self, path):
            return [_NEW_CANDIDATE]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))

    dialog._ui.btnCheck.click()
    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 1)

    assert dialog._ok_button.isEnabled() is False

    _tree_items(dialog)[0].setCheckState(0, Qt.CheckState.Checked)

    assert dialog._ok_button.isEnabled() is True

    _tree_items(dialog)[0].setCheckState(0, Qt.CheckState.Unchecked)

    assert dialog._ok_button.isEnabled() is False


def test_import_from_file_commits_only_checked_fingerprints(
    qtbot, monkeypatch, tmp_path
):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")
    commit_calls = []

    class _FakeBackend:
        def preview_import_from_file(self, path):
            return [_NEW_CANDIDATE, _EXISTING_CANDIDATE]

        def commit_import_from_file(self, path, approved):
            commit_calls.append((path, approved))
            return [_IMPORTED_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))
    dialog._ui.btnCheck.click()
    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 2)
    new_item, existing_item = _tree_items(dialog)
    new_item.setCheckState(0, Qt.CheckState.Checked)
    existing_item.setCheckState(0, Qt.CheckState.Unchecked)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.imported_keys == [_IMPORTED_KEY])
    assert commit_calls == [
        (str(key_file), {_NEW_CANDIDATE.fingerprint}),
    ]


def test_import_from_keyserver_check_then_commit(qtbot, monkeypatch):
    preview_calls = []
    commit_calls = []
    preferences.set_keyservers([("hkps://a.example", True), ("hkps://b.example", True)])

    class _FakeBackend:
        def preview_import_from_keyservers(self, query, keyservers):
            preview_calls.append((query, keyservers))
            return [_NEW_CANDIDATE]

        def commit_import_from_keyservers(self, query, keyservers, approved):
            commit_calls.append((query, keyservers, approved))
            return [_IMPORTED_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("alice@example.com")

    dialog._ui.btnCheck.click()

    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 1)
    assert preview_calls == [
        ("alice@example.com", ["hkps://a.example", "hkps://b.example"])
    ]
    _tree_items(dialog)[0].setCheckState(0, Qt.CheckState.Checked)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.imported_keys == [_IMPORTED_KEY])
    assert commit_calls == [
        (
            "alice@example.com",
            ["hkps://a.example", "hkps://b.example"],
            {_NEW_CANDIDATE.fingerprint},
        )
    ]


def test_import_from_keyserver_requires_at_least_one_checked_server(qtbot):
    preferences.set_keyservers(
        [("hkps://a.example", False), ("hkps://b.example", False)]
    )
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("alice@example.com")

    dialog._ui.btnCheck.click()

    assert "No keyserver is checked" in dialog._ui.lblStatus.text()
    assert dialog._ui.treeCandidates.topLevelItemCount() == 0


def test_check_reports_backend_failure_and_resets_to_editing(
    qtbot, monkeypatch, tmp_path
):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")

    class _FailingBackend:
        def preview_import_from_file(self, path):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))

    dialog._ui.btnCheck.click()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.tabs.isEnabled() is True
    assert dialog._ui.btnCheck.isEnabled() is True
    assert dialog._ui.treeCandidates.topLevelItemCount() == 0
    assert dialog._ok_button.isEnabled() is False
    assert dialog.imported_keys == []


def test_import_reports_backend_failure_and_resets_to_editing(
    qtbot, monkeypatch, tmp_path
):
    key_file = tmp_path / "key.asc"
    key_file.write_text("dummy")

    class _FailingBackend:
        def preview_import_from_file(self, path):
            return [_NEW_CANDIDATE]

        def commit_import_from_file(self, path, approved):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.tabs.setCurrentIndex(1)
    dialog._ui.txtFilePath.setText(str(key_file))
    dialog._ui.btnCheck.click()
    qtbot.waitUntil(lambda: dialog._ui.treeCandidates.topLevelItemCount() == 1)
    _tree_items(dialog)[0].setCheckState(0, Qt.CheckState.Checked)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.tabs.isEnabled() is True
    assert dialog._ui.treeCandidates.topLevelItemCount() == 0
    assert dialog._ok_button.isEnabled() is False
    assert dialog.imported_keys == []


def test_status_label_text_is_selectable(qtbot):
    dialog = ImportKeyDialog()
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
