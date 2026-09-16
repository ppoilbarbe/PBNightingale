Preferences
=============

**Settings…** (toolbar icon, or the **Edit** menu) opens a small dialog
with four options:

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
