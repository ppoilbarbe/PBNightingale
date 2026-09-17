"""Refresh Keys dialog — picks the scope of a keyserver "Refresh".

Lets the user choose whether "Refresh" (Keyservers toolbar/menu)
re-fetches only the selected key or every key in the keyring, before the
(possibly slow) network operation starts.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.refresh_keys_dialog_ui import Ui_RefreshKeysDialog


class RefreshKeysDialog(GeometryMixin, QDialog):
    """Lets the user choose between refreshing the selected key or all of them, before the network operation starts."""

    def __init__(self, *, has_selection: bool, parent=None) -> None:
        """Build the dialog, defaulting to "selected key" when possible.

        Parameters
        ----------
        has_selection
            Whether a key is currently selected — when ``False``, the
            "selected key" option is disabled and "every key" is
            pre-checked instead.
        parent
            The owning window.
        """
        super().__init__(parent)
        self._ui = Ui_RefreshKeysDialog()
        self._ui.setupUi(self)
        self._init_geometry("refresh_keys_dialog")

        self._ui.lblExplanation.setText(
            _(
                "Re-download keys from their keyserver, picking up any new "
                "signatures, identities or revocations."
            )
        )
        self._ui.radioSelected.setEnabled(has_selection)
        if has_selection:
            self._ui.radioSelected.setChecked(True)
        else:
            self._ui.radioAll.setChecked(True)

        self._ui.buttonBox.accepted.connect(self.accept)
        self._ui.buttonBox.rejected.connect(self.reject)

    def refresh_all(self) -> bool:
        """Report which scope the user chose.

        Returns
        -------
        :
            ``True`` when the user chose "every key" over "the selected
            key".
        """
        return self._ui.radioAll.isChecked()
