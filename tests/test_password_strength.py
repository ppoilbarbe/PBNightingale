"""Tests for core.password_strength (zxcvbn-based entropy estimation)."""

from __future__ import annotations

import math

import zxcvbn

from pbnightingale.core.password_strength import (
    _MAX_ZXCVBN_LENGTH,
    PasswordQuality,
    evaluate_password_strength,
)


def test_empty_password_is_zero_entropy_and_bad():
    strength = evaluate_password_strength("")

    assert strength.entropy_bits == 0.0
    assert strength.quality is PasswordQuality.BAD


def test_short_common_password_is_poor_or_worse():
    strength = evaluate_password_strength("password")

    assert strength.quality in (PasswordQuality.BAD, PasswordQuality.POOR)


def test_long_passphrase_reaches_at_least_weak():
    strength = evaluate_password_strength("correct horse battery staple")

    assert strength.entropy_bits > 40
    assert strength.quality in (
        PasswordQuality.WEAK,
        PasswordQuality.GOOD,
        PasswordQuality.EXCELLENT,
    )


def test_longer_passphrase_reaches_good():
    strength = evaluate_password_strength("correct-horse-battery-staple-42!")

    assert strength.entropy_bits >= 75
    assert strength.quality in (PasswordQuality.GOOD, PasswordQuality.EXCELLENT)


def test_long_random_password_is_excellent():
    strength = evaluate_password_strength(r"4oal-e\_kmTEcdcS?<9;7tlx|ob#!Fi\(7i/]l$-")

    assert strength.entropy_bits > 100
    assert strength.quality is PasswordQuality.EXCELLENT


def test_longer_password_never_has_less_entropy_than_a_prefix_of_it():
    short_strength = evaluate_password_strength("Tr0ub4dor&3")
    long_strength = evaluate_password_strength("Tr0ub4dor&3" * 3)

    assert long_strength.entropy_bits >= short_strength.entropy_bits


def test_password_longer_than_the_zxcvbn_limit_does_not_raise():
    # _MAX_ZXCVBN_LENGTH is this module's own deliberate performance
    # threshold (zxcvbn's max_length is a tunable parameter, not a fixed
    # library ceiling — verified working correctly, just increasingly
    # slowly, up to at least 1024 characters); past it, the backend
    # extrapolates instead of scoring the whole password (mirrors
    # KeePassXC's own PasswordHealth extrapolation past its own threshold).
    password = "aB3!" * (_MAX_ZXCVBN_LENGTH // 4 + 25)  # well past the limit
    prefix = password[:_MAX_ZXCVBN_LENGTH]

    strength = evaluate_password_strength(password)
    prefix_strength = evaluate_password_strength(prefix)

    assert strength.entropy_bits > prefix_strength.entropy_bits

    prefix_bits = zxcvbn.zxcvbn(prefix, max_length=_MAX_ZXCVBN_LENGTH)[
        "guesses_log10"
    ] / math.log10(2)
    expected = prefix_bits + (prefix_bits / _MAX_ZXCVBN_LENGTH) * (
        len(password) - _MAX_ZXCVBN_LENGTH
    )
    assert strength.entropy_bits == expected
