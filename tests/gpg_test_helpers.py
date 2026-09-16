"""Shared test helper: generate a real (but tiny/fast) GPG key pair.

Not a test module itself (no ``test_*``/``*_test`` name, so pytest never
collects it) — imported by tests that need fixture key material.
"""

from __future__ import annotations

import random
from pathlib import Path

import gnupg
from PySide6.QtGui import QColor, QImage, qRgb


def generate_test_key(
    gnupghome,
    *,
    name: str = "Test User",
    email: str = "test@example.com",
    with_subkey: bool = False,
) -> str:
    """Generate a key pair directly in *gnupghome* and return its fingerprint.

    Bypasses ``GPGBackend`` on purpose: key generation is milestone 8's
    concern (the personal key wizard). RSA-1024 keeps generation to a
    fraction of a second — plenty for test fixture data, not for real use.
    """
    home = Path(gnupghome)
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    gpg = gnupg.GPG(gnupghome=str(home))
    gpg.encoding = "utf-8"
    kwargs = {
        "key_type": "RSA",
        "key_length": 1024,
        "name_real": name,
        "name_email": email,
        "expire_date": 0,
        "no_protection": True,
    }
    if with_subkey:
        kwargs.update(
            key_usage="cert,sign",
            subkey_type="RSA",
            subkey_length=1024,
            subkey_usage="encrypt",
        )
    key = gpg.gen_key(gpg.gen_key_input(**kwargs))
    return str(key.fingerprint)


def make_test_jpeg(path, color: str = "blue") -> Path:
    """Write a tiny (real, valid) JPEG file to *path* and return it.

    gpg's ``addphoto`` rejects anything that isn't a genuine JPEG (verified
    empirically — it checks the file's magic bytes), so photo-related
    tests need actual image bytes, not an arbitrary placeholder file.
    """
    target = Path(path)
    image = QImage(24, 30, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    if not image.save(str(target), "JPEG"):
        raise RuntimeError(f"Could not write test JPEG to {target}")
    return target


def make_large_test_jpeg(path) -> Path:
    """Write a real JPEG large enough (tens of KB) to trigger gpg's
    ``photoid.jpeg.add``'s follow-up ``photoid.jpeg.size`` "this is quite
    a large JPEG, use it anyway?" confirmation prompt during ``addphoto`` —
    a solid-color image like ``make_test_jpeg()`` compresses to under 1 KB
    and never triggers it. Random noise defeats JPEG's compression instead
    of relying on a specific pixel dimension, which isn't reliably enough
    on its own (verified empirically against a real key).
    """
    target = Path(path)
    image = QImage(240, 240, QImage.Format.Format_RGB32)
    rng = random.Random(0)  # noqa: S311 — fixture data, not security-sensitive
    for y in range(image.height()):
        for x in range(image.width()):
            image.setPixel(
                x, y, qRgb(rng.randrange(256), rng.randrange(256), rng.randrange(256))
            )
    if not image.save(str(target), "JPEG", 85):
        raise RuntimeError(f"Could not write large test JPEG to {target}")
    return target
