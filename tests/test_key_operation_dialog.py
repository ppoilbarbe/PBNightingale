"""Tests for the KeyOperationDialog mixin in isolation from any real
dialog. Each real add/set/revoke dialog's own test file also carries one
light integration test confirming it's actually wired up correctly.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
)

from pbnightingale import preferences
from pbnightingale.core import passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog

_FAKE_KEY = Key(
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


class _DummyDialog(KeyOperationDialog, QDialog):
    """The minimal shape KeyOperationDialog needs from a host dialog."""

    def __init__(self, fingerprint, call, parent=None) -> None:
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._call = call

        class _Ui:
            pass

        self._ui = _Ui()
        self._ui.txtPassphrase = QLineEdit(self)
        self._ui.progress = QProgressBar(self)
        self._ui.progress.setVisible(False)
        self._ui.lblStatus = QLabel(self)
        self._ui.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        layout = QVBoxLayout(self)
        for widget in (
            self._ui.txtPassphrase,
            self._ui.progress,
            self._ui.lblStatus,
            self._ui.buttonBox,
        ):
            layout.addWidget(widget)

        self._init_key_operation()
        self._ui.buttonBox.accepted.connect(self._on_accept)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_accept(self) -> None:
        self._run_operation(
            self._call, busy_text="Working…", error_template="Failed: {error}"
        )


class _DummyPassphraselessDialog(KeyOperationDialog, QDialog):
    """A host dialog whose operation needs no passphrase at all (e.g.
    ``DeleteKeyDialog``) — ``_passphrase_line_edit()`` returns ``None``.
    """

    def __init__(self, call, parent=None) -> None:
        super().__init__(parent)
        self._call = call

        class _Ui:
            pass

        self._ui = _Ui()
        self._ui.progress = QProgressBar(self)
        self._ui.progress.setVisible(False)
        self._ui.lblStatus = QLabel(self)
        self._ui.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        layout = QVBoxLayout(self)
        for widget in (self._ui.progress, self._ui.lblStatus, self._ui.buttonBox):
            layout.addWidget(widget)

        self._init_key_operation()
        self._ui.buttonBox.accepted.connect(self._on_accept)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _passphrase_line_edit(self):
        return None

    def _set_form_enabled(self, enabled: bool) -> None:
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_accept(self) -> None:
        self._run_operation(
            self._call, busy_text="Working…", error_template="Failed: {error}"
        )


def test_passphraseless_dialog_runs_the_operation_without_a_passphrase_field(qtbot):
    dialog = _DummyPassphraselessDialog(lambda: None)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted)


def test_passphraseless_dialog_caches_nothing_on_success(qtbot):
    passphrase_cache.clear()
    dialog = _DummyPassphraselessDialog(lambda: None)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) is None


def test_prefills_passphrase_field_from_the_cache(qtbot):
    passphrase_cache.store(_FAKE_KEY.fingerprint, Passphrase("cached-pass"), 60)

    dialog = _DummyDialog(_FAKE_KEY.fingerprint, lambda: _FAKE_KEY)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == "cached-pass"


def test_passphrase_field_empty_when_nothing_cached(qtbot):
    dialog = _DummyDialog(_FAKE_KEY.fingerprint, lambda: _FAKE_KEY)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == ""


def test_successful_operation_caches_the_passphrase(qtbot):
    dialog = _DummyDialog(_FAKE_KEY.fingerprint, lambda: _FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("s3cret")


def test_failed_operation_does_not_cache_the_passphrase(qtbot):
    def _fail():
        raise GPGBackendError("boom")

    dialog = _DummyDialog(_FAKE_KEY.fingerprint, _fail)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("wrong-guess")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) is None


def test_empty_passphrase_is_not_cached_on_success(qtbot):
    dialog = _DummyDialog(_FAKE_KEY.fingerprint, lambda: _FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) is None


def test_zero_minute_preference_disables_caching(qtbot):
    preferences.set_passphrase_cache_minutes(0)
    dialog = _DummyDialog(_FAKE_KEY.fingerprint, lambda: _FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) is None


def test_default_bad_passphrase_message(qtbot):
    def _fail():
        raise BadPassphraseError("[GNUPG:] ERROR keysig 67108875")

    dialog = _DummyDialog(_FAKE_KEY.fingerprint, _fail)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_form_reenabled_and_progress_hidden_on_error(qtbot):
    def _fail():
        raise GPGBackendError("boom")

    dialog = _DummyDialog(_FAKE_KEY.fingerprint, _fail)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtPassphrase.isEnabled() is True
    assert dialog._ui.progress.isVisible() is False
