"""Tests for the Refresh Keys report dialog."""

from __future__ import annotations

from pbnightingale.core.gpg_backend import Key, RefreshedKey, Uid
from pbnightingale.ui.refresh_keys_report_dialog import RefreshKeysReportDialog

_KEY_A = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="u",
    owner_trust="",
    uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=True,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)

_KEY_B = Key(
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


def test_summary_reports_nothing_new_when_no_key_was_updated(qtbot):
    dialog = RefreshKeysReportDialog(
        [
            RefreshedKey(key=_KEY_A, updated=False),
            RefreshedKey(key=_KEY_B, updated=False),
        ]
    )
    qtbot.addWidget(dialog)

    assert "nothing new" in dialog._ui.lblSummary.text()
    assert dialog._ui.updatedList.count() == 0


def test_summary_lists_only_the_updated_keys(qtbot):
    dialog = RefreshKeysReportDialog(
        [
            RefreshedKey(key=_KEY_A, updated=True),
            RefreshedKey(key=_KEY_B, updated=False),
        ]
    )
    qtbot.addWidget(dialog)

    assert "1" in dialog._ui.lblSummary.text()
    assert "2" in dialog._ui.lblSummary.text()
    assert dialog._ui.updatedList.count() == 1
    assert "alice@example.com" in dialog._ui.updatedList.item(0).text()


def test_accept_sets_the_dialog_result(qtbot):
    dialog = RefreshKeysReportDialog([])
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    assert dialog.result() == RefreshKeysReportDialog.DialogCode.Accepted
