"""Tests for core.gpg_backend — always against an isolated GNUPGHOME."""

from __future__ import annotations

import os
import time
from datetime import date, datetime

import gnupg
import pytest

from pbnightingale.core import activity_log
from pbnightingale.core import gpg_backend as gpg_backend_module
from pbnightingale.core.gpg_backend import (
    BadPassphraseError,
    GPGBackend,
    GPGBackendError,
    NewKeyRequest,
)
from pbnightingale.core.secret import Passphrase
from tests.gpg_test_helpers import generate_test_key as _generate_key
from tests.gpg_test_helpers import make_large_test_jpeg, make_test_jpeg

_MISMATCH_STDERR = "[GNUPG:] WARNING server_version_mismatch 0"


def test_creates_gnupghome_directory(tmp_path):
    home = tmp_path / "gnupghome"

    backend = GPGBackend(home)

    assert home.is_dir()
    assert backend.home == str(home)
    if os.name == "posix":
        assert (home.stat().st_mode & 0o777) == 0o700


def test_list_keys_empty_on_fresh_keyring(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    assert backend.list_keys() == []
    assert backend.list_keys(secret=True) == []


def test_running_a_command_records_it_in_the_activity_log(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    backend.list_keys()

    commands = [entry.command for entry in activity_log.entries()]
    assert any("--list-keys" in command for command in commands)


def test_python_gnupg_mediated_calls_are_recorded_too(tmp_path):
    # Regression test: python-gnupg's own high-level methods (list_keys(),
    # search_keys(), recv_keys(), send_keys(), gen_key(), ...) spawn their
    # own subprocess internally, never through _traced_run()/_traced_popen()
    # — a real gap that made e.g. a keyserver search invisible in the
    # Activity window entirely. GPGBackend.list_keys() itself already goes
    # through _traced_run() calls (_load_photos()/_load_primary_uids()), so
    # this calls the underlying self._gpg.list_keys() directly to isolate
    # just the python-gnupg-mediated path (see gpg_backend._TracedGPG).
    backend = GPGBackend(tmp_path / "home")
    activity_log.reset()

    backend._gpg.list_keys()

    commands = [entry.command for entry in activity_log.entries()]
    assert any("--list-keys" in command for command in commands)


def test_traced_gpg_open_subprocess_records_before_delegating(tmp_path, monkeypatch):
    from pbnightingale.core.gpg_backend import _TracedGPG

    home = tmp_path / "home"
    home.mkdir()
    # Construct first, with the real _open_subprocess() still in place —
    # __init__ itself calls it once (to probe gpg's version), which a fake
    # returning None would break.
    gpg = _TracedGPG(gnupghome=str(home))

    calls = []
    monkeypatch.setattr(
        gnupg.GPG,
        "_open_subprocess",
        lambda self, args, passphrase=False: calls.append(args),
    )
    activity_log.reset()

    gpg._open_subprocess(
        ["--search-keys", "alice", "--keyserver", "hkps://example.org"]
    )

    # The real (here, faked) subprocess still gets spawned — recording is
    # additive, not a replacement for the actual call.
    assert calls == [["--search-keys", "alice", "--keyserver", "hkps://example.org"]]
    commands = [entry.command for entry in activity_log.entries()]
    assert any("--search-keys" in command for command in commands)


def test_list_keys_parses_generated_key(tmp_path):
    home = tmp_path / "home"
    fingerprint = _generate_key(home, with_subkey=True)
    backend = GPGBackend(home)

    keys = backend.list_keys()

    assert len(keys) == 1
    key = keys[0]
    assert key.fingerprint == fingerprint
    assert [uid.value for uid in key.uids] == ["Test User <test@example.com>"]
    assert key.uids[0].revoked is False
    assert key.algo == "1"
    assert key.length == 1024
    assert key.has_secret is True
    # gpg auto-assigns ultimate ownertrust to any key you hold the secret
    # part of, unless explicitly overridden — see set_owner_trust() tests.
    assert key.owner_trust == "u"
    assert key.can_certify is True
    assert key.can_sign is True
    # gpg's `cap` field on the "pub" record is a whole-key aggregate: it
    # reports encrypt as usable because a subkey provides it, even though
    # the primary key's own usage was cert,sign only.
    assert key.can_encrypt is True

    assert len(key.subkeys) == 1
    subkey = key.subkeys[0]
    assert subkey.length == 1024
    assert subkey.can_encrypt is True
    assert subkey.can_sign is False


def test_list_keys_secret_returns_only_secret_entries(tmp_path):
    home = tmp_path / "home"
    fingerprint = _generate_key(home)
    backend = GPGBackend(home)

    secret_keys = backend.list_keys(secret=True)

    assert [k.fingerprint for k in secret_keys] == [fingerprint]
    assert secret_keys[0].has_secret is True


def test_has_secret_is_false_for_public_only_key(tmp_path):
    source_home = tmp_path / "source"
    _generate_key(source_home)
    source_gpg = gnupg.GPG(gnupghome=str(source_home))
    armored_public = source_gpg.export_keys(source_gpg.list_keys()[0]["fingerprint"])

    dest_home = tmp_path / "dest"
    backend = GPGBackend(dest_home)
    import_result = gnupg.GPG(gnupghome=str(dest_home)).import_keys(armored_public)
    assert import_result.count == 1

    keys = backend.list_keys()

    assert len(keys) == 1
    assert keys[0].has_secret is False


def test_version_is_a_tuple_of_ints(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    version = backend.version

    assert isinstance(version, tuple)
    assert all(isinstance(part, int) for part in version)


def test_invalid_gpgbinary_raises_gpgbackenderror(tmp_path):
    with pytest.raises(GPGBackendError):
        GPGBackend(tmp_path / "home", gpgbinary="/nonexistent/gpg")


def test_generate_key_defaults_to_cert_only_primary_with_two_subkeys(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(name="Alice Example", email="alice@example.com", key_length=1024)
    )

    assert [uid.value for uid in key.uids] == ["Alice Example <alice@example.com>"]
    assert key.has_secret is True
    assert len(key.subkeys) == 2
    usages = {sub.can_sign: sub for sub in key.subkeys}
    assert usages[True].can_encrypt is False
    assert usages[False].can_encrypt is True
    # Whole-key `cap` aggregate: True because a subkey provides each usage.
    assert key.can_sign is True
    assert key.can_encrypt is True
    assert key.can_certify is True


def test_generate_key_without_subkeys_uses_primary_for_all_usages(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(
            name="Bob Example",
            email="bob@example.com",
            key_length=1024,
            signing_subkey=False,
            encryption_subkey=False,
        )
    )

    assert key.subkeys == []
    assert key.can_certify is True
    assert key.can_sign is True
    assert key.can_encrypt is True


def test_generate_key_with_passphrase_succeeds(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(
            name="Carol Example",
            email="carol@example.com",
            key_length=1024,
            passphrase=Passphrase("s3cret-pass"),
        )
    )

    assert len(key.subkeys) == 2


def test_generate_key_raises_when_gen_key_fails(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeResult:
        fingerprint = ""
        stderr = "boom"

    monkeypatch.setattr(gnupg.GPG, "gen_key", lambda self, input_data: _FakeResult())

    with pytest.raises(GPGBackendError, match="boom"):
        backend.generate_key(NewKeyRequest(name="Test User", email="test@example.com"))


def test_generate_key_raises_when_subkey_creation_fails(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeSubkeyResult:
        fingerprint = ""
        stderr = "bad subkey"

        def __bool__(self) -> bool:
            return False

    monkeypatch.setattr(
        gnupg.GPG, "add_subkey", lambda self, **kwargs: _FakeSubkeyResult()
    )

    with pytest.raises(GPGBackendError, match="bad subkey"):
        backend.generate_key(
            NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
        )


def test_generate_key_ed25519_defaults_to_dedicated_subkeys(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(
            name="Alice Example", email="alice@example.com", algorithm="ED25519"
        )
    )

    assert key.algo == "22"  # EdDSA
    assert len(key.subkeys) == 2
    by_usage = {sub.can_encrypt: sub for sub in key.subkeys}
    assert by_usage[True].algo == "18"  # ECDH (Curve25519)
    assert by_usage[False].algo == "22"  # EdDSA


def test_generate_key_ed25519_forces_encryption_subkey_even_if_unchecked(tmp_path):
    # EdDSA cannot itself encrypt: unlike RSA, unchecking "encryption
    # subkey" cannot fold that usage into the primary key.
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(
            name="Bob Example",
            email="bob@example.com",
            algorithm="ED25519",
            signing_subkey=False,
            encryption_subkey=False,
        )
    )

    assert len(key.subkeys) == 1
    assert key.subkeys[0].can_encrypt is True
    assert key.can_encrypt is True


def test_generate_key_ed25519_without_signing_subkey_uses_primary_for_sign(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(
            name="Carol Example",
            email="carol@example.com",
            algorithm="ED25519",
            signing_subkey=False,
        )
    )

    assert key.can_sign is True
    assert all(not sub.can_sign for sub in key.subkeys)


def test_add_subkey_to_existing_key(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Dave Example",
            email="dave@example.com",
            key_length=1024,
            signing_subkey=False,
            encryption_subkey=False,
        )
    )
    assert key.subkeys == []

    updated = backend.add_subkey(
        key.fingerprint, Passphrase(""), usage="auth", algorithm="RSA", key_length=1024
    )

    assert len(updated.subkeys) == 1
    assert updated.subkeys[0].can_authenticate is True


def test_add_subkey_ed25519_picks_curve_from_usage(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Eve Example",
            email="eve@example.com",
            algorithm="ED25519",
            signing_subkey=False,
            encryption_subkey=False,
        )
    )

    updated = backend.add_subkey(
        key.fingerprint, Passphrase(""), usage="auth", algorithm="ED25519"
    )

    auth_subkey = next(s for s in updated.subkeys if s.can_authenticate)
    assert auth_subkey.algo == "22"  # EdDSA, not Curve25519


def test_add_subkey_raises_on_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Frank Example", email="frank@example.com", key_length=1024)
    )

    class _FakeSubkeyResult:
        fingerprint = ""
        stderr = "bad subkey"

        def __bool__(self) -> bool:
            return False

    monkeypatch.setattr(
        gnupg.GPG, "add_subkey", lambda self, **kwargs: _FakeSubkeyResult()
    )

    with pytest.raises(GPGBackendError, match="bad subkey"):
        backend.add_subkey(key.fingerprint, Passphrase(""), usage="auth")


def test_add_subkey_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Grace Example",
            email="grace@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.add_subkey(
            key.fingerprint, Passphrase("wrong-passphrase"), usage="auth"
        )


def test_revoke_subkey_marks_it_revoked(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Grace Example", email="grace@example.com", key_length=1024)
    )
    subkey = key.subkeys[0]

    updated = backend.revoke_subkey(key.fingerprint, subkey.keyid, Passphrase(""))

    revoked = next(s for s in updated.subkeys if s.keyid == subkey.keyid)
    assert revoked.trust == "r"


def test_revoke_subkey_wrong_passphrase_raises_and_leaves_it_intact(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Heidi Example",
            email="heidi@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    subkey = key.subkeys[0]

    with pytest.raises(BadPassphraseError):
        backend.revoke_subkey(
            key.fingerprint, subkey.keyid, Passphrase("wrong-passphrase")
        )

    unchanged = next(
        s for s in backend.list_keys()[0].subkeys if s.keyid == subkey.keyid
    )
    assert unchanged.trust != "r"


def test_revoke_key_marks_it_revoked(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Iris Example", email="iris@example.com", key_length=1024)
    )

    updated = backend.revoke_key(key.fingerprint, Passphrase(""))

    assert updated.trust == "r"


def test_revoke_key_wrong_passphrase_raises_and_leaves_it_intact(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="James Example",
            email="james@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.revoke_key(key.fingerprint, Passphrase("wrong-passphrase"))

    assert backend.list_keys()[0].trust != "r"


def test_change_passphrase_changes_it(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Kelly Example",
            email="kelly@example.com",
            key_length=1024,
            passphrase=Passphrase("old-secret"),
        )
    )

    updated = backend.change_passphrase(
        key.fingerprint, Passphrase("old-secret"), Passphrase("new-secret")
    )

    assert updated.fingerprint == key.fingerprint
    # The only way to see the new passphrase actually protects the key
    # without shelling out to gpg directly: change it right back with the
    # *old* one now rejected and the *new* one accepted.
    with pytest.raises(BadPassphraseError):
        backend.change_passphrase(
            key.fingerprint, Passphrase("old-secret"), Passphrase("whatever")
        )
    backend.change_passphrase(
        key.fingerprint, Passphrase("new-secret"), Passphrase("old-secret")
    )


def test_change_passphrase_wrong_old_passphrase_raises_and_leaves_it_intact(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Liam Example",
            email="liam@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.change_passphrase(
            key.fingerprint, Passphrase("wrong-passphrase"), Passphrase("new-secret")
        )

    # The original passphrase must still work — the failed attempt above
    # must not have left the key in some half-changed state.
    backend.change_passphrase(
        key.fingerprint, Passphrase("correct-horse"), Passphrase("new-secret")
    )


def test_change_passphrase_still_checks_old_one_when_agent_has_it_cached(tmp_path):
    """Regression test: gpg-agent caches a just-unlocked key for several
    minutes. Without change_passphrase() actively clearing that cache
    first, gpg silently skips the old-passphrase prompt on a still-cached
    key and this call's fixed two-line script would misapply
    *old_passphrase*'s value as the *new* passphrase instead of actually
    checking it — verified empirically, see CODING.md, "Changing a key's
    passphrase".
    """
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Nora Example",
            email="nora@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    # Prime the agent's cache for this key via an unrelated secret-key
    # operation first, like a user doing something else before this.
    backend.set_key_expiration(key.fingerprint, Passphrase("correct-horse"), "0")

    with pytest.raises(BadPassphraseError):
        backend.change_passphrase(
            key.fingerprint, Passphrase("wrong-passphrase"), Passphrase("new-secret")
        )

    # Must still be "correct-horse" — not silently overwritten with
    # "wrong-passphrase" by a misfired single-prompt exchange.
    backend.change_passphrase(
        key.fingerprint, Passphrase("correct-horse"), Passphrase("new-secret")
    )


def test_change_passphrase_wrong_old_one_with_several_subkeys_reports_cleanly(
    tmp_path,
):
    """Regression test for a real user report: with a wrong old passphrase,
    gpg retries once per secret-key part (primary + each subkey) instead
    of just once — with only 2 subkeys plus the primary (3 parts) this
    still worked, but a 4th part (as reported, primary + 3 subkeys) ran
    this call's old fixed-length script dry partway through gpg's own
    retry sequence, downgrading a clean bad-passphrase error into a
    confusing "operation canceled" dump of gpg's raw multi-attempt
    diagnostic output. See CODING.md, "Changing a key's passphrase".
    """
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Oscar Example",
            email="oscar@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    backend.add_subkey(
        key.fingerprint, Passphrase("correct-horse"), usage="auth", key_length=1024
    )
    assert len(backend.list_keys()[0].subkeys) == 3  # sign + encrypt + auth

    with pytest.raises(BadPassphraseError):
        backend.change_passphrase(
            key.fingerprint, Passphrase("wrong-passphrase"), Passphrase("new-secret")
        )

    # The original passphrase must still work.
    backend.change_passphrase(
        key.fingerprint, Passphrase("correct-horse"), Passphrase("new-secret")
    )


def test_delete_key_removes_secret_and_public_key(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Kara Example", email="kara@example.com", key_length=1024)
    )

    backend.delete_key(key.fingerprint, secret=True)

    assert backend.list_keys() == []


def test_delete_key_public_only_key(tmp_path):
    source_home = tmp_path / "source"
    fingerprint = _generate_key(source_home)
    source_gpg = gnupg.GPG(gnupghome=str(source_home))
    armored_public = source_gpg.export_keys(fingerprint)

    dest_home = tmp_path / "dest"
    backend = GPGBackend(dest_home)
    gnupg.GPG(gnupghome=str(dest_home)).import_keys(armored_public)
    assert len(backend.list_keys()) == 1

    backend.delete_key(fingerprint, secret=False)

    assert backend.list_keys() == []


def test_delete_key_unknown_fingerprint_raises(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    with pytest.raises(GPGBackendError):
        backend.delete_key("AAAA111122223333444455556666777788889999", secret=False)


def test_format_uid_builds_the_conventional_gpg_uid_string():
    assert (
        gpg_backend_module.format_uid("Alice", "alice@example.com")
        == "Alice <alice@example.com>"
    )
    assert (
        gpg_backend_module.format_uid("Alice", "alice@example.com", "work")
        == "Alice (work) <alice@example.com>"
    )


def test_add_uid_appends_a_new_uid(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Judy Example", email="judy@example.com", key_length=1024)
    )

    updated = backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Judy Example",
        email="judy@work.example.com",
    )

    # gpg's own UID listing order isn't stable/meaningful (verified
    # empirically — see CODING.md, "Editable UID fields"), so this only
    # checks membership, not position.
    assert {uid.value for uid in updated.uids} == {
        "Judy Example <judy@example.com>",
        "Judy Example <judy@work.example.com>",
    }
    assert all(not uid.revoked for uid in updated.uids)


def test_generate_key_marks_its_only_uid_as_primary(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    key = backend.generate_key(
        NewKeyRequest(name="Nora Example", email="nora@example.com", key_length=1024)
    )

    assert key.uids[0].primary is True


def test_add_uid_new_uid_becomes_primary_by_default(tmp_path):
    # Empirically verified: with no explicit primary set yet, gpg treats
    # the most recently added UID as primary (a newer self-signature wins
    # in the absence of an explicit "primary" flag).
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Omar Example", email="omar@example.com", key_length=1024)
    )

    updated = backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Omar Example",
        email="omar@work.example.com",
    )

    primary = [uid for uid in updated.uids if uid.primary]
    assert [uid.value for uid in primary] == ["Omar Example <omar@work.example.com>"]


def test_add_uid_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Karl Example",
            email="karl@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.add_uid(
            key.fingerprint,
            Passphrase("wrong-passphrase"),
            name="Karl Example",
            email="karl@work.example.com",
        )


def test_set_primary_uid_leaves_both_uids_present_and_unrevoked(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Laura Example", email="laura@example.com", key_length=1024)
    )
    key = backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Laura Example",
        email="laura@work.example.com",
    )
    target = key.uids[1].value

    updated = backend.set_primary_uid(key.fingerprint, Passphrase(""), target)

    assert {uid.value for uid in updated.uids} == {uid.value for uid in key.uids}
    assert all(not uid.revoked for uid in updated.uids)


def test_primary_uid_lookup_failure_leaves_no_uid_flagged_primary(
    tmp_path, monkeypatch
):
    # A multi-UID key whose gpg --edit-key lookup fails for some reason
    # (any non-zero exit) degrades gracefully: no uid is flagged primary,
    # rather than crashing or guessing.
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Pia Example", email="pia@example.com", key_length=1024)
    )
    backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Pia Example",
        email="pia@work.example.com",
    )

    real_run = gpg_backend_module.subprocess.run

    class _FailedCompleted:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def _fake_run(*args, **kwargs):
        if "--edit-key" in args[0]:
            return _FailedCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    keys = backend.list_keys()

    assert all(not uid.primary for uid in keys[0].uids)


def test_set_primary_uid_flags_the_chosen_uid_as_primary(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Mona Example", email="mona@example.com", key_length=1024)
    )
    key = backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Mona Example",
        email="mona@work.example.com",
    )
    non_primary = next(uid for uid in key.uids if not uid.primary)

    updated = backend.set_primary_uid(
        key.fingerprint, Passphrase(""), non_primary.value
    )

    primary = [uid for uid in updated.uids if uid.primary]
    assert [uid.value for uid in primary] == [non_primary.value]


def test_revoke_uid_marks_it_revoked(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Mallory Example", email="mallory@example.com", key_length=1024
        )
    )
    key = backend.add_uid(
        key.fingerprint,
        Passphrase(""),
        name="Mallory Example",
        email="mallory@work.example.com",
    )
    second_uid = key.uids[1].value

    updated = backend.revoke_uid(key.fingerprint, Passphrase(""), second_uid)

    revoked = next(uid for uid in updated.uids if uid.value == second_uid)
    assert revoked.revoked is True


def test_revoke_uid_wrong_passphrase_raises_and_leaves_it_intact(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Nadia Example",
            email="nadia@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    key = backend.add_uid(
        key.fingerprint,
        Passphrase("correct-horse"),
        name="Nadia Example",
        email="nadia@work.example.com",
    )
    second_uid = key.uids[1].value
    # Without this, gpg-agent still has "correct-horse" cached from the
    # add_uid() call above and would silently accept any passphrase here —
    # this test needs a fresh unlock attempt to actually exercise the
    # wrong-passphrase path.
    backend._restart_agent()

    with pytest.raises(BadPassphraseError):
        backend.revoke_uid(key.fingerprint, Passphrase("wrong-passphrase"), second_uid)

    unchanged = next(
        uid for uid in backend.list_keys()[0].uids if uid.value == second_uid
    )
    assert unchanged.revoked is False


def test_revoke_uid_refuses_to_revoke_the_last_valid_uid(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Oscar Example", email="oscar@example.com", key_length=1024)
    )

    with pytest.raises(GPGBackendError):
        backend.revoke_uid(key.fingerprint, Passphrase(""), key.uids[0].value)


def test_set_key_expiration_relative_duration(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Wendy Example", email="wendy@example.com", key_length=1024)
    )
    assert key.expires is None

    before = time.time()
    updated = backend.set_key_expiration(key.fingerprint, Passphrase(""), "30d")

    assert updated.expires is not None
    assert abs(updated.expires - (before + 30 * 86400)) < 120
    # Setting the primary key's expiration must not touch its subkeys.
    assert all(sub.expires is None for sub in updated.subkeys)


def test_set_key_expiration_absolute_date(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Xena Example", email="xena@example.com", key_length=1024)
    )

    updated = backend.set_key_expiration(key.fingerprint, Passphrase(""), "2030-06-15")

    assert datetime.fromtimestamp(updated.expires).date() == date(2030, 6, 15)  # noqa: DTZ006


def test_set_key_expiration_zero_removes_it(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Yara Example", email="yara@example.com", key_length=1024)
    )
    key = backend.set_key_expiration(key.fingerprint, Passphrase(""), "30d")
    assert key.expires is not None

    updated = backend.set_key_expiration(key.fingerprint, Passphrase(""), "0")

    assert updated.expires is None


def test_set_key_expiration_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Zach Example",
            email="zach@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.set_key_expiration(
            key.fingerprint, Passphrase("wrong-passphrase"), "30d"
        )


def test_set_subkey_expiration_updates_only_that_subkey(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Amy Example", email="amy2@example.com", key_length=1024)
    )
    assert len(key.subkeys) == 2
    target, other = key.subkeys

    updated = backend.set_subkey_expiration(
        key.fingerprint, Passphrase(""), target.fingerprint, "30d"
    )

    updated_target = next(
        s for s in updated.subkeys if s.fingerprint == target.fingerprint
    )
    updated_other = next(
        s for s in updated.subkeys if s.fingerprint == other.fingerprint
    )
    assert updated_target.expires is not None
    assert updated_other.expires is None
    assert updated.expires is None  # the primary key itself must stay untouched


def test_set_subkey_expiration_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Bella Example",
            email="bella@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    subkey = key.subkeys[0]

    with pytest.raises(BadPassphraseError):
        backend.set_subkey_expiration(
            key.fingerprint, Passphrase("wrong-passphrase"), subkey.fingerprint, "30d"
        )


def test_set_key_expiration_retries_once_after_agent_version_mismatch(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        if "--quick-set-expire" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.set_key_expiration(key.fingerprint, Passphrase(""), "30d")

    assert len(calls) == 2
    assert updated.expires is not None


def test_set_owner_trust_round_trips_through_every_level(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Owner Example", email="owner@example.com", key_length=1024)
    )
    assert key.owner_trust == "u"  # own secret key: auto-ultimate

    for level, code in (
        ("never", "n"),
        ("marginal", "m"),
        ("full", "f"),
        ("undefined", "q"),
        ("ultimate", "u"),
    ):
        updated = backend.set_owner_trust(key.fingerprint, level)
        assert updated.owner_trust == code


def test_set_owner_trust_rejects_an_invalid_level(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Owner Example", email="owner2@example.com", key_length=1024)
    )

    with pytest.raises(GPGBackendError):
        backend.set_owner_trust(key.fingerprint, "bogus")


def test_sign_key_raises_the_signed_keys_validity(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(
            name="Signer Example", email="signer@example.com", key_length=1024
        )
    )
    target = backend.generate_key(
        NewKeyRequest(
            name="Target Example", email="target@example.com", key_length=1024
        )
    )
    # Own secret keys are auto-ultimately-trusted, which would mask the
    # effect of signing on computed validity — override that first so it's
    # the web-of-trust math (signer's ultimate ownertrust + a real
    # signature), not the auto-ultimate shortcut, raising target's validity.
    target = backend.set_owner_trust(target.fingerprint, "never")
    assert target.trust != "f"

    updated = backend.sign_key(
        target.fingerprint,
        Passphrase(""),
        signing_key_fingerprint=signer.fingerprint,
        cert_level=2,
    )

    assert updated.trust == "f"


def test_sign_key_local_only_still_raises_validity(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(
            name="Signer Example", email="signer2@example.com", key_length=1024
        )
    )
    target = backend.generate_key(
        NewKeyRequest(
            name="Target Example", email="target2@example.com", key_length=1024
        )
    )
    target = backend.set_owner_trust(target.fingerprint, "never")

    # cert_level=1 ("persona", not verified) is below gpg's own default
    # --min-cert-level of 2 and would be disregarded for validity — use 2
    # here so this test actually demonstrates local-only signing counts.
    updated = backend.sign_key(
        target.fingerprint,
        Passphrase(""),
        signing_key_fingerprint=signer.fingerprint,
        cert_level=2,
        local_only=True,
    )

    assert updated.trust == "f"


def test_sign_key_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(
            name="Signer Example",
            email="signer3@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    target = backend.generate_key(
        NewKeyRequest(
            name="Target Example", email="target3@example.com", key_length=1024
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.sign_key(
            target.fingerprint,
            Passphrase("wrong-passphrase"),
            signing_key_fingerprint=signer.fingerprint,
        )


def test_sign_key_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(
            name="Signer Example", email="signer4@example.com", key_length=1024
        )
    )
    target = backend.generate_key(
        NewKeyRequest(
            name="Target Example", email="target4@example.com", key_length=1024
        )
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        if "--quick-sign-key" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.sign_key(
        target.fingerprint, Passphrase(""), signing_key_fingerprint=signer.fingerprint
    )

    assert len(calls) == 2
    assert updated is not None


def test_refresh_trust_does_not_raise(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    backend.generate_key(
        NewKeyRequest(
            name="Someone Example", email="someone@example.com", key_length=1024
        )
    )

    backend.refresh_trust()  # must not raise


def test_key_has_no_photos_by_default(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Peggy Example", email="peggy@example.com", key_length=1024)
    )

    assert key.photos == []


def test_add_photo_uid_appends_a_photo(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Peggy Example", email="peggy@example.com", key_length=1024)
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")

    updated = backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)

    assert len(updated.photos) == 1
    photo = updated.photos[0]
    assert photo.index == 1
    assert photo.revoked is False
    assert photo.image.startswith(b"\xff\xd8")


def test_add_photo_uid_handles_the_large_jpeg_size_confirmation_prompt(tmp_path):
    # Reported against real usage: gpg's addphoto asks an extra
    # "photoid.jpeg.size" yes/no prompt for a JPEG above some internal size
    # threshold, which the small solid-color fixture JPEG used by every
    # other photo test never triggers. Without an explicit answer queued
    # for it, the next scripted line (the passphrase) got silently
    # consumed as that prompt's answer instead, corrupting the whole
    # remaining script — see the comment on add_photo_uid() itself.
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Rhonda Example", email="rhonda@example.com", key_length=1024
        )
    )
    jpeg = make_large_test_jpeg(tmp_path / "large.jpg")
    assert jpeg.stat().st_size > 20_000  # large enough to trigger the prompt

    updated = backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)

    assert len(updated.photos) == 1
    assert updated.photos[0].image.startswith(b"\xff\xd8")


def test_add_photo_uid_second_photo_gets_the_next_index(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Quinn Example", email="quinn@example.com", key_length=1024)
    )
    blue_jpeg = make_test_jpeg(tmp_path / "blue.jpg", "blue")
    red_jpeg = make_test_jpeg(tmp_path / "red.jpg", "red")

    key = backend.add_photo_uid(key.fingerprint, Passphrase(""), blue_jpeg)
    updated = backend.add_photo_uid(key.fingerprint, Passphrase(""), red_jpeg)

    assert [p.index for p in updated.photos] == [1, 2]
    assert all(not p.revoked for p in updated.photos)
    # The two distinct images must not have been mixed up.
    assert updated.photos[0].image != updated.photos[1].image


def test_add_photo_uid_wrong_passphrase_raises_bad_passphrase_error(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Randy Example",
            email="randy@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")

    with pytest.raises(BadPassphraseError):
        backend.add_photo_uid(key.fingerprint, Passphrase("wrong-passphrase"), jpeg)


def test_add_photo_uid_rejects_a_non_jpeg_file(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Sybil Example", email="sybil@example.com", key_length=1024)
    )
    not_a_jpeg = tmp_path / "not_a_photo.jpg"
    not_a_jpeg.write_bytes(b"this is not a jpeg file")

    with pytest.raises(GPGBackendError):
        backend.add_photo_uid(key.fingerprint, Passphrase(""), not_a_jpeg)


def test_load_photos_records_the_attribute_file_content_in_the_activity_log(
    tmp_path,
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Tia Example", email="tia@example.com", key_length=1024)
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)
    activity_log.reset()

    backend.list_keys()

    entries = activity_log.entries()
    command_entry = next(e for e in entries if "--attribute-file" in e.command)
    detail_entry = next(
        e for e in entries if e.command.startswith("--attribute-file content")
    )
    assert detail_entry.seq == command_entry.seq
    assert "ffd8" in detail_entry.command


def test_revoke_photo_uid_marks_it_revoked(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Trent Example", email="trent@example.com", key_length=1024)
    )
    blue_jpeg = make_test_jpeg(tmp_path / "blue.jpg", "blue")
    red_jpeg = make_test_jpeg(tmp_path / "red.jpg", "red")
    key = backend.add_photo_uid(key.fingerprint, Passphrase(""), blue_jpeg)
    key = backend.add_photo_uid(key.fingerprint, Passphrase(""), red_jpeg)

    updated = backend.revoke_photo_uid(key.fingerprint, Passphrase(""), photo_index=2)

    assert [p.revoked for p in updated.photos] == [False, True]


def test_revoke_photo_uid_wrong_passphrase_raises_and_leaves_it_intact(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Ursula Example",
            email="ursula@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    key = backend.add_photo_uid(key.fingerprint, Passphrase("correct-horse"), jpeg)
    # See test_revoke_uid_wrong_passphrase_raises_and_leaves_it_intact: the
    # agent still has "correct-horse" cached from add_photo_uid() above.
    backend._restart_agent()

    with pytest.raises(BadPassphraseError):
        backend.revoke_photo_uid(
            key.fingerprint, Passphrase("wrong-passphrase"), photo_index=1
        )

    unchanged = backend.list_keys()[0].photos[0]
    assert unchanged.revoked is False


def test_revoke_photo_uid_unknown_index_raises(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Victor Example", email="victor@example.com", key_length=1024
        )
    )

    with pytest.raises(GPGBackendError):
        backend.revoke_photo_uid(key.fingerprint, Passphrase(""), photo_index=1)


def test_add_uid_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        # list_keys() (called via _find_key() once add_uid() succeeds) also
        # runs subprocess.run() for its own photo listing — only count
        # calls for the --quick-add-uid invocation under test, and let
        # every other call through untouched.
        if "--quick-add-uid" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.add_uid(
        key.fingerprint, Passphrase(""), name="Test User", email="test@work.example.com"
    )

    assert len(calls) == 2
    assert len(updated.uids) == 2


def test_add_uid_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"

    monkeypatch.setattr(
        gpg_backend_module.subprocess, "run", lambda *a, **k: _FailedCompleted()
    )

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.add_uid(
            key.fingerprint,
            Passphrase(""),
            name="Test User",
            email="test@work.example.com",
        )

    assert restart_calls == []


def test_import_from_file_imports_a_public_key(tmp_path):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Ivy Example", email="ivy@example.com", key_length=1024)
    )
    key_file = tmp_path / "ivy.asc"
    key_file.write_text(source.export_public_key(key.fingerprint), encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")
    imported = dest.import_from_file(key_file)

    assert [entry.key.fingerprint for entry in imported] == [key.fingerprint]
    assert imported[0].key.has_secret is False
    assert imported[0].is_new is True


def test_import_from_file_reimport_of_existing_key_is_not_new(tmp_path):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Ivy Example", email="ivy@example.com", key_length=1024)
    )
    key_file = tmp_path / "ivy.asc"
    key_file.write_text(source.export_public_key(key.fingerprint), encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")
    dest.import_from_file(key_file)

    imported = dest.import_from_file(key_file)

    assert imported[0].is_new is False


def test_import_from_file_raises_when_no_key_found(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    junk_file = tmp_path / "not-a-key.asc"
    junk_file.write_text("this is not a key")

    with pytest.raises(GPGBackendError):
        backend.import_from_file(junk_file)


def test_preview_import_from_file_lists_candidates_without_importing(tmp_path):
    source = GPGBackend(tmp_path / "source")
    alice = source.generate_key(
        NewKeyRequest(name="Alice Example", email="alice@example.com", key_length=1024)
    )
    bob = source.generate_key(
        NewKeyRequest(name="Bob Example", email="bob@example.com", key_length=1024)
    )
    key_file = tmp_path / "export.asc"
    armored = source.export_public_key(alice.fingerprint) + source.export_public_key(
        bob.fingerprint
    )
    key_file.write_text(armored, encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")
    preview = dest.preview_import_from_file(key_file)

    assert {p.fingerprint for p in preview} == {alice.fingerprint, bob.fingerprint}
    by_fp = {p.fingerprint: p for p in preview}
    assert by_fp[alice.fingerprint].keyid == alice.keyid
    assert by_fp[alice.fingerprint].uids == ["Alice Example <alice@example.com>"]
    assert all(p.is_new for p in preview)
    # The whole point: nothing was actually imported.
    assert dest.list_keys() == []


def test_preview_import_from_file_marks_existing_key_as_not_new(tmp_path):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Carl Example", email="carl@example.com", key_length=1024)
    )
    key_file = tmp_path / "carl.asc"
    key_file.write_text(source.export_public_key(key.fingerprint), encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")
    dest.import_from_file(key_file)

    preview = dest.preview_import_from_file(key_file)

    assert preview[0].is_new is False


def test_preview_import_from_file_raises_when_no_key_found(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    junk_file = tmp_path / "not-a-key.asc"
    junk_file.write_text("this is not a key")

    with pytest.raises(GPGBackendError):
        backend.preview_import_from_file(junk_file)


def test_commit_import_from_file_imports_only_approved_fingerprints(tmp_path):
    source = GPGBackend(tmp_path / "source")
    alice = source.generate_key(
        NewKeyRequest(name="Dana Example", email="dana@example.com", key_length=1024)
    )
    erin = source.generate_key(
        NewKeyRequest(name="Erin Example", email="erin2@example.com", key_length=1024)
    )
    key_file = tmp_path / "export.asc"
    armored = source.export_public_key(alice.fingerprint) + source.export_public_key(
        erin.fingerprint
    )
    key_file.write_text(armored, encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")
    imported = dest.commit_import_from_file(key_file, {alice.fingerprint})

    assert [entry.key.fingerprint for entry in imported] == [alice.fingerprint]
    assert {k.fingerprint for k in dest.list_keys()} == {alice.fingerprint}


def test_commit_import_from_file_never_deletes_an_already_present_key(tmp_path):
    source = GPGBackend(tmp_path / "source")
    existing = source.generate_key(
        NewKeyRequest(name="Fara Example", email="fara@example.com", key_length=1024)
    )
    new_key = source.generate_key(
        NewKeyRequest(name="Gus Example", email="gus@example.com", key_length=1024)
    )

    dest = GPGBackend(tmp_path / "dest")
    existing_file = tmp_path / "existing.asc"
    existing_file.write_text(
        source.export_public_key(existing.fingerprint), encoding="utf-8"
    )
    dest.import_from_file(existing_file)

    combined_file = tmp_path / "combined.asc"
    combined_file.write_text(
        source.export_public_key(existing.fingerprint)
        + source.export_public_key(new_key.fingerprint),
        encoding="utf-8",
    )

    # Neither box checked: the pre-existing key must survive untouched,
    # the genuinely new one must not stick around.
    imported = dest.commit_import_from_file(combined_file, set())

    assert imported == []
    assert {k.fingerprint for k in dest.list_keys()} == {existing.fingerprint}


def test_commit_import_from_file_returns_empty_when_nothing_approved(tmp_path):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Hana Example", email="hana@example.com", key_length=1024)
    )
    key_file = tmp_path / "hana.asc"
    key_file.write_text(source.export_public_key(key.fingerprint), encoding="utf-8")

    dest = GPGBackend(tmp_path / "dest")

    imported = dest.commit_import_from_file(key_file, set())

    assert imported == []
    assert dest.list_keys() == []


def test_import_from_keyserver_by_fingerprint_uses_recv_keys(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Jack Example", email="jack@example.com", key_length=1024)
    )
    calls = []

    class _FakeImportResult:
        fingerprints = (key.fingerprint,)
        stderr = ""

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append((keyserver, keyids))
        return _FakeImportResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = backend.import_from_keyserver(key.fingerprint, "hkps://example.org")

    assert calls == [("hkps://example.org", (key.fingerprint,))]
    assert [entry.key.fingerprint for entry in imported] == [key.fingerprint]
    # The key was already generated in this same keyring above, so this
    # mocked "fetch" is really a re-import of an existing key.
    assert imported[0].is_new is False


def test_import_from_keyserver_by_fingerprint_marks_new_key_as_new(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Leah Example", email="leah@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        # A real recv_keys() would fetch and import the key; reproduce
        # that side effect against dest's own keyring instead of the
        # network, so import_from_keyserver()'s existing-fingerprints
        # snapshot is taken before the key genuinely appears.
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = dest.import_from_keyserver(key.fingerprint, "hkps://example.org")

    assert imported[0].is_new is True


def test_import_from_keyserver_raises_when_not_found(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        fingerprints = ()
        stderr = "gpg: keyserver receive failed: No data"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="No data"):
        backend.import_from_keyserver("DEADBEEF", "hkps://example.org")


def test_import_from_keyserver_raises_a_friendly_error_for_a_key_with_no_user_id(
    tmp_path, monkeypatch
):
    # Real IMPORT_RES observed importing a key.openpgp.org key whose email
    # was never verified there: gpg fetches it (count=1) but refuses to
    # import a key with no user ID, so imported/unchanged both stay 0 and
    # no IMPORT_OK/fingerprint is ever reported.
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        fingerprints = ()
        stderr = (
            "gpg: Warning: server 'dirmngr' is older than us (2.4.4 < 2.5.22)\n"
            "gpg: key EAD8AABFDD999172: new key but contains no user ID - "
            "skipped\n"
            "gpg: Total number processed: 1\n"
        )
        count = 1
        imported = 0
        unchanged = 0

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="no user ID"):
        backend.import_from_keyserver("0xEAD8AABFDD999172", "hkps://example.org")


def test_import_from_keyserver_by_email_locates_via_gpg_with_keyserver_first(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Kim Example", email="kim@example.com", key_length=1024)
    )
    calls = []
    real_run = gpg_backend_module.subprocess.run

    class _FakeCompleted:
        returncode = 0
        stderr = ""
        stdout = f"fpr:::::::::{key.fingerprint}:\n"

    def _fake_run(*args, **kwargs):
        if "--locate-keys" in args[0]:
            calls.append(args[0])
            return _FakeCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    imported = backend.import_from_keyserver("kim@example.com", "hkps://example.org")

    assert len(calls) == 1
    cmd = calls[0]
    # --keyserver must appear before --auto-key-locate/--locate-keys, or
    # gpg silently swallows it as a bogus extra user ID instead of
    # parsing it as an option (the real bug this test guards against —
    # see _locate_key_by_email()'s docstring).
    assert cmd.index("--keyserver") < cmd.index("--locate-keys")
    assert cmd[cmd.index("--keyserver") + 1] == "hkps://example.org"
    assert cmd[-1] == "kim@example.com"
    assert [entry.key.fingerprint for entry in imported] == [key.fingerprint]
    # Already generated in this same keyring above, so this mocked locate
    # is really a re-import of an existing key.
    assert imported[0].is_new is False


def test_import_from_keyserver_by_email_marks_new_key_as_new(tmp_path, monkeypatch):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Moe Example", email="moe@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")
    real_run = gpg_backend_module.subprocess.run

    class _FakeCompleted:
        returncode = 0
        stderr = ""
        stdout = f"fpr:::::::::{key.fingerprint}:\n"

    def _fake_run(*args, **kwargs):
        if "--locate-keys" in args[0]:
            # A real lookup would fetch and import the key via WKD/
            # keyserver; reproduce that side effect against dest's own
            # keyring so import_from_keyserver()'s existing-fingerprints
            # snapshot is taken before the key genuinely appears.
            dest._gpg.import_keys(armored)
            return _FakeCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    imported = dest.import_from_keyserver("moe@example.com", "hkps://example.org")

    assert imported[0].is_new is True


def test_import_from_keyserver_raises_when_email_not_found(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    real_run = gpg_backend_module.subprocess.run

    class _FakeCompleted:
        returncode = 2
        stderr = "gpg: error reading key: No data"
        stdout = ""

    def _fake_run(*args, **kwargs):
        if "--locate-keys" in args[0]:
            return _FakeCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    with pytest.raises(GPGBackendError, match="No data"):
        backend.import_from_keyserver("unknown@example.com", "hkps://example.org")


def test_preview_import_from_keyserver_does_not_touch_the_real_keyring(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Ida Example", email="ida@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        # Whichever keyring (the scratch one preview_import_from_keyserver()
        # creates internally) issues the call receives the key — never
        # `dest` directly, which is exactly what's under test.
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    preview = dest.preview_import_from_keyserver(key.fingerprint, "hkps://example.org")

    assert len(preview) == 1
    assert preview[0].fingerprint == key.fingerprint
    assert preview[0].keyid == key.keyid
    assert preview[0].uids == ["Ida Example <ida@example.com>"]
    assert preview[0].is_new is True
    assert dest.list_keys() == []


def test_preview_import_from_keyserver_marks_existing_key_as_not_new(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Jon Example", email="jon@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")
    key_file = tmp_path / "jon.asc"
    key_file.write_text(armored, encoding="utf-8")
    dest.import_from_file(key_file)

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    preview = dest.preview_import_from_keyserver(key.fingerprint, "hkps://example.org")

    assert preview[0].is_new is False


def test_commit_import_from_keyserver_returns_empty_when_nothing_approved(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyids)
        raise AssertionError("recv_keys must not be called when nothing is approved")

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = backend.commit_import_from_keyserver(
        "DEADBEEF", "hkps://example.org", set()
    )

    assert imported == []
    assert calls == []


def test_commit_import_from_keyserver_imports_when_approved(tmp_path, monkeypatch):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Kara Example", email="kara2@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = dest.commit_import_from_keyserver(
        key.fingerprint, "hkps://example.org", {key.fingerprint}
    )

    assert [entry.key.fingerprint for entry in imported] == [key.fingerprint]
    assert {k.fingerprint for k in dest.list_keys()} == {key.fingerprint}


def test_preview_import_from_keyservers_merges_every_server_without_touching_the_real_keyring(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Lior Example", email="lior@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyserver)
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    preview = dest.preview_import_from_keyservers(
        key.fingerprint, ["hkps://a.example", "hkps://b.example"]
    )

    assert calls == ["hkps://a.example", "hkps://b.example"]
    assert [entry.fingerprint for entry in preview] == [key.fingerprint]
    assert preview[0].is_new is True
    assert dest.list_keys() == []


def test_preview_import_from_keyservers_succeeds_when_only_one_server_has_the_key(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Mona Example", email="mona@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        if keyserver == "hkps://empty.example":
            return type(
                "_FakeImportResult",
                (),
                {"fingerprints": (), "stderr": "No data"},
            )()
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    preview = dest.preview_import_from_keyservers(
        key.fingerprint, ["hkps://empty.example", "hkps://has-it.example"]
    )

    assert [entry.fingerprint for entry in preview] == [key.fingerprint]


def test_preview_import_from_keyservers_raises_when_no_server_has_the_key(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        fingerprints = ()
        stderr = "gpg: keyserver receive failed: No data"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="No data"):
        backend.preview_import_from_keyservers(
            "DEADBEEF", ["hkps://a.example", "hkps://b.example"]
        )


def test_commit_import_from_keyservers_returns_empty_when_nothing_approved(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyserver)
        raise AssertionError("recv_keys must not be called when nothing is approved")

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = backend.commit_import_from_keyservers(
        "DEADBEEF", ["hkps://a.example", "hkps://b.example"], set()
    )

    assert imported == []
    assert calls == []


def test_commit_import_from_keyservers_merges_every_server_into_the_real_keyring(
    tmp_path, monkeypatch
):
    source = GPGBackend(tmp_path / "source")
    key = source.generate_key(
        NewKeyRequest(name="Nadia Example", email="nadia@example.com", key_length=1024)
    )
    armored = source.export_public_key(key.fingerprint)

    dest = GPGBackend(tmp_path / "dest")
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyserver)
        self.import_keys(armored)
        return type("_FakeImportResult", (), {"fingerprints": (key.fingerprint,)})()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    imported = dest.commit_import_from_keyservers(
        key.fingerprint, ["hkps://a.example", "hkps://b.example"], {key.fingerprint}
    )

    assert calls == ["hkps://a.example", "hkps://b.example"]
    assert [entry.key.fingerprint for entry in imported] == [key.fingerprint]
    assert {k.fingerprint for k in dest.list_keys()} == {key.fingerprint}


def test_commit_import_from_keyservers_raises_when_no_server_has_the_key(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        fingerprints = ()
        stderr = "gpg: keyserver receive failed: No data"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="No data"):
        backend.commit_import_from_keyservers(
            "DEADBEEF", ["hkps://a.example", "hkps://b.example"], {"DEADBEEF"}
        )


def test_search_keyserver_returns_parsed_results(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    calls = []

    class _FakeSearchResult(list):
        stderr = ""

    def _fake_search_keys(self, query, keyserver="pgp.mit.edu", extra_args=None):
        calls.append((query, keyserver))
        result = _FakeSearchResult()
        result.append(
            {
                "keyid": "AAAA111122223333444455556666777788889999",
                "algo": "1",
                "length": "4096",
                "date": "1700000000",
                "expires": "",
                "uids": ["Alice Example <alice@example.com>"],
            }
        )
        return result

    monkeypatch.setattr(gnupg.GPG, "search_keys", _fake_search_keys)

    results = backend.search_keyserver("alice", "hkps://example.org")

    assert calls == [("alice", "hkps://example.org")]
    assert len(results) == 1
    assert results[0].fingerprint == "AAAA111122223333444455556666777788889999"
    assert results[0].uids == ["Alice Example <alice@example.com>"]
    assert results[0].algo == "1"
    assert results[0].length == 4096
    assert results[0].created == 1700000000


def test_search_keyserver_decodes_percent_encoded_uids(tmp_path, monkeypatch):
    # gpg passes an HKP index's uid field straight through, percent-encoded
    # (space as %20, "<"/">" as %3C/%3E) — see _decode_hkp_uid().
    backend = GPGBackend(tmp_path / "home")

    class _FakeSearchResult(list):
        stderr = ""

    def _fake_search_keys(self, query, keyserver="pgp.mit.edu", extra_args=None):
        result = _FakeSearchResult()
        result.append(
            {
                "keyid": "AAAA111122223333444455556666777788889999",
                "algo": "1",
                "length": "4096",
                "date": "1700000000",
                "expires": "",
                "uids": ["Alice%20Example%20%3Calice%40example.com%3E"],
            }
        )
        return result

    monkeypatch.setattr(gnupg.GPG, "search_keys", _fake_search_keys)

    results = backend.search_keyserver("alice", "hkps://example.org")

    assert results[0].uids == ["Alice Example <alice@example.com>"]


def test_search_keyserver_raises_when_no_matches(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeSearchResult(list):
        stderr = "gpg: error: No keys found matching pattern"

    monkeypatch.setattr(
        gnupg.GPG,
        "search_keys",
        lambda self, query, keyserver="pgp.mit.edu", extra_args=None: (
            _FakeSearchResult()
        ),
    )

    with pytest.raises(GPGBackendError, match="No keys found"):
        backend.search_keyserver("nobody", "hkps://example.org")


def test_search_keyserver_returns_empty_list_when_key_genuinely_not_found(
    tmp_path, monkeypatch
):
    # Real-world gpg output for a search with zero matches: a FAILURE
    # search-keys status line packing GPG_ERR_NOT_FOUND (27), often
    # alongside an unrelated dirmngr version-mismatch WARNING. This must
    # surface as "0 results", not a raw error dump — see
    # _is_not_found_failure().
    backend = GPGBackend(tmp_path / "home")

    class _FakeSearchResult(list):
        stderr = (
            "gpg: Warning: server 'dirmngr' is older than us (2.4.4 < 2.5.22)\n"
            "gpg: Note: Outdated servers may lack important security fixes.\n"
            'gpg: Note: Use the command "gpgconf --kill all" to restart them.\n'
            "[GNUPG:] WARNING server_version_mismatch 0 ...\n"
            "gpg: key 'coucou' not found on keyserver\n"
            "[GNUPG:] FAILURE search-keys 33554459\n"
            "gpg: keyserver search failed: Not found\n"
        )

    monkeypatch.setattr(
        gnupg.GPG,
        "search_keys",
        lambda self, query, keyserver="pgp.mit.edu", extra_args=None: (
            _FakeSearchResult()
        ),
    )

    assert backend.search_keyserver("coucou", "hkps://example.org") == []


def test_publish_to_keyserver_calls_send_keys(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Leo Example", email="leo@example.com", key_length=1024)
    )
    calls = []

    class _FakeSendResult:
        returncode = 0
        stderr = ""

    def _fake_send_keys(self, keyserver, *keyids):
        calls.append((keyserver, keyids))
        return _FakeSendResult()

    monkeypatch.setattr(gnupg.GPG, "send_keys", _fake_send_keys)

    backend.publish_to_keyserver(key.fingerprint, "hkps://example.org")

    assert calls == [("hkps://example.org", (key.fingerprint,))]


def test_publish_to_keyserver_raises_on_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeSendResult:
        returncode = 2
        stderr = "gpg: keyserver send failed: No route to host"

    monkeypatch.setattr(
        gnupg.GPG, "send_keys", lambda self, keyserver, *keyids: _FakeSendResult()
    )

    with pytest.raises(GPGBackendError, match="No route to host"):
        backend.publish_to_keyserver("DEADBEEF", "hkps://example.org")


def test_publish_to_keyservers_publishes_to_every_server(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Leo Two Example", email="leo2@example.com", key_length=1024)
    )
    calls = []

    class _FakeSendResult:
        returncode = 0
        stderr = ""

    def _fake_send_keys(self, keyserver, *keyids):
        calls.append((keyserver, keyids))
        return _FakeSendResult()

    monkeypatch.setattr(gnupg.GPG, "send_keys", _fake_send_keys)

    published = backend.publish_to_keyservers(
        key.fingerprint, ["hkps://a.example", "hkps://b.example"]
    )

    assert calls == [
        ("hkps://a.example", (key.fingerprint,)),
        ("hkps://b.example", (key.fingerprint,)),
    ]
    assert published == ["hkps://a.example", "hkps://b.example"]


def test_publish_to_keyservers_succeeds_when_only_one_server_accepts_it(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Leo Three Example", email="leo3@example.com", key_length=1024
        )
    )

    class _FakeSendResult:
        def __init__(self, returncode, stderr=""):
            self.returncode = returncode
            self.stderr = stderr

    def _fake_send_keys(self, keyserver, *keyids):
        if keyserver == "hkps://down.example":
            return _FakeSendResult(2, "gpg: keyserver send failed: No route to host")
        return _FakeSendResult(0)

    monkeypatch.setattr(gnupg.GPG, "send_keys", _fake_send_keys)

    published = backend.publish_to_keyservers(
        key.fingerprint, ["hkps://down.example", "hkps://up.example"]
    )

    assert published == ["hkps://up.example"]


def test_publish_to_keyservers_raises_when_every_server_fails(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    class _FakeSendResult:
        returncode = 2
        stderr = "gpg: keyserver send failed: No route to host"

    monkeypatch.setattr(
        gnupg.GPG, "send_keys", lambda self, keyserver, *keyids: _FakeSendResult()
    )

    with pytest.raises(GPGBackendError, match="No route to host"):
        backend.publish_to_keyservers(
            "DEADBEEF", ["hkps://a.example", "hkps://b.example"]
        )


def test_refresh_from_keyserver_fetches_every_key_in_the_keyring(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    first = backend.generate_key(
        NewKeyRequest(name="Mona Example", email="mona@example.com", key_length=1024)
    )
    second = backend.generate_key(
        NewKeyRequest(name="Nick Example", email="nick@example.com", key_length=1024)
    )
    calls = []

    class _FakeImportResult:
        returncode = 0
        stderr = ""

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append((keyserver, keyids))
        return _FakeImportResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    refreshed = backend.refresh_from_keyserver(keyservers=["hkps://example.org"])

    assert len(calls) == 1
    keyserver, keyids = calls[0]
    assert keyserver == "hkps://example.org"
    assert set(keyids) == {first.fingerprint, second.fingerprint}
    # The fake recv_keys doesn't actually touch the keyring, so nothing
    # about either key changed — both report back as not updated.
    assert {r.key.fingerprint for r in refreshed} == {
        first.fingerprint,
        second.fingerprint,
    }
    assert all(not r.updated for r in refreshed)


def test_refresh_from_keyserver_refreshes_only_the_given_fingerprints(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    first = backend.generate_key(
        NewKeyRequest(name="Priya Example", email="priya@example.com", key_length=1024)
    )
    backend.generate_key(
        NewKeyRequest(name="Quinn Example", email="quinn@example.com", key_length=1024)
    )
    calls = []

    class _FakeImportResult:
        returncode = 0
        stderr = ""

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyids)
        return _FakeImportResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    refreshed = backend.refresh_from_keyserver(
        fingerprints=[first.fingerprint], keyservers=["hkps://example.org"]
    )

    assert len(calls) == 1
    assert calls[0] == (first.fingerprint,)
    assert [r.key.fingerprint for r in refreshed] == [first.fingerprint]


def test_refresh_from_keyserver_only_pays_the_primary_uid_lookup_for_the_refreshed_key(
    tmp_path, monkeypatch
):
    # Regression test: before/after snapshots used to list() the whole
    # keyring, so refreshing one key paid _load_primary_uids()'s per-key
    # --edit-key cost for every *other* multi-UID key too.
    backend = GPGBackend(tmp_path / "home")
    refreshed_key = backend.generate_key(
        NewKeyRequest(name="Uma Example", email="uma@example.com", key_length=1024)
    )
    backend.add_uid(
        refreshed_key.fingerprint,
        Passphrase(""),
        name="Uma Example",
        email="uma@work.example.com",
    )
    other_key = backend.generate_key(
        NewKeyRequest(name="Vik Example", email="vik@example.com", key_length=1024)
    )
    backend.add_uid(
        other_key.fingerprint,
        Passphrase(""),
        name="Vik Example",
        email="vik@work.example.com",
    )

    class _FakeImportResult:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )
    activity_log.reset()

    backend.refresh_from_keyserver(
        fingerprints=[refreshed_key.fingerprint], keyservers=["hkps://example.org"]
    )

    edit_key_commands = [
        entry.command
        for entry in activity_log.entries()
        if "--edit-key" in entry.command
    ]
    assert all(refreshed_key.fingerprint in cmd for cmd in edit_key_commands)
    assert not any(other_key.fingerprint in cmd for cmd in edit_key_commands)


def test_refresh_from_keyserver_reports_updated_when_the_key_actually_changed(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Rosa Example", email="rosa@example.com", key_length=1024)
    )

    class _FakeImportResult:
        returncode = 0
        stderr = ""

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        # Simulate the keyserver's copy carrying a UID this keyring
        # doesn't have yet, merged in by the "fetch".
        backend.add_uid(
            key.fingerprint,
            Passphrase(""),
            name="Rosa Example",
            email="rosa@newmail.example.com",
        )
        return _FakeImportResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    (refreshed,) = backend.refresh_from_keyserver(
        fingerprints=[key.fingerprint], keyservers=["hkps://example.org"]
    )

    assert refreshed.updated is True
    assert len(refreshed.key.uids) == 2


def test_refresh_from_keyserver_is_a_noop_on_an_empty_keyring(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")

    def _fail(self, keyserver, *keyids):
        raise AssertionError("recv_keys should not be called on an empty keyring")

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fail)

    assert backend.refresh_from_keyserver(keyservers=["hkps://example.org"]) == []


def test_refresh_from_keyserver_is_a_noop_with_an_explicitly_empty_fingerprint_list(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    backend.generate_key(
        NewKeyRequest(name="Sam Example", email="sam@example.com", key_length=1024)
    )

    def _fail(self, keyserver, *keyids):
        raise AssertionError("recv_keys should not be called with no fingerprints")

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fail)

    assert (
        backend.refresh_from_keyserver(
            fingerprints=[], keyservers=["hkps://example.org"]
        )
        == []
    )


def test_refresh_from_keyserver_is_a_noop_with_no_keyservers(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    backend.generate_key(
        NewKeyRequest(name="Sam Two Example", email="sam2@example.com", key_length=1024)
    )

    def _fail(self, keyserver, *keyids):
        raise AssertionError("recv_keys should not be called with no keyservers")

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fail)

    assert backend.refresh_from_keyserver(keyservers=[]) == []


def test_refresh_from_keyserver_raises_on_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    backend.generate_key(
        NewKeyRequest(name="Oscar Example", email="oscar@example.com", key_length=1024)
    )

    class _FakeImportResult:
        returncode = 2
        stderr = "gpg: keyserver receive failed: Network is unreachable"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="Network is unreachable"):
        backend.refresh_from_keyserver(keyservers=["hkps://example.org"])


def test_refresh_from_keyserver_succeeds_when_only_one_server_works(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Oscar Two Example", email="oscar2@example.com", key_length=1024
        )
    )

    class _FakeFailResult:
        returncode = 2
        stderr = "gpg: keyserver receive failed: Network is unreachable"

    class _FakeOkResult:
        returncode = 0
        stderr = ""

    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyserver)
        if keyserver == "hkps://down.example":
            return _FakeFailResult()
        return _FakeOkResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    refreshed = backend.refresh_from_keyserver(
        fingerprints=[key.fingerprint],
        keyservers=["hkps://down.example", "hkps://up.example"],
    )

    assert calls == ["hkps://down.example", "hkps://up.example"]
    assert [r.key.fingerprint for r in refreshed] == [key.fingerprint]


def test_refresh_from_keyserver_raises_when_every_server_fails(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    backend.generate_key(
        NewKeyRequest(
            name="Oscar Three Example", email="oscar3@example.com", key_length=1024
        )
    )

    class _FakeImportResult:
        returncode = 2
        stderr = "gpg: keyserver receive failed: Network is unreachable"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    with pytest.raises(GPGBackendError, match="Network is unreachable"):
        backend.refresh_from_keyserver(
            keyservers=["hkps://a.example", "hkps://b.example"]
        )


def test_refresh_from_keyserver_ignores_a_no_data_failure_for_one_key(
    tmp_path, monkeypatch
):
    # Real-world gpg output when refreshing several keys and one of them is
    # no longer available from the keyserver: an overall FAILURE recv-keys
    # status line packing GPG_ERR_NO_DATA (58), surrounded by a wall of
    # unrelated KEYEXPIRED noise for the *other*, perfectly fine keys. This
    # must not turn into a raw error dump for a mostly-successful refresh —
    # see _is_no_data_failure().
    backend = GPGBackend(tmp_path / "home")
    first = backend.generate_key(
        NewKeyRequest(name="Tia Example", email="tia@example.com", key_length=1024)
    )
    second = backend.generate_key(
        NewKeyRequest(name="Uma Example", email="uma@example.com", key_length=1024)
    )

    class _FakeImportResult:
        returncode = 2
        stderr = (
            "[GNUPG:] KEYEXPIRED 1700061830\n"
            "[GNUPG:] IMPORT_OK 0 SOMEFINGERPRINT\n"
            "gpg: key 0xDEADBEEF: not changed\n"
            "gpg: Total number processed: 2\n"
            "[GNUPG:] FAILURE recv-keys 167772218\n"
            "gpg: keyserver receive failed: No data\n"
        )

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    refreshed = backend.refresh_from_keyserver(keyservers=["hkps://example.org"])

    assert {r.key.fingerprint for r in refreshed} == {
        first.fingerprint,
        second.fingerprint,
    }
    assert all(not r.updated for r in refreshed)


def test_list_key_signatures_returns_empty_for_an_unsigned_key(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Vera Example", email="vera@example.com", key_length=1024)
    )

    assert backend.list_key_signatures(key.fingerprint) == []


def test_list_key_signatures_excludes_the_self_signature(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Walt Example", email="walt@example.com", key_length=1024)
    )

    # Every key self-certifies its own user IDs on generation — that must
    # never show up as "signed by another key".
    assert backend.list_key_signatures(key.fingerprint) == []


def test_list_key_signatures_reports_a_known_signer(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(name="Xena Example", email="xena@example.com", key_length=1024)
    )
    target = backend.generate_key(
        NewKeyRequest(name="Yara Example", email="yara@example.com", key_length=1024)
    )
    backend.sign_key(
        target.fingerprint, Passphrase(""), signing_key_fingerprint=signer.fingerprint
    )

    (signature,) = backend.list_key_signatures(target.fingerprint)

    assert signature.keyid == signer.keyid
    assert signature.fingerprint == signer.fingerprint
    assert signature.key is not None
    assert signature.key.fingerprint == signer.fingerprint


def test_list_key_signatures_reports_a_signer_no_longer_in_the_keyring(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    signer = backend.generate_key(
        NewKeyRequest(name="Zane Example", email="zane@example.com", key_length=1024)
    )
    target = backend.generate_key(
        NewKeyRequest(name="Amara Example", email="amara@example.com", key_length=1024)
    )
    backend.sign_key(
        target.fingerprint, Passphrase(""), signing_key_fingerprint=signer.fingerprint
    )
    backend.delete_key(signer.fingerprint, secret=True)

    (signature,) = backend.list_key_signatures(target.fingerprint)

    # The signature packet's own issuer-fingerprint subpacket still
    # identifies the signer, even though it's gone from the keyring —
    # see KeySignature's docstring.
    assert signature.keyid == signer.keyid
    assert signature.fingerprint == signer.fingerprint
    assert signature.key is None


def test_download_unknown_signatures_imports_a_found_key(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    elsewhere = GPGBackend(tmp_path / "elsewhere")
    foreign = elsewhere.generate_key(
        NewKeyRequest(name="Boaz Example", email="boaz@example.com", key_length=1024)
    )
    armored = elsewhere.export_public_key(foreign.fingerprint)
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append((keyserver, keyids))
        return self.import_keys(armored)

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    (downloaded,) = backend.download_unknown_signatures(
        [foreign.fingerprint], ["hkps://example.org"]
    )

    assert calls == [("hkps://example.org", (foreign.fingerprint,))]
    assert downloaded.identifier == foreign.fingerprint
    assert downloaded.key is not None
    assert downloaded.key.fingerprint == foreign.fingerprint


def test_download_unknown_signatures_reports_a_key_not_on_the_server(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        returncode = 2
        fingerprints = ()
        stderr = "[GNUPG:] FAILURE recv-keys 167772218\ngpg: no data\n"

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    (downloaded,) = backend.download_unknown_signatures(
        ["0" * 16], ["hkps://example.org"]
    )

    assert downloaded.identifier == "0" * 16
    assert downloaded.key is None


def test_download_unknown_signatures_fetches_one_identifier_at_a_time(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    calls = []

    class _FakeImportResult:
        returncode = 2
        fingerprints = ()
        stderr = ""

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyids)
        return _FakeImportResult()

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    backend.download_unknown_signatures(["A" * 16, "B" * 16], ["hkps://example.org"])

    assert calls == [("A" * 16,), ("B" * 16,)]


def test_download_unknown_signatures_tries_every_server_for_each_identifier(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    elsewhere = GPGBackend(tmp_path / "elsewhere")
    foreign = elsewhere.generate_key(
        NewKeyRequest(
            name="Boaz Two Example", email="boaz2@example.com", key_length=1024
        )
    )
    armored = elsewhere.export_public_key(foreign.fingerprint)
    calls = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        calls.append(keyserver)
        if keyserver == "hkps://empty.example":
            return type("_FakeImportResult", (), {"fingerprints": ()})()
        return self.import_keys(armored)

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)

    (downloaded,) = backend.download_unknown_signatures(
        [foreign.fingerprint], ["hkps://empty.example", "hkps://has-it.example"]
    )

    assert calls == ["hkps://empty.example", "hkps://has-it.example"]
    assert downloaded.key is not None
    assert downloaded.key.fingerprint == foreign.fingerprint


def test_download_unknown_signatures_stays_not_found_when_no_server_has_it(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")

    class _FakeImportResult:
        fingerprints = ()

    monkeypatch.setattr(
        gnupg.GPG,
        "recv_keys",
        lambda self, keyserver, *keyids, **kwargs: _FakeImportResult(),
    )

    (downloaded,) = backend.download_unknown_signatures(
        ["0" * 16], ["hkps://a.example", "hkps://b.example"]
    )

    assert downloaded.key is None


def test_export_public_key_returns_armored_text(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Ivan Example", email="ivan@example.com", key_length=1024)
    )

    armored = backend.export_public_key(key.fingerprint)

    assert "BEGIN PGP PUBLIC KEY BLOCK" in armored


def test_export_public_key_raises_for_unknown_fingerprint(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    with pytest.raises(GPGBackendError):
        backend.export_public_key("0" * 40)


def test_export_secret_key_returns_armored_secret_block(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Jill Example",
            email="jill@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    armored = backend.export_secret_key(key.fingerprint, Passphrase("correct-horse"))

    assert "BEGIN PGP PRIVATE KEY BLOCK" in armored


def test_export_secret_key_with_no_passphrase_set(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Kian Example", email="kian@example.com", key_length=1024)
    )

    armored = backend.export_secret_key(key.fingerprint, Passphrase(""))

    assert "BEGIN PGP PRIVATE KEY BLOCK" in armored


def test_export_secret_key_wrong_passphrase_raises(tmp_path):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Liam Example",
            email="liam@example.com",
            key_length=1024,
            passphrase=Passphrase("correct-horse"),
        )
    )

    with pytest.raises(BadPassphraseError):
        backend.export_secret_key(key.fingerprint, Passphrase("wrong-passphrase"))


def test_export_secret_key_raises_for_unknown_fingerprint(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    with pytest.raises(GPGBackendError):
        backend.export_secret_key("0" * 40, Passphrase(""))


def test_export_secret_key_retries_once_after_agent_version_mismatch(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR
        stdout = ""

    def _fake_run(*args, **kwargs):
        if "--export-secret-keys" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    armored = backend.export_secret_key(key.fingerprint, Passphrase(""))

    assert len(calls) == 2
    assert "BEGIN PGP PRIVATE KEY BLOCK" in armored


def test_export_secret_key_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"
        stdout = ""

    monkeypatch.setattr(
        gpg_backend_module.subprocess, "run", lambda *a, **k: _FailedCompleted()
    )

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.export_secret_key(key.fingerprint, Passphrase(""))

    assert restart_calls == []


def test_restart_agent_runs_gpgconf_without_raising(tmp_path):
    backend = GPGBackend(tmp_path / "home")

    backend._restart_agent()  # no agent running against a fresh home; must not raise


def test_homedir_args_includes_flag_when_gnupghome_is_set(tmp_path):
    home = tmp_path / "home"
    backend = GPGBackend(home)

    assert backend._homedir_args() == ["--homedir", str(home)]


def test_homedir_args_omits_flag_when_gnupghome_is_none(tmp_path):
    # Reproduces the production shape: default_backend() with no configure()
    # override constructs GPGBackend(None), and python-gnupg never resolves
    # that to gpg's actual default homedir path — self._gpg.gnupghome stays
    # None. Passing None straight to subprocess.run() raises a TypeError
    # ("expected str, bytes or os.PathLike object, not NoneType"), reported
    # against the real Add Subkey dialog.
    backend = GPGBackend(tmp_path / "home")
    backend._gpg.gnupghome = None

    assert backend._homedir_args() == []


def test_generate_key_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    real_gen_key = gnupg.GPG.gen_key
    calls = []

    class _MismatchResult:
        fingerprint = ""
        stderr = _MISMATCH_STDERR

    def _fake_gen_key(self, input_data):
        calls.append(1)
        if len(calls) == 1:
            return _MismatchResult()
        return real_gen_key(self, input_data)

    monkeypatch.setattr(gnupg.GPG, "gen_key", _fake_gen_key)

    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )

    assert len(calls) == 2
    assert restart_calls == [1]
    assert [uid.value for uid in key.uids] == ["Test User <test@example.com>"]
    assert key.uids[0].revoked is False


def test_generate_key_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FakeResult:
        fingerprint = ""
        stderr = "some other error"

    monkeypatch.setattr(gnupg.GPG, "gen_key", lambda self, input_data: _FakeResult())

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.generate_key(NewKeyRequest(name="Test User", email="test@example.com"))

    assert restart_calls == []


def test_add_subkey_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Test User",
            email="test@example.com",
            key_length=1024,
            signing_subkey=False,
            encryption_subkey=False,
        )
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_add_subkey = gnupg.GPG.add_subkey
    calls = []

    class _MismatchResult:
        fingerprint = ""
        stderr = _MISMATCH_STDERR

        def __bool__(self) -> bool:
            return False

    def _fake_add_subkey(self, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return _MismatchResult()
        return real_add_subkey(self, **kwargs)

    monkeypatch.setattr(gnupg.GPG, "add_subkey", _fake_add_subkey)

    updated = backend.add_subkey(
        key.fingerprint, Passphrase(""), usage="auth", algorithm="RSA", key_length=1024
    )

    assert len(calls) == 2
    assert len(updated.subkeys) == 1


def test_revoke_subkey_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    subkey = key.subkeys[0]
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        # list_keys() (called via _find_key() once revoke_subkey() succeeds)
        # also runs subprocess.run() for its own photo listing — only count
        # calls for the --edit-key invocation under test, and let every
        # other call through untouched.
        if "--edit-key" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.revoke_subkey(key.fingerprint, subkey.keyid, Passphrase(""))

    assert len(calls) == 2
    revoked = next(s for s in updated.subkeys if s.keyid == subkey.keyid)
    assert revoked.trust == "r"


def test_revoke_subkey_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    subkey = key.subkeys[0]
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"

    monkeypatch.setattr(
        gpg_backend_module.subprocess, "run", lambda *a, **k: _FailedCompleted()
    )

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.revoke_subkey(key.fingerprint, subkey.keyid, Passphrase(""))

    assert restart_calls == []


def test_revoke_key_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        if "--edit-key" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.revoke_key(key.fingerprint, Passphrase(""))

    assert len(calls) == 2
    assert updated.trust == "r"


def test_revoke_key_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"

    monkeypatch.setattr(
        gpg_backend_module.subprocess, "run", lambda *a, **k: _FailedCompleted()
    )

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.revoke_key(key.fingerprint, Passphrase(""))

    assert restart_calls == []


def test_change_passphrase_retries_once_after_agent_version_mismatch(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Test User",
            email="test@example.com",
            key_length=1024,
            passphrase=Passphrase("old-secret"),
        )
    )
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        if "--change-passphrase" in args[0]:
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.change_passphrase(
        key.fingerprint, Passphrase("old-secret"), Passphrase("new-secret")
    )

    assert len(calls) == 2
    assert updated.fingerprint == key.fingerprint


def test_change_passphrase_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"

    monkeypatch.setattr(
        gpg_backend_module.subprocess, "run", lambda *a, **k: _FailedCompleted()
    )

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.change_passphrase(
            key.fingerprint, Passphrase(""), Passphrase("new-secret")
        )

    assert restart_calls == []


def test_add_photo_uid_retries_once_after_agent_version_mismatch(tmp_path, monkeypatch):
    # add_photo_uid() drives gpg via subprocess.Popen (an interactive,
    # partly-read protocol — see its docstring), not subprocess.run like
    # every sibling edit-key method, so the mismatch has to be faked at
    # the Popen level instead: a fake process whose stderr looks
    # immediately exhausted (ending the peek loop right away) and whose
    # communicate() reports the mismatch.
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_popen = gpg_backend_module.subprocess.Popen
    calls = []

    class _FakeMismatchProcess:
        args = ("gpg",)
        returncode = 2

        class stdin:
            @staticmethod
            def write(_data):
                pass

            @staticmethod
            def flush():
                pass

        class stderr:
            @staticmethod
            def readline():
                return ""

        @staticmethod
        def communicate(input=None, timeout=None):
            return "", _MISMATCH_STDERR

    def _fake_popen(*args, **kwargs):
        # subprocess.run() is itself implemented on top of
        # subprocess.Popen(), so patching Popen also intercepts every
        # *other* method's subprocess.run() call (e.g. the raw
        # --attribute-file listing add_photo_uid's own _find_key()
        # triggers afterwards) — only fake the addphoto invocation
        # itself, identified by its --command-fd/--edit-key signature.
        argv = args[0] if args else kwargs.get("args", [])
        if "--edit-key" not in argv:
            return real_popen(*args, **kwargs)
        calls.append(1)
        if len(calls) == 1:
            return _FakeMismatchProcess()
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "Popen", _fake_popen)

    updated = backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)

    assert len(calls) == 2
    assert len(updated.photos) == 1


def test_revoke_photo_uid_retries_once_after_agent_version_mismatch(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    key = backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)
    monkeypatch.setattr(GPGBackend, "_restart_agent", lambda self: None)

    real_run = gpg_backend_module.subprocess.run
    calls = []

    class _MismatchCompleted:
        returncode = 2
        stderr = _MISMATCH_STDERR

    def _fake_run(*args, **kwargs):
        if "revuid" in kwargs.get("input", ""):
            calls.append(1)
            if len(calls) == 1:
                return _MismatchCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    updated = backend.revoke_photo_uid(key.fingerprint, Passphrase(""), photo_index=1)

    assert len(calls) == 2
    assert updated.photos[0].revoked is True


def test_revoke_photo_uid_does_not_retry_on_unrelated_failure(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
    )
    jpeg = make_test_jpeg(tmp_path / "photo.jpg")
    key = backend.add_photo_uid(key.fingerprint, Passphrase(""), jpeg)
    restart_calls = []
    monkeypatch.setattr(
        GPGBackend, "_restart_agent", lambda self: restart_calls.append(1)
    )

    real_run = gpg_backend_module.subprocess.run

    class _FailedCompleted:
        returncode = 2
        stderr = "some other error"

    def _fake_run(*args, **kwargs):
        if "revuid" in kwargs.get("input", ""):
            return _FailedCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)

    with pytest.raises(GPGBackendError, match="some other error"):
        backend.revoke_photo_uid(key.fingerprint, Passphrase(""), photo_index=1)

    assert restart_calls == []


class TestDebugTracing:
    """External-program calls are traced at DEBUG, with secrets redacted."""

    def test_redact_replaces_every_secret_occurrence(self):
        text = gpg_backend_module._redact("old\nnew\nold\n", ("old", "new", "", None))

        assert text == "**********\n**********\n**********\n"

    def test_redact_leaves_text_alone_without_secrets(self):
        assert gpg_backend_module._redact("list\nquit\n", ()) == "list\nquit\n"

    def test_traced_run_logs_command_and_redacts_stdin(self, caplog):
        caplog.set_level("DEBUG", logger=gpg_backend_module.__name__)

        result = gpg_backend_module._traced_run(
            ["true"],
            input="hunter2\n",
            secrets=("hunter2",),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "hunter2" not in caplog.text
        assert "**********" in caplog.text
        assert "true" in caplog.text

    def test_traced_run_silent_below_debug_level(self, caplog):
        caplog.set_level("INFO", logger=gpg_backend_module.__name__)

        gpg_backend_module._traced_run(
            ["true"],
            input="hunter2\n",
            secrets=("hunter2",),
            capture_output=True,
            text=True,
        )

        assert caplog.text == ""

    def test_traced_popen_logs_command_only(self, caplog):
        caplog.set_level("DEBUG", logger=gpg_backend_module.__name__)

        process = gpg_backend_module._traced_popen(
            ["true"], stdout=gpg_backend_module.subprocess.DEVNULL
        )
        process.wait()

        assert "true" in caplog.text

    def test_change_passphrase_never_logs_passphrases_in_debug(self, tmp_path, caplog):
        caplog.set_level("DEBUG", logger=gpg_backend_module.__name__)
        backend = GPGBackend(tmp_path / "home")
        key = backend.generate_key(
            NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
        )
        backend.change_passphrase(
            key.fingerprint, Passphrase(""), Passphrase("correct horse battery staple")
        )

        assert "correct horse battery staple" not in caplog.text
        assert "--change-passphrase" in caplog.text


class TestKeyExpiredNoiseFiltering:
    """``[GNUPG:] KEYEXPIRED <ts>`` status lines never reach a raised message."""

    def test_strip_gnupg_noise_removes_keyexpired_line(self):
        stderr = (
            "gpg: some real problem\n"
            "[GNUPG:] KEYEXPIRED 1664870288\n"
            "gpg: more diagnostic\n"
        )

        cleaned = gpg_backend_module._strip_gnupg_noise(stderr)

        assert "KEYEXPIRED" not in cleaned
        assert "some real problem" in cleaned
        assert "more diagnostic" in cleaned

    def test_strip_gnupg_noise_leaves_ordinary_text_alone(self):
        text = "Could not delete key ABCD1234"

        assert gpg_backend_module._strip_gnupg_noise(text) == text

    def test_gpg_backend_error_strips_keyexpired_from_message(self):
        exc = GPGBackendError("gpg: signing failed\n[GNUPG:] KEYEXPIRED 1664870288\n")

        assert "KEYEXPIRED" not in str(exc)
        assert "signing failed" in str(exc)

    def test_bad_passphrase_error_also_strips_keyexpired(self):
        exc = BadPassphraseError("[GNUPG:] KEYEXPIRED 1664870288\nbad passphrase\n")

        assert "KEYEXPIRED" not in str(exc)
        assert "bad passphrase" in str(exc)

    def test_delete_key_error_never_shows_keyexpired(self, tmp_path, monkeypatch):
        backend = GPGBackend(tmp_path / "home")
        key = backend.generate_key(
            NewKeyRequest(name="Test User", email="test@example.com", key_length=1024)
        )

        class _FailedCompleted:
            returncode = 2
            stderr = "[GNUPG:] KEYEXPIRED 1664870288\ngpg: deletion failed\n"

        monkeypatch.setattr(
            gpg_backend_module, "_traced_run", lambda *a, **kw: _FailedCompleted()
        )

        with pytest.raises(GPGBackendError) as exc_info:
            backend.delete_key(key.fingerprint, secret=False)

        assert "KEYEXPIRED" not in str(exc_info.value)
        assert "deletion failed" in str(exc_info.value)

    def test_clean_stderr_mutates_in_place_and_returns_result(self):
        class _Result:
            stderr = "[GNUPG:] KEYEXPIRED 1664870288\ngpg: real error\n"

        result = _Result()

        returned = gpg_backend_module._clean_stderr(result)

        assert returned is result
        assert "KEYEXPIRED" not in result.stderr
        assert "real error" in result.stderr

    def test_clean_stderr_tolerates_missing_or_empty_stderr(self):
        class _NoStderr:
            pass

        class _EmptyStderr:
            stderr = ""

        gpg_backend_module._clean_stderr(_NoStderr())  # must not raise
        result = gpg_backend_module._clean_stderr(_EmptyStderr())
        assert result.stderr == ""

    def test_traced_run_cleans_stderr_at_the_source(self, monkeypatch):
        class _Completed:
            returncode = 0
            stderr = "[GNUPG:] KEYEXPIRED 1664870288\nharmless diagnostic\n"
            stdout = ""

        monkeypatch.setattr(
            gpg_backend_module.subprocess, "run", lambda *a, **kw: _Completed()
        )

        result = gpg_backend_module._traced_run(["gpg", "--version"])

        assert "KEYEXPIRED" not in result.stderr
        assert "harmless diagnostic" in result.stderr

    def test_run_with_agent_retry_cleans_stderr_at_the_source(self, tmp_path):
        backend = GPGBackend(tmp_path / "home")

        class _Result:
            fingerprint = "ABCD1234"
            stderr = "[GNUPG:] KEYEXPIRED 1664870288\n"

        cleaned = backend._run_with_agent_retry(lambda: _Result())

        assert "KEYEXPIRED" not in cleaned.stderr

    def test_search_keyserver_error_never_shows_keyexpired(self, tmp_path, monkeypatch):
        backend = GPGBackend(tmp_path / "home")

        class _EmptyResult(list):
            stderr = "[GNUPG:] KEYEXPIRED 1664870288\ngpg: search failed\n"

        monkeypatch.setattr(
            backend._gpg, "search_keys", lambda *a, **kw: _EmptyResult()
        )

        with pytest.raises(GPGBackendError) as exc_info:
            backend.search_keyserver("nobody@example.com", "hkps://example.org")

        assert "KEYEXPIRED" not in str(exc_info.value)
        assert "search failed" in str(exc_info.value)


# ── Third-party signatures from keyservers (self-sigs-only) ──────────────

_NO_SELF_SIGS_ONLY = ["--keyserver-options", "no-self-sigs-only"]


def _capture_recv_keys(monkeypatch, result):
    """Replace ``recv_keys`` with a fake recording each call's ``extra_args``."""
    extra = []

    def _fake_recv_keys(self, keyserver, *keyids, **kwargs):
        extra.append(kwargs.get("extra_args"))
        return result(self)

    monkeypatch.setattr(gnupg.GPG, "recv_keys", _fake_recv_keys)
    return extra


class _EmptyImportResult:
    fingerprints = ()
    returncode = 0
    stderr = ""
    count = 0


def test_keyserver_fetches_keep_gnupgs_self_sigs_only_default(tmp_path, monkeypatch):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Sigrid Example", email="sigrid@example.com", key_length=1024
        )
    )
    extra = _capture_recv_keys(monkeypatch, lambda gpg: _EmptyImportResult())

    backend.refresh_from_keyserver([key.fingerprint], keyservers=["hkps://a.example"])
    backend.download_unknown_signatures([key.fingerprint], ["hkps://a.example"])

    assert extra == [[], []]


def test_every_keyserver_fetch_passes_no_self_sigs_only_when_enabled(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Sigrid Example", email="sigrid@example.com", key_length=1024
        )
    )

    class _FoundImportResult:
        fingerprints = (key.fingerprint,)
        returncode = 0
        stderr = ""

    extra = _capture_recv_keys(monkeypatch, lambda gpg: _FoundImportResult())
    gpg_backend_module.set_keep_third_party_signatures(True)

    backend.import_from_keyserver(key.fingerprint, "hkps://a.example")
    backend.refresh_from_keyserver([key.fingerprint], keyservers=["hkps://a.example"])
    backend.download_unknown_signatures([key.fingerprint], ["hkps://a.example"])

    assert extra == [_NO_SELF_SIGS_ONLY] * 3


def test_email_lookup_passes_no_self_sigs_only_before_locate_keys_when_enabled(
    tmp_path, monkeypatch
):
    backend = GPGBackend(tmp_path / "home")
    key = backend.generate_key(
        NewKeyRequest(
            name="Sigrid Example", email="sigrid@example.com", key_length=1024
        )
    )
    calls = []
    real_run = gpg_backend_module.subprocess.run

    class _FakeCompleted:
        returncode = 0
        stderr = ""
        stdout = f"fpr:::::::::{key.fingerprint}:\n"

    def _fake_run(*args, **kwargs):
        if "--locate-keys" in args[0]:
            calls.append(args[0])
            return _FakeCompleted()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gpg_backend_module.subprocess, "run", _fake_run)
    gpg_backend_module.set_keep_third_party_signatures(True)

    backend.import_from_keyserver("sigrid@example.com", "hkps://a.example")

    (cmd,) = calls
    index = cmd.index("--keyserver-options")
    assert cmd[index + 1] == "no-self-sigs-only"
    # Like --keyserver: every option must precede --locate-keys, which
    # swallows every later argument as a user ID to locate.
    assert index < cmd.index("--locate-keys")
