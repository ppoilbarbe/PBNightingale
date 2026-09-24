Preferences
=============

|icon-preferences-system| **Settings…** (toolbar icon, or the **Edit**
menu) opens a dialog with the following options:

- **Language** — the interface language. Takes effect after restarting
  PBNightingale.
- **Preferred key algorithm** — the algorithm pre-selected on the key
  creation wizard's Parameters page and on **Add subkey…** (RSA or
  ED25519; see :doc:`first_key` for the difference). Only changes the
  default selection — you can still pick the other one for any individual
  key or subkey.
- **Toolbar icon size** — either *System* (matches your desktop's own
  toolbar icon size) or a fixed pixel size. Applies immediately, no
  restart needed.
- **Remember passphrases for** — how long a passphrase you enter stays
  cached in memory after use, in minutes, so you are not re-prompted for
  every single operation on the same key within that window (see
  :doc:`managing_keys`, "The main window", for the lock icon that shows
  this). Set to *Never* to disable caching entirely and be prompted every
  time.
- **Activity history** — how many recent commands the **Activity
  (advanced)** window (see :doc:`managing_keys`) keeps, from 1 to 1000
  (default 50).

Key Servers
--------------

Every keyserver operation in PBNightingale (searching, importing,
publishing, and refreshing — see :doc:`importing_keys`) draws its list of
servers from here, rather than a single fixed address: a checkable,
reorderable list of keyserver URLs.

- The checkbox next to each server controls whether **Import…**,
  **Refresh**, and **Download Unknown Keys** (see :doc:`trust_and_signing`)
  query it — every checked server is tried, and whatever any of them
  find is merged together. **Search…** and **Publish…** instead let you
  pick from (or check) the servers to use each time you open them, so an
  unchecked server here still shows up as an option there.
- **Add…**, **Remove**, **Move Up**, and **Move Down** edit the list.
  The list can never be emptied completely, and at least one server must
  stay checked — the dialog will not accept your changes otherwise.
- **Restore Default List** resets the list back to its built-in defaults
  (``keys.openpgp.org`` and ``keyserver.ubuntu.com``, checked, plus a few
  other reachable servers, unchecked) — handy if you have edited it into
  a state you no longer want.
- **Import other people's signatures along with keys** — off by default;
  see below before turning it on.

.. _third-party-signatures:

Other people's signatures
-----------------------------

When GnuPG fetches a key from a keyserver, it keeps by default only the
signatures made by the key's **owner** (the ones that tie the key to its
own user IDs) and silently discards every signature made by **other
people**. This applies to everything PBNightingale fetches from a
keyserver: **Import…**, **Search…**, **Refresh** and **Download Unknown
Keys**.

This default is a protection. Keyservers used to accept any signature
from anyone, and in 2019 attackers exploited that to attach tens of
thousands of bogus signatures to some well-known keys (a "certificate
flooding" attack, CVE-2019-13050). A flooded key becomes so large that
GnuPG slows to a crawl, or gives up, as soon as it is imported, which can
make your whole keyring unusable. Keeping only the owner's own signatures
makes that attack harmless.

The price is that the web of trust (see :doc:`trust_and_signing`) no
longer works from keyserver data: a signature someone made on a key can
only reach you through a keyserver if this option is checked. What each
server offers also differs:

- ``keys.openpgp.org`` never distributes other people's signatures, with
  or without this option.
- ``keyserver.ubuntu.com`` does, and limits flooding on its side.

Check **Import other people's signatures along with keys** only if you
actually rely on the web of trust (for instance within a community that
signs each other's keys, such as a Linux distribution's developers). The
setting applies from the next keyserver operation on; it does not change
keys already in your keyring. Leave it unchecked otherwise: verifying a
fingerprint directly with its owner (see :doc:`trust_and_signing`) needs
no third-party signature at all.

Whatever this setting, a signature can always reach you as a file: the
person who signed a key can export it and send it to you, or to the
key's owner, and importing that file with **Import…** → **From file**
keeps every signature it contains. This protection only concerns
keyservers.
