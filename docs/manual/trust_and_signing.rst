Trust and key signing
=======================

Read :doc:`concepts` first, specifically "Trust: how do you know a public
key really belongs to them?" — this page is the practical follow-up.
PBNightingale surfaces two related but independent concepts, shown as two
separate rows in a key's detail panel:

- **Validity** — is this key's UID-to-key binding genuine? Computed
  automatically from the signatures actually present on the key, combined
  with how much you trust each signer (below). This is what changes when
  you sign a key, or when someone whose signatures you rely on signs one.
- **Owner trust** — a private, personal judgment: how much do *you*
  trust this person to correctly verify *other* people's identities
  before signing their keys? It is never published anywhere and only
  affects how *your* copy of GPG computes validity for keys signed by
  them.

Note that GPG automatically treats any key you hold the private part of
as **ultimately** trusted, unless you explicitly override that — your own
keys don't need this workflow applied to themselves.

Signing a key
----------------

|icon-key-sign| Select a key — anyone's, not just your own — and use
**Sign key…** (Trust toolbar/menu). Before doing this, verify through
some channel you
actually trust that the key really belongs to who it claims: compare its
fingerprint with the owner in person or over a call you initiated
yourself, rather than trusting whatever channel you found the key
through. Signing a key you have not actually verified defeats the whole
point of the web of trust — it turns your signature into noise instead
of a meaningful vouch.

The dialog offers:

- **Sign as** — which of your own certify-capable keys performs the
  signature, if you have more than one.
- **Verification level** — how carefully you checked, from *no particular
  claim* (0) up to *extensive verification* (3). This is recorded on the
  signature but, in practice, GPG's own validity computation only cares
  whether it is 0 or at least 2 — a *casual* (1) check has no effect on
  the signed key's computed validity, so if you are going to record a
  level at all beyond the default, treat 1 as equivalent to not bothering.
- **Local signature only** (checked by default) — keeps the signature in
  your own keyring, never published or exported alongside the key. This
  is the safer default: a *local* signature only affects your own trust
  computations, while an *exportable* (non-local) signature becomes a
  public statement the moment the key is published, visible to anyone
  who fetches it. Uncheck it only once you are comfortable making that
  public claim.

Seeing who signed a key
---------------------------

Signing a key is only half the picture — the **Signatures** tab in a
key's detail panel (next to **Details**) lists every signature already on
the *selected* key's user IDs: who has certified this key as genuine. A
signer already in your keyring is shown the same way as the main key
list (name, email, key ID, expiry); one your keyring cannot resolve shows
up as "Unknown locally" with only its identifier.

**Download Unknown Keys**, below the list, fetches every unresolved
signer from every keyserver checked in :doc:`preferences` and reports
which ones were found — useful after importing a key with signatures
from people you don't have yet, since a signature from a signer you
cannot even look up contributes nothing to that key's computed validity.

Where do those signatures come from? By default, not from keyservers:
GnuPG discards other people's signatures whenever it fetches a key from
one, to protect you against a key flooded with bogus signatures (see
:ref:`third-party-signatures` in :doc:`preferences`, which also explains
how to turn this off). Signatures you see here were therefore made in
your own keyring, or arrived in a key imported from a file. The usual way
to pass a signature on is exactly that: after signing someone's key, send
them the signed key as a file (**Export…**), and they import it and
publish it themselves, to a keyserver that keeps such signatures
(``keyserver.ubuntu.com`` does, ``keys.openpgp.org`` does not).

Setting owner trust
-----------------------

|icon-trust-set| **Set owner trust…** (Trust toolbar/menu) records how
much you trust the selected key's owner to correctly verify *other*
people's identities —
*undefined*, *never*, *marginal*, *full*, or *ultimate*. This needs no
passphrase: it is a purely local note in your own trust database, not a
cryptographic operation on the key itself.

Refreshing trust
--------------------

|icon-trust-refresh| Validity is computed once and cached; **Refresh
trust** (Trust toolbar/menu) recomputes it for every key in your
keyring — useful after
signing several keys in a row, changing someone's owner trust, or
importing new signatures, so the key list's validity column reflects the
current state rather than a stale one.
