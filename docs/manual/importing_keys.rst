Importing and publishing keys
===============================

Before you can send someone an encrypted message, or verify a signature
of theirs, you need their **public key** in your keyring (see
:doc:`concepts`). This page covers getting keys in, and making your own
findable by others.

Importing a key
-------------------

|icon-key-import| **Import…** (Keys toolbar/menu) opens a two-tab dialog:

- **From file** — for a key someone handed you directly (an exported
  ``.asc``/``.gpg`` file), or a whole exported keyring containing several
  keys at once.
- **From keyserver** — fetch by exact **fingerprint** or **key ID**, or
  by **email address** (tried via Web Key Directory first — a lookup
  straight from the owner's own email domain, when their provider
  supports it — falling back to the keyserver).

Either way, importing is a **two-step, review-first** process:

1. Click **Check…**. PBNightingale fetches (or reads the file) and shows
   every candidate key it found — identities, key ID, fingerprint, and
   whether it is already in your keyring — without changing your keyring
   yet. A key already present is pre-checked (bringing in something you
   already trust enough to have is low-stakes); a genuinely new key is
   left unchecked, requiring you to opt in deliberately.
2. Review the list, adjust the checkboxes, and click **Import** to commit
   only the checked rows. Unchecking a candidate that was already present
   never removes your existing copy — it just skips re-merging it from
   this source.

Prefer fetching by **fingerprint** over a name or email search whenever
you have it (read aloud to you, printed on a business card, compared at
an in-person meeting) — see :doc:`trust_and_signing` for why: finding a
key is not the same as knowing it genuinely belongs to who it claims.

Searching a keyserver
-------------------------

|icon-server-search| **Search…** (Keyservers toolbar/menu) is for when
you do not have an exact fingerprint or key ID — searching by name or
email against a
keyserver that supports it, and picking the right result from a list of
matches. Not every keyserver indexes names or emails this way (this
app's default, ``keys.openpgp.org``, deliberately does not, for privacy
reasons — searching there only works by exact fingerprint or key ID, and
even then without showing identities); point **Search…** at a different
keyserver if you need this.

Publishing your own key
---------------------------

|icon-server-publish| **Publish…** (Keyservers toolbar/menu, needs a
selected key) uploads the selected key to a keyserver, making it easy
for people who have never met you to find it. This is worth doing once your key is in a state you are
comfortable with (an email address you intend to keep using, for
instance), since publishing is effectively one-way — a public key already
picked up by a keyserver cannot be fully retracted, only revoked (see
:doc:`managing_keys`).

Refreshing from keyservers
------------------------------

|icon-server-refresh| **Refresh** (Keyservers toolbar/menu) re-fetches
keys from their keyserver, picking up anything that has changed since you
last imported them — new signatures from people who have since signed a
key you hold, a since-added or since-revoked UID, or a revocation. A
dialog first asks whether to refresh just the currently selected key or
every key in your keyring; a progress indicator is shown while it runs
(refreshing the whole keyring can take a while), and a report afterward
lists exactly which keys actually picked up a change. Run this
occasionally, and especially before relying on a key's current validity
for something important — see :doc:`trust_and_signing`, "Seeing who
signed a key".
