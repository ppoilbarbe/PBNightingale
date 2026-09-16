"""Run GPGBackend calls off the GUI thread.

``core.gpg_backend`` is synchronous and framework-agnostic; this module is
the Qt-side bridge that runs those calls on ``QThreadPool`` and delivers the
result back on the thread that owns the receiving slot (normally the GUI
thread), via Qt's queued signal delivery.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(Exception)


class GPGWorker(QRunnable):
    """Runs ``fn(*args, **kwargs)`` in a thread pool.

    The result (or exception) is emitted on ``signals`` rather than
    returned or raised directly, since ``run()`` executes on a worker
    thread with no caller to return to.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 — forwarded via signal, not swallowed
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


# QThreadPool owns a runnable on the C++ side only; without a Python-side
# reference kept until completion, a worker with no other referrer (the
# common case: `run_async(pool, fn, on_success=...)` with the return value
# discarded) can be garbage-collected right after run() returns, silently
# dropping its still-pending queued signal before the GUI thread delivers it.
_active_workers: set[GPGWorker] = set()


def run_async(
    pool: QThreadPool,
    fn: Callable[..., Any],
    *args: Any,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    **kwargs: Any,
) -> GPGWorker:
    """Submit ``fn(*args, **kwargs)`` to *pool* and wire up its callbacks."""
    worker = GPGWorker(fn, *args, **kwargs)
    _active_workers.add(worker)
    worker.signals.finished.connect(lambda *_: _active_workers.discard(worker))
    worker.signals.failed.connect(lambda *_: _active_workers.discard(worker))
    if on_success is not None:
        worker.signals.finished.connect(on_success)
    if on_error is not None:
        worker.signals.failed.connect(on_error)
    pool.start(worker)
    return worker
