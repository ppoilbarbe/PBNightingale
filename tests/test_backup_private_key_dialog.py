"""Tests for the Back Up Private Key dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, GPGBackendError, Key, Uid
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.backup_private_key_dialog import BackupPrivateKeyDialog

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

_ARMORED = (
    "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----\n"
)


def _choose_destination(monkeypatch, path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )


def test_warning_mentions_the_key_id(qtbot):
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    assert _FAKE_KEY.keyid in dialog._ui.lblWarning.text()


def test_suggested_destination_defaults_under_the_home_directory(qtbot, monkeypatch):
    seen = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (seen.append(a[2]), ("", ""))[1]),
    )
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    assert seen[0] == str(Path.home() / f"{_FAKE_KEY.fingerprint}-secret.asc")


def test_cancelling_the_file_dialog_does_not_run_the_backend(qtbot, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    calls = []

    class _FakeBackend:
        def export_secret_key(self, fingerprint, passphrase):
            calls.append(fingerprint)
            return _ARMORED

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    assert calls == []


def test_backup_writes_the_chosen_file(qtbot, monkeypatch, tmp_path):
    destination = tmp_path / "secret.asc"
    _choose_destination(monkeypatch, destination)

    class _FakeBackend:
        def export_secret_key(self, fingerprint, passphrase):
            return _ARMORED

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: destination.exists())
    assert destination.read_text(encoding="utf-8") == _ARMORED


def test_successful_backup_caches_the_passphrase(qtbot, monkeypatch, tmp_path):
    destination = tmp_path / "secret.asc"
    _choose_destination(monkeypatch, destination)

    class _FakeBackend:
        def export_secret_key(self, fingerprint, passphrase):
            return _ARMORED

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)
    dialog._ui.txtPassphrase.setText("s3cret")

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: destination.exists())
    assert passphrase_cache.get(_FAKE_KEY.fingerprint) == Passphrase("s3cret")


def test_prefills_passphrase_from_the_cache(qtbot):
    passphrase_cache.store(_FAKE_KEY.fingerprint, Passphrase("cached-pass"), 60)

    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    assert dialog._ui.txtPassphrase.text() == "cached-pass"


def test_backup_reports_backend_failure_and_reenables_form(
    qtbot, monkeypatch, tmp_path
):
    _choose_destination(monkeypatch, tmp_path / "secret.asc")

    class _FailingBackend:
        def export_secret_key(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtPassphrase.isEnabled() is True


def test_backup_bad_passphrase_shows_friendly_message(qtbot, monkeypatch, tmp_path):
    _choose_destination(monkeypatch, tmp_path / "secret.asc")

    class _FailingBackend:
        def export_secret_key(self, *args, **kwargs):
            raise BadPassphraseError("[GNUPG:] ERROR export_secret 67108875")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(
        lambda: "Incorrect primary key passphrase" in dialog._ui.lblStatus.text()
    )
    assert "GNUPG" not in dialog._ui.lblStatus.text()


def test_backup_reports_write_failure_and_reenables_form(qtbot, monkeypatch, tmp_path):
    # A directory as the destination makes write_text() raise OSError.
    _choose_destination(monkeypatch, tmp_path)

    class _FakeBackend:
        def export_secret_key(self, fingerprint, passphrase):
            return _ARMORED

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = BackupPrivateKeyDialog(_FAKE_KEY)
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "Could not write file" in dialog._ui.lblStatus.text())
    assert dialog._ui.txtPassphrase.isEnabled() is True
