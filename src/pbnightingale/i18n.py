"""Internationalisation bootstrap.

Call ``setup(app)`` once, before creating any window. It:
  * reads the language override from QSettings (if set),
  * detects the system language from environment variables as fallback,
  * loads the matching gettext catalogue (falls back to no-op),
  * installs ``_()`` as a builtin for Python-side strings,
  * registers a QTranslator so Qt's own strings are also translated.
"""

from __future__ import annotations

import gettext
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QSettings, QTranslator
from PySide6.QtWidgets import QApplication

from pbnightingale.platform import system_language

_DOMAIN = "pbnightingale"
_LOCALE_DIR = Path(__file__).parent / "locale"
_SETTINGS_KEY = "language/override"


class _GettextTranslator(QTranslator):
    """Qt translator that delegates every lookup to a gettext catalogue."""

    def __init__(
        self, translation: gettext.NullTranslations, parent: QApplication
    ) -> None:
        """Wrap a gettext translation catalogue as a Qt translator.

        Parameters
        ----------
        translation
            The catalogue to delegate every lookup to.
        parent
            The Qt object owning this translator.
        """
        super().__init__(parent)
        self._t = translation

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Look up a source string in the wrapped gettext catalogue.

        Parameters
        ----------
        context
            Unused — gettext lookups here aren't context-scoped.
        source_text
            The string to translate.
        disambiguation
            Unused.
        n
            Unused — plural forms aren't handled by this translator.

        Returns
        -------
        :
            The translated string, or ``source_text`` unchanged if no
            catalogue entry matches.
        """
        return self._t.gettext(source_text)


_system_language = system_language


def available_languages() -> list[tuple[str, str]]:
    """Return every language this app has a compiled catalogue for.

    Discovers languages dynamically by scanning ``.mo`` files under the locale
    directory.  Each catalogue must contain a ``language_name`` msgid whose
    msgstr is the language name written in that language (e.g. "Français").

    Returns
    -------
    :
        ``(lang_code, lang_name_in_that_language)`` pairs, sorted by code.
    """
    result: list[tuple[str, str]] = []
    for mo_path in sorted(_LOCALE_DIR.glob(f"*/LC_MESSAGES/{_DOMAIN}.mo")):
        lang_code = mo_path.parts[-3]
        try:
            t = gettext.translation(
                _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang_code]
            )
        except FileNotFoundError:
            continue
        lang_name = t.gettext("language_name")
        if lang_name == "language_name":
            lang_name = lang_code
        result.append((lang_code, lang_name))
    return result


def _settings() -> QSettings:
    """Return the ``QSettings`` instance backing the language override."""
    import pbnightingale.settings as _settings_mod

    cfg = _settings_mod._dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def get_language_override() -> str:
    """Return the saved language override.

    Returns
    -------
    :
        The saved language code, or ``""`` for system default.
    """
    val = _settings().value(_SETTINGS_KEY, "")
    return val if isinstance(val, str) else ""


def set_language_override(code: str) -> None:
    """Persist a language override.

    Parameters
    ----------
    code
        The language code to save, or ``""`` to clear the override and
        fall back to the system default.
    """
    _settings().setValue(_SETTINGS_KEY, code)


def current_language() -> str:
    """Return the effective interface language code (override or system).

    Falls back to ``"en"`` when the resolved code has no catalogue of its
    own (no `.mo` under `locale/`) — e.g. a system language this app hasn't
    been translated into.

    Returns
    -------
    :
        The 2-letter language code currently in effect.
    """
    override = get_language_override()
    lang = override if override else _system_language()
    codes = {code for code, _ in available_languages()}
    return lang if lang in codes else "en"


def setup(app: QApplication) -> None:
    """Install translations for an application.

    Safe to call multiple times (each call replaces the previous translator).

    Parameters
    ----------
    app
        The application to install the gettext- and Qt-level translators on.
    """
    override = get_language_override()
    lang = override if override else _system_language()

    try:
        t: gettext.NullTranslations = gettext.translation(
            _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang]
        )
    except FileNotFoundError:
        t = gettext.NullTranslations()

    t.install()

    translator = _GettextTranslator(t, app)
    app.installTranslator(translator)

    # Load Qt's own translations (dialog buttons, standard item views, etc.)
    qt_translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    qt_lang = lang.split("_")[0] if lang else ""
    qt_translator = QTranslator(app)
    if qt_translator.load(f"qtbase_{qt_lang}", qt_translations):
        app.installTranslator(qt_translator)
