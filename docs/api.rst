API Reference
=============

.. contents:: Modules
   :local:
   :depth: 1

Package
-------

.. automodule:: pbnightingale
   :members:
   :undoc-members:

Entry point
-----------

.. automodule:: pbnightingale.__main__
   :members: main

Internationalisation
--------------------

.. automodule:: pbnightingale.i18n
   :members:
   :undoc-members:

Application settings
--------------------

.. automodule:: pbnightingale.settings
   :members:
   :undoc-members:

Preferences
-----------

.. automodule:: pbnightingale.preferences
   :members:
   :undoc-members:

core — GPG backend
------------------

gpg backend
~~~~~~~~~~~

.. automodule:: pbnightingale.core.gpg_backend
   :members:
   :undoc-members:

passphrase cache
~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.core.passphrase_cache
   :members:
   :undoc-members:

password strength
~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.core.password_strength
   :members:
   :undoc-members:

platform
--------

dirs
~~~~

.. automodule:: pbnightingale.platform.dirs
   :members:
   :undoc-members:

locale
~~~~~~

.. automodule:: pbnightingale.platform.locale
   :members:
   :undoc-members:

auto update
~~~~~~~~~~~

.. automodule:: pbnightingale.platform.auto_update
   :members:
   :undoc-members:

ui
--

about dialog
~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.about_dialog
   :members:
   :undoc-members:

add photo dialog
~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.add_photo_dialog
   :members:
   :undoc-members:

add subkey dialog
~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.add_subkey_dialog
   :members:
   :undoc-members:

add uid dialog
~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.add_uid_dialog
   :members:
   :undoc-members:

backup private key dialog
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.backup_private_key_dialog
   :members:
   :undoc-members:

change passphrase dialog
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.change_passphrase_dialog
   :members:
   :undoc-members:

delete key dialog
~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.delete_key_dialog
   :members:
   :undoc-members:

geometry mixin
~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.geometry_mixin
   :members:
   :undoc-members:

gpg worker
~~~~~~~~~~

.. automodule:: pbnightingale.ui.gpg_worker
   :members:
   :undoc-members:

.. note::

   ``import_key_dialog``, ``key_list_view`` and ``search_key_dialog`` are
   not documented here — a module-level ``Qt.ItemDataRole.UserRole``
   constant in the first two breaks autodoc's PySide6 mocking (and
   ``search_key_dialog`` imports from ``key_list_view``). See CODING.md,
   "Packaging & docs".

key operation dialog
~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.key_operation_dialog
   :members:
   :undoc-members:

main window
~~~~~~~~~~~

.. automodule:: pbnightingale.ui.main_window
   :members:
   :undoc-members:

new key wizard
~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.new_key_wizard
   :members:
   :undoc-members:

password line edit
~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.password_line_edit
   :members:
   :undoc-members:

password strength meter
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.password_strength_meter
   :members:
   :undoc-members:

photo viewer dialog
~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.photo_viewer_dialog
   :members:
   :undoc-members:

revoke key dialog
~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.revoke_key_dialog
   :members:
   :undoc-members:

revoke photo dialog
~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.revoke_photo_dialog
   :members:
   :undoc-members:

revoke subkey dialog
~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.revoke_subkey_dialog
   :members:
   :undoc-members:

revoke uid dialog
~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.revoke_uid_dialog
   :members:
   :undoc-members:

set expiration dialog
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.set_expiration_dialog
   :members:
   :undoc-members:

set owner trust dialog
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.set_owner_trust_dialog
   :members:
   :undoc-members:

set primary uid dialog
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.set_primary_uid_dialog
   :members:
   :undoc-members:

settings dialog
~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.settings_dialog
   :members:
   :undoc-members:

sign key dialog
~~~~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.sign_key_dialog
   :members:
   :undoc-members:

window state
~~~~~~~~~~~~

.. automodule:: pbnightingale.ui.window_state
   :members:
   :undoc-members:
