"""Tests for core.secret.Passphrase."""

from __future__ import annotations

import pytest

from pbnightingale.core.secret import Passphrase


def test_str_never_shows_the_real_value():
    assert str(Passphrase("hunter2")) == "**********"


def test_repr_never_shows_the_real_value():
    assert repr(Passphrase("hunter2")) == "<Passphrase '**********'>"


def test_passphrase_property_returns_the_real_value():
    assert Passphrase("hunter2").passphrase == "hunter2"


def test_bool_reflects_emptiness_of_the_wrapped_value():
    assert bool(Passphrase("hunter2")) is True
    assert bool(Passphrase("")) is False


def test_equal_when_wrapped_values_are_equal():
    assert Passphrase("hunter2") == Passphrase("hunter2")
    assert Passphrase("hunter2") != Passphrase("other")


def test_frozen_instance_cannot_be_mutated():
    passphrase = Passphrase("hunter2")

    with pytest.raises(AttributeError):
        passphrase._value = "changed"  # type: ignore[misc]


def test_never_appears_when_a_frame_dumps_its_locals():
    """Simulate an enhanced traceback tool that prints each frame's locals.

    Plain ``traceback.format_exc()`` only ever prints source lines, never
    variable values, so it can't demonstrate the leak this class closes
    off. A tool like ``rich``'s or ``cgitb``'s traceback view — or a
    debugger breaking on the exception — does print each local's
    ``repr()``, which is exactly the scenario ``Passphrase`` protects
    against.
    """

    def _boom(secret: Passphrase) -> None:
        raise ValueError("boom")

    try:
        _boom(Passphrase("hunter2"))
    except ValueError as exc:
        dumped = repr(exc.__traceback__.tb_next.tb_frame.f_locals)

    assert "hunter2" not in dumped


def test_fstring_interpolation_does_not_leak_the_value():
    passphrase = Passphrase("hunter2")

    assert f"{passphrase}" == "**********"
