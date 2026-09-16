"""Tests for pbnightingale.settings — configuration directory override."""

from __future__ import annotations

from pbnightingale import settings
from pbnightingale.platform import AppDirs


def test_configure_overrides_config_home(tmp_path):
    settings.configure(tmp_path)
    try:
        assert settings._dirs.config_home == tmp_path
        assert settings._dirs.data_home == tmp_path
        assert settings._dirs.cache_home == tmp_path
    finally:
        settings.configure()


def test_configure_none_restores_platform_default():
    settings.configure(None)
    default = AppDirs(settings._DOMAIN)
    assert settings._dirs.config_home == default.config_home
