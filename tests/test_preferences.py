"""Tests for preferences.py — always against the isolated config directory."""

from __future__ import annotations

from pbnightingale import preferences


def test_default_is_rsa():
    assert preferences.get_preferred_algorithm() == "RSA"


def test_round_trips_ed25519():
    preferences.set_preferred_algorithm("ED25519")

    assert preferences.get_preferred_algorithm() == "ED25519"


def test_corrupt_value_falls_back_to_default():
    preferences._settings().setValue(preferences._ALGORITHM_KEY, "not-an-algorithm")

    assert preferences.get_preferred_algorithm() == "RSA"


def test_toolbar_icon_size_defaults_to_system():
    assert preferences.get_toolbar_icon_size() == "system"


def test_toolbar_icon_size_round_trips():
    preferences.set_toolbar_icon_size("32")

    assert preferences.get_toolbar_icon_size() == "32"


def test_toolbar_icon_size_corrupt_value_falls_back_to_default():
    preferences._settings().setValue(preferences._ICON_SIZE_KEY, "huge")

    assert preferences.get_toolbar_icon_size() == "system"


def test_passphrase_cache_minutes_defaults_to_ten():
    assert preferences.get_passphrase_cache_minutes() == 10


def test_passphrase_cache_minutes_round_trips():
    preferences.set_passphrase_cache_minutes(30)

    assert preferences.get_passphrase_cache_minutes() == 30


def test_passphrase_cache_minutes_zero_disables_but_is_valid():
    preferences.set_passphrase_cache_minutes(0)

    assert preferences.get_passphrase_cache_minutes() == 0


def test_passphrase_cache_minutes_corrupt_value_falls_back_to_default():
    preferences._settings().setValue(preferences._PASSPHRASE_CACHE_KEY, "lots")

    assert preferences.get_passphrase_cache_minutes() == 10


def test_passphrase_cache_minutes_negative_value_falls_back_to_default():
    preferences._settings().setValue(preferences._PASSPHRASE_CACHE_KEY, -5)

    assert preferences.get_passphrase_cache_minutes() == 10
