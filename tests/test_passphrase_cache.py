"""Tests for core.passphrase_cache — an in-memory, TTL-based cache."""

from __future__ import annotations

from pbnightingale.core import passphrase_cache


def test_get_returns_none_when_never_stored():
    assert passphrase_cache.get("AAAA") is None


def test_stores_and_returns_the_passphrase():
    passphrase_cache.store("AAAA", "s3cret", 60)

    assert passphrase_cache.get("AAAA") == "s3cret"


def test_expired_entry_is_forgotten(monkeypatch):
    times = iter([100.0, 200.0])
    monkeypatch.setattr(passphrase_cache.time, "monotonic", lambda: next(times))

    passphrase_cache.store("AAAA", "s3cret", 60)  # expires at 160.0

    assert passphrase_cache.get("AAAA") is None


def test_entry_still_valid_just_before_expiry(monkeypatch):
    times = iter([100.0, 159.0])
    monkeypatch.setattr(passphrase_cache.time, "monotonic", lambda: next(times))

    passphrase_cache.store("AAAA", "s3cret", 60)  # expires at 160.0

    assert passphrase_cache.get("AAAA") == "s3cret"


def test_non_positive_ttl_is_a_noop():
    passphrase_cache.store("AAAA", "s3cret", 0)

    assert passphrase_cache.get("AAAA") is None


def test_empty_passphrase_is_a_noop():
    passphrase_cache.store("AAAA", "", 60)

    assert passphrase_cache.get("AAAA") is None


def test_clear_forgets_everything():
    passphrase_cache.store("AAAA", "s3cret", 60)

    passphrase_cache.clear()

    assert passphrase_cache.get("AAAA") is None


def test_different_fingerprints_are_independent():
    passphrase_cache.store("AAAA", "one", 60)
    passphrase_cache.store("BBBB", "two", 60)

    assert passphrase_cache.get("AAAA") == "one"
    assert passphrase_cache.get("BBBB") == "two"


def test_forget_removes_only_the_given_fingerprint():
    passphrase_cache.store("AAAA", "one", 60)
    passphrase_cache.store("BBBB", "two", 60)

    passphrase_cache.forget("AAAA")

    assert passphrase_cache.get("AAAA") is None
    assert passphrase_cache.get("BBBB") == "two"


def test_forget_unknown_fingerprint_is_a_noop():
    passphrase_cache.forget("AAAA")

    assert passphrase_cache.get("AAAA") is None
