"""Tests for the CLI entry point (`python -m pbnightingale`)."""

from __future__ import annotations

import logging

import pytest

from pbnightingale import __main__ as _main_mod
from pbnightingale import __version__


def test_build_parser_version(capsys):
    parser = _main_mod._build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"pbnightingale {__version__}"


def test_main_launches_gui(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pbnightingale"])
    called = []
    monkeypatch.setattr(_main_mod, "_gui_main", lambda: called.append(True))

    _main_mod.main()

    assert called == [True]


def test_main_version_exits_before_gui(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["pbnightingale", "--version"])
    monkeypatch.setattr(
        _main_mod,
        "_gui_main",
        lambda: pytest.fail("--version must not launch the GUI"),
    )

    with pytest.raises(SystemExit) as exc:
        _main_mod.main()

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"pbnightingale {__version__}"


class TestAutoUpdateFlag:
    """--auto-update is only registered for a PyInstaller-frozen executable."""

    def test_not_offered_when_not_frozen(self):
        parser = _main_mod._build_parser(frozen=False)

        with pytest.raises(SystemExit):
            parser.parse_args(["--auto-update"])

    def test_offered_when_frozen(self):
        parser = _main_mod._build_parser(frozen=True)

        ns = parser.parse_args(["--auto-update"])

        assert ns.auto_update is True

    def test_defaults_to_sys_frozen(self, monkeypatch):
        monkeypatch.setattr("sys.frozen", True, raising=False)
        parser = _main_mod._build_parser()

        ns = parser.parse_args(["--auto-update"])

        assert ns.auto_update is True


class TestVerbosityFlags:
    """-d/--debug and -q/--quiet select the effective logging level."""

    def test_defaults_to_info(self):
        parser = _main_mod._build_parser(frozen=False)

        ns = parser.parse_args([])

        assert ns.loglevel == logging.INFO

    def test_debug_sets_debug_level(self):
        parser = _main_mod._build_parser(frozen=False)

        ns = parser.parse_args(["-d"])

        assert ns.loglevel == logging.DEBUG

    def test_quiet_sets_warning_level(self):
        parser = _main_mod._build_parser(frozen=False)

        ns = parser.parse_args(["-q"])

        assert ns.loglevel == logging.WARNING

    def test_debug_and_quiet_are_mutually_exclusive(self):
        parser = _main_mod._build_parser(frozen=False)

        with pytest.raises(SystemExit):
            parser.parse_args(["-d", "-q"])

    def test_main_configures_root_logger_level(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["pbnightingale", "--debug"])
        monkeypatch.setattr(_main_mod, "_gui_main", lambda: None)
        monkeypatch.setattr(logging.root, "handlers", [])

        _main_mod.main()

        assert logging.root.level == logging.DEBUG


class TestPrintCompletionFlag:
    """--print-completion prints a shtab-generated completion script and exits."""

    def test_prints_bash_completion_and_exits_zero(self, capsys):
        parser = _main_mod._build_parser(frozen=False)

        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--print-completion", "bash"])

        assert exc.value.code == 0
        assert "pbnightingale" in capsys.readouterr().out

    def test_rejects_unknown_shell(self):
        parser = _main_mod._build_parser(frozen=False)

        with pytest.raises(SystemExit):
            parser.parse_args(["--print-completion", "not-a-shell"])


class TestMainAutoUpdateDispatch:
    def test_success_prints_to_stdout_and_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["pbnightingale", "--auto-update"])
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr(
            "pbnightingale.platform.auto_update.perform_auto_update",
            lambda: (True, "Updated to version 9.9.9."),
        )
        monkeypatch.setattr(
            _main_mod,
            "_gui_main",
            lambda: pytest.fail("--auto-update must not launch the GUI"),
        )

        with pytest.raises(SystemExit) as exc:
            _main_mod.main()

        assert exc.value.code == 0
        assert capsys.readouterr().out.strip() == "Updated to version 9.9.9."

    def test_failure_prints_to_stderr_and_exits_nonzero(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["pbnightingale", "--auto-update"])
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr(
            "pbnightingale.platform.auto_update.perform_auto_update",
            lambda: (False, "error: could not reach GitHub"),
        )

        with pytest.raises(SystemExit) as exc:
            _main_mod.main()

        assert exc.value.code == 1
        assert capsys.readouterr().err.strip() == "error: could not reach GitHub"
