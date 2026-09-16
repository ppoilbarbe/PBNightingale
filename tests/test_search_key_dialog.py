"""Tests for the Search Keyserver dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import (
    DEFAULT_KEYSERVER,
    GPGBackendError,
    ImportedKey,
    Key,
    SearchResult,
    Uid,
)
from pbnightingale.ui.search_key_dialog import SearchKeyDialog

_FOUND_RESULT = SearchResult(
    fingerprint="AAAA111122223333444455556666777788889999",
    uids=["Alice Example <alice@example.com>"],
    algo="1",
    length=4096,
    created=1_700_000_000,
)

_IMPORTED_KEY = ImportedKey(
    key=Key(
        fingerprint="AAAA111122223333444455556666777788889999",
        keyid="4444555566667777",
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


def test_keyserver_field_prefilled_with_the_default(qtbot):
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.txtKeyserver.text() == DEFAULT_KEYSERVER


def test_keyserver_hint_shown_only_for_the_default_keyserver(qtbot):
    # isHidden() (not isVisible(), which also depends on the whole ancestor
    # chain being shown on screen) reflects this widget's own visibility
    # flag regardless of whether the dialog itself is shown.
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)

    assert dialog._ui.lblKeyserverHint.isHidden() is False

    dialog._ui.txtKeyserver.setText("hkps://my-own-server.example")

    assert dialog._ui.lblKeyserverHint.isHidden() is True

    dialog._ui.txtKeyserver.setText(DEFAULT_KEYSERVER)

    assert dialog._ui.lblKeyserverHint.isHidden() is False


def test_import_button_disabled_until_a_result_is_selected(qtbot):
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)

    assert dialog._ok_button.isEnabled() is False


def test_search_requires_a_query_first(qtbot):
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)

    dialog._ui.btnSearch.click()

    assert "Enter a search query" in dialog._ui.lblStatus.text()


def test_search_populates_results_and_selecting_enables_import(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def search_keyserver(self, query, keyserver):
            calls.append((query, keyserver))
            return [_FOUND_RESULT]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("alice")

    dialog._ui.btnSearch.click()

    qtbot.waitUntil(lambda: dialog._ui.resultsList.count() == 1)
    assert calls == [("alice", DEFAULT_KEYSERVER)]
    assert "alice@example.com" in dialog._ui.resultsList.item(0).text()

    dialog._ui.resultsList.setCurrentRow(0)

    assert dialog._ok_button.isEnabled() is True


def test_pressing_enter_in_the_query_field_launches_the_search(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def search_keyserver(self, query, keyserver):
            calls.append((query, keyserver))
            return [_FOUND_RESULT]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)
    # The dialog (and its buttons) must actually be shown: QDialogButtonBox
    # only auto-promotes a disabled default button to another visible one —
    # the bug this guards against — once the buttons are realized on screen.
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog._ui.txtQuery.setText("alice")

    qtbot.keyClick(dialog._ui.txtQuery, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: dialog._ui.resultsList.count() == 1)
    assert calls == [("alice", DEFAULT_KEYSERVER)]
    # Return must trigger the search, not the "Cancel" button that
    # QDialogButtonBox promotes to default while "Import" is disabled.
    assert dialog.isVisible() is True


def test_search_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def search_keyserver(self, query, keyserver):
            raise GPGBackendError("no keys found")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("nobody")

    dialog._ui.btnSearch.click()

    qtbot.waitUntil(lambda: "no keys found" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtQuery.isEnabled() is True


def test_import_succeeds_with_mocked_backend(qtbot, monkeypatch):
    import_calls = []

    class _FakeBackend:
        def search_keyserver(self, query, keyserver):
            return [_FOUND_RESULT]

        def import_from_keyserver(self, query, keyserver):
            import_calls.append((query, keyserver))
            return [_IMPORTED_KEY]

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("alice")
    dialog._ui.btnSearch.click()
    qtbot.waitUntil(lambda: dialog._ui.resultsList.count() == 1)
    dialog._ui.resultsList.setCurrentRow(0)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.imported_keys == [_IMPORTED_KEY])
    assert import_calls == [(_FOUND_RESULT.fingerprint, DEFAULT_KEYSERVER)]


def test_import_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FakeBackend:
        def search_keyserver(self, query, keyserver):
            return [_FOUND_RESULT]

        def import_from_keyserver(self, query, keyserver):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)
    dialog._ui.txtQuery.setText("alice")
    dialog._ui.btnSearch.click()
    qtbot.waitUntil(lambda: dialog._ui.resultsList.count() == 1)
    dialog._ui.resultsList.setCurrentRow(0)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtQuery.isEnabled() is True
    assert dialog.imported_keys == []


def test_status_label_text_is_selectable(qtbot):
    dialog = SearchKeyDialog()
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
