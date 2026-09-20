"""Thin wrapper around python-gnupg exposing the operations PBNightingale needs.

Framework-agnostic: no PySide6 imports here.
GPG calls are synchronous and can take a noticeable time (key generation,
network operations in later milestones); running them without blocking the GUI
thread is the Qt-side worker's job, not this module's — see ``ui/gpg_worker.py``.
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib.parse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import gnupg

from pbnightingale.core.secret import Passphrase

# gpg emits a `[GNUPG:] KEYEXPIRED <timestamp>` status line whenever a key
# involved in the operation (e.g. a signature's signing key) has expired —
# purely informational, never itself the cause of a failure, but it shows
# up interleaved with the actual diagnostic often enough to be worth
# stripping systematically. Filtered at the source — the moment gpg's raw
# stderr is captured, in `_traced_run()`/`_run_with_agent_retry()`/every
# python-gnupg-mediated call site that reads a result's `.stderr` — rather
# than only where it happens to surface (an exception message, say): every
# consumer downstream (exceptions, logs, a future diagnostic display)
# sees already-clean text without having to remember to sanitize it
# itself.
_KEYEXPIRED_LINE_RE = re.compile(r"^\[GNUPG:\] KEYEXPIRED \S*\n?", re.MULTILINE)


def _strip_gnupg_noise(text: str) -> str:
    """Remove purely informational gpg status lines from *text*.

    Applied to gpg's raw stderr as soon as it's captured — before it
    reaches status-code detection (``_is_bad_passphrase_error()`` and
    friends), an exception message, or anything else. Safe there: every
    marker those functions look for (``[GNUPG:] ERROR ...``,
    ``server_version_mismatch``, ``[GNUPG:] ATTRIBUTE ...``) is a
    different status line, never ``KEYEXPIRED`` itself.
    """
    return _KEYEXPIRED_LINE_RE.sub("", text)


def _clean_stderr(result):
    """Strip informational gpg noise from *result*'s ``stderr``, in place.

    Works for both a ``subprocess.CompletedProcess`` and a python-gnupg
    result object — both expose a plain, freely-assignable ``stderr``
    string attribute.

    Parameters
    ----------
    result
        Anything with a ``stderr`` attribute holding gpg's raw stderr.

    Returns
    -------
    :
        *result*, for chaining at the call site.
    """
    stderr = getattr(result, "stderr", None)
    if stderr:
        result.stderr = _strip_gnupg_noise(stderr)
    return result


class GPGBackendError(RuntimeError):
    """Raised when the GPG backend cannot be initialized or invoked."""

    def __init__(self, message: str = "") -> None:
        """Build the error, stripping purely informational gpg noise.

        A last line of defense on top of ``_clean_stderr()``: every
        genuine gpg-stderr source is already sanitized well before it
        gets here, but this keeps the guarantee even for a message built
        some other way.

        Parameters
        ----------
        message
            The diagnostic text — often gpg's raw stderr.
        """
        super().__init__(_strip_gnupg_noise(message))


class BadPassphraseError(GPGBackendError):
    """Raised when gpg rejects the passphrase for a secret-key operation.

    A specialization of GPGBackendError so the UI can show a short,
    friendly message instead of gpg's full diagnostic dump — see
    ``_is_bad_passphrase_error()``.
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
    """Return whether *stderr* contains gpg's bad-passphrase status code."""
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
    """Return whether *stderr* contains gpg's not-found failure code."""
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
    """Return whether *stderr* contains gpg's no-data failure code."""
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
    """Split raw attribute-file data into per-fingerprint photos.

    Each subpacket is an RFC 4880 "Image Attribute": a little-endian
    16-bit header length, a version byte, a format byte (1 = JPEG), 12
    reserved bytes, then the raw image — the header length is read rather
    than assumed to be 16, in case a future header version is longer.

    Parameters
    ----------
    stderr
        gpg's status output, whose ``ATTRIBUTE`` status lines give each
        subpacket's key, size and revoked flag.
    attribute_data
        The raw bytes from gpg's ``--attribute-file`` output.

    Returns
    -------
    :
        ``{fingerprint: [PhotoUid, ...]}``.
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
    """A single user ID (identity) attached to a primary key."""

    #: The UID string itself, e.g. ``"Name (Comment) <email>"``.
    value: str
    #: Whether this UID has been revoked.
    revoked: bool
    #: Whether gpg currently considers this its primary UID. A single-UID
    #: key's only UID is trivially primary; for a key with more than one
    #: UID, gpg's plain ``--list-keys`` output never exposes which one is
    #: primary (that flag only shows up in ``--edit-key``'s interactive
    #: listing, verified empirically — see CODING.md, "Editable user IDs"),
    #: and UID listing order is *not* a reliable stand-in for it either
    #: (verified: UIDs added in order A, B, C came back listed as C, A, B).
    #: So a multi-UID key costs one extra ``gpg --edit-key`` subprocess
    #: call to resolve this — see ``GPGBackend._load_primary_uids()``/
    #: ``_primary_uid_value()`` — kept cheap in aggregate by only paying it
    #: for keys that actually have more than one UID.
    primary: bool = False


def format_uid(name: str, email: str, comment: str = "") -> str:
    """Build a GPG user ID string, e.g. ``"Name (Comment) <email>"``.

    Mirrors the conventional form gpg itself produces from separate
    name/comment/email fields — used both for ``GPGBackend.add_uid()`` and
    for previewing the resulting identity in the UI.

    Parameters
    ----------
    name
        The identity's real name.
    email
        The identity's email address.
    comment
        An optional parenthesized comment; omitted from the result
        entirely when empty.

    Returns
    -------
    :
        The formatted user ID string.
    """
    return f"{name} ({comment}) <{email}>" if comment else f"{name} <{email}>"


@dataclass(frozen=True)
class PhotoUid:
    """A photo (image) user attribute attached to a primary key."""

    #: 1-based, counting only this key's photos in the order gpg reports
    #: them — the identifier ``GPGBackend.revoke_photo_uid()`` needs, since
    #: (unlike a text ``Uid``) a photo has no string to select it by.
    index: int
    #: The raw decoded image bytes (JPEG).
    image: bytes
    #: Whether this photo has been revoked.
    revoked: bool


@dataclass(frozen=True)
class Subkey:
    """A single subkey attached to a primary key."""

    #: The subkey's short key ID.
    keyid: str
    #: The subkey's own full fingerprint.
    fingerprint: str
    #: The subkey's algorithm, e.g. ``"rsa4096"`` or ``"ed25519"``.
    algo: str
    #: The subkey's length in bits (0 when not applicable, e.g. EdDSA).
    length: int
    #: Creation date, as a Unix timestamp.
    created: int
    #: Expiration date, as a Unix timestamp, or ``None`` if it never
    #: expires.
    expires: int | None
    #: This subkey's own validity/trust, gpg's one-letter colon code.
    trust: str
    #: Whether this subkey can sign.
    can_sign: bool
    #: Whether this subkey can encrypt.
    can_encrypt: bool
    #: Whether this subkey can certify.
    can_certify: bool
    #: Whether this subkey can authenticate.
    can_authenticate: bool


@dataclass(frozen=True)
class NewKeyRequest:
    """Parameters for ``GPGBackend.generate_key()``.

    Expiration is always "never" for now — expiry management is milestone
    11's concern.
    """

    #: The primary identity's real name.
    name: str
    #: The primary identity's email address.
    email: str
    #: An optional parenthesized comment on the primary identity.
    comment: str = ""
    #: ``"RSA"`` or ``"ED25519"`` (EdDSA/Curve25519, the modern default
    #: pairing).
    algorithm: str = "RSA"
    #: The RSA key length in bits; unused for ED25519.
    key_length: int = 4096
    #: The new key's passphrase; empty for an unprotected key.
    passphrase: Passphrase = field(default_factory=lambda: Passphrase(""))
    #: Add a dedicated signing subkey (default ``True``). When turned off,
    #: the primary key itself takes on signing usage instead — the primary
    #: key is otherwise certify-only, per current best practice.
    signing_subkey: bool = True
    #: Add a dedicated encryption subkey (default ``True``). When turned
    #: off, the primary key itself takes on encryption usage instead —
    #: except under ED25519, which EdDSA cannot itself provide, so a
    #: dedicated Curve25519 encryption subkey is always created regardless
    #: of this flag.
    encryption_subkey: bool = True


#: Valid values for GPGBackend.set_owner_trust()'s *trust* argument, in
#: increasing order — gpg's own --quick-set-ownertrust keywords, verified
#: empirically (its own error message on an invalid value doesn't list
#: them).
OWNER_TRUST_LEVELS = ("undefined", "never", "marginal", "full", "ultimate")

#: GPGBackend.import_from_keyserver()'s default: a modern, privacy-respecting
#: keyserver (no email search, doesn't propagate third-party signatures) run
#: by the OpenPGP community — a sensible default for a fingerprint/key-ID
#: fetch when the caller doesn't ask for a specific one.
DEFAULT_KEYSERVER = "hkps://keys.openpgp.org"


@dataclass(frozen=True)
class Key:
    """A primary key: its identity (UIDs) plus its subkeys."""

    #: The key's full fingerprint.
    fingerprint: str
    #: The key's short key ID.
    keyid: str
    #: The primary key's algorithm, e.g. ``"rsa4096"`` or ``"ed25519"``.
    algo: str
    #: The primary key's length in bits (0 when not applicable, e.g.
    #: EdDSA).
    length: int
    #: Creation date, as a Unix timestamp.
    created: int
    #: Expiration date, as a Unix timestamp, or ``None`` if it never
    #: expires.
    expires: int | None
    #: The key's computed *validity* — how much the UID-to-key binding
    #: itself is trusted, per the web of trust (gpg's one-letter colon
    #: code). Confusingly, gpg's own colon output also calls this field
    #: "trust"; see ``ui/key_list_view.py``'s ``_trust_label()`` for the
    #: code-to-label mapping.
    trust: str
    #: How much *you* trust this key's owner to correctly certify *other*
    #: people's keys — a purely local judgment call (see
    #: ``GPGBackend.set_owner_trust()``) that feeds back into computing
    #: everyone else's validity. A different thing entirely from ``trust``
    #: above, despite sharing the same one-letter codes.
    owner_trust: str
    #: This key's text user IDs.
    uids: list[Uid]
    #: This key's photo user IDs.
    photos: list[PhotoUid]
    #: This key's subkeys.
    subkeys: list[Subkey]
    #: Whether the secret part of this key is held in this keyring.
    has_secret: bool
    #: Whether the primary key itself can sign.
    can_sign: bool
    #: Whether the primary key itself can encrypt.
    can_encrypt: bool
    #: Whether the primary key itself can certify.
    can_certify: bool
    #: Whether the primary key itself can authenticate.
    can_authenticate: bool


@dataclass(frozen=True)
class SearchResult:
    """One hit from ``GPGBackend.search_keyserver()``.

    Enough to show a candidate in a picker; once chosen, it's imported by
    fingerprint through the already-exact ``import_from_keyserver()``.
    """

    #: The candidate's fingerprint (or, depending on the keyserver, only
    #: its key ID).
    fingerprint: str
    #: The candidate's user IDs, as raw strings.
    uids: list[str]
    #: The candidate's algorithm.
    algo: str
    #: The candidate's length in bits.
    length: int
    #: Creation date, as a Unix timestamp.
    created: int


@dataclass(frozen=True)
class ImportedKey:
    """One key produced by ``import_from_keyserver()``/``import_from_file()``.

    gpg's import is a merge, so re-importing a key already in the keyring
    can still pick up new signatures/UIDs/subkeys without counting as
    "new" here — both cases report as already present, since there's no
    cheap way to tell "genuinely unchanged" from "merged something" apart
    without special-casing gpg's own per-import-source result shapes (the
    WKD/email path doesn't expose one at all — see
    ``import_from_keyserver()``).
    """

    #: The imported key, as it now stands in the keyring.
    key: Key
    #: Whether this key was absent from the keyring before this import (an
    #: entirely new key) as opposed to already present.
    is_new: bool


@dataclass(frozen=True)
class RefreshedKey:
    """One key produced by ``refresh_from_keyserver()``."""

    #: The key, as it now stands in the keyring after the refresh.
    key: Key
    #: Whether anything about the key actually changed. Computed by
    #: comparing the full ``Key`` snapshot before and after the refresh
    #: (frozen dataclasses compare structurally, deep through
    #: ``uids``/``photos``/``subkeys``) — this catches a new/revoked UID,
    #: a new subkey, a changed expiration or a validity change, but *not*
    #: a certification (signature) added by someone else that doesn't
    #: itself change any of those fields: same "no cheap way to tell
    #: genuinely unchanged from merged something apart" limitation already
    #: documented on ``ImportedKey`` above, just via a different mechanism
    #: (gpg's own per-import status reasons are exactly as ambiguous
    #: here).
    updated: bool


@dataclass(frozen=True)
class KeySignature:
    """One certification found on a key's own user IDs.

    As reported by ``GPGBackend.list_key_signatures()`` (``gpg
    --list-sigs``). Self-certifications (the key signing its own user
    IDs) are excluded by ``list_key_signatures()``, not represented here.
    """

    #: The signing key's classic 16-character long key ID.
    keyid: str
    #: The signing key's full fingerprint, read straight from the
    #: signature packet's own "Issuer Fingerprint" subpacket — colon field
    #: 13 of the ``sig`` record — which GnuPG has embedded in every
    #: signature it makes since 2.1, regardless of whether the signing key
    #: is still present in the local keyring (verified empirically:
    #: deleting the signer from the keyring entirely still leaves this
    #: field populated). ``None`` only for a signature old enough to
    #: predate that subpacket, leaving ``keyid`` as the sole identifier.
    fingerprint: str | None
    #: The matching local ``Key`` when the signer is already in the
    #: keyring, ``None`` otherwise.
    key: Key | None


@dataclass(frozen=True)
class DownloadedSignature:
    """One signer key fetch attempted by ``download_unknown_signatures()``."""

    #: The identifier this fetch was requested with — a ``KeySignature``'s
    #: ``fingerprint``, or its bare ``keyid`` when no fingerprint was
    #: available.
    identifier: str
    #: The fetched key on success, ``None`` when the keyserver has no such
    #: key.
    key: Key | None


@dataclass(frozen=True)
class ImportPreview:
    """One key that WOULD be imported, shown to the user for approval.

    Produced by ``commit_import_from_file()``/
    ``commit_import_from_keyserver()`` before anything is actually
    committed to the real keyring. Deliberately lighter than
    ``Key``/``ImportedKey`` — just enough for the user to recognize and
    approve/reject a candidate (identities, full key ID, fingerprint, and
    whether it's already in the keyring).
    """

    #: The candidate's full fingerprint.
    fingerprint: str
    #: The candidate's short key ID.
    keyid: str
    #: The candidate's user IDs, as raw strings.
    uids: list[str]
    #: Whether this key is absent from the keyring (an entirely new key)
    #: as opposed to already present.
    is_new: bool


def _int_or_none(value: str) -> int | None:
    """Return *value* parsed as an int, or ``None`` if it's empty."""
    return int(value) if value else None


def _decode_hkp_uid(uid: str) -> str:
    r"""Percent-decode a user ID from a keyserver's index listing.

    The HKP index format (RFC draft, ``op=index``) percent-encodes the uid
    field (e.g. a space as ``%20``, ``<``/``>`` as ``%3C``/``%3E``) like a
    URL component; gpg passes it straight through on its `uid` status line
    without decoding it, and python-gnupg's own uid parsing only handles
    gpg's *other* colon-format escapes (``\xHH``, ``\:``), not this one —
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
    r"""Undo gpg's ``--with-colons`` string escaping.

    ``\xHH`` hex escapes plus a handful of named ones for control
    characters — mirrors python-gnupg's own internal
    ``SearchKeys.uid()`` handling, needed here because
    ``_primary_uid_value()`` reads gpg's raw colon output directly via
    ``subprocess`` rather than through python-gnupg's own wrapper.
    """
    value = _COLON_HEX_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), value)
    for escaped, actual in _COLON_BASIC_ESCAPES.items():
        value = value.replace(escaped, actual)
    return value


def _has_capability(cap: str, letter: str) -> bool:
    """Return whether a capability letter appears in a ``cap`` field.

    Checked case-insensitively. python-gnupg's ``cap`` field concatenates
    the potential (lowercase) and usable (uppercase) capability letters,
    e.g. ``"escarESCA"``. Any casing of the letter being present is
    enough to consider the capability offered.

    Parameters
    ----------
    cap
        The raw ``cap`` field to check.
    letter
        The capability letter to look for (``s``/``e``/``c``/``a``).

    Returns
    -------
    :
        Whether *letter* appears in *cap*.
    """
    return letter in cap.lower()


def _parse_subkey(keyid: str, info: dict) -> Subkey:
    """Build a ``Subkey`` from python-gnupg's raw per-subkey info dict.

    Parameters
    ----------
    keyid
        The subkey's short key ID.
    info
        python-gnupg's ``subkey_info`` entry for this key ID.

    Returns
    -------
    :
        The parsed subkey.
    """
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
    """Build this key's ``Uid`` list from python-gnupg's raw uid data.

    Parameters
    ----------
    raw_uids
        This key's raw UID strings, in gpg's own listing order.
    uid_map
        python-gnupg's ``ListKeys.uid_map``, keyed by raw UID string
        across the *whole* listing, not scoped per key — a byte-identical
        UID string on two different keys in the same keyring would
        collide here. Harmless in practice (worst case: a wrong revoked
        flag on that rare shared string) and there is no other public API
        to get per-UID validity out of python-gnupg.
    primary_value
        The UID string gpg currently considers primary, or ``None`` — see
        ``GPGBackend._primary_uid_value()``. A single-UID key's only UID
        is trivially primary (this is never even looked up for those —
        see ``GPGBackend._load_primary_uids()``); for a multi-UID key,
        only the one matching this value is flagged (none are, if
        resolving it failed for some reason).

    Returns
    -------
    :
        The parsed UIDs, in the same order as *raw_uids*.
    """
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
    """Build a ``Key`` from python-gnupg's raw per-key listing entry.

    Parameters
    ----------
    entry
        python-gnupg's raw listing entry for this key.
    has_secret
        Whether this key's secret part is held in this keyring.
    uid_map
        python-gnupg's ``ListKeys.uid_map`` for the whole listing — see
        ``_parse_uids()``.
    photos
        ``{fingerprint: [PhotoUid, ...]}`` for the whole keyring — see
        ``GPGBackend._load_photos()``.
    primary_uids
        ``{fingerprint: primary_uid_value}`` for keys with more than one
        UID — see ``GPGBackend._load_primary_uids()``.

    Returns
    -------
    :
        The parsed key.
    """
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
    """Return the key-generation parameters for a primary key/algorithm pair.

    Parameters
    ----------
    algorithm
        ``"RSA"`` or ``"ED25519"``.
    key_length
        The RSA key length in bits; unused for ED25519.

    Returns
    -------
    :
        A 4-tuple: the primary key's ``gen_key_input`` kwargs, the
        signing-subkey algorithm, the encryption-subkey algorithm, and
        whether encryption *must* be a dedicated subkey (true for
        ED25519, whose EdDSA primary key cannot itself encrypt).
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


_log = logging.getLogger(__name__)
_REDACTED = "**********"


def _redact(text: str, secrets: Iterable[Passphrase | str | None]) -> str:
    """Replace every occurrence of each non-empty secret in *text*.

    Used to sanitize a debug trace before it is logged — never to sanitize
    anything actually sent to gpg. *secrets* takes ``Passphrase`` wrappers
    directly (unwrapped here, the one legitimate place this module reads
    ``.passphrase`` purely to redact it) so call sites never need to
    unwrap one just to build this list.
    """
    for secret in secrets:
        value = secret.passphrase if isinstance(secret, Passphrase) else secret
        if value:
            text = text.replace(value, _REDACTED)
    return text


def _traced_run(
    args: Sequence[str], *, secrets: Iterable[Passphrase | str | None] = (), **kwargs
) -> subprocess.CompletedProcess:
    """``subprocess.run()``, tracing the call at DEBUG level.

    gpg's ``--command-fd``/``--passphrase-fd`` scripting protocols feed
    passphrases over stdin (``kwargs["input"]``), never as an argv element,
    so only *that* needs redacting — *secrets* lists every passphrase that
    may appear in it, each replaced with a fixed placeholder before the
    trace is logged. The real, unredacted input is still what's sent to
    gpg; only the log line is sanitized.

    The returned result's ``stderr`` has gpg's own informational noise
    (``KEYEXPIRED`` — see ``_strip_gnupg_noise()``) already stripped, so
    every caller sees clean text without doing it itself.
    """
    if _log.isEnabledFor(logging.DEBUG):
        _log.debug("Running: %s", shlex.join(str(a) for a in args))
        stdin = kwargs.get("input")
        if stdin is not None:
            _log.debug("stdin:\n%s", _redact(stdin, secrets))
    result = subprocess.run(  # noqa: S603, PLW1510 — every caller passes check=False
        args, **kwargs
    )
    return _clean_stderr(result)


def _traced_popen(args: Sequence[str], **kwargs) -> subprocess.Popen:
    """``subprocess.Popen()``, tracing the invocation (argv only) at DEBUG level.

    Unlike ``_traced_run()``, there is no single ``input`` to trace here —
    callers scripting an interactive exchange over ``process.stdin`` must
    log each line they send themselves, redacting any secret first.
    """
    if _log.isEnabledFor(logging.DEBUG):
        _log.debug("Running: %s", shlex.join(str(a) for a in args))
    return subprocess.Popen(args, **kwargs)  # noqa: S603


class GPGBackend:
    """Wraps a single GNUPGHOME and exposes the key operations the GUI needs."""

    def __init__(
        self,
        gnupghome: str | Path | None = None,
        *,
        gpgbinary: str | None = None,
    ) -> None:
        """Wrap the GNUPGHOME at *gnupghome*.

        Parameters
        ----------
        gnupghome
            The GNUPGHOME directory to use — always an isolated directory
            in tests, never the real user's keyring. Passing ``None``
            (the default) uses GnuPG's own default (``~/.gnupg`` or
            platform equivalent), which is what the running application
            does in production. Created with ``0o700`` permissions if it
            doesn't exist yet.
        gpgbinary
            The ``gpg`` executable to use; ``None`` lets python-gnupg
            resolve it from ``PATH``.

        Raises
        ------
        GPGBackendError
            If the underlying ``gnupg.GPG`` wrapper cannot be
            initialized.
        """
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
        """The backend's GNUPGHOME, or ``None`` for GnuPG's own default."""
        return self._gpg.gnupghome

    def _homedir_args(self) -> list[str]:
        """Return the ``--homedir`` argument list for a direct subprocess call.

        Returns
        -------
        :
            ``["--homedir", <path>]``, or ``[]`` when ``self._gpg.gnupghome``
            is ``None`` (production, no ``configure()`` override): gpg then
            uses its own platform default homedir, which python-gnupg never
            resolves to an actual path — passing ``None`` straight through
            to ``subprocess.run()`` would raise a ``TypeError``, so
            ``--homedir`` is omitted entirely (mirrors python-gnupg's own
            ``make_args()``).
        """
        return ["--homedir", self._gpg.gnupghome] if self._gpg.gnupghome else []

    def _restart_agent(self) -> None:
        """Kill the running ``gpg-agent``.

        The next call needing it starts a fresh one.
        """
        _traced_run(
            ["gpgconf", *self._homedir_args(), "--kill", "gpg-agent"],
            capture_output=True,
            text=True,
            check=False,
        )

    def _clear_agent_passphrase_cache(self) -> None:
        """Flush gpg-agent's passphrase cache in place, synchronously.

        Uses ``RELOADAGENT`` rather than ``_restart_agent()``'s ``gpgconf
        --kill``: a kill is asynchronous and can race the very next gpg
        call into reusing the not-yet-dead agent's still-cached passphrase
        (verified empirically). Only ``change_passphrase()`` needs this:
        every other secret-key operation here is unaffected by (or
        actively benefits from) an already-unlocked key.
        """
        _traced_run(
            ["gpg-connect-agent", *self._homedir_args(), "RELOADAGENT", "/bye"],
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_with_agent_retry(self, call):
        """Run *call*, retrying once on a stale-agent version mismatch.

        Parameters
        ----------
        call
            A zero-argument callable returning a python-gnupg result with
            a ``fingerprint`` and a ``stderr`` attribute.

        Returns
        -------
        :
            *call*'s result — retried once, restarting the agent first, if
            the first attempt failed with a stale-agent version mismatch
            (see ``_AGENT_VERSION_MISMATCH_MARKER``).
        """
        result = call()
        if not result.fingerprint and _AGENT_VERSION_MISMATCH_MARKER in (
            result.stderr or ""
        ):
            self._restart_agent()
            result = call()
        return _clean_stderr(result)

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
            result = _traced_run(
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
        """Return ``{fingerprint: primary_uid_value}`` for multi-UID keys.

        Computed only for keys with more than one UID — see
        ``Uid.primary``'s docstring for why a single-UID key never needs
        this. Unlike ``_load_photos()``, this can't be done in one pass
        over the whole keyring: the primary flag only appears in
        ``--edit-key``'s own listing, which is inherently per-key, so
        this costs one ``gpg`` subprocess call for each key that actually
        has more than one identity.
        """
        return {
            entry["fingerprint"]: value
            for entry in raw
            if len(entry.get("uids", [])) > 1
            for value in [self._primary_uid_value(entry["fingerprint"])]
            if value is not None
        }

    def _primary_uid_value(self, fingerprint: str) -> str | None:
        """Return the exact UID string gpg currently considers primary.

        ``None`` if it can't be determined. Scripted the same way as the
        photo-revoked-flag lookup right above this class's other
        ``--edit-key`` uses (``list``/``quit``, no passphrase needed for
        a read-only listing): the ``uid`` colon
        record's second-to-last field holds ``"<rank>,p"`` for the primary
        UID and just ``"<rank>,"`` for the others (verified empirically —
        undocumented in gpg's own doc/DETAILS, which only spells out the
        plain ``--list-keys`` colon format, not ``--edit-key``'s).
        """
        result = _traced_run(
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
        """Generate a new personal key and return it.

        Blocking (can take a noticeable time for large key sizes) — always
        run via ``ui/gpg_worker.run_async``, never on the GUI thread.

        Parameters
        ----------
        request
            The key to generate.

        Returns
        -------
        :
            The newly generated key.

        Raises
        ------
        GPGBackendError
            If gpg failed to generate the primary key.
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
            passphrase=request.passphrase.passphrase,
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
        passphrase: Passphrase,
        *,
        usage: str,
        algorithm: str = "RSA",
        key_length: int = 4096,
    ) -> Key:
        """Add a new subkey to an existing (secret) key and return it updated.

        Parameters
        ----------
        fingerprint
            The primary key to add the subkey to.
        passphrase
            Unlocks the primary key's secret part.
        usage
            ``"sign"``, ``"encrypt"`` or ``"auth"``.
        algorithm
            ``"RSA"`` or ``"ED25519"`` — for ED25519 the actual curve is
            picked from *usage* (EdDSA for sign/auth, Curve25519 for
            encrypt, since EdDSA itself cannot encrypt).
        key_length
            The RSA key length in bits; unused for ED25519.

        Returns
        -------
        :
            The key, updated with the new subkey.
        """
        if algorithm == "ED25519":
            raw_algorithm = "cv25519" if usage == "encrypt" else "ed25519"
        else:
            raw_algorithm = f"rsa{key_length}"
        self._add_subkey(fingerprint, passphrase, raw_algorithm, usage)
        return self._find_key(fingerprint)

    def _add_subkey(
        self, fingerprint: str, passphrase: Passphrase, algorithm: str, usage: str
    ) -> None:
        """Add a subkey to *fingerprint*, in gpg's own raw algorithm/usage form.

        Parameters
        ----------
        fingerprint
            The primary key to add the subkey to.
        passphrase
            Unlocks the primary key's secret part. Must be a string,
            never ``None``, even when empty: python-gnupg only enables
            ``--pinentry-mode loopback`` when the value is not ``None``,
            and an unprotected primary key still needs that mode to add a
            subkey without an interactive pinentry program available.
        algorithm
            gpg's own raw algorithm string, e.g. ``"rsa4096"`` or
            ``"ed25519"``.
        usage
            ``"sign"``, ``"encrypt"`` or ``"auth"``.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """
        result = self._run_with_agent_retry(
            lambda: self._gpg.add_subkey(
                master_key=fingerprint,
                master_passphrase=passphrase.passphrase,
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
        self, fingerprint: str, old_passphrase: Passphrase, new_passphrase: Passphrase
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

        Parameters
        ----------
        fingerprint
            The key whose passphrase is being changed.
        old_passphrase
            The key's current passphrase. Only meaningful for a key that
            is *already* passphrase-protected — this presupposes one
            exists. Verified empirically: unlike ``--edit-key``'s
            ``passwd`` sub-command, ``--change-passphrase`` silently does
            nothing when *fingerprint* currently has no protection at all
            (*old_passphrase* would be ``""`` with nothing to actually
            check), even though it reports success — it is not a
            substitute for a "protect this bare key" operation.
        new_passphrase
            The key's new passphrase.

        Returns
        -------
        :
            The key, unchanged except for its new passphrase.

        Raises
        ------
        BadPassphraseError
            If *old_passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """
        self._clear_agent_passphrase_cache()
        old_value = old_passphrase.passphrase
        new_value = new_passphrase.passphrase
        retries = f"{old_value}\n" * _MAX_SECRET_KEY_PARTS
        script = f"{old_value}\n{new_value}\n{retries}save\n"

        def _run() -> subprocess.CompletedProcess:
            return _traced_run(
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
                secrets=(old_passphrase, new_passphrase),
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
        self, fingerprint: str, subkey_keyid: str, passphrase: Passphrase
    ) -> Key:
        """Revoke one subkey of a key.

        Irreversible — the caller must already have obtained a strong
        confirmation from the user before calling this. python-gnupg has no
        wrapper for subkey revocation, so this drives ``gpg --edit-key``
        directly over its `--command-fd`/`--status-fd` scripting protocol
        (verified empirically; see CODING.md — "Subkey management").

        Parameters
        ----------
        fingerprint
            The primary key owning the subkey.
        subkey_keyid
            The subkey to revoke, by its short key ID.
        passphrase
            Unlocks the primary key's secret part.

        Returns
        -------
        :
            The key, updated with the subkey now revoked.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """
        script = (
            f"key {subkey_keyid}\nrevkey\ny\n0\n\ny\n{passphrase.passphrase}\nsave\n"
        )

        def _run() -> subprocess.CompletedProcess:
            # --status-fd 2 (stderr), matching python-gnupg's own
            # make_args(): keeps every diagnostic (both the human "gpg: …"
            # lines and the machine-readable "[GNUPG:] …" status lines) in
            # one stream, since both the agent-mismatch and bad-passphrase
            # detection below read result.stderr.
            return _traced_run(
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
                secrets=(passphrase,),
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

    def revoke_key(self, fingerprint: str, passphrase: Passphrase) -> Key:
        """Revoke a primary key itself — not one of its subkeys.

        See ``revoke_subkey()`` for the latter. Irreversible — the caller
        must already have obtained a strong confirmation from the user
        before calling this. Same ``--edit-key`` scripting as
        ``revoke_subkey()``, minus the leading ``key <keyid>`` selection:
        with no subkey selected, ``revkey`` targets the primary key
        instead (verified empirically).

        Parameters
        ----------
        fingerprint
            The key to revoke.
        passphrase
            Unlocks the key's secret part.

        Returns
        -------
        :
            The key, now revoked.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """
        script = f"revkey\ny\n0\n\ny\n{passphrase.passphrase}\nsave\n"

        def _run() -> subprocess.CompletedProcess:
            return _traced_run(
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
                secrets=(passphrase,),
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
        """Permanently remove a key from the keyring.

        Unlike ``revoke_key()``, which keeps the (now untrustworthy) key
        around, this actually erases the key material, public and (if
        *secret*) private alike. Irreversible — the caller must already
        have obtained a strong confirmation from the user before calling
        this.

        No passphrase needed: deleting is a local keyring-management
        operation, not a cryptographic one, so GnuPG never asks to unlock
        the secret key for it (unlike revoking, which must produce a
        valid signature).

        Parameters
        ----------
        fingerprint
            The key to delete.
        secret
            Also erase the secret key material, not just the public part.

        Raises
        ------
        GPGBackendError
            If gpg failed to delete the key.
        """
        command = "--delete-secret-and-public-key" if secret else "--delete-keys"
        result = _traced_run(
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
        passphrase: Passphrase,
        *,
        name: str,
        email: str,
        comment: str = "",
    ) -> Key:
        """Add a new user ID (identity) to an existing (secret) key.

        Parameters
        ----------
        fingerprint
            The key to add the identity to.
        passphrase
            Unlocks the key's secret part.
        name
            The identity's real name.
        email
            The identity's email address.
        comment
            An optional parenthesized comment on the identity.

        Returns
        -------
        :
            The key, updated with the new user ID.
        """
        uid = format_uid(name, email, comment)
        self._run_quick_command("--quick-add-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def set_primary_uid(
        self, fingerprint: str, passphrase: Passphrase, uid: str
    ) -> Key:
        """Flag an existing user ID as a key's primary identity.

        Parameters
        ----------
        fingerprint
            The key to update.
        passphrase
            Unlocks the key's secret part.
        uid
            The user ID to flag as primary, by its exact string.

        Returns
        -------
        :
            The key, updated with the new primary user ID.
        """
        self._run_quick_command("--quick-set-primary-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def revoke_uid(self, fingerprint: str, passphrase: Passphrase, uid: str) -> Key:
        """Revoke a user ID on a key.

        Irreversible — the caller must already have obtained a strong
        confirmation from the user before calling this.

        Parameters
        ----------
        fingerprint
            The key owning the user ID.
        passphrase
            Unlocks the key's secret part.
        uid
            The user ID to revoke, by its exact string.

        Returns
        -------
        :
            The key, updated with the user ID now revoked.

        Raises
        ------
        GPGBackendError
            On any failure — including gpg's own refusal to revoke the
            last non-revoked UID on a key; the UI should disable this
            action in that case rather than let the user hit that wall.
        """
        self._run_quick_command("--quick-revoke-uid", fingerprint, passphrase, uid)
        return self._find_key(fingerprint)

    def set_key_expiration(
        self, fingerprint: str, passphrase: Passphrase, expire: str
    ) -> Key:
        """Set the primary key's own expiration.

        Leaves every subkey's own expiration untouched — verified
        empirically, see CODING.md, "Expiration dates".

        Parameters
        ----------
        fingerprint
            The key to update.
        passphrase
            Unlocks the key's secret part.
        expire
            Follows gpg's own ``--quick-set-expire`` syntax: ``"0"`` for
            no expiration, ``"<n>d"``/``"w"``/``"m"``/``"y"`` for a
            relative duration from now, or an absolute ``"YYYY-MM-DD"``
            date.

        Returns
        -------
        :
            The key, updated with its new expiration.
        """
        self._run_quick_command("--quick-set-expire", fingerprint, passphrase, expire)
        return self._find_key(fingerprint)

    def set_subkey_expiration(
        self,
        fingerprint: str,
        passphrase: Passphrase,
        subkey_fingerprint: str,
        expire: str,
    ) -> Key:
        """Set one subkey's expiration.

        Leaves the primary key's own expiration and every other subkey's
        untouched.

        Parameters
        ----------
        fingerprint
            The primary key owning the subkey.
        passphrase
            Unlocks the primary key's secret part.
        subkey_fingerprint
            The subkey to update, identified by its own fingerprint (not
            the primary key's) — see ``Subkey.fingerprint``.
        expire
            Follows gpg's own ``--quick-set-expire`` syntax — see
            ``set_key_expiration()``.

        Returns
        -------
        :
            The key, updated with the subkey's new expiration.
        """
        self._run_quick_command(
            "--quick-set-expire", fingerprint, passphrase, expire, subkey_fingerprint
        )
        return self._find_key(fingerprint)

    def sign_key(
        self,
        fingerprint: str,
        passphrase: Passphrase,
        *,
        signing_key_fingerprint: str,
        cert_level: int = 0,
        local_only: bool = False,
    ) -> Key:
        """Sign every user ID of a key — the foundation of the web of trust.

        Parameters
        ----------
        fingerprint
            The key being signed.
        passphrase
            Unlocks the signing key's secret part.
        signing_key_fingerprint
            The secret key used to make the signature.
        cert_level
            gpg's own certification-check scale (0-3): 0 (no particular
            claim), 1 (not verified — a "persona" signature), 2 (casual
            verification), 3 (extensive verification).
        local_only
            Drive ``--quick-lsign-key`` instead of ``--quick-sign-key``: a
            local signature never leaves this keyring on export, useful
            for casual verification the signer isn't ready to assert
            publicly.

        Returns
        -------
        :
            The signed key.
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
        """Set how much a key's owner is trusted to certify other keys.

        The other half of the web of trust (see ``sign_key()``): a
        signature only strengthens a key's computed *validity* if it
        comes from a sufficiently trusted owner.

        Unlike every other write operation in this module, this is a
        purely local judgment call recorded in the trust database — no
        secret key or passphrase is involved at all.

        Parameters
        ----------
        fingerprint
            The key whose owner trust is being set.
        trust
            One of ``"undefined"``, ``"never"``, ``"marginal"``,
            ``"full"`` or ``"ultimate"`` — see ``OWNER_TRUST_LEVELS``.

        Returns
        -------
        :
            The key, updated with its new owner trust.

        Raises
        ------
        GPGBackendError
            If gpg failed to set the owner trust.
        """
        result = _traced_run(
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
        """Recompute the web of trust for the whole keyring.

        Non-interactive (``--check-trustdb``, not ``--update-trustdb``) —
        skips keys with a not-yet-defined ownertrust rather than asking
        about them.
        """
        result = _traced_run(
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
        passphrase: Passphrase,
        *args: str,
        extra_options: tuple[str, ...] = (),
    ) -> None:
        """Run one of gpg's non-interactive ``--quick-*`` commands (2.1+).

        No python-gnupg wrapper for any of these — they all take the
        passphrase non-interactively via ``--passphrase-fd``, unlike
        subkey/photo revocation which still need the ``--edit-key``
        scripting protocol (see ``revoke_subkey()``). The passphrase is
        piped over stdin, never passed as a ``--passphrase`` argument, so
        it never shows up in a process listing.

        Parameters
        ----------
        command
            The ``--quick-*`` command itself, e.g.
            ``"--quick-set-primary-uid"``.
        fingerprint
            The key the command applies to.
        passphrase
            Unlocks the key's secret part.
        *args
            Positional arguments to *command*, after *fingerprint*.
        extra_options
            Options of gpg itself, inserted *before* *command* — unlike
            *args*, which are *command*'s own positional arguments. Used
            by ``sign_key()`` for ``"-u <signer>"`` and
            ``"--default-cert-level <n>"``.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """

        def _run() -> subprocess.CompletedProcess:
            return _traced_run(
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
                input=passphrase.passphrase,
                secrets=(passphrase,),
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
        self, fingerprint: str, passphrase: Passphrase, jpeg_path: str | Path
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

        Parameters
        ----------
        fingerprint
            The key to add the photo to.
        passphrase
            Unlocks the key's secret part.
        jpeg_path
            Path to the JPEG file to attach.

        Returns
        -------
        :
            The key, updated with the new photo.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """

        def _run() -> subprocess.CompletedProcess:
            process = _traced_popen(
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
                if _log.isEnabledFor(logging.DEBUG):
                    _log.debug("stdin: %s", _redact(line, (passphrase,)))
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

            final_input = f"{passphrase.passphrase}\nsave\n"
            if _log.isEnabledFor(logging.DEBUG):
                _log.debug("stdin:\n%s", _redact(final_input, (passphrase,)))
            remaining_stdout, remaining_stderr = process.communicate(final_input)
            output.append(remaining_stderr)
            return _clean_stderr(
                subprocess.CompletedProcess(
                    process.args,
                    process.returncode,
                    stdout=remaining_stdout,
                    stderr="".join(output),
                )
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
        self, fingerprint: str, passphrase: Passphrase, photo_index: int
    ) -> Key:
        """Revoke a photo on a key.

        Irreversible — the caller must already have obtained a strong
        confirmation. There is no ``--quick-revoke-uid`` equivalent for a
        photo (it has no text to match against), so this drives
        ``gpg --edit-key`` directly, same shape as ``revoke_subkey()``,
        after resolving *photo_index* to gpg's own uid-editing index via
        ``_resolve_photo_edit_index()``.

        Parameters
        ----------
        fingerprint
            The key owning the photo.
        passphrase
            Unlocks the key's secret part.
        photo_index
            The photo to revoke, 1-based in ``Key.photos`` order.

        Returns
        -------
        :
            The key, updated with the photo now revoked.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """
        edit_index = self._resolve_photo_edit_index(fingerprint, photo_index)
        script = f"uid {edit_index}\nrevuid\ny\n0\n\ny\n{passphrase.passphrase}\nsave\n"

        def _run() -> subprocess.CompletedProcess:
            return _traced_run(
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
                secrets=(passphrase,),
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
        """Resolve a photo's index to gpg's own ``--edit-key`` uid index.

        Read off a read-only ``list`` — see ``Key.photos``/
        ``PhotoUid.index``.

        Parameters
        ----------
        fingerprint
            The key owning the photo.
        photo_index
            The photo's 1-based index, in ``Key.photos`` order.

        Returns
        -------
        :
            The ``uid N`` index ``--edit-key`` uses for this photo.

        Raises
        ------
        GPGBackendError
            If the listing itself failed, or *photo_index* is out of
            range for *fingerprint*.
        """
        result = _traced_run(
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
        """Import one or more keys from an exported key file.

        *path* may hold a single key or a whole keyring export, armored
        or binary.

        Returns
        -------
        :
            The imported keys, each flagged with whether it was new to
            the keyring.

        Raises
        ------
        GPGBackendError
            If no key was found in the file.
        """
        existing = {e["fingerprint"] for e in self._gpg.list_keys(False)}
        result = _clean_stderr(self._gpg.import_keys_file(str(path)))
        if not result.fingerprints:
            raise GPGBackendError(str(result.stderr) or f"No key found in {path}")
        return [
            ImportedKey(self._find_key(fp), fp not in existing)
            for fp in result.fingerprints
        ]

    def _locate_key_by_email(
        self, email: str, keyserver: str
    ) -> tuple[str | None, str]:
        """Resolve an email address to a fingerprint via gpg's auto-key-locate.

        WKD first, falling back to *keyserver* — importing the key into
        the keyring as a side effect if found. Scripted directly with
        ``subprocess`` rather than python-gnupg's own
        ``auto_locate_key()``: that method appends its ``extra_args``
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

        Parameters
        ----------
        email
            The email address to resolve.
        keyserver
            The keyserver to fall back to when WKD fails.

        Returns
        -------
        :
            ``(fingerprint, stderr)`` — *fingerprint* is ``None`` if
            nothing was found.
        """
        result = _traced_run(
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
        """Import a key from a keyserver.

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

        Parameters
        ----------
        query
            A fingerprint, key ID, or email address identifying the key.
        keyserver
            The keyserver to fetch from.

        Returns
        -------
        :
            The imported key, as a single-element list.

        Raises
        ------
        GPGBackendError
            If no key was found, or gpg refused to import it (e.g. a key
            with no user ID attached).
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
        result = _clean_stderr(self._gpg.recv_keys(keyserver, query))
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
        """Report what ``commit_import_from_file()`` would import.

        Without touching the keyring at all. Uses python-gnupg's
        ``scan_keys()``, which drives gpg's own
        ``--dry-run --import-options import-show --import`` — verified
        empirically to leave the keyring untouched (``list_keys()``
        unchanged before/after) and to report the same fingerprint/keyid/
        uids shape as a real listing.

        Parameters
        ----------
        path
            Path to the exported key file to preview.

        Returns
        -------
        :
            The keys that would be imported.

        Raises
        ------
        GPGBackendError
            If no key was found in the file.
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
        """Report what ``commit_import_from_keyserver()`` would import.

        Without touching this keyring at all. There is no dry-run
        equivalent for a keyserver/WKD fetch — gpg always merges straight
        into whatever keyring it's pointed at — so this actually fetches
        into a throwaway scratch keyring instead (discarded before
        returning), and reuses ``import_from_keyserver()`` entirely for
        the fetch itself (WKD/email vs. exact key ID, and its error
        messages). ``is_new`` is recomputed against *this* (real)
        keyring — the scratch keyring's own copy is always "new" since it
        started empty, which isn't the answer the caller needs.

        Parameters
        ----------
        query
            A fingerprint, key ID, or email address identifying the key.
        keyserver
            The keyserver to fetch from.

        Returns
        -------
        :
            The key that would be imported, as a single-element list.

        Raises
        ------
        GPGBackendError
            If no key was found for *query*.
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
        """Filter a real import down to only the approved keys.

        Deletes any newly-added (never pre-existing) key that wasn't
        approved. A key that was already present is left untouched
        either way — leaving it unchecked only means "don't count it as
        imported here", never "remove my existing copy".

        Parameters
        ----------
        imported
            Every key a real import just brought in.
        approved
            The fingerprints the caller actually wants kept.

        Returns
        -------
        :
            *imported*, filtered down to only the approved keys.
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
        """Import from a file for real, keeping only the approved keys.

        Any other, newly-added key that came along in the same file is
        removed again immediately.

        Parameters
        ----------
        path
            Path to the exported key file to import (see
            ``preview_import_from_file()``).
        approved
            The fingerprints to actually keep. A no-op (no import at all)
            if empty.

        Returns
        -------
        :
            The approved, newly-imported keys.
        """
        if not approved:
            return []
        return self._commit_filtered(self.import_from_file(path), approved)

    def commit_import_from_keyserver(
        self, query: str, keyserver: str, approved: set[str]
    ) -> list[ImportedKey]:
        """Import from a keyserver for real, keeping only the approved keys.

        Parameters
        ----------
        query
            A fingerprint, key ID, or email address identifying the key
            (see ``preview_import_from_keyserver()``).
        keyserver
            The keyserver to fetch from.
        approved
            The fingerprints to actually keep. A no-op — no fetch at all —
            if empty, so declining the one candidate this can ever
            surface never touches the network or the keyring.

        Returns
        -------
        :
            The approved, newly-imported keys.
        """
        if not approved:
            return []
        return self._commit_filtered(
            self.import_from_keyserver(query, keyserver), approved
        )

    def search_keyserver(
        self, query: str, keyserver: str = DEFAULT_KEYSERVER
    ) -> list[SearchResult]:
        """Search a keyserver, returning every match for the user to pick.

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

        Parameters
        ----------
        query
            The search query — a name, email address, fingerprint or key
            ID, depending on what *keyserver* supports.
        keyserver
            The keyserver to search.

        Returns
        -------
        :
            Every match, empty if none.

        Raises
        ------
        GPGBackendError
            If the search itself failed (as opposed to a normal empty
            result).
        """
        result = _clean_stderr(self._gpg.search_keys(query, keyserver=keyserver))
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
        """Publish a public key to a keyserver.

        Parameters
        ----------
        fingerprint
            The key to publish.
        keyserver
            The keyserver to publish to.

        Raises
        ------
        GPGBackendError
            If gpg failed to publish the key.
        """
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
        """Re-fetch keys already in the keyring from a keyserver.

        The same effect as gpg's own ``--refresh-keys``, which
        python-gnupg doesn't wrap: fetching a key already present merges
        in any new signatures, revocations or expiry changes rather than
        duplicating it.

        Parameters
        ----------
        fingerprints
            Which keys to refresh; ``None`` (the default) refreshes every
            key in the keyring.
        keyserver
            The keyserver to refresh from.

        Returns
        -------
        :
            The refreshed keys, each flagged with whether anything about
            it actually changed. Empty when there is nothing to refresh —
            either an empty keyring with *fingerprints* unset, or an
            explicitly empty *fingerprints* list — since calling
            ``recv_keys()`` with zero keyids would otherwise wait on
            unexpected input.

        Raises
        ------
        GPGBackendError
            If the refresh itself failed (as opposed to one requested key
            no longer being available from the keyserver, which is
            silently skipped).
        """
        if fingerprints is None:
            fingerprints = [key.fingerprint for key in self.list_keys()]
        if not fingerprints:
            return []
        before = {key.fingerprint: key for key in self.list_keys()}
        result = _clean_stderr(self._gpg.recv_keys(keyserver, *fingerprints))
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
        """Return every key that has certified a key's user IDs.

        Driven by a raw ``--with-colons --list-sigs`` listing rather than
        python-gnupg's own ``list_keys(sigs=True)``: that wrapper's ``sig()``
        handler keeps only the signer's key ID and a display string, never
        the signer's full fingerprint that gpg lists right alongside it
        (colon field 13 — see ``KeySignature``). Self-certifications
        (key ID matching *fingerprint*'s own) are excluded, and several
        user IDs signed by the same key collapse to a single entry.

        Parameters
        ----------
        fingerprint
            The key whose signatures are being listed.

        Returns
        -------
        :
            Every certifying signature found, deduplicated by signer.
        """
        result = _traced_run(
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
        """Fetch signer keys not already in the keyring, one at a time.

        One at a time rather than a single batched ``--recv-keys`` call:
        such a call can't tell a genuine per-key miss apart from another
        identifier in the same request merely failing for an unrelated
        reason (see ``refresh_from_keyserver()``'s own note on this) — the
        caller needs to know exactly which ones were found.

        Parameters
        ----------
        identifiers
            A ``KeySignature``'s ``fingerprint``, or its bare ``keyid``
            when no fingerprint was available, for each signer to fetch.
        keyserver
            The keyserver to fetch from.

        Returns
        -------
        :
            One entry per identifier, in the same order, each with the
            fetched key on success or ``None`` when not found.
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
        """Return the ASCII-armored public key block for a key.

        Raises
        ------
        GPGBackendError
            If gpg failed to export the key.
        """
        armored = self._gpg.export_keys(fingerprint)
        if not armored:
            raise GPGBackendError(f"Could not export key {fingerprint}")
        return armored

    def export_secret_key(self, fingerprint: str, passphrase: Passphrase) -> str:
        """Return the ASCII-armored *secret* key block for a key.

        A full backup of the private key material, unlike
        ``export_public_key()``. GnuPG >= 2.1 refuses to export a secret
        key at all without its passphrase (see python-gnupg's own
        ``export_keys()`` docstring);
        driven directly via ``--passphrase-fd`` rather than through that
        wrapper, whose ``export_keys()`` only returns the raw armored
        bytes and discards stderr, so a wrong passphrase couldn't be told
        apart from any other failure.

        Parameters
        ----------
        fingerprint
            The key to export.
        passphrase
            Unlocks the key's secret part.

        Returns
        -------
        :
            The ASCII-armored secret key block.

        Raises
        ------
        BadPassphraseError
            If *passphrase* is wrong.
        GPGBackendError
            On any other failure.
        """

        def _run() -> subprocess.CompletedProcess:
            return _traced_run(
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
                input=f"{passphrase.passphrase}\n",
                secrets=(passphrase,),
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
        """Look up a key by fingerprint.

        Re-lists the keyring to get its current state.

        Raises
        ------
        GPGBackendError
            If no key with this fingerprint is in the keyring.
        """
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
