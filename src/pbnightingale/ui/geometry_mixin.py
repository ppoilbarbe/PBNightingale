"""Mixin restoring and persisting window geometry (and splitter sizes)."""

from __future__ import annotations

from pbnightingale.ui import window_state


class GeometryMixin:
    """Persist and restore a window's geometry, and optionally its splitters.

    Usage::

        class MyDialog(GeometryMixin, QDialog):
            def __init__(self, parent=None) -> None:
                super().__init__(parent)
                ...
                self._init_geometry("my_dialog", splitters={"main": self.splitter})

    ``splitters`` maps a short key to each ``QSplitter`` whose sizes should
    be persisted (omit for a window with none). ``toolbars=True`` also
    persists ``QMainWindow.saveState()`` (toolbar position, order and
    visibility) — only meaningful for a ``QMainWindow``. For
    ``QDialog``/``QWizard`` subclasses geometry is saved on the
    ``finished`` signal (fires on accept, reject, and the window's close
    button); a plain ``QWidget`` (no such signal, e.g. ``QMainWindow``)
    saves it from ``closeEvent`` instead.
    """

    def _init_geometry(
        self,
        state_key: str,
        *,
        splitters: dict | None = None,
        toolbars: bool = False,
    ) -> None:
        self._geo_state_key = state_key
        self._geo_splitters = splitters or {}
        self._geo_save_toolbars = toolbars
        self._geo_restored = False
        if hasattr(self, "finished"):
            self.finished.connect(lambda *_args: self._save_geometry())

    def _save_geometry(self) -> None:
        window_state.save_geometry(self._geo_state_key, self.saveGeometry())
        for splitter_key, splitter in self._geo_splitters.items():
            window_state.save_splitter_state(
                self._geo_state_key, splitter_key, splitter.saveState()
            )
        if self._geo_save_toolbars:
            window_state.save_toolbar_state(self._geo_state_key, self.saveState())

    def _restore_geometry(self) -> None:
        geometry = window_state.load_geometry(self._geo_state_key)
        if geometry is not None:
            self.restoreGeometry(geometry)
        for splitter_key, splitter in self._geo_splitters.items():
            state = window_state.load_splitter_state(self._geo_state_key, splitter_key)
            if state is not None:
                splitter.restoreState(state)
        if self._geo_save_toolbars:
            toolbar_state = window_state.load_toolbar_state(self._geo_state_key)
            if toolbar_state is not None:
                self.restoreState(toolbar_state)

    def showEvent(self, event) -> None:
        if not self._geo_restored:
            self._geo_restored = True
            self._restore_geometry()
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        if not hasattr(self, "finished"):
            self._save_geometry()
        super().closeEvent(event)
