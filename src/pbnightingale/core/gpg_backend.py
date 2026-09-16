"""Thin wrapper around python-gnupg exposing the operations PBNightingale needs.

Framework-agnostic: no PySide6 imports here.
GPG calls are synchronous and can take a noticeable time (key generation,
network operations in later milestones); running them without blocking the GUI
thread is the Qt-side worker's job, not this module's — see ``ui/gpg_worker.py``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import gnupg


class GPGBackendError(RuntimeError):
    """Raised when the GPG backend cannot be initialized or invoked."""


class BadPassphraseError(GPGBackendError):
    """Raised when gpg rejects the passphrase for a secret-key operation
    (add/revoke subkey). A specialization of GPGBackendError so the UI can
    show a short, friendly message instead of gpg's full diagnostic dump —
    see ``_is_bad_passphrase_error()``.
    """


# Emitted by gpg (as a `[GNUPG:] WARNING server_version_mismatch ...` status
# line) when it talks to an already-running gpg-agent from a different,
# incompatible GnuPG install — e.g. an older system package that was
# already running before this app's own (newer, conda-forge) gpg tried to
# use it. Some secret-key operations then fail outright rather than just
# warning. gpg's own suggested fix is `gpgconf --kill gpg-agent` (see
# CODING.md — "Subkey management"); the next operation needing the agent
# then autostarts a fresh one matching this install.
_AGENT_VERSION_MISMATCH_MARKER = "server_version_mismatch"

# Generous upper bound on a key's total secret-key parts (primary +
# subkeys) — see change_passphrase()'s docstring for why this many
# old-passphrase retries are queued as filler.
_MAX_SECRET_KEY_PARTS = 64

# libgpg-error GPG_ERR_BAD_PASSPHRASE (11), read off gpg's machine-readable
# `[GNUPG:] ERROR <location> <code>` status line (packed as
# (source << 24) | code) — locale-independent, unlike gpg's own
# human-readable "Mauvaise phrase secrète" / "Bad Passphrase" text, which
# would make this detection break for anyone not running gpg in French.
# Verified empirically against a real wrong-passphrase attempt.
_BAD_PASSPHRASE_CODE = 11
_ERROR_STATUS_RE = re.compile(r"\[GNUPG:\] ERROR \S+ (\d+)")


def _is_bad_passphrase_error(stderr: str) -> bool:
    return any(
        int(code) & 0xFFFF == _BAD_PASSPHRASE_CODE
        for code in _ERROR_STATUS_RE.findall(stderr)
    )


# libgpg-error GPG_ERR_NOT_FOUND (27), read off gpg's `[GNUPG:] FAILURE
# <location> <code>` status line — the same locale-independent decoding as
# _is_bad_passphrase_error() above, needed because `--search-keys` reports
# "no matches" as a failure rather than an empty success. Without this, a
# perfectly normal empty search result (e.g. a keyserver's own dirmngr
# logging an unrelated "server too old" warning alongside it) surfaces to
# the user as a raw gpg error dump instead of "0 results".
_NOT_FOUND_CODE = 27
_FAILURE_STATUS_RE = re.compile(r"\[GNUPG:\] FAILURE \S+ (\d+)")


def _is_not_found_failure(stderr: str) -> bool:
    return any(
        int(code) & 0xFFFF == _NOT_FOUND_CODE
        for code in _FAILURE_STATUS_RE.findall(stderr)
    )


# libgpg-error GPG_ERR_NO_DATA (58), the same locale-independent decoding as
# _is_not_found_failure() above. `--recv-keys`/`--refresh-keys` reports this
# as one overall FAILURE when at least one of several requested keys is no
# longer available from the keyserver (deleted, expired off it, a stale
# fingerprint, …) — even though every other key in the same batch refreshed
# fine. Without this, refreshing "all keys" turns into a raw multi-hundred-
# line gpg diagnostic dump the moment a single key in the keyring can't be
# found any more, instead of silently leaving that one key as-is and
# reporting every other key's real result — reported against real usage
# (a keyring with a keyserver-deleted key), see CODING.md.
_NO_DATA_CODE = 58


def _is_no_data_failure(stderr: str) -> bool:
    return any(
        int(code) & 0xFFFF == _NO_DATA_CODE
        for code in _FAILURE_STATUS_RE.findall(stderr)
    )


# `[GNUPG:] ATTRIBUTE <fpr> <octets> <type> <index> <count> <timestamp>
# <expiredate> <flags>` — one line per attribute subpacket seen during a
# key listing (see GnuPG's own doc/DETAILS). <type> 1 is an image; bit 0x02
# of <flags> means "this attribute packet is revoked" — both read straight
# off this status line, no extra --edit-key round trip needed for either.
_ATTRIBUTE_STATUS_RE = re.compile(
    r"\[GNUPG:\] ATTRIBUTE (\S+) (\d+) (\d+) \d+ \d+ \d+ \d+ (\d+)"
)
_IMAGE_ATTRIBUTE_TYPE = "1"
_ATTRIBUTE_REVOKED_FLAG = 0x02


def _parse_photos(stderr: str, attribute_data: bytes) -> dict[str, list[PhotoUid]]:
    """Split *attribute_data* (gpg's ``--attribute-file`` output) into
    per-fingerprint photos, using *stderr*'s ``ATTRIBUTE`` status lines to
    know each subpacket's key, size and revoked flag.

    Each subpacket is an RFC 4880 "Image Attribute": a little-endian
    16-bit header length, a version byte, a format byte (1 = JPEG), 12
    reserved bytes, then the raw image — the header length is read rather
    than assumed to be 16, in case a future header version is longer.
    """
    photos: dict[str, list[PhotoUid]] = {}
    cursor = 0
    for match in _ATTRIBUTE_STATUS_RE.finditer(stderr):
        fingerprint, octets_str, type_str, flags_str = match.groups()
        octets = int(octets_str)
        block = attribute_data[cursor : cursor + octets]
        cursor += octets
        if type_str != _IMAGE_ATTRIBUTE_TYPE or len(block) < 2:
            continue
        header_length = block[0] | (block[1] << 8)
        bucket = photos.setdefault(fingerprint, [])
        bucket.append(
            PhotoUid(
                index=len(bucket) + 1,
                image=bytes(block[header_length:]),
                revoked=bool(int(flags_str) & _ATTRIBUTE_REVOKED_FLAG),
            )
        )
    return photos


@dataclass(frozen=True)
class Uid:
    """A single user ID (identity) attached to a primary key.

    ``primary`` flags gpg's currently-designated primary UID. A single-UID
    key's only UID is trivially primary; for a key with more than one UID,
    gpg's plain ``--list-keys`` output never exposes which one is primary
    (that flag only shows up in ``--edit-key``'s interactive listing,
    verified empirically — see CODING.md, "Editable user IDs"), and UID
    listing order is *not* a reliable stand-in for it either (verified: UIDs
    added in order A, B, C came back listed as C, A, B). So a multi-UID key
    costs one extra ``gpg --edit-key`` subprocess call to resolve this —
    see ``GPGBackend._load_primary_uids()``/``_primary_uid_value()`` — kept
    cheap in aggregate by only paying it for keys that actually have more
    than one UID.
    """

    value: str
    revoked: bool
    primary: bool = False


def format_uid(name: str, email: str, comment: str = "") -> str:
    """Build a GPG user ID string, e.g. ``"Name (Comment) <email>"``.

    Mirrors the conventional form gpg itself produces from separate
    name/comment/email fields — used both for ``GPGBackend.add_uid()`` and
    for previewing the resulting identity in the UI.
    """
    return f"{name} ({comment}) <{email}>" if comment else f"{name} <{email}>"


@dataclass(frozen=True)
class PhotoUid:
    """A photo (image) user attribute attached to a primary key.

    ``index`` is 1-based, counting only this key's photos in the order gpg
    reports them — the identifier ``GPGBackend.revoke_photo_uid()`` needs,
    since (unlike a text ``Uid``) a photo has no string to select it by.
    """

    index: int
    image: bytes
    revoked: bool


@dataclass(frozen=True)
class Subkey:
    """A single subkey attached to a primary key."""

    keyid: str
    fingerprint: str
    algo: str
    length: int
    created: int
    expires: int | None
    trust: str
    can_sign: bool
    can_encrypt: bool
    can_certify: bool
    can_authenticate: bool


@dataclass(frozen=True)
class NewKeyRequest:
    """Parameters for ``GPGBackend.generate_key()``.

    ``algorithm`` is ``"RSA"`` or ``"ED25519"`` (EdDSA/Curve25519, the
    modern default pairing). ``signing_subkey``/``encryption_subkey`` (both
    ``True`` by default) each add a dedicated subkey with that usage; when
    one is turned off, the primary key itself takes on that usage instead —
    except encryption under ED25519, which EdDSA cannot itself provide, so
    a dedicated Curve25519 encryption subkey is always created regardless of
    ``encryption_subkey``. The primary key is otherwise certify-only, per
    current best practice. Expiration is always "never" for now — expiry
    management is milestone 11's concern.
    """

    name: str
    email: str
    comment: str = ""
    algorithm: str = "RSA"
    key_length: int = 4096
    passphrase: str = ""
    signing_subkey: bool = True
    encryption_subkey: bool = True


# Valid values for GPGBackend.set_owner_trust()'s *trust* argument, in
# increasing order — gpg's own --quick-set-ownertrust keywords, verified
# empirically (its own error message on an invalid value doesn't list them).
OWNER_TRUST_LEVELS = ("undefined", "never", "marginal", "full", "ultimate")

# GPGBackend.import_from_keyserver()'s default: a modern, privacy-respecting
# keyserver (no email search, doesn't propagate third-party signatures) run
# by the OpenPGP community — a sensible default for a fingerprint/key-ID
# fetch when the caller doesn't ask for a specific one.
DEFAULT_KEYSERVER = "hkps://keys.openpgp.org"


@dataclass(frozen=True)
class Key:
    """A primary key: its identity (UIDs) plus its subkeys.

    ``trust`` is the key's computed *validity* (how much the UID-to-key
    binding itself is trusted, per the web of trust) — confusingly, gpg's
    own colon output also calls this field "trust". ``owner_trust`` is a
    different thing entirely: how much *you* trust this key's owner to
    correctly certify *other* people's keys, a purely local judgment call
    (see ``GPGBackend.set_owner_trust()``) that feeds back into computing
    everyone else's validity. Both use the same one-letter codes (see
    ``ui/key_list_view.py``'s ``_trust_label()``).
    """

    fingerprint: str
    keyid: str
    algo: str
    length: int
    created: int
    expires: int | None
    trust: str
    owner_trust: str
    uids: list[Uid]
    photos: list[PhotoUid]
    subkeys: list[Subkey]
    has_secret: bool
    can_sign: bool
    can_encrypt: bool
    can_certify: bool
    can_authenticate: bool


@dataclass(frozen=True)
class SearchResult:
    """One hit from ``GPGBackend.search_keyserver()`` — enough to show a
    candidate in a picker; once chosen, it's imported by fingerprint
    through the already-exact ``import_from_keyserver()``.
    """

    fingerprint: str
    uids: list[str]
    algo: str
    length: int
    created: int


@dataclass(frozen=True)
class ImportedKey:
    """One key produced by ``import_from_keyserver()``/``import_from_file()``,
    plus whether it was absent from the keyring before this import (an
    entirely new key) as opposed to already present. gpg's import is a
    merge, so re-importing a key already in the keyring can still pick up
    new signatures/UIDs/subkeys without counting as "new" here — both
    cases report as already present, since there's no cheap way to tell
    "genuinely unchanged" from "merged something" apart without special-
    casing gpg's own per-import-source result shapes (the WKD/email path
    doesn't expose one at all — see ``import_from_keyserver()``).
    """

    key: Key
    is_new: bool


@dataclass(frozen=True)
class RefreshedKey:
    """One key produced by ``refresh_from_keyserver()``, plus whether
    anything about it actually changed.

    ``updated`` is computed by comparing the full ``Key`` snapshot before
    and after the refresh (frozen dataclasses compare structurally, deep
    through ``uids``/``photos``/``subkeys``) — this catches a new/revoked
    UID, a new subkey, a changed expiration or a validity change, but
    *not* a certification (signature) added by someone else that doesn't
    itself change any of those fields: same "no cheap way to tell
    genuinely unchanged from merged something apart" limitation already
    documented on ``ImportedKey`` above, just via a different mechanism
    (gpg's own per-import status reasons are exactly as ambiguous here).
    """

    key: Key
    updated: bool


@dataclass(frozen=True)
class KeySignature:
    """One certification found on a key's own user IDs, as reported by
    ``GPGBackend.list_key_signatures()`` (``gpg --list-sigs``).

    ``fingerprint`` comes straight from the signature packet's own "Issuer
    Fingerprint" subpacket — colon field 13 of the ``sig`` record — which
    GnuPG has embedded in every signature it makes since 2.1, regardless
    of whether the signing key is still present in the local keyring
    (verified empirically: deleting the signer from the keyring entirely
    still leaves this field populated). It's ``None`` only for a signature
    old enough to predate that subpacket, leaving ``keyid`` (the classic
    16-character long key ID) as the sole identifier. ``key`` is the
    matching local ``Key`` when the signer is already in the keyring,
    ``None`` otherwise. Self-certifications (the key signing its own user
    IDs) are excluded by ``list_key_signatures()``, not represented here.
    """

    keyid: str
    fingerprint: str | None
    key: Key | None


@dataclass(frozen=True)
class DownloadedSignature:
    """One signer key ``GPGBackend.download_unknown_signatures()`` tried to
    fetch from a keyserver, keyed by the *identifier* it was requested
    with (a ``KeySignature``'s ``fingerprint``, or its bare ``keyid`` when
    no fingerprint was available). ``key`` is populated on success,
    ``None`` when the keyserver has no such key.
    """

    identifier: str
    key: Key | None


@dataclass(frozen=True)
class ImportPreview:
    """One key that WOULD be imported by ``commit_import_from_file()``/
    ``commit_import_from_keyserver()``, for the caller to show the user
    before anything is actually committed to the real keyring.

    Deliberately lighter than ``Key``/``ImportedKey`` — just enough for
    the user to recognize and approve/reject a candidate (identities,
    full key ID, fingerprint, and whether it's already in the keyring).
    """

    fingerprint: str
    keyid: str
    uids: list[str]
    is_new: bool


def _int_or_none(value: str) -> int | None:
    return int(value) if value else None


def _decode_hkp_uid(uid: str) -> str:
    """Percent-decode a user ID coming from a keyserver's ``--search-keys``
    index listing.

    The HKP index format (RFC draft, ``op=index``) percent-encodes the uid
    field (e.g. a space as ``%20``, ``<``/``>`` as ``%3C``/``%3E``) like a
    URL component; gpg passes it straight through on its `uid` status line
    without decoding it, and python-gnupg's own uid parsing only handles
    gpg's *other* colon-format escapes (``\\xHH``, ``\\:``), not this one —
    so without this, search results show the raw encoded text.
    """
    return urllib.parse.unquote(uid)


_COLON_HEX_ESCAPE_RE = re.compile(r"\\x([0-9a-fA-F]{2})")
_COLON_BASIC_ESCAPES = {
    r"\n": "\n",
    r"\r": "\r",
    r"\f": "\f",
    r"\v": "\v",
    r"\b": "\b",
    r"\0": "\0",
}


def _unescape_colon_field(value: str) -> str:
    """Undo gpg's ``--with-colons`` string escaping (``\\xHH`` hex escapes
    plus a handful of named ones for control characters) — mirrors
    python-gnupg's own internal ``SearchKeys.uid()`` handling, needed here
    because ``_primary_uid_value()`` reads gpg's raw colon output directly
    via ``subprocess`` rather than through python-gnupg's own wrapper.
    """
    value = _COLON_HEX_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), value)
    for escaped, actual in _COLON_BASIC_ESCAPES.items():
        value = value.replace(escaped, actual)
    return value


def _has_capability(cap: str, letter: str) -> bool:
    """Return True if *letter* (s/e/c/a) appears in *cap*, in either case.

    python-gnupg's ``cap`` field concatenates the potential (lowercase) and
    usable (uppercase) capability letters, e.g. ``"escarESCA"``. Any casing
    of the letter being present is enough to consider the capability offered.
    """
    return letter in cap.lower()


def _parse_subkey(keyid: str, info: dict) -> Subkey:
    return Subkey(
        keyid=keyid,
        fingerprint=info.get("fingerprint", ""),
        algo=info.get("algo", ""),
        length=int(info["length"]) if info.get("length") else 0,
        created=_int_or_none(info.get("date", "")) or 0,
        expires=_int_or_none(info.get("expires", "")),
        trust=info.get("trust", ""),
        can_sign=_has_capability(info.get("cap", ""), "s"),
        can_encrypt=_has_capability(info.get("cap", ""), "e"),
        can_certify=_has_capability(info.get("cap", ""), "c"),
        can_authenticate=_has_capability(info.get("cap", ""), "a"),
    )


def _parse_uids(
    raw_uids: list[str], uid_map: dict[str, dict], primary_value: str | None
) -> list[Uid]:
    # uid_map (python-gnupg's ListKeys.uid_map) is keyed by raw UID string
    # across the *whole* listing, not scoped per key — a byte-identical UID
    # string on two different keys in the same keyring would collide here.
    # Harmless in practice (worst case: a wrong revoked flag on that rare
    # shared string) and there is no other public API to get per-UID
    # validity out of python-gnupg.
    #
    # A single-UID key's only UID is trivially primary (primary_value is
    # never even looked up for those — see _load_primary_uids()); for a
    # multi-UID key, only the one matching the resolved primary_value is
    # flagged (none are, if resolving it failed for some reason).
    single = len(raw_uids) == 1
    return [
        Uid(
            value=raw,
            revoked=uid_map.get(raw, {}).get("trust") == "r",
            primary=single or raw == primary_value,
        )
        for raw in raw_uids
    ]


def _parse_key(
    entry: dict,
    *,
    has_secret: bool,
    uid_map: dict[str, dict],
    photos: dict[str, list[PhotoUid]],
    primary_uids: dict[str, str],
) -> Key:
    subkey_info: dict = entry.get("subkey_info", {})
    subkeys = [
        _parse_subkey(keyid, info)
        for keyid, info in subkey_info.items()
        if info.get("type") == "sub"
    ]
    cap = entry.get("cap", "")
    return Key(
        fingerprint=entry["fingerprint"],
        keyid=entry["keyid"],
        algo=entry.get("algo", ""),
        length=int(entry["length"]) if entry.get("length") else 0,
        created=_int_or_none(entry.get("date", "")) or 0,
        expires=_int_or_none(entry.get("expires", "")),
        trust=entry.get("trust", ""),
        owner_trust=entry.get("ownertrust", ""),
        uids=_parse_uids(
            entry.get("uids", []), uid_map, primary_uids.get(entry["fingerprint"])
        ),
        photos=photos.get(entry["fingerprint"], []),
        subkeys=subkeys,
        has_secret=has_secret,
        can_sign=_has_capability(cap, "s"),
        can_encrypt=_has_capability(cap, "e"),
        can_certify=_has_capability(cap, "c"),
        can_authenticate=_has_capability(cap, "a"),
    )


def _algo_spec(algorithm: str, key_length: int) -> tuple[dict, str, str, bool]:
    """Return (primary ``gen_key_input`` kwargs, sign-subkey algorithm,
    encrypt-subkey algorithm, whether encryption *must* be a dedicated
    subkey) for *algorithm* (``"RSA"`` or ``"ED25519"``).
    """
    if algorithm == "ED25519":
        return (
            {"key_type": "eddsa", "key_curve": "ed25519"},
            "ed25519",
            "cv25519",
            True,
        )
    return (
        {"key_type": "RSA", "key_length": key_length},
        f"rsa{key_length}",
        f"rsa{key_length}",
        False,
    )


class GPGBackend:
    """Wraps a single GNUPGHOME and exposes the key operations the GUI needs.

    *gnupghome* must always be an isolated directory in tests — never the
    real user's keyring. Passing ``None`` uses GnuPG's own default
    (``~/.gnupg`` or platform equivalent), which is what the running application
    does in production.
    """

    def __init__(
        self,
        gnupghome: str | Path | None = None,
        *,
        gpgbinary: str | None = None,
    ) -> None:
        home = Path(gnupghome) if gnupghome is not None else None
        if home is not None:
            home.mkdir(mode=0o700, parents=True, exist_ok=True)
            home.chmod(0o700)
        kwargs: dict = {"gnupghome": str(home) if home else None}
        if gpgbinary is not None:
            kwargs["gpgbinary"] = gpgbinary
        try:
            self._gpg = gnupg.GPG(**kwargs)
        except (OSError, ValueError) as exc:
            raise GPGBackendError(str(exc)) from exc
        self._gpg.encoding = "utf-8"

    @property
    def home(self) -> str | None:
        return self._gpg.gnupghome

    def _homedir_args(self) -> list[str]:
        # self._gpg.gnupghome is None in production (no configure() override):
        # gpg then uses its own platform default homedir, which python-gnupg
        # never resolves to an actual path — passing None straight through to
        # subprocess.run() would raise a TypeError, so omit --homedir entirely
        # (mirrors python-gnupg's own make_args()).
        return ["--homedir", self._gpg.gnupghome] if self._gpg.gnupghome else []

    def _restart_agent(self) -> None:
        subprocess.run(  # noqa: S603
            ["gpgconf", *self._homedir_args(), "--kill", "gpg-agent"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )

    def _clear_agent_passphrase_cache(self) -> None:
        # RELOADAGENT (not _restart_agent()'s `gpgconf --kill`) flushes
        # gpg-agent's passphrase cache in place, synchronously — a kill is
        # asynchronous and can race the very next gpg call into reusing the
        # not-yet-dead agent's still-cached passphrase (verified
        # empirically). Only change_passphrase() needs this: every other
        # secret-key operation here is unaffected by (or actively benefits
        # from) an already-unlocked key.
        subprocess.run(  # noqa: S603
            ["gpg-connect-agent", *self._homedir_args(), "RELOADAGENT", "/bye"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_with_agent_retry(self, call):
        """Run *call* (returning a python-gnupg result with a ``fingerprint``
        and a ``stderr``); on a stale-agent version mismatch, restart the
        agent and retry once — see ``_AGENT_VERSION_MISMATCH_MARKER``.
        """
        result = call()
        if not result.fingerprint and _AGENT_VERSION_MISMATCH_MARKER in (
            result.stderr or ""
        ):
            self._restart_agent()
            result = call()
        return result

    @property
    def version(self) -> tuple[int, ...]:
        """The version of the underlying ``gpg`` binary, e.g. ``(2, 4, 4)``."""
        return self._gpg.version

    def list_keys(self, *, secret: bool = False) -> list[Key]:
        """Return the public keyring, or the secret keyring if *secret*.

        Public entries carry ``has_secret=True`` when a matching secret key
        also exists, so the UI can tell "your keys" apart from keys you only
        hold the public part of.
        """
        try:
            raw = self._gpg.list_keys(secret)
        except ValueError as exc:
            raise GPGBackendError(str(exc)) from exc

        photos = self._load_photos()
        primary_uids = self._load_primary_uids(raw)

        if secret:
            return [
                _parse_key(
                    entry,
                    has_secret=True,
                    uid_map=raw.uid_map,
                    photos=photos,
                    primary_uids=primary_uids,
                )
                for entry in raw
            ]

        secret_fingerprints = {e["fingerprint"] for e in self._gpg.list_keys(True)}
        return [
            _parse_key(
                entry,
                has_secret=entry["fingerprint"] in secret_fingerprints,
                uid_map=raw.uid_map,
                photos=photos,
                primary_uids=primary_uids,
            )
            for entry in raw
        ]

    def _load_photos(self) -> dict[str, list[PhotoUid]]:
        """Return ``{fingerprint: [PhotoUid, ...]}`` for the whole keyring.

        python-gnupg's own ``list_keys()`` silently drops "uat" (user
        attribute / photo) records: its record-type allowlist in
        ``_decode_result()`` doesn't include them (verified against its
        source). This runs one extra raw listing with ``--attribute-file``
        to recover the image bytes and each photo's revoked flag instead —
        one subprocess call for the *whole* keyring, not one per key, since
        the ``ATTRIBUTE`` status line already names the fingerprint.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            attribute_path = Path(tmp_dir) / "attributes"
            result = subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--with-colons",
                    "--status-fd",
                    "2",
                    "--attribute-file",
                    str(attribute_path),
                    "--list-keys",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            attribute_data = (
                attribute_path.read_bytes() if attribute_path.exists() else b""
            )
        return _parse_photos(result.stderr, attribute_data)

    def _load_primary_uids(self, raw) -> dict[str, str]:
        """Return ``{fingerprint: primary_uid_value}``, computed only for
        keys with more than one UID — see ``Uid.primary``'s docstring for
        why a single-UID key never needs this. Unlike ``_load_photos()``,
        this can't be done in one pass over the whole keyring: the primary
        flag only appears in ``--edit-key``'s own listing, which is
        inherently per-key, so this costs one ``gpg`` subprocess call for
        each key that actually has more than one identity.
        """
        return {
            entry["fingerprint"]: value
            for entry in raw
            if len(entry.get("uids", [])) > 1
            for value in [self._primary_uid_value(entry["fingerprint"])]
            if value is not None
        }

    def _primary_uid_value(self, fingerprint: str) -> str | None:
        """Return the exact UID string gpg currently considers primary for
        *fingerprint*, or ``None`` if it can't be determined.

        Scripted the same way as the photo-revoked-flag lookup right above
        this class's other ``--edit-key`` uses (``list``/``quit``, no
        passphrase needed for a read-only listing): the ``uid`` colon
        record's second-to-last field holds ``"<rank>,p"`` for the primary
        UID and just ``"<rank>,"`` for the others (verified empirically —
        undocumented in gpg's own doc/DETAILS, which only spells out the
        plain ``--list-keys`` colon format, not ``--edit-key``'s).
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--no-tty",
                "--command-fd",
                "0",
                "--with-colons",
                "--edit-key",
                fingerprint,
            ],
            input="list\nquit\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        primary_blocks_seen = 0
        for line in result.stdout.splitlines():
            fields = line.split(":")
            if fields[0] in ("sec", "pub"):
                primary_blocks_seen += 1
                if primary_blocks_seen > 1:
                    # "list" prints the whole listing twice before quitting
                    # (verified empirically, same as the photo lookup).
                    break
            elif fields[0] == "uid" and len(fields) > 13:
                if "p" in fields[13].split(","):
                    return _unescape_colon_field(fields[9])
        return None

    def generate_key(self, request: NewKeyRequest) -> Key:
        """Generate a new personal key per *request* and return it.

        Blocking (can take a noticeable time for large key sizes) — always
        run via ``ui/gpg_worker.run_async``, never on the GUI thread.
        """
        primary_kwargs, sign_algo, encrypt_algo, encryption_forced = _algo_spec(
            request.algorithm, request.key_length
        )
        need_encryption_subkey = request.encryption_subkey or encryption_forced

        usage = ["cert"]
        if not request.signing_subkey:
            usage.append("sign")
        if not need_encryption_subkey:
            usage.append("encrypt")

        input_data = self._gpg.gen_key_input(
            key_usage=",".join(usage),
            name_real=request.name,
            name_comment=request.comment,
            name_email=request.email,
            expire_date="0",
            passphrase=request.passphrase,
            no_protection=not request.passphrase,
            **primary_kwargs,
        )
        result = self._run_with_agent_retry(lambda: self._gpg.gen_key(input_data))
        if not result.fingerprint:
            raise GPGBackendError(str(result.stderr))

        if request.signing_subkey:
            self._add_subkey(result.fingerprint, request.passphrase, sign_algo, "sign")
        if need_encryption_subkey:
            self._add_subkey(
                result.fingerprint, request.passphrase, encrypt_algo, "encrypt"
            )

        return self._find_key(result.fingerprint)

    def add_subkey(
        self,
        fingerprint: str,
        passphrase: str,
        *,
        usage: str,
        algorithm: str = "RSA",
        key_length: int = 4096,
    ) -> Key:
        """Add a new subkey to an existing (secret) key and return it updated.

        *usage* is ``"sign"``, ``"encrypt"`` or ``"auth"``. *algorithm* is
        ``"RSA"`` or ``"ED25519"`` — for ED25519 the actual curve is picked
        from *usage* (EdDSA for sign/auth, Curve25519 for encrypt, since
        EdDSA itself cannot encrypt).
        """
        if algorithm == "ED25519":
            raw_algorithm = "cv25519" if usage == "encrypt" else "ed25519"
        else:
            raw_algorithm = f"rsa{key_length}"
        self._add_subkey(fingerprint, passphrase, raw_algorithm, usage)
        return self._find_key(fingerprint)

    def _add_subkey(
        self, fingerprint: str, passphrase: str, algorithm: str, usage: str
    ) -> None:
        # master_passphrase must be a string, never None, even when empty:
        # python-gnupg only enables --pinentry-mode loopback when the value
        # is not None, and an unprotected primary key still needs that mode
        # to add a subkey without an interactive pinentry program available.
        result = self._run_with_agent_retry(
            lambda: self._gpg.add_subkey(
                master_key=fingerprint,
                master_passphrase=passphrase,
                algorithm=algorithm,
                usage=usage,
                expire="0",
            )
        )
        if not result:
            stderr = str(result.stderr)
            if _is_bad_passphrase_error(stderr):
                raise BadPassphraseError(stderr)
            raise GPGBackendError(stderr)

    def change_passphrase(
        self, fingerprint: str, old_passphrase: str, new_passphrase: str
    ) -> Key:
        """Change the passphrase protecting *fingerprint*'s secret key.

        Uses gpg's dedicated ``--change-passphrase`` command rather than
        scripting ``--edit-key``'s ``passwd`` sub-command: unlike ``passwd``,
        a wrong old passphrase is reported as a proper ``[GNUPG:] ERROR
        keyedit.passwd <code>`` status line, so ``_is_bad_passphrase_error()``
        works unmodified — the ``--edit-key`` route only ever emits a
        localized "erreur de modification..." message with no
        machine-readable code for this specific failure (verified
        empirically).

        The script fed over ``--command-fd`` has one entry for the old
        passphrase and one for the new one — no repeat-to-confirm step over
        this protocol, that's purely a client-side UI concern (see
        ``ui/change_passphrase_dialog.py``). Critically, this call always
        clears gpg-agent's own passphrase cache for the whole session first
        (``RELOADAGENT`` via ``gpg-connect-agent``, not ``_restart_agent()``'s
        ``gpgconf --kill``, which is asynchronous and races the very next
        call): if the agent still has *this* key cached from an earlier,
        unrelated operation in the same session (its default cache TTL is
        several minutes), gpg silently skips the old-passphrase prompt
        entirely and only asks once — so this call's fixed two-line script
        would misfire, feeding *old_passphrase*'s value into the slot meant
        for the new passphrase instead. Verified empirically against a real
        agent; see CODING.md, "Changing a key's passphrase".

        Only meaningful for a key that is *already* passphrase-protected —
        this dialog always asks for the current passphrase first, which
        presupposes one exists. Verified empirically: unlike ``--edit-key``'s
        ``passwd`` sub-command, ``--change-passphrase`` silently does
        nothing when *fingerprint* currently has no protection at all
        (``old_passphrase`` would be ``""`` with nothing to actually check),
        even though it reports success — it is not a substitute for a
        "protect this bare key" operation.

        A *correct* old passphrase always takes exactly two prompts
        (old, then new) no matter how many subkeys the key has — gpg
        unlocks the primary key once and reuses that for every subkey via
        its own agent cache. A *wrong* one does not: with nothing to cache,
        gpg retries the old-passphrase prompt once per secret-key part
        (primary + each subkey) before finally giving up, and it cannot be
        told apart from a correct one until each of those has actually
        played out — so ``old_passphrase`` is repeated ``_MAX_SECRET_PARTS``
        times as trailing filler, a generous upper bound on primary +
        subkeys no real key should ever reach. Without this, a key with
        4+ secret parts and a wrong passphrase runs this call's input dry
        partway through that retry sequence, which gpg reports as a plain
        "operation canceled" (``[GNUPG:] ERROR keyedit.passwd`` code 99,
        not 11) rather than the expected bad-passphrase code — silently
        defeating ``_is_bad_passphrase_error()`` and surfacing gpg's whole
        raw, multi-attempt diagnostic dump to the user instead of a clean
        message (reported against a real 4-part key; verified empirically).
        The extra filler lines are harmless once a real success or failure
        is reached: gpg simply stops reading and exits without consuming
        them, exactly like the trailing ``save`` line below (not a
        ``--edit-key`` REPL command — verified unread even today).
        """
        self._clear_agent_passphrase_cache()
        retries = f"{old_passphrase}\n" * _MAX_SECRET_KEY_PARTS
        script = f"{old_passphrase}\n{new_passphrase}\n{retries}save\n"

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--pinentry-mode",
                    "loopback",
                    "--command-fd",
                    "0",
                    "--status-fd",
                    "2",
                    "--change-passphrase",
                    fingerprint,
                ],
                input=script,
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def revoke_subkey(
        self, fingerprint: str, subkey_keyid: str, passphrase: str
    ) -> Key:
        """Revoke one subkey of the key identified by *fingerprint*.

        Irreversible — the caller must already have obtained a strong
        confirmation from the user before calling this. python-gnupg has no
        wrapper for subkey revocation, so this drives ``gpg --edit-key``
        directly over its `--command-fd`/`--status-fd` scripting protocol
        (verified empirically; see CODING.md — "Subkey management").
        """
        script = f"key {subkey_keyid}\nrevkey\ny\n0\n\ny\n{passphrase}\nsave\n"

        def _run() -> subprocess.CompletedProcess:
            # --status-fd 2 (stderr), matching python-gnupg's own
            # make_args(): keeps every diagnostic (both the human "gpg: …"
            # lines and the machine-readable "[GNUPG:] …" status lines) in
            # one stream, since both the agent-mismatch and bad-passphrase
            # detection below read result.stderr.
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--pinentry-mode",
                    "loopback",
                    "--command-fd",
                    "0",
                    "--status-fd",
                    "2",
                    "--edit-key",
                    fingerprint,
                ],
                input=script,
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def revoke_key(self, fingerprint: str, passphrase: str) -> Key:
        """Revoke the primary key identified by *fingerprint* itself — not
        one of its subkeys (see ``revoke_subkey()``).

        Irreversible — the caller must already have obtained a strong
        confirmation from the user before calling this. Same
        ``--edit-key`` scripting as ``revoke_subkey()``, minus the leading
        ``key <keyid>`` selection: with no subkey selected, ``revkey``
        targets the primary key instead (verified empirically).
        """
        script = f"revkey\ny\n0\n\ny\n{passphrase}\nsave\n"

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--pinentry-mode",
                    "loopback",
                    "--command-fd",
                    "0",
                    "--status-fd",
                    "2",
                    "--edit-key",
                    fingerprint,
                ],
                input=script,
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def delete_key(self, fingerprint: str, *, secret: bool) -> None:
        """Permanently remove *fingerprint* from the keyring — unlike
        ``revoke_key()``, which keeps the (now untrustworthy) key around,
        this actually erases the key material, public and (if *secret*)
        private alike. Irreversible — the caller must already have
        obtained a strong confirmation from the user before calling this.

        No passphrase needed: deleting is a local keyring-management
        operation, not a cryptographic one, so GnuPG never asks to unlock
        the secret key for it (unlike revoking, which must produce a
        valid signature).
        """
        command = "--delete-secret-and-public-key" if secret else "--delete-keys"
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--yes",
                command,
                fingerprint,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GPGBackendError(
                result.stderr or f"Could not delete key {fingerprint}"
            )

    def add_uid(
        self,
        fingerprint: str,
        passphrase: str,
        *,
        name: str,
        email: str,
        comment: str = "",
    ) -> Key:
        """Add a new user ID (identity) to an existing (secret) key."""
        uid = format_uid(name, email, comment)
        self._run_quick_command("--quick-add-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def set_primary_uid(self, fingerprint: str, passphrase: str, uid: str) -> Key:
        """Flag *uid* (an existing UID's exact string) as the primary
        identity of the key identified by *fingerprint*."""
        self._run_quick_command("--quick-set-primary-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def revoke_uid(self, fingerprint: str, passphrase: str, uid: str) -> Key:
        """Revoke *uid* (an existing UID's exact string) on the key
        identified by *fingerprint*.

        Irreversible — the caller must already have obtained a strong
        confirmation from the user before calling this. gpg itself refuses
        to revoke the last non-revoked UID on a key (raised as a plain
        ``GPGBackendError``); the UI should disable this action in that case
        rather than let the user hit that wall.
        """
        self._run_quick_command("--quick-revoke-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def set_key_expiration(self, fingerprint: str, passphrase: str, expire: str) -> Key:
        """Set the primary key's own expiration.

        *expire* follows gpg's own ``--quick-set-expire`` syntax: ``"0"``
        for no expiration, ``"<n>d"``/``"w"``/``"m"``/``"y"`` for a relative
        duration from now, or an absolute ``"YYYY-MM-DD"`` date. Leaves
        every subkey's own expiration untouched — verified empirically,
        see CODING.md, "Expiration dates".
        """
        self._run_quick_command("--quick-set-expire", fingerprint, passphrase, expire)
        return self._find_key(fingerprint)

    def set_subkey_expiration(
        self, fingerprint: str, passphrase: str, subkey_fingerprint: str, expire: str
    ) -> Key:
        """Set one subkey's expiration, identified by *subkey_fingerprint*
        (the subkey's own fingerprint, not the primary key's) — see
        ``Subkey.fingerprint``. Leaves the primary key's own expiration and
        every other subkey's untouched.
        """
        self._run_quick_command(
            "--quick-set-expire", fingerprint, passphrase, expire, subkey_fingerprint
        )
        return self._find_key(fingerprint)

    def sign_key(
        self,
        fingerprint: str,
        passphrase: str,
        *,
        signing_key_fingerprint: str,
        cert_level: int = 0,
        local_only: bool = False,
    ) -> Key:
        """Sign every user ID of the key identified by *fingerprint*, using
        the secret key identified by *signing_key_fingerprint* — the
        foundation of the web of trust.

        *cert_level* (0-3) is gpg's own certification-check scale: 0 (no
        particular claim), 1 (not verified — a "persona" signature), 2
        (casual verification), 3 (extensive verification). *local_only*
        drives ``--quick-lsign-key`` instead of ``--quick-sign-key``: a
        local signature never leaves this keyring on export, useful for
        casual verification the signer isn't ready to assert publicly.
        """
        command = "--quick-lsign-key" if local_only else "--quick-sign-key"
        self._run_quick_command(
            command,
            fingerprint,
            passphrase,
            extra_options=(
                "-u",
                signing_key_fingerprint,
                "--default-cert-level",
                str(cert_level),
            ),
        )
        return self._find_key(fingerprint)

    def set_owner_trust(self, fingerprint: str, trust: str) -> Key:
        """Set how much *fingerprint*'s owner is trusted to correctly
        certify other people's keys — the other half of the web of trust
        (see ``sign_key()``): a signature only strengthens a key's
        computed *validity* if it comes from a sufficiently trusted owner.

        *trust* is one of ``"undefined"``, ``"never"``, ``"marginal"``,
        ``"full"`` or ``"ultimate"``. Unlike every other write operation in
        this module, this is a purely local judgment call recorded in the
        trust database — no secret key or passphrase is involved at all.
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--yes",
                "--status-fd",
                "2",
                "--quick-set-ownertrust",
                fingerprint,
                trust,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def refresh_trust(self) -> None:
        """Recompute the web of trust for the whole keyring, without
        prompting for anything (``--check-trustdb``, not the interactive
        ``--update-trustdb``) — skips keys with a not-yet-defined
        ownertrust rather than asking about them.
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--yes",
                "--status-fd",
                "2",
                "--check-trustdb",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GPGBackendError(result.stderr)

    def _run_quick_command(
        self,
        command: str,
        fingerprint: str,
        passphrase: str,
        *args: str,
        extra_options: tuple[str, ...] = (),
    ) -> None:
        # No python-gnupg wrapper for any of gpg's --quick-* commands
        # (2.1+) — they all take the passphrase non-interactively via
        # --passphrase-fd, unlike subkey/photo revocation which still need
        # the --edit-key scripting protocol (see revoke_subkey()). The
        # passphrase is piped over stdin, never passed as a --passphrase
        # argument, so it never shows up in a process listing.
        # *extra_options* are inserted before *command* itself — e.g.
        # sign_key()'s "-u <signer>" and "--default-cert-level <n>", which
        # (unlike every other quick command's arguments) are options of
        # gpg itself, not positional arguments of the command.
        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-fd",
                    "0",
                    "--status-fd",
                    "2",
                    *extra_options,
                    command,
                    fingerprint,
                    *args,
                ],
                input=passphrase,
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)

    def add_photo_uid(
        self, fingerprint: str, passphrase: str, jpeg_path: str | Path
    ) -> Key:
        """Add a photo user ID from the JPEG file at *jpeg_path*.

        python-gnupg has no wrapper for this either — like UID/subkey
        revocation, it drives ``gpg --edit-key``'s ``addphoto`` directly
        over the ``--command-fd``/``--status-fd`` scripting protocol.
        Verified empirically (see CODING.md, "Photo user IDs"): unlike
        subkey revocation, gpg asks for the passphrase (to sign the new
        self-signature — needed even on an unprotected key, where the
        empty line is just harmlessly consumed) right after the file path
        is accepted, *before* ``save`` — not at save time. ``--no-tty`` is
        required: without it, ``addphoto`` tries to open a controlling
        terminal and fails outright in any headless or GUI-launched
        process that doesn't have one.

        gpg also asks an extra ``photoid.jpeg.size`` yes/no confirmation
        right after the file path for a JPEG above some internal size
        threshold ("this is quite a large JPEG, use it anyway?") — a tiny
        placeholder image never triggers it, but any real photo routinely
        does. This can't be scripted blindly like every other step here:
        reported against real usage, always answering it unconditionally
        (on the theory that an extra line is harmless when unneeded, as it
        is for the passphrase step on an unprotected key) instead corrupts
        the *small*-JPEG-on-a-*protected*-key case — there, gpg asks for
        the passphrase immediately after the file path with no prompt in
        between, so the unconditional filler line gets consumed as the
        passphrase itself. There is no option to suppress the prompt and
        no documented size threshold to replicate client-side, so this
        peeks at gpg's live status output just long enough to see whether
        it actually shows up this time before deciding what to send next.
        """

        def _run() -> subprocess.CompletedProcess:
            process = subprocess.Popen(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--no-tty",
                    "--pinentry-mode",
                    "loopback",
                    "--command-fd",
                    "0",
                    "--status-fd",
                    "2",
                    "--edit-key",
                    fingerprint,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # A separate pipe, like every other method here — not merged
                # into stdout via STDOUT. Merging was tried first and caused
                # a real deadlock: gpg's stdout is fully block-buffered
                # (glibc stdio, since it isn't a tty) once anything else
                # shares that fd, so status lines sat in gpg's own internal
                # buffer instead of reaching this process, while this
                # process sat blocked reading them — each side waiting on
                # the other forever. stderr in C is unbuffered by default,
                # which is exactly why the original blind-script version of
                # this method (and every sibling method) already used
                # ``--status-fd 2`` — this keeps that, and only reads this
                # one pipe up front (never stdout, which stays small and
                # unread until the final communicate() drains both safely).
                stderr=subprocess.PIPE,
                text=True,
            )
            assert process.stdin is not None  # noqa: S101 — for the type checker
            assert process.stderr is not None  # noqa: S101

            output: list[str] = []

            def _send(line: str) -> None:
                process.stdin.write(line + "\n")
                process.stdin.flush()

            _send("addphoto")
            _send(str(jpeg_path))
            # gpg's very first prompt is "GET_LINE keyedit.prompt" (asking
            # for the "addphoto" command itself), which looks identical to
            # the "back at the main prompt, nothing more to sign" signal
            # looked for below — so that signal can't be trusted until
            # *after* the file has actually been requested once. Without
            # this guard the loop broke on that very first prompt, sent
            # the passphrase where gpg still expected the file path, and
            # the whole exchange deadlocked (verified: reproduced a hang
            # identical to the reported bug's cascade of misread lines).
            seen_file_request = False
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                output.append(line)
                if not seen_file_request:
                    if "GET_LINE photoid.jpeg.add" in line:
                        seen_file_request = True
                    continue
                if "GET_BOOL photoid.jpeg.size" in line:
                    _send("y")
                    break
                if (
                    "GET_HIDDEN" in line
                    or "GET_LINE keyedit.prompt" in line
                    or "GET_LINE photoid.jpeg.add" in line
                ):
                    # Either straight to the passphrase (no confirmation
                    # this time), back at the main prompt (nothing to sign
                    # on an unprotected key), or gpg rejected the file and
                    # is asking for it again — in every case, the rest of
                    # the script below is exactly what a plain --edit-key
                    # flow with no size prompt already expects next.
                    break

            remaining_stdout, remaining_stderr = process.communicate(
                f"{passphrase}\nsave\n"
            )
            output.append(remaining_stderr)
            return subprocess.CompletedProcess(
                process.args,
                process.returncode,
                stdout=remaining_stdout,
                stderr="".join(output),
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def revoke_photo_uid(
        self, fingerprint: str, passphrase: str, photo_index: int
    ) -> Key:
        """Revoke the *photo_index*-th photo (1-based, in ``Key.photos``
        order) on the key identified by *fingerprint*.

        Irreversible — the caller must already have obtained a strong
        confirmation. There is no ``--quick-revoke-uid`` equivalent for a
        photo (it has no text to match against), so this drives
        ``gpg --edit-key`` directly, same shape as ``revoke_subkey()``,
        after resolving *photo_index* to gpg's own uid-editing index via
        ``_resolve_photo_edit_index()``.
        """
        edit_index = self._resolve_photo_edit_index(fingerprint, photo_index)
        script = f"uid {edit_index}\nrevuid\ny\n0\n\ny\n{passphrase}\nsave\n"

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--no-tty",
                    "--pinentry-mode",
                    "loopback",
                    "--command-fd",
                    "0",
                    "--status-fd",
                    "2",
                    "--edit-key",
                    fingerprint,
                ],
                input=script,
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(result.stderr)
        return self._find_key(fingerprint)

    def _resolve_photo_edit_index(self, fingerprint: str, photo_index: int) -> int:
        """Return the ``uid N`` index ``--edit-key`` uses for the
        *photo_index*-th photo (1-based) on *fingerprint*, read off a
        read-only ``list`` — see ``Key.photos``/``PhotoUid.index``.
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--yes",
                "--no-tty",
                "--command-fd",
                "0",
                "--with-colons",
                "--status-fd",
                "2",
                "--edit-key",
                fingerprint,
            ],
            input="list\nquit\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GPGBackendError(result.stderr)

        seen_photos = 0
        primary_blocks_seen = 0
        for line in result.stdout.splitlines():
            fields = line.split(":")
            if fields[0] in ("sec", "pub"):
                primary_blocks_seen += 1
                if primary_blocks_seen > 1:
                    # --edit-key's "list" prints the whole listing twice
                    # before quitting (verified empirically) — stop at the
                    # first repeat so photos aren't double-counted.
                    break
            elif fields[0] == "uat" and len(fields) > 13:
                seen_photos += 1
                if seen_photos == photo_index:
                    return int(fields[13].split(",")[0])
        raise GPGBackendError(f"Photo {photo_index} not found on key {fingerprint}")

    def import_from_file(self, path: str | Path) -> list[ImportedKey]:
        """Import one or more keys from an exported key file (armored or
        binary; a single key or a whole keyring export) and return them,
        each flagged with whether it was new to the keyring.
        """
        existing = {e["fingerprint"] for e in self._gpg.list_keys(False)}
        result = self._gpg.import_keys_file(str(path))
        if not result.fingerprints:
            raise GPGBackendError(str(result.stderr) or f"No key found in {path}")
        return [
            ImportedKey(self._find_key(fp), fp not in existing)
            for fp in result.fingerprints
        ]

    def _locate_key_by_email(
        self, email: str, keyserver: str
    ) -> tuple[str | None, str]:
        """Resolve *email* to a fingerprint via gpg's own auto-key-locate
        (WKD first, falling back to *keyserver*), importing it into the
        keyring as a side effect if found. Returns ``(fingerprint, stderr)``
        — *fingerprint* is ``None`` if nothing was found.

        Scripted directly with ``subprocess`` rather than python-gnupg's
        own ``auto_locate_key()``: that method appends its ``extra_args``
        (needed here for ``--keyserver``) *after* the positional *email*
        argument to ``--locate-keys``, which gpg then swallows as an
        extra, bogus user ID to locate instead of parsing as an option —
        verified empirically (gpg's own "« --keyserver » n'est pas
        considéré comme une option"). This silently breaks the keyserver
        fallback whenever WKD itself fails (no WKD endpoint published for
        the domain, or a plain DNS failure) — unless the key happened to
        already be cached in the keyring from an earlier lookup, which is
        exactly why this went unnoticed until ``preview_import_from_keyserver()``
        started exercising a cold lookup against a keyring that never has
        anything cached. Every option — not just ``--keyserver`` — must
        come *before* ``--auto-key-locate``/``--locate-keys``, which
        consumes every argument after it as a user ID to locate.
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--batch",
                "--no-tty",
                "--status-fd",
                "2",
                "--with-colons",
                "--keyserver",
                keyserver,
                "--auto-key-locate",
                "wkd,keyserver",
                "--locate-keys",
                email,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                fields = line.split(":")
                if fields[0] == "fpr":
                    return fields[9], result.stderr
        return None, result.stderr

    def import_from_keyserver(
        self, query: str, keyserver: str = DEFAULT_KEYSERVER
    ) -> list[ImportedKey]:
        """Import a key from a keyserver, identified by fingerprint, key
        ID, or email address.

        An address containing "@" is resolved through gpg's own
        auto-key-locate (WKD first — a direct HTTPS lookup at the email
        domain's own well-known endpoint, no keyserver search involved —
        falling back to *keyserver*), since public keyservers generally
        don't support lookup by email at all: `--search-keys` (the one
        keyserver operation that does) returns a numbered list for
        *interactive* disambiguation, which has no non-interactive
        equivalent to script against, and modern keyservers such as
        keys.openpgp.org don't index email addresses at all for privacy
        reasons. See CODING.md, "Key import". Anything else is treated as
        a literal fingerprint or key ID and fetched directly with
        `--recv-keys`, which needs an exact match.
        """
        query = query.strip()
        existing = {e["fingerprint"] for e in self._gpg.list_keys(False)}
        if "@" in query:
            fingerprint, stderr = self._locate_key_by_email(query, keyserver)
            if fingerprint is None:
                raise GPGBackendError(stderr or f"No key found for {query}")
            return [
                ImportedKey(self._find_key(fingerprint), fingerprint not in existing)
            ]
        result = self._gpg.recv_keys(keyserver, query)
        if not result.fingerprints:
            if (
                getattr(result, "count", 0)
                and not getattr(result, "imported", 0)
                and not getattr(result, "unchanged", 0)
            ):
                # gpg fetched something (count > 0) but imported nothing —
                # not "not found" (that's count == 0 with empty stderr or a
                # FAILURE search-keys/not-found status, handled elsewhere).
                # The one case seen in practice: the key has no user ID at
                # all, which some GnuPG versions (verified: 2.5.22 exits
                # with FAILURE gpg-exit for this, unlike 2.4.4's plain
                # "skipped") refuse to import outright. keys.openpgp.org
                # strips every UID from a key whose email hasn't been
                # verified there, which is the common real-world cause.
                # gpg's own text for this ("no user ID") is locale-
                # dependent, so it isn't matched here — only the numeric,
                # locale-independent IMPORT_RES counts are.
                raise GPGBackendError(
                    "This key has no user ID attached, so gpg could not "
                    "import it (common for a key on keys.openpgp.org whose "
                    "email address hasn't been verified there)."
                )
            raise GPGBackendError(str(result.stderr) or f"No key found for {query}")
        return [
            ImportedKey(self._find_key(fp), fp not in existing)
            for fp in result.fingerprints
        ]

    def preview_import_from_file(self, path: str | Path) -> list[ImportPreview]:
        """Report what ``commit_import_from_file()`` would import from
        *path*, without touching the keyring at all.

        Uses python-gnupg's ``scan_keys()``, which drives gpg's own
        ``--dry-run --import-options import-show --import`` — verified
        empirically to leave the keyring untouched (``list_keys()``
        unchanged before/after) and to report the same fingerprint/keyid/
        uids shape as a real listing.
        """
        existing = {e["fingerprint"] for e in self._gpg.list_keys(False)}
        result = self._gpg.scan_keys(str(path))
        if not result:
            raise GPGBackendError(str(result.stderr) or f"No key found in {path}")
        return [
            ImportPreview(
                fingerprint=entry["fingerprint"],
                keyid=entry["keyid"],
                uids=list(entry["uids"]),
                is_new=entry["fingerprint"] not in existing,
            )
            for entry in result
        ]

    def preview_import_from_keyserver(
        self, query: str, keyserver: str = DEFAULT_KEYSERVER
    ) -> list[ImportPreview]:
        """Report what ``commit_import_from_keyserver()`` would import for
        *query*, without touching this keyring at all.

        There is no dry-run equivalent for a keyserver/WKD fetch — gpg
        always merges straight into whatever keyring it's pointed at — so
        this actually fetches into a throwaway scratch keyring instead
        (discarded before returning), and reuses ``import_from_keyserver()``
        entirely for the fetch itself (WKD/email vs. exact key ID, and its
        error messages). ``is_new`` is recomputed against *this* (real)
        keyring — the scratch keyring's own copy is always "new" since it
        started empty, which isn't the answer the caller needs.
        """
        existing = {e["fingerprint"] for e in self._gpg.list_keys(False)}
        scratch_dir = tempfile.mkdtemp()
        try:
            scratch = GPGBackend(scratch_dir, gpgbinary=self._gpg.gpgbinary)
            imported = scratch.import_from_keyserver(query, keyserver)
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)
        return [
            ImportPreview(
                fingerprint=entry.key.fingerprint,
                keyid=entry.key.keyid,
                uids=[uid.value for uid in entry.key.uids],
                is_new=entry.key.fingerprint not in existing,
            )
            for entry in imported
        ]

    def _commit_filtered(
        self, imported: list[ImportedKey], approved: set[str]
    ) -> list[ImportedKey]:
        """After a real import that may have brought in more keys than the
        user approved, delete any newly-added (never pre-existing) key
        that wasn't approved, and return only the approved ones.

        A key that was already present is left untouched either way —
        leaving it unchecked only means "don't count it as imported here",
        never "remove my existing copy".
        """
        kept = []
        for entry in imported:
            if entry.key.fingerprint in approved:
                kept.append(entry)
            elif entry.is_new:
                self.delete_key(entry.key.fingerprint, secret=False)
        return kept

    def commit_import_from_file(
        self, path: str | Path, approved: set[str]
    ) -> list[ImportedKey]:
        """Import from *path* for real, keeping only the *approved*
        fingerprints (see ``preview_import_from_file()``) — any other,
        newly-added key that came along in the same file is removed again
        immediately. A no-op (no import at all) if *approved* is empty.
        """
        if not approved:
            return []
        return self._commit_filtered(self.import_from_file(path), approved)

    def commit_import_from_keyserver(
        self, query: str, keyserver: str, approved: set[str]
    ) -> list[ImportedKey]:
        """Import *query* from *keyserver* for real, keeping only the
        *approved* fingerprints (see ``preview_import_from_keyserver()``).
        A no-op — no fetch at all — if *approved* is empty, so declining
        the one candidate this can ever surface never touches the network
        or the keyring.
        """
        if not approved:
            return []
        return self._commit_filtered(
            self.import_from_keyserver(query, keyserver), approved
        )

    def search_keyserver(
        self, query: str, keyserver: str = DEFAULT_KEYSERVER
    ) -> list[SearchResult]:
        """Search *keyserver* for *query*, returning every match for the
        caller to pick from.

        Unlike ``import_from_keyserver()``, which needs an exact
        fingerprint, key ID or email and fetches it directly, this drives
        ``--search-keys`` — the one keyserver operation meant for an
        ambiguous query with several possible matches, left for a human to
        disambiguate (see CODING.md, "Key import" for why
        ``import_from_keyserver()`` avoids it for email lookups instead).
        Not every keyserver supports it: this app's own default,
        `keys.openpgp.org`, deliberately doesn't — for the same privacy
        reasons it doesn't index emails either — so this only returns
        anything against a keyserver that still offers `op=index` (a
        self-hosted one, for instance).
        """
        result = self._gpg.search_keys(query, keyserver=keyserver)
        if not result:
            stderr = str(result.stderr)
            if _is_not_found_failure(stderr):
                return []
            raise GPGBackendError(stderr or f"No key found for {query}")
        return [
            SearchResult(
                fingerprint=entry["keyid"],
                uids=[_decode_hkp_uid(uid) for uid in entry["uids"]],
                algo=entry.get("algo", ""),
                length=(
                    int(entry["length"])
                    if str(entry.get("length", "")).isdigit()
                    else 0
                ),
                created=_int_or_none(entry.get("date", "")) or 0,
            )
            for entry in result
        ]

    def publish_to_keyserver(
        self, fingerprint: str, keyserver: str = DEFAULT_KEYSERVER
    ) -> None:
        """Publish *fingerprint*'s public key to *keyserver*."""
        result = self._gpg.send_keys(keyserver, fingerprint)
        if result.returncode != 0:
            raise GPGBackendError(
                str(result.stderr) or f"Could not publish {fingerprint} to {keyserver}"
            )

    def refresh_from_keyserver(
        self,
        fingerprints: list[str] | None = None,
        keyserver: str = DEFAULT_KEYSERVER,
    ) -> list[RefreshedKey]:
        """Re-fetch keys already in the keyring from *keyserver* — the same
        effect as gpg's own ``--refresh-keys``, which python-gnupg doesn't
        wrap: fetching a key already present merges in any new signatures,
        revocations or expiry changes rather than duplicating it.

        *fingerprints* selects which keys to refresh; ``None`` (the
        default) refreshes every key in the keyring. A no-op (returns
        ``[]``) when there is nothing to refresh — either an empty keyring
        with *fingerprints* unset, or an explicitly empty *fingerprints*
        list — since calling ``recv_keys()`` with zero keyids would
        otherwise wait on unexpected input.
        """
        if fingerprints is None:
            fingerprints = [key.fingerprint for key in self.list_keys()]
        if not fingerprints:
            return []
        before = {key.fingerprint: key for key in self.list_keys()}
        result = self._gpg.recv_keys(keyserver, *fingerprints)
        stderr = str(result.stderr)
        if result.returncode != 0 and not _is_no_data_failure(stderr):
            raise GPGBackendError(stderr or "Could not refresh keys")
        after = {key.fingerprint: key for key in self.list_keys()}
        return [
            RefreshedKey(key=after[fp], updated=before.get(fp) != after[fp])
            for fp in fingerprints
            if fp in after
        ]

    def list_key_signatures(self, fingerprint: str) -> list[KeySignature]:
        """Return every key that has certified *fingerprint*'s user IDs.

        Driven by a raw ``--with-colons --list-sigs`` listing rather than
        python-gnupg's own ``list_keys(sigs=True)``: that wrapper's ``sig()``
        handler keeps only the signer's key ID and a display string, never
        the signer's full fingerprint that gpg lists right alongside it
        (colon field 13 — see ``KeySignature``). Self-certifications
        (key ID matching *fingerprint*'s own) are excluded, and several
        user IDs signed by the same key collapse to a single entry.
        """
        result = subprocess.run(  # noqa: S603
            [
                self._gpg.gpgbinary,
                *self._homedir_args(),
                "--with-colons",
                "--list-sigs",
                fingerprint,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        own_keyid: str | None = None
        seen: set[str] = set()
        entries: list[tuple[str, str | None]] = []
        for line in result.stdout.splitlines():
            fields = line.split(":")
            if fields[0] in ("pub", "sec") and own_keyid is None:
                own_keyid = fields[4]
            elif fields[0] == "sig":
                keyid = fields[4]
                if not keyid or keyid == own_keyid or keyid in seen:
                    continue
                seen.add(keyid)
                sig_fingerprint = (
                    fields[12] if len(fields) > 12 and fields[12] else None
                )
                entries.append((keyid, sig_fingerprint))
        if not entries:
            return []
        known = self.list_keys()
        by_fingerprint = {key.fingerprint: key for key in known}
        by_keyid = {key.keyid: key for key in known}
        return [
            KeySignature(
                keyid=keyid,
                fingerprint=sig_fingerprint,
                key=(
                    (by_fingerprint.get(sig_fingerprint) if sig_fingerprint else None)
                    or by_keyid.get(keyid)
                ),
            )
            for keyid, sig_fingerprint in entries
        ]

    def download_unknown_signatures(
        self, identifiers: list[str], keyserver: str = DEFAULT_KEYSERVER
    ) -> list[DownloadedSignature]:
        """Fetch each of *identifiers* (a ``KeySignature``'s ``fingerprint``,
        or its bare ``keyid`` when no fingerprint was available) from
        *keyserver*, one at a time.

        One at a time rather than a single batched ``--recv-keys`` call:
        such a call can't tell a genuine per-key miss apart from another
        identifier in the same request merely failing for an unrelated
        reason (see ``refresh_from_keyserver()``'s own note on this) — the
        caller needs to know exactly which ones were found.
        """
        results = []
        for identifier in identifiers:
            result = self._gpg.recv_keys(keyserver, identifier)
            key = (
                self._find_key(result.fingerprints[0]) if result.fingerprints else None
            )
            results.append(DownloadedSignature(identifier, key))
        return results

    def export_public_key(self, fingerprint: str) -> str:
        """Return the ASCII-armored public key block for *fingerprint*."""
        armored = self._gpg.export_keys(fingerprint)
        if not armored:
            raise GPGBackendError(f"Could not export key {fingerprint}")
        return armored

    def export_secret_key(self, fingerprint: str, passphrase: str) -> str:
        """Return the ASCII-armored *secret* key block for *fingerprint* —
        a full backup of the private key material, unlike
        ``export_public_key()``. GnuPG >= 2.1 refuses to export a secret
        key at all without its passphrase (see python-gnupg's own
        ``export_keys()`` docstring); driven directly via
        ``--passphrase-fd`` rather than through that wrapper, whose
        ``export_keys()`` only returns the raw armored bytes and discards
        stderr, so a wrong passphrase couldn't be told apart from any
        other failure.
        """

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(  # noqa: S603
                [
                    self._gpg.gpgbinary,
                    *self._homedir_args(),
                    "--batch",
                    "--yes",
                    "--pinentry-mode",
                    "loopback",
                    "--status-fd",
                    "2",
                    "--passphrase-fd",
                    "0",
                    "--armor",
                    "--export-secret-keys",
                    fingerprint,
                ],
                input=f"{passphrase}\n",
                capture_output=True,
                text=True,
                check=False,
            )

        result = _run()
        if result.returncode != 0 and _AGENT_VERSION_MISMATCH_MARKER in result.stderr:
            self._restart_agent()
            result = _run()
        if result.returncode != 0 or not result.stdout:
            if _is_bad_passphrase_error(result.stderr):
                raise BadPassphraseError(result.stderr)
            raise GPGBackendError(
                result.stderr or f"Could not export secret key {fingerprint}"
            )
        return result.stdout

    def _find_key(self, fingerprint: str) -> Key:
        for key in self.list_keys():
            if key.fingerprint == fingerprint:
                return key
        raise GPGBackendError(f"Key {fingerprint} not found in keyring")


# ---------------------------------------------------------------------------
# Default backend — overridable for tests
# ---------------------------------------------------------------------------

_gnupghome_override: str | None = None


def configure(gnupghome: str | Path | None = None) -> None:
    """Override the GNUPGHOME used by ``default_backend()``.

    Pass ``None`` to restore GnuPG's own platform default (the real user
    keyring). Intended for testing — tests must never touch the real user's
    keyring; ``tests/conftest.py``'s autouse ``_isolated_gnupghome`` fixture
    calls this with a temp directory before every test.
    """
    global _gnupghome_override
    _gnupghome_override = str(gnupghome) if gnupghome is not None else None


def default_backend() -> GPGBackend:
    """Return a ``GPGBackend`` for the configured GNUPGHOME.

    Uses the override set via ``configure()`` if any, else GnuPG's own
    platform default — what the running application uses in production.
    """
    return GPGBackend(_gnupghome_override)
