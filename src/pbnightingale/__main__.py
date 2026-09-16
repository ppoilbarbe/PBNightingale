"""Entry point — run as `python -m pbnightingale` or `pbnightingale`."""

from __future__ import annotations

import argparse
import logging
import sys

_log = logging.getLogger(__name__)


def _build_parser(*, frozen: bool | None = None) -> argparse.ArgumentParser:
    from pbnightingale import __version__

    # --auto-update is only meaningful for the single-file PyInstaller
    # executable; a source checkout or a pip/PyPI install has no running
    # binary to replace, so the option is not even offered there.
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    parser = argparse.ArgumentParser(
        prog="pbnightingale",
        description="PBNightingale — graphical GPG key management utility.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    if frozen:
        update_group = parser.add_argument_group(
            "self-update",
            "Available only in PyInstaller-built executables — a source or "
            "pip/PyPI install has no single running binary to replace.",
        )
        update_group.add_argument(
            "--auto-update",
            action="store_true",
            default=False,
            help=(
                "Download the latest release from GitHub and replace the "
                "running executable, then exit"
            ),
        )

    return parser


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=logging.WARNING,
    )

    parser = _build_parser()
    ns = parser.parse_args()

    if getattr(ns, "auto_update", False):
        from pbnightingale.platform.auto_update import perform_auto_update

        ok, message = perform_auto_update()
        print(message, file=sys.stderr if not ok else sys.stdout)
        sys.exit(0 if ok else 1)

    _gui_main()  # pragma: no cover — GUI mode; not invoked by tests


def _load_bundled_fonts(app: object) -> None:  # pragma: no cover
    """Register bundled fonts into Qt's font database (frozen builds only).

    In a PyInstaller onefile build, fontconfig uses paths hardcoded at build
    time that don't exist on the target machine. QFontDatabase.addApplicationFont
    bypasses fontconfig entirely and guarantees that the bundled fonts (Ubuntu,
    DejaVu, …) are available regardless of the host fontconfig configuration.
    The runtime hook (hooks/pyi_rth_fonts.py) regenerates a portable
    fontconfig config as a first line of defense, but that still depends on
    fontconfig itself being present and correctly re-initialized on the
    target machine — this is the fix that actually holds regardless.
    """
    if not getattr(sys, "frozen", False):
        return
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(sys._MEIPASS) / "fonts"  # type: ignore[attr-defined]
    if not fonts_dir.is_dir():
        return

    loaded: set[str] = set()
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            loaded.update(QFontDatabase.applicationFontFamilies(fid))

    # Set Ubuntu as the default application font so the bundle renders
    # consistently on any machine, regardless of whether fontconfig finds
    # the system config. The bundled libfontconfig.so has its default config
    # path hardcoded to the build machine's conda prefix, which does not
    # exist on target machines, so font selection cannot rely on fontconfig.
    if "Ubuntu" in loaded:
        current = app.font()  # type: ignore[union-attr]
        app.setFont(  # type: ignore[union-attr]
            QFont("Ubuntu", current.pointSize() if current.pointSize() > 0 else 10)
        )


def _gui_main() -> None:  # pragma: no cover
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from pbnightingale import __version__
    from pbnightingale.resources import path as _resource
    from pbnightingale.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    _load_bundled_fonts(app)
    app.setApplicationName("PBNightingale")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("PBMou")
    app.setWindowIcon(QIcon(_resource("pbnightingale.png")))

    # i18n must be set up before any window is created so that translated
    # strings are picked up on first construction.
    from pbnightingale import i18n

    i18n.setup(app)

    _log.info("PBNightingale %s starting", __version__)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
