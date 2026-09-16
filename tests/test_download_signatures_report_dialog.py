"""Tests for the Download Unknown Keys report dialog."""

from __future__ import annotations

from pbnightingale.core.gpg_backend import DownloadedSignature, Key, Uid
from pbnightingale.ui.download_signatures_report_dialog import (
    DownloadSignaturesReportDialog,
)

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


def test_summary_reports_no_unknown_key_when_the_list_is_empty(qtbot):
    dialog = DownloadSignaturesReportDialog([])
    qtbot.addWidget(dialog)

    assert "No unknown key" in dialog._ui.lblSummary.text()
    assert dialog._ui.downloadedList.count() == 0
    assert dialog._ui.notFoundList.count() == 0


def test_summary_lists_downloaded_and_not_found_keys_separately(qtbot):
    dialog = DownloadSignaturesReportDialog(
        [
            DownloadedSignature(_KEY_A.fingerprint, _KEY_A),
            DownloadedSignature("DEADBEEFDEADBEEF", None),
        ]
    )
    qtbot.addWidget(dialog)

    assert "1" in dialog._ui.lblSummary.text()
    assert "2" in dialog._ui.lblSummary.text()
    assert dialog._ui.downloadedList.count() == 1
    assert "alice@example.com" in dialog._ui.downloadedList.item(0).text()
    assert dialog._ui.notFoundList.count() == 1
    assert dialog._ui.notFoundList.item(0).text() == "DEADBEEFDEADBEEF"


def test_accept_sets_the_dialog_result(qtbot):
    dialog = DownloadSignaturesReportDialog([])
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    assert dialog.result() == DownloadSignaturesReportDialog.DialogCode.Accepted
