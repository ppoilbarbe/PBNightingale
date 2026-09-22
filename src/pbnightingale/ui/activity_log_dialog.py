"""Activity (advanced) window — a live view of every external command run.

Non-modal (``setModal(False)``, shown via ``show()`` rather than
``exec()``) so it never blocks the rest of the application — see
``MainWindow._on_activity_log()``, which keeps a single instance alive for
the window's whole lifetime and just raises it on repeat activation,
rather than creating a new one each time.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem

from pbnightingale.core import activity_log
from pbnightingale.core.activity_log import ActivityEntry
from pbnightingale.ui.activity_log_dialog_ui import Ui_ActivityLogDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin

#: The table column holding the raw, unformatted command text — what
#: Ctrl+C copies, as opposed to the sequence-number/timestamp columns
#: before it.
_COMMAND_COLUMN = 2


class ActivityLogDialog(GeometryMixin, QDialog):
    """Non-modal, live view of the last commands PBNightingale has run."""

    #: Re-emitted, from whichever thread ``core.activity_log`` calls the
    #: subscriber on (normally a ``QThreadPool`` worker — see
    #: ``ui/gpg_worker.py``); Qt marshals the connection below back to the
    #: GUI thread automatically since it crosses threads.
    _entry_recorded = Signal(object)

    def __init__(self, parent=None) -> None:
        """Build the window and populate it with the current activity history."""
        super().__init__(parent)
        self.setModal(False)
        self._ui = Ui_ActivityLogDialog()
        self._ui.setupUi(self)
        self._init_geometry("activity_log_dialog")

        QShortcut(QKeySequence.StandardKey.Copy, self._ui.tblActivity, self._on_copy)
        self._ui.btnClearActivity.clicked.connect(self._on_clear)
        self._entry_recorded.connect(self._append_entry)
        # Kept subscribed for this dialog's whole lifetime, which is the
        # application's own — see the module docstring on why only one
        # instance ever exists.
        activity_log.subscribe(self._entry_recorded.emit)
        self.refresh()

    def refresh(self) -> None:
        """Repopulate the table from ``activity_log.entries()``.

        Called on creation, and again whenever the Activity history size
        preference changes (the ring buffer may have shrunk since).
        """
        table = self._ui.tblActivity
        table.setRowCount(0)
        for entry in activity_log.entries():
            self._append_entry(entry)

    def _append_entry(self, entry: ActivityEntry) -> None:
        """Append one row for *entry*, scrolling it into view."""
        table = self._ui.tblActivity
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(str(entry.seq)))
        table.setItem(row, 1, QTableWidgetItem(entry.timestamp.strftime("%H:%M:%S")))
        table.setItem(row, _COMMAND_COLUMN, QTableWidgetItem(entry.command))
        table.scrollToBottom()

    def _on_clear(self) -> None:
        """Discard the recorded history and clear the table.

        The dialog's own subscription is untouched (``activity_log.
        clear()``, not ``reset()``) — a command run right afterward still
        shows up live.
        """
        activity_log.clear()
        self._ui.tblActivity.setRowCount(0)

    def _on_copy(self) -> None:
        """Copy the selected row's command text to the clipboard."""
        row = self._ui.tblActivity.currentRow()
        if row < 0:
            return
        item = self._ui.tblActivity.item(row, _COMMAND_COLUMN)
        if item is not None:
            QApplication.clipboard().setText(item.text())
