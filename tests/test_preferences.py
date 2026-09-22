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


def test_keyservers_default_to_the_built_in_list():
    assert preferences.get_keyservers() == list(preferences.DEFAULT_KEYSERVERS)


def test_keyservers_round_trip():
    servers = [("hkps://a.example", True), ("hkps://b.example", False)]

    preferences.set_keyservers(servers)

    assert preferences.get_keyservers() == servers


def test_keyservers_saved_as_empty_stays_empty_rather_than_falling_back():
    preferences.set_keyservers([("hkps://a.example", True)])

    preferences.set_keyservers([])

    assert preferences.get_keyservers() == []


def test_keyservers_round_trip_shrinking_the_list():
    preferences.set_keyservers(
        [("hkps://a.example", True), ("hkps://b.example", False)]
    )

    preferences.set_keyservers([("hkps://c.example", True)])

    assert preferences.get_keyservers() == [("hkps://c.example", True)]


def test_activity_log_max_entries_defaults_to_fifty():
    assert preferences.get_activity_log_max_entries() == 50


def test_activity_log_max_entries_round_trips():
    preferences.set_activity_log_max_entries(200)

    assert preferences.get_activity_log_max_entries() == 200


def test_activity_log_max_entries_corrupt_value_falls_back_to_default():
    preferences._settings().setValue(preferences._ACTIVITY_LOG_MAX_ENTRIES_KEY, "lots")

    assert preferences.get_activity_log_max_entries() == 50


def test_activity_log_max_entries_zero_falls_back_to_default():
    preferences._settings().setValue(preferences._ACTIVITY_LOG_MAX_ENTRIES_KEY, 0)

    assert preferences.get_activity_log_max_entries() == 50


def test_checked_keyserver_urls_returns_only_checked_ones_in_order():
    preferences.set_keyservers(
        [
            ("hkps://a.example", False),
            ("hkps://b.example", True),
            ("hkps://c.example", True),
        ]
    )

    assert preferences.get_checked_keyserver_urls() == [
        "hkps://b.example",
        "hkps://c.example",
    ]
