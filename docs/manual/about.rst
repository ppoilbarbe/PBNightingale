About PBNightingale
===================

.. image:: /_static/pbnightingale.png
   :alt: PBNightingale icon: a key lying in a wheat field under a cloudy
         blue sky
   :width: 160px
   :align: right

PBNightingale is a cross-platform graphical GPG key management utility,
for Linux, Windows and macOS.

Why
---

Many people shy away from encryption keys, whatever their operating system
(Linux, Windows, macOS or other), because the tooling, GPG's command line
in particular, is too intimidating. PBNightingale makes everyday GPG key
management approachable on Linux, Windows and macOS, without hiding what
it does.

This program is a legacy (heavily improved) from an older Python program,
itself an evolution of an ancient (~2014) Perl program.

Features
--------

- **Personal keys**: generate an RSA or ED25519 key pair, with a live
  passphrase strength meter (see :doc:`first_key`).
- **Subkeys**: add signing/encryption/authentication subkeys, revoke one
  (strong confirmation), export a key's public part, back up its private
  material, or delete a key from your keyring (see :doc:`managing_keys`).
- **Identities**: add, set primary, and revoke text user IDs (name, email,
  comment) and photo user IDs.
- **Expiration**: set or clear an expiration date on the primary key or on
  an individual subkey.
- **Passphrases**: change a key's passphrase; every passphrase field has a
  show/hide toggle and a configurable in-memory cache, with a per-key lock
  indicator in the key list.
- **Trust & signing**: sign other people's keys and set owner trust to
  build the web of trust, see who has already signed a given key, and
  fetch signer keys you don't have yet (see :doc:`trust_and_signing`).
- **Import & keyservers**: import keys from a file or a keyserver (by
  fingerprint, key ID, or email address) with a review step before
  anything is merged into your keyring, plus search, publish, and refresh
  against a keyserver (see :doc:`importing_keys`).
- **Interface**: French and English, with a preferences dialog for
  language, preferred key algorithm, toolbar icon size, and passphrase
  cache duration (see :doc:`preferences`).

The icon
--------

PBNightingale's icon shows a key lying in a wheat field, under a cloudy
blue sky. It illustrates the French expression *« prendre la clef des
champs »*, literally "to take the key of the fields": to leave, to escape,
to break free. Here is how the Académie française explains it:

   L’expression *prendre la clef des champs*, « s’en aller, s’enfuir,
   s’évader », remonte au XVe siècle. Dès cette époque, le nom *champ*
   désignait non seulement un espace destiné à l’agriculture (le champ du
   paysan) ou à l’activité militaire (le champ de bataille), mais aussi un
   espace ouvert, ni ville ni forêt, dans lequel on pouvait se promener, et
   cette liberté d’aller et venir symbolisait la détente ou l’évasion :
   *rendre les champs à quelqu’un* signifiait « lui donner sa liberté, le
   laisser partir » ; et *avoir champ et voie*, « être libre, pouvoir
   partir ». *La clef des champs* s’utilisait encore de façon autonome
   pour « la possibilité de sortir, d’être libre » : on désirait,
   demandait, ou on avait la clef des champs.

In short: the fields stand for an open space where one is free to come
and go, and their key for the freedom to get there. That is what your GPG
keys give you: the freedom to communicate privately, without depending on
anyone else to keep your messages safe.

The name
--------

"Nightingale" translates to French as *rossignol*, the bird. In French
slang, though, *rossignol* also means a lock pick (a skeleton key). Hence
the name, for a program that manages keys.
