"""Tests for the Qt-side async runner wrapping GPGBackend calls."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool

from pbnightingale.ui.gpg_worker import run_async


def test_run_async_delivers_result_on_success(qtbot):
    pool = QThreadPool()
    results = []

    run_async(pool, lambda: 42, on_success=results.append)

    qtbot.waitUntil(lambda: results == [42])


def test_run_async_delivers_exception_on_failure(qtbot):
    pool = QThreadPool()
    errors = []

    def boom():
        raise ValueError("nope")

    run_async(pool, boom, on_error=errors.append)

    qtbot.waitUntil(lambda: len(errors) == 1)
    assert isinstance(errors[0], ValueError)
    assert str(errors[0]) == "nope"


def test_run_async_passes_args_and_kwargs(qtbot):
    pool = QThreadPool()
    results = []

    run_async(pool, lambda a, b, c=0: a + b + c, 1, 2, on_success=results.append, c=3)

    qtbot.waitUntil(lambda: results == [6])


def test_run_async_without_callbacks_does_not_raise(qtbot):
    pool = QThreadPool()

    worker = run_async(pool, lambda: 1)

    qtbot.waitUntil(lambda: pool.activeThreadCount() == 0)
    assert worker is not None
