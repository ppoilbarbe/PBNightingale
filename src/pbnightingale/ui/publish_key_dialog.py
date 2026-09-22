"""Publish Key dialog — picks which of the configured keyservers to publish a key to.

Lists every keyserver from Preferences ("Key Servers"), pre-checking
whichever are checked there — the list itself isn't editable from here
(adding/removing/reordering servers stays Preferences' job), only each
row's own checkbox is, to say which of them this one publish actually
goes to.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidgetItem

from pbnightingale import preferences
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.publish_key_dialog_ui import Ui_PublishKeyDialog


class PublishKeyDialog(GeometryMixin, QDialog):
    """Lets the user pick which keyservers to publish a key to."""

    def __init__(self, keyid: str, parent=None) -> None:
        """Build the dialog, pre-checking every keyserver checked in Preferences.

        Parameters
        ----------
        keyid
            The key ID shown in the confirmation question.
        parent
            The owning window.
        """
        super().__init__(parent)
        self._ui = Ui_PublishKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("publish_key_dialog")

        self._ui.lblQuestion.setText(_("Publish {keyid} to:").format(keyid=keyid))
        self._ui.lblWarning.setText(
            _(
                "Once a key is on a public keyserver, it generally cannot "
                "be fully removed again, only revoked."
            )
        )
        for url, checked in preferences.get_keyservers():
            item = QListWidgetItem(url)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._ui.lstKeyservers.addItem(item)

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._update_ok_enabled()
        self._ui.lstKeyservers.itemChanged.connect(self._update_ok_enabled)

        self._ui.buttonBox.accepted.connect(self.accept)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _update_ok_enabled(self) -> None:
        """Enable Publish only while at least one keyserver is checked."""
        self._ok_button.setEnabled(bool(self.selected_keyservers()))

    def selected_keyservers(self) -> list[str]:
        """Return the URLs of every checked keyserver, in display order.

        Returns
        -------
        :
            The keyservers to publish to.
        """
        list_widget = self._ui.lstKeyservers
        return [
            list_widget.item(i).text()
            for i in range(list_widget.count())
            if list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
