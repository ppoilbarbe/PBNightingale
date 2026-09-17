"""Password strength estimation via the zxcvbn algorithm.

Quality tiers and entropy thresholds mirror KeePassXC's own
``PasswordHealth`` class (``src/core/PasswordHealth.cpp`` in the KeePassXC
source tree) — see CODING.md, "Password strength".

Framework-agnostic: no PySide6 imports here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import zxcvbn

# zxcvbn-python's own default max_length is 72 (it raises ValueError past
# whatever max_length is passed, rather than truncating) — but that's a
# tunable parameter, not a hard limit of the algorithm itself: verified
# empirically up to 1024 characters, it just gets quadratically slower
# (~2s at 1024 chars, vs. ~200ms worst case at 256 for dictionary-heavy
# content), which matters here since the strength meter recomputes on
# every keystroke with no debounce. 256 matches KeePassXC's own C++
# zxcvbn port's real extrapolation threshold (its own average-entropy
# extrapolation past this many characters, mirrored below) — high enough
# for any realistic passphrase, without risking a laggy meter for
# pathological ones.
_MAX_ZXCVBN_LENGTH = 256


class PasswordQuality(Enum):
    """Password quality tier — mirrors KeePassXC's ``PasswordHealth::Quality``."""

    #: Entropy <= 0.
    BAD = "bad"
    #: Entropy < 40 bits.
    POOR = "poor"
    #: Entropy < 75 bits.
    WEAK = "weak"
    #: Entropy < 100 bits.
    GOOD = "good"
    #: Entropy >= 100 bits.
    EXCELLENT = "excellent"


@dataclass(frozen=True)
class PasswordStrength:
    """A password's estimated strength: raw entropy plus its quality tier."""

    #: Estimated entropy, in bits, from zxcvbn (extrapolated past
    #: ``_MAX_ZXCVBN_LENGTH`` characters — see ``_entropy_bits()``).
    entropy_bits: float
    #: Quality tier derived from ``entropy_bits`` — see ``_quality_for()``.
    quality: PasswordQuality


def _quality_for(entropy_bits: float) -> PasswordQuality:
    """Map an entropy value to its quality tier.

    Same thresholds as ``PasswordHealth::quality()`` in KeePassXC
    (0/40/75/100).
    """
    if entropy_bits <= 0:
        return PasswordQuality.BAD
    if entropy_bits < 40:
        return PasswordQuality.POOR
    if entropy_bits < 75:
        return PasswordQuality.WEAK
    if entropy_bits < 100:
        return PasswordQuality.GOOD
    return PasswordQuality.EXCELLENT


def _entropy_bits(password: str) -> float:
    """Return zxcvbn's estimated entropy for a password, in bits.

    Extrapolates linearly past ``_MAX_ZXCVBN_LENGTH`` characters rather
    than truncating, mirroring KeePassXC's own average-entropy
    extrapolation.
    """
    if not password:
        # zxcvbn-python raises on an empty string instead of returning a
        # zero score (verified empirically), so this has to be special-cased.
        return 0.0
    sample = password[:_MAX_ZXCVBN_LENGTH]
    result = zxcvbn.zxcvbn(sample, max_length=_MAX_ZXCVBN_LENGTH)
    bits = result["guesses_log10"] / math.log10(2)
    if len(password) > _MAX_ZXCVBN_LENGTH:
        average = bits / _MAX_ZXCVBN_LENGTH
        bits += average * (len(password) - _MAX_ZXCVBN_LENGTH)
    return bits


def evaluate_password_strength(password: str) -> PasswordStrength:
    """Estimate a password's strength: entropy in bits, plus a quality tier.

    Parameters
    ----------
    password
        The candidate passphrase to score.

    Returns
    -------
    :
        The estimated entropy and its corresponding quality tier.
    """
    entropy_bits = _entropy_bits(password)
    return PasswordStrength(
        entropy_bits=entropy_bits, quality=_quality_for(entropy_bits)
    )
