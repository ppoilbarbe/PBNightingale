"""Tests for the Set Owner Trust dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import GPGBackendError, Key, Uid
from pbnightingale.ui.set_owner_trust_dialog import SetOwnerTrustDialog

_FAKE_KEY = Key(
    fingerprint="AAAA111122223333444455556666777788889999",
    keyid="4444555566667777",
    algo="1",
    length=4096,
    created=1_700_000_000,
    expires=None,
    trust="-",
    owner_trust="m",
    uids=[Uid("Alice Example <alice@example.com>", revoked=False)],
    photos=[],
    subkeys=[],
    has_secret=False,
    can_sign=True,
    can_encrypt=True,
    can_certify=True,
    can_authenticate=False,
)


def test_explanation_mentions_the_uid(qtbot):
    dialog = SetOwnerTrustDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    assert _FAKE_KEY.uids[0].value in dialog._ui.lblExplanation.text()


def test_preselects_the_keys_current_owner_trust(qtbot):
    dialog = SetOwnerTrustDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbOwnerTrust.currentData() == "marginal"


def test_defaults_to_undefined_for_an_unknown_code(qtbot):
    unknown_key = Key(**{**_FAKE_KEY.__dict__, "owner_trust": ""})

    dialog = SetOwnerTrustDialog([unknown_key])
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbOwnerTrust.currentData() == "undefined"


def test_set_succeeds_with_mocked_backend(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_owner_trust(self, fingerprint, trust):
            calls.append((fingerprint, trust))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetOwnerTrustDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)
    idx = dialog._ui.cmbOwnerTrust.findData("full")
    dialog._ui.cmbOwnerTrust.setCurrentIndex(idx)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is _FAKE_KEY)
    assert calls[0] == (_FAKE_KEY.fingerprint, "full")


def test_reports_backend_failure_and_reenables_form(qtbot, monkeypatch):
    class _FailingBackend:
        def set_owner_trust(self, *args, **kwargs):
            raise GPGBackendError("boom")

    monkeypatch.setattr(gpg_backend, "default_backend", _FailingBackend)
    dialog = SetOwnerTrustDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: "boom" in dialog._ui.lblStatus.text())
    assert dialog._ui.cmbOwnerTrust.isEnabled() is True
    assert dialog.updated_key is None


def test_status_label_text_is_selectable(qtbot):
    dialog = SetOwnerTrustDialog([_FAKE_KEY])
    qtbot.addWidget(dialog)

    flags = dialog._ui.lblStatus.textInteractionFlags()

    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse


_OTHER_KEY = Key(
    **{
        **_FAKE_KEY.__dict__,
        "fingerprint": "BBBB111122223333444455556666777788889999",
        "keyid": "5555666677778888",
    }
)


def test_explanation_lists_every_key_id_for_several_keys(qtbot):
    dialog = SetOwnerTrustDialog([_FAKE_KEY, _OTHER_KEY])
    qtbot.addWidget(dialog)

    text = dialog._ui.lblExplanation.text()
    assert "2 keys" in text
    assert _FAKE_KEY.keyid in text
    assert _OTHER_KEY.keyid in text


def test_preselects_a_shared_owner_trust_for_several_keys(qtbot):
    dialog = SetOwnerTrustDialog([_FAKE_KEY, _OTHER_KEY])
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbOwnerTrust.currentData() == "marginal"


def test_preselects_undefined_for_several_keys_with_differing_owner_trust(qtbot):
    full_key = Key(**{**_OTHER_KEY.__dict__, "owner_trust": "f"})

    dialog = SetOwnerTrustDialog([_FAKE_KEY, full_key])
    qtbot.addWidget(dialog)

    assert dialog._ui.cmbOwnerTrust.currentData() == "undefined"


def test_set_applies_the_same_trust_to_every_key(qtbot, monkeypatch):
    calls = []

    class _FakeBackend:
        def set_owner_trust(self, fingerprint, trust):
            calls.append((fingerprint, trust))
            return _FAKE_KEY

    monkeypatch.setattr(gpg_backend, "default_backend", _FakeBackend)
    dialog = SetOwnerTrustDialog([_FAKE_KEY, _OTHER_KEY])
    qtbot.addWidget(dialog)
    dialog._ui.cmbOwnerTrust.setCurrentIndex(dialog._ui.cmbOwnerTrust.findData("full"))

    dialog._ui.buttonBox.accepted.emit()

    qtbot.waitUntil(lambda: dialog.updated_key is not None)
    assert calls == [(_FAKE_KEY.fingerprint, "full"), (_OTHER_KEY.fingerprint, "full")]
