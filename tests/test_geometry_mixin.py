"""Tests for ui.geometry_mixin — restore/persist window geometry and splitters."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QSplitter,
    QTextEdit,
    QToolBar,
    QWidget,
)

from pbnightingale.ui.geometry_mixin import GeometryMixin


class _DummyDialog(GeometryMixin, QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_geometry("dummy_dialog")


class _DummyMainWindow(GeometryMixin, QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(QTextEdit(self.splitter))
        self.splitter.addWidget(QTextEdit(self.splitter))
        self.setCentralWidget(self.splitter)
        self._init_geometry("dummy_main_window", splitters={"main": self.splitter})


def test_dialog_first_show_without_saved_state_does_not_crash(qtbot):
    dialog = _DummyDialog()
    qtbot.addWidget(dialog)

    dialog.show()

    assert dialog.isVisible() is True


def test_dialog_geometry_persists_across_instances(qtbot):
    first = _DummyDialog()
    qtbot.addWidget(first)
    first.show()
    first.resize(444, 333)
    first.accept()  # QDialog.accept() emits `finished`

    second = _DummyDialog()
    qtbot.addWidget(second)
    second.show()

    assert second.size().width() == 444
    assert second.size().height() == 333


def test_main_window_geometry_persists_via_close_event(qtbot):
    first = _DummyMainWindow()
    qtbot.addWidget(first)
    first.show()
    first.resize(800, 500)
    first.close()

    second = _DummyMainWindow()
    qtbot.addWidget(second)
    second.show()

    # A few pixels of drift is expected: the offscreen platform's layout
    # pass can nudge a QMainWindow's final size around what was requested.
    assert second.size().width() == pytest.approx(800, abs=5)
    assert second.size().height() == pytest.approx(500, abs=5)


def test_splitter_sizes_persist_via_close_event(qtbot):
    first = _DummyMainWindow()
    qtbot.addWidget(first)
    first.show()
    first.resize(800, 500)
    first.splitter.setSizes([600, 200])
    first.close()

    second = _DummyMainWindow()
    qtbot.addWidget(second)
    second.show()

    sizes = second.splitter.sizes()
    assert sizes[0] == pytest.approx(600, abs=5)
    assert sizes[1] == pytest.approx(200, abs=5)


def test_geometry_only_restored_once_per_instance(qtbot):
    dialog = _DummyDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.resize(444, 333)

    dialog.hide()
    dialog.move(10, 10)
    dialog.show()  # second showEvent must not re-apply the saved geometry

    assert dialog.pos().x() == 10


class _DummyMainWindowWithToolbar(GeometryMixin, QMainWindow):
    def __init__(self, *, save_toolbars: bool, parent=None) -> None:
        super().__init__(parent)
        self.toolbar = QToolBar("Test", self)
        self.toolbar.setObjectName("testToolbar")
        self.addToolBar(self.toolbar)
        self._init_geometry("dummy_main_window_toolbars", toolbars=save_toolbars)


def test_toolbar_visibility_persists_via_close_event(qtbot):
    first = _DummyMainWindowWithToolbar(save_toolbars=True)
    qtbot.addWidget(first)
    first.show()
    first.toolbar.setVisible(False)
    first.close()

    second = _DummyMainWindowWithToolbar(save_toolbars=True)
    qtbot.addWidget(second)
    second.show()

    assert second.toolbar.isVisible() is False


def test_toolbars_not_persisted_when_opted_out(qtbot):
    first = _DummyMainWindowWithToolbar(save_toolbars=False)
    qtbot.addWidget(first)
    first.show()
    first.toolbar.setVisible(False)
    first.close()

    second = _DummyMainWindowWithToolbar(save_toolbars=False)
    qtbot.addWidget(second)
    second.show()

    assert second.toolbar.isVisible() is True


def test_no_splitters_argument_is_safe(qtbot):
    class _Plain(GeometryMixin, QWidget):
        def __init__(self) -> None:
            super().__init__()
            self._init_geometry("dummy_plain_widget")

    widget = _Plain()
    qtbot.addWidget(widget)
    widget.show()
    widget.close()  # must not raise even though there is no `finished` signal
