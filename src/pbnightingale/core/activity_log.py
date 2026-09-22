"""In-memory history of external commands PBNightingale has run.

Framework-agnostic (no PySide6 import here): feeds the "Activity (advanced)"
window (``ui/activity_log_dialog.py``), which is the only place that turns
this into a live, GUI-thread-safe view. This module itself only owns a
lock-protected ring buffer and calls its subscribers synchronously, in
whichever thread called ``record()`` — normally a ``QThreadPool`` worker
thread (see ``ui/gpg_worker.py``), never the GUI thread.

Independent of ``logging``'s ``-d``/``--debug`` gate on purpose: the
Activity window is meant to always have something to show, not only when
debug logging happens to be enabled — see ``gpg_backend._traced_run()``/
``_traced_popen()``, the two call sites that feed this module.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

#: Fallback capacity until ``configure()`` is called with the preferences
#: value (``preferences.DEFAULT_ACTIVITY_LOG_MAX_ENTRIES``).
DEFAULT_MAX_ENTRIES = 50


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    """One external-program invocation, as shown in the Activity window."""

    #: Monotonically increasing across the process's whole lifetime —
    #: never reused or reset by ``clear()``, so a sequence number still
    #: identifies a command's original run order even once older entries
    #: have aged out of (or been cleared from) the ring buffer.
    seq: int
    timestamp: datetime
    command: str


_lock = threading.Lock()
_entries: deque[ActivityEntry] = deque(maxlen=DEFAULT_MAX_ENTRIES)
_subscribers: list[Callable[[ActivityEntry], None]] = []
_next_seq = 1


def configure(max_entries: int) -> None:
    """Resize the ring buffer, keeping whatever most-recent entries still fit.

    Parameters
    ----------
    max_entries
        The new capacity; values below 1 are clamped to 1.
    """
    global _entries
    with _lock:
        _entries = deque(_entries, maxlen=max(1, max_entries))


def record(command: str) -> ActivityEntry:
    """Append *command* to the history and notify every subscriber.

    Parameters
    ----------
    command
        The shell-quoted argv of the external command that was run.

    Returns
    -------
    :
        The recorded entry — a caller that needs a supplementary line
        grouped with this exact command (e.g. some out-of-band output
        gpg wrote to a side file rather than stdout/stderr) passes its
        ``seq`` to ``record_detail()``. See ``gpg_backend._traced_run()``,
        which attaches it to its ``CompletedProcess`` result as
        ``.activity_seq`` for that purpose.
    """
    global _next_seq
    # astimezone(), not now(): the Activity window shows local wall-clock
    # time (see ActivityLogDialog._append_entry()'s strftime("%H:%M:%S")),
    # but ruff's DTZ005 still wants a tz-aware value to guard against an
    # accidental UTC/local mix-up elsewhere.
    timestamp = datetime.now().astimezone()
    with _lock:
        seq = _next_seq
        _next_seq += 1
        entry = ActivityEntry(seq=seq, timestamp=timestamp, command=command)
        _entries.append(entry)
    _notify(entry)
    return entry


def record_detail(seq: int, text: str) -> None:
    """Append a supplementary line sharing an already-recorded command's number.

    Used when a command's real output lives in a side file rather than
    stdout/stderr — e.g. gpg's ``--attribute-file``, read by
    ``core/gpg_backend.py::_load_photos()`` only after the command has
    finished, so it can't be folded into the original ``record()`` call.
    Does not allocate a new sequence number: *seq* must be one a prior
    ``record()`` call already returned, so this line stays visibly
    grouped with that command in the Activity window instead of looking
    like a step of its own.

    Parameters
    ----------
    seq
        The sequence number to reuse, as returned by ``record()``'s
        ``ActivityEntry``.
    text
        The line's content.
    """
    entry = ActivityEntry(seq=seq, timestamp=datetime.now().astimezone(), command=text)
    with _lock:
        _entries.append(entry)
    _notify(entry)


def _notify(entry: ActivityEntry) -> None:
    """Call every subscriber with *entry*, snapshotting the list first.

    A subscriber unsubscribing itself mid-notification (or another thread
    doing so concurrently) must not skip or crash iterating the live list
    — ruff's PERF101 doesn't see that this ``list()`` is a defensive
    copy, not a redundant cast.
    """
    for subscriber in list(_subscribers):  # noqa: PERF101
        subscriber(entry)


def clear() -> None:
    """Discard every currently-kept entry, without touching subscribers.

    Unlike ``reset()`` (test-only teardown, also drops every subscriber),
    this is what a "Clear History" button in the UI should call — an
    already-open Activity window stays subscribed and keeps showing
    commands recorded afterward.
    """
    global _entries
    with _lock:
        _entries = deque(maxlen=_entries.maxlen)


def entries() -> list[ActivityEntry]:
    """Return every currently-kept entry, oldest first.

    Returns
    -------
    :
        A snapshot list — safe to iterate even while ``record()`` runs
        concurrently on another thread.
    """
    with _lock:
        return list(_entries)


def subscribe(callback: Callable[[ActivityEntry], None]) -> Callable[[], None]:
    """Register *callback* to be called with each new entry as it's recorded.

    Parameters
    ----------
    callback
        Called synchronously, on whichever thread called ``record()`` —
        a GUI subscriber must marshal back to the GUI thread itself (e.g.
        by emitting a Qt signal from within *callback*).

    Returns
    -------
    :
        A function that unregisters *callback* again; safe to call more
        than once.
    """
    _subscribers.append(callback)

    def _unsubscribe() -> None:
        if callback in _subscribers:
            _subscribers.remove(callback)

    return _unsubscribe


def reset() -> None:
    """Clear every entry and subscriber, and restart the sequence counter.

    This module-level state otherwise persists for the whole pytest
    session; see ``tests/conftest.py``'s autouse ``_isolated_activity_log``.
    Test-only teardown — unlike ``clear()``, which a "Clear History"
    button can safely call at any time, resetting the sequence counter
    mid-session would make a new entry reuse a number already shown for
    an older, now-forgotten one.
    """
    global _entries, _next_seq
    with _lock:
        _entries = deque(maxlen=DEFAULT_MAX_ENTRIES)
        _next_seq = 1
    _subscribers.clear()
