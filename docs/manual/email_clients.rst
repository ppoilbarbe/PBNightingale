Using your key with an email client
=====================================

PBNightingale manages keys; it does not send or receive email itself.
This page explains how the keys you create or import here actually get
used to send encrypted and signed mail, in whichever email client you
already use.

The shared keyring
----------------------

PBNightingale operates on your system's normal GnuPG keyring — the same
one the ``gpg`` command line and most GPG-aware desktop applications use.
That means any key you generate or import here is immediately available,
with no extra export step, to **any application that itself relies on
the system's GnuPG installation** — which covers most Linux mail clients
and Windows/macOS setups built on Gpg4win/GPG Suite. There is one
significant exception, covered below: Thunderbird's modern built-in
OpenPGP support keeps its own separate key storage.

Thunderbird
--------------

Thunderbird has built-in OpenPGP support (since version 78) — but its
implementation manages keys **independently of GnuPG**, with its own
storage. A key you create in PBNightingale does not appear there
automatically:

1. In PBNightingale, **Export…** your key's public part (and, if you want
   Thunderbird to be able to decrypt/sign with it, **Back up private
   key…** as well — see :doc:`managing_keys`).
2. In Thunderbird: *Account Settings* → *End-to-End Encryption* → *Add
   Key* → *Use your external key* (or *Import an existing OpenPGP Key*,
   wording varies by version), and point it at the file(s) you exported.

Once added, composing a message offers **Encrypt** and **Digitally Sign**
toggles per message (and a per-recipient default under Account Settings),
and an incoming signed or encrypted message is verified/decrypted
automatically, with a padlock/seal indicator showing the result.

Outlook (Windows)
---------------------

Outlook has no built-in OpenPGP support. Install
`Gpg4win <https://www.gpg4win.org/>`_ (which PBNightingale on Windows
already relies on for the ``gpg`` binary itself — see the installation
notes) — its bundled **GpgOL** add-in integrates directly into Outlook's
compose window and uses your system GnuPG keyring, so a key created or
imported in PBNightingale is available there immediately, no export
needed.

Apple Mail (macOS)
----------------------

Apple Mail has no built-in OpenPGP support either. Install
`GPG Suite <https://gpgtools.org/>`_, whose **GPGMail** plugin adds
encrypt/sign controls to Mail's compose window and, like GpgOL, uses your
system GnuPG keyring directly.

Linux mail clients
----------------------

Most Linux mail clients (Evolution, KMail, GNOME's Geary, and others)
have OpenPGP support built on the system's ``gpg``/``gpgme`` directly —
no extra plugin needed, and a key managed in PBNightingale is available
to them immediately. Check your client's account or identity settings
for an "OpenPGP" or "Encryption" section to select which key to use for
your address.

What to expect once it's set up
------------------------------------

Whichever client you use, the everyday behavior is the same once your
key is configured:

- **Sending** — a compose-window toggle to sign, encrypt, or both (see
  :doc:`concepts`, "Encrypted **and** signed") for the current message,
  using the *recipient's* public key to encrypt and *your own* private
  key to sign. Encrypting requires already having the recipient's public
  key (see :doc:`importing_keys`) — most clients will tell you plainly if
  they don't.
- **Receiving** — decryption and signature verification happen
  automatically on open, with a clear indicator of the result: decrypted
  successfully or not, signature valid/invalid/from an unverified key.
  Pay attention to that indicator — a mail client that silently displayed
  an unverified or tampered message the same as a verified one would
  defeat the entire point.
