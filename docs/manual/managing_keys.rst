Managing your keys
====================

The main window
------------------

The key list on the left groups your keys under **My keys** (ones you hold
the private part of) and **Other keys** (public keys you have imported,
belonging to other people). Selecting a key shows its details on the
right: fingerprint, algorithm, capabilities, dates, trust, and three
tables — **identities** (user IDs), **photos**, and **subkeys**.

Only one of those three tables is ever "active" at a time — whichever you
last clicked into or tabbed to — and the toolbar/menu actions enable
themselves accordingly: select a subkey to enable subkey actions, select
a user ID to enable identity actions, and so on. Every action is also
available from a right-click context menu on the relevant list (or press
``c`` to open it from the keyboard), and from the corresponding menu bar
entry.

The unlabeled column next to each key's name shows a lock icon for any
key you hold the private part of: unlocked while its passphrase is
currently cached in memory (see :doc:`concepts`, "Your passphrase" — GPG
does this itself via ``gpg-agent`` so you are not re-prompted on every
single operation), locked otherwise. Double-click that icon to forget a
cached passphrase immediately, without waiting for it to expire on its
own. How long a passphrase stays cached is configurable in
:doc:`preferences`.

|icon-view-refresh| **Refresh** (Keys toolbar/menu, or ``F5``) reloads the
list from your local GPG keyring — useful if you changed something with
the ``gpg`` command line directly. This only re-reads what is already on
disk; to pick up changes made by *other people* (a new signature on your
key, a since-revoked UID), see "Refreshing from keyservers" in
:doc:`importing_keys`.

Every key, subkey and user ID also has a |icon-edit-copy| **Copy ID**/
**Copy email** action (toolbar, menu, or right-click), and the
fingerprint shown in the details panel has its own **Copy** button next
to it — handy for grabbing an exact identifier to share or compare
without retyping it, for instance during the fingerprint check described
in :doc:`trust_and_signing`.

Toolbars can be dragged, rearranged, or hidden to your liking (**View**
menu); **View → Reset toolbars** restores the default layout. Press
``Shift+F1`` (or the |icon-help-contextual| **What's This** toolbar
button) and then click any control for a short explanation of what it
does.

|icon-history| **View → Activity (advanced)…** (or ``F12``) opens a
non-blocking window listing the most recent external commands
PBNightingale has run (``gpg``, ``gpg-connect-agent``, …) — a technical,
advanced view, mainly useful for troubleshooting. Each command is
numbered sequentially; select a row and press ``Ctrl+C`` to copy it to
the clipboard. **Clear History** empties the list without resetting the
numbering, so a number always identifies the same command even after
clearing. How many commands are kept is configurable in
:doc:`preferences`.

.. _uids:

Identities (user IDs)
------------------------

A user ID binds a name and email address to your key (see :doc:`concepts`,
"Identities"). A key can carry several — for instance if you use more than
one email address — with one marked **primary** (shown with a ✓ in the
identities list, and used as the key list's default Name/Email columns).

- |icon-user-add| **Add user ID…** — adds a new identity to a key you
  hold the private part of. Needs that key's passphrase, since the new
  UID has to be signed by the key itself.
- |icon-user-default| **Set as primary…** — makes the selected identity
  the default one. Disabled when it already is the primary, or when it
  is revoked.
- |icon-user-delete| **Revoke user ID…** — permanently marks the selected
  identity as no longer valid (for instance, an email address you no
  longer use). Requires the strong confirmation checkbox all revocation
  dialogs use, since this cannot be undone. Disabled when it is the
  *last* remaining valid identity on the key — a key needs at least one.

Photo user IDs
------------------

A photo is a special kind of user ID: a small JPEG embedded in the key
instead of a name and email. It is mostly a human sanity check (matching
a face to a key at an in-person key-signing, for instance) rather than a
security mechanism in itself.

- |icon-photo-add| **Add photo…** — attaches an image file to the
  selected key (needs its passphrase). PBNightingale handles the JPEG
  conversion for you.
- |icon-photo-delete| **Revoke photo…** — permanently marks the selected
  photo as no longer valid, behind the same strong confirmation as
  revoking a UID.
- |icon-view| **Show** (toolbar, Identities menu, context menu, or just
  double-clicking the photo) opens it at full, unscaled size.

Subkeys
---------

Recall from :doc:`concepts` ("Subkeys") that your primary key normally
delegates day-to-day signing and encryption to dedicated subkeys, so that
a compromised subkey can be replaced without touching your identity or
your accumulated web-of-trust signatures.

- |icon-subkey-add| **Add subkey…** — adds a signing, encryption, or
  authentication subkey to the selected key (needs its passphrase). Uses
  the same algorithm choice as the key creation wizard; see
  :doc:`first_key`.
- |icon-subkey-revoke| **Revoke subkey…** — permanently marks the
  selected subkey as no longer valid, behind the strong confirmation
  checkbox. Do this as soon as you suspect a subkey's private material
  may have leaked (a stolen laptop, for instance) — a revoked subkey
  stops being offered for new encryption or trusted for new signatures
  the moment your updated public key reaches whoever you communicate
  with, which is exactly why :doc:`importing_keys` covers refreshing
  keys from a keyserver.

Expiration dates
-------------------

- |icon-key-expire| **Set key expiration…** — sets the *primary* key's
  own expiration date.
- |icon-subkey-expire| **Set subkey expiration…** — sets the *selected
  subkey's* expiration date.

Both open the same dialog: a "Never expires" checkbox, checked by
default, gating a date picker. Setting an expiration is routine hygiene,
not an emergency measure — unlike revocation, it does not require
confirmation, and accepting the dialog without changing anything is
always a safe no-op. Note that setting the *primary* key's expiration
never touches its subkeys, and vice versa — each is independent.

Changing a passphrase
------------------------

|icon-password-change| **Change passphrase…** replaces the passphrase
protecting a key's private material: enter the current passphrase once,
then the new one twice (to
catch typos before they lock you out). This re-encrypts every part of the
private key — the primary key and every subkey — so it can take a moment
on a key with several subkeys.

Backing up and exporting
----------------------------

- |icon-key-export| **Export…** saves the selected key's **public** part
  to a file — safe to share freely, and the normal way to hand your key
  to someone directly instead of through a keyserver.
- |icon-key-backup| **Back up private key…** saves the selected key's
  **private** material to a file, protected by its passphrase. Treat the
  resulting file exactly
  like the key itself: store it somewhere as secure as you would the
  original (an offline encrypted drive, for instance), since anyone who
  obtains it and the passphrase can fully impersonate you. This is your
  disaster-recovery copy — the only way to keep using this identity if
  your computer is lost, stops working, or is replaced.

Revoking and deleting
-------------------------

These are different operations, easy to confuse:

- |icon-key-revoke| **Revoke key…** announces, publicly and permanently,
  that your *primary* key itself should no longer be trusted — the
  strongest statement GPG has, reserved for a suspected full compromise
  or permanently retiring an identity. Behind the strong confirmation
  checkbox, and irreversible: once you publish the revoked key (see
  :doc:`importing_keys`), there is no walking it back.
- |icon-key-delete| **Delete…** removes a key from *your own local
  keyring* — public material, and private material too if present. This
  is purely local
  bookkeeping, not a security announcement: it does not need a passphrase
  (nothing cryptographic happens), and it does nothing to any copies of
  the key already published elsewhere or held by other people. Deleting
  your *own* key without first revoking and publishing it does not
  invalidate it — anyone who already has a copy of it can still use it as
  if nothing happened.
