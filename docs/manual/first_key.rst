Creating your first key
=========================

This page assumes you have read :doc:`concepts` and know what a key pair,
a passphrase and a subkey are. It walks through **Keys → New key…**
(toolbar icon, or the **Keys** menu), which opens a four-page wizard.

1. Identity
-------------

Enter your **name**, **email address**, and optionally a short
**comment**. These become your key's first :ref:`user ID <uids>` — the
public label attached to your key (``Name (Comment) <email@example.com>``).
You can add more email addresses later; see :doc:`managing_keys`.

2. Parameters
---------------

Choose the **algorithm**:

- **RSA** (2048/3072/4096 bits) — the traditional, universally supported
  choice.
- **ED25519** (Curve25519) — a modern elliptic-curve algorithm: smaller
  keys and faster operations for equivalent security, supported by any
  reasonably recent GPG. Because ED25519 is a signature-only curve, a key
  generated on it cannot itself perform encryption — the wizard silently
  forces a dedicated Curve25519 **encryption subkey** on for you in this
  case (see below), rather than letting you produce a key that could sign
  but never decrypt anything.

The default matches whatever is set in **Settings…** as your preferred
algorithm (see :doc:`preferences`).

Also on this page: which **subkeys** to generate alongside your primary
key. Both a **signing subkey** and an **encryption subkey** are proposed
and checked by default — leave them checked. Unchecking one folds that
capability into the primary key itself instead, which still works but
gives up the damage-control benefit explained in :doc:`concepts`
("Subkeys: not everything on one key"): if that capability is ever
compromised, you would have to revoke your primary key itself rather
than just a subkey.

3. Passphrase
---------------

Choose the passphrase that will protect your new private key on disk (see
:doc:`concepts`, "Your passphrase"). A colored strength meter updates as
you type, showing an estimated entropy in bits and a quality tier from
*Bad* to *Excellent* — aim for at least *Good*. This passphrase is asked
for every time the key is used to decrypt or sign something, so make it
something you can reliably type or recall, not just something that scores
well once and is then forgotten.

4. Generate
-------------

Review the summary and click **Finish**. Key generation runs in the
background with a progress indicator — it can take a few seconds,
depending on the algorithm and your machine, since it involves genuine
randomness gathering. If something goes wrong (for instance, the two
passphrase fields not matching earlier), an error is shown and **Back**
lets you correct the earlier pages without starting over.

Once generation succeeds, your new key appears in the main key list,
where you can now add more identities, subkeys, a photo, sign other
people's keys, publish it to a keyserver, and everything else covered in
the rest of this manual.
