GPG/PGP concepts
=================

This page has no PBNightingale-specific instructions. It explains what
GPG (GNU Privacy Guard, an implementation of the OpenPGP standard) actually
does and why you might want to use it, in plain language. If you already
know what a key pair, encryption and signing are, skip ahead to
:doc:`first_key`.

The problem GPG solves
-----------------------

An ordinary email is a postcard, not a sealed letter. It travels through
several servers before reaching its recipient, and at every one of those
stops, anyone with access can read it, and anyone who controls part of the
path can alter it or send a convincing forgery in your name. The same is
true of a file sent over most messaging apps or uploaded to a shared
drive.

GPG addresses two separate problems at once:

- **Confidentiality** — making sure that *only the intended recipient* can
  read a message, even if it is intercepted along the way.
- **Authenticity and integrity** — making sure that a message *really
  comes from who it claims to*, and that it was not altered after it was
  written.

These are solved with two different, complementary operations:
**encryption** for confidentiality, and **digital signing** for
authenticity and integrity. Both rely on the same underlying idea: a
**key pair**.

Key pairs: a lock only you can open
-------------------------------------

Traditional ("symmetric") encryption uses a single secret shared by both
sides — like a physical key that opens and locks the same padlock. That
works fine between two people who can meet in person to agree on the
secret, but it does not scale to the internet: you cannot securely hand a
shared secret to someone you have never met, over a channel that is not
already secure — which is exactly the problem you were trying to solve in
the first place.

GPG instead uses **asymmetric ("public-key") cryptography**. Instead of
one shared secret, you generate a mathematically linked **pair** of keys:

- A **public key**, which you give to anyone — post it on your website,
  email it around, upload it to a keyserver. It is not a secret and
  sharing it as widely as possible is the whole point.
- A **private key**, which never leaves your computer and which you
  protect with a passphrase. Anyone who obtains your private key can
  impersonate you and read messages meant for you — treat it like a house
  key, not like a business card.

The two keys are linked so that:

- Anything **encrypted with your public key** can only be **decrypted
  with your private key**.
- Anything **signed with your private key** can be **verified by anyone**
  using your public key.

Notice the asymmetry in both directions: encryption uses the
*recipient's* public key, signing uses the *sender's* private key. This
one design choice is what makes the rest of this page work.

Encryption: only the recipient can read it
--------------------------------------------

To send someone a confidential message:

1. You obtain their **public key** (from their website, a keyserver, a
   business card, or however they choose to share it — see
   :doc:`importing_keys`).
2. Your GPG software encrypts the message using that public key.
3. You send the resulting scrambled ciphertext through whatever channel
   you like — it does not need to be private, because only the matching
   private key can undo the scrambling.
4. Only the recipient, who holds the matching private key, can decrypt
   it. Not you (once encrypted, you cannot read your own message back
   unless you also encrypted a copy to yourself), not their email
   provider, not anyone who intercepts it in transit.

This is the digital equivalent of a padlock that only its owner has the
key to: anyone can snap it shut, but only the owner can open it again.

Signing: proving who sent it, and that it wasn't changed
-----------------------------------------------------------

Signing solves the opposite problem: not hiding content, but *vouching*
for it.

1. Your GPG software computes a cryptographic fingerprint of your message
   and encrypts *that fingerprint* with your **private key**, attaching
   the result as a signature.
2. Anyone who has your **public key** can recompute the same fingerprint
   from the message they received and check it against your signature.
3. If they match, two things are proven at once: the message really was
   signed by whoever holds your private key, and it has not been altered
   by so much as a single character since it was signed — recomputing the
   fingerprint would give a different result if it had.

This is the digital equivalent of a wax seal: anyone can *check* the seal
by comparing it against your known signet ring (your public key), but
only you could have *pressed* it, because only you have the ring (your
private key).

Encrypted **and** signed
--------------------------

Encryption and signing are independent and are normally used together:
encrypt the message with the *recipient's* public key so only they can
read it, and sign it with *your own* private key so they know it genuinely
came from you and was not tampered with in transit. Your email client (or
GPG itself, from the command line) does both operations in one pass — see
:doc:`email_clients` for how this looks day to day.

Your passphrase: the lock on your private key
-------------------------------------------------

Because losing control of your private key is equivalent to losing
control of your digital identity, GPG encrypts the private key itself on
disk with a **passphrase** you choose. Every time your private key is
used — to decrypt a message addressed to you, or to sign something — you
are asked for that passphrase (`gpg-agent`, running quietly in the
background, caches it for a short while so you are not prompted on every
single operation). A weak or reused passphrase undermines everything
above it; PBNightingale's key creation wizard shows a live strength meter
while you choose one for exactly this reason.

Identities: binding a key to "you"
-------------------------------------

A key pair on its own is just a block of mathematics — nothing ties it to
a name or an email address yet. That binding is done through one or more
**user IDs** (UIDs), each typically of the form ``Name (Comment)
<email@example.com>``, attached to your key and signed by it. A single
key can carry several UIDs — for instance one per email address you use —
and one of them is marked as *primary*, the one shown by default. See
:doc:`managing_keys` for adding, changing and revoking UIDs, including
photo UIDs (a JPEG embedded in the key, mostly a visual sanity check
rather than a security feature).

Subkeys: not everything on one key
--------------------------------------

Although it is possible to use a single key pair for both signing and
encryption, GPG strongly encourages splitting these into separate
**subkeys** bound under one primary key: typically the primary key only
*certifies* (signs UIDs and subkeys, and signs other people's keys — see
below), a dedicated **signing subkey** signs your everyday messages, and a
dedicated **encryption subkey** decrypts messages sent to you. The
benefit is damage control: if your laptop is compromised and your
encryption subkey leaks, you revoke and replace *that subkey alone* —
your identity, your accumulated signatures from other people, and your
primary key's own signing power are unaffected. Losing the primary key
itself is far more serious, which is exactly why it is used as little as
possible day to day. PBNightingale's key creation wizard proposes this
signing/encryption subkey split by default; see :doc:`managing_keys`.

Expiration and revocation: keys don't last forever
-------------------------------------------------------

A key pair can carry an **expiration date**, after which it stops being
usable — a routine hygiene measure that limits how long a lost or
forgotten key stays trusted. Independently, a key, subkey, UID or photo
can be explicitly **revoked** at any time, which is how you announce "this
is no longer valid" — for a suspected compromise, or simply because a UID's
email address is no longer yours. A revocation, once published, cannot be
undone; anyone who fetches your updated public key sees it and stops
trusting the revoked material. See :doc:`managing_keys`.

Trust: how do you know a public key really belongs to them?
------------------------------------------------------------------

Encryption and signing only deliver on their promises if the public key
you are using really belongs to the person you think it does. Nothing
stops an attacker from generating a key pair, attaching *your* name and
email to it as a UID, and publishing it — this is exactly what happens
if you fetch a key from a keyserver by name alone without checking
further.

GPG's answer to this is the **web of trust**: you can **sign someone
else's key** once you have verified, through some channel you trust (in
person, a video call, comparing fingerprints read aloud, a
well-established prior relationship), that a given public key really
belongs to them. That signature, published alongside their key, is your
public statement "I checked, this key really is theirs." Anyone who
already trusts *you* to verify identities carefully can then trust that
key transitively, without doing the verification work themselves — hence
*web* of trust, rather than a single central authority. This has two
separate dimensions, easy to confuse but genuinely different:

- **Validity** — is this UID/key binding genuine? Built from the
  signatures actually present on the key.
- **Owner trust** — how much do *you personally* trust this key's owner
  to correctly verify *other people's* identities before signing their
  keys? A personal, private setting that only affects how *your* GPG
  computes validity for other keys signed by them — it is never published.

See :doc:`trust_and_signing` for how this looks in PBNightingale.

Keyservers: publishing and finding public keys
--------------------------------------------------

Since a public key is meant to be shared as widely as possible, GPG users
routinely publish theirs to public **keyservers** — a loose network of
servers that store and distribute public keys, searchable by fingerprint,
key ID, or email address. Publishing your key there makes it easy for
someone who has never met you to find it (though, per the trust model
above, finding a key is not the same as knowing it is genuinely yours).
See :doc:`importing_keys`.

Why bother: concrete, everyday benefits
-------------------------------------------

Put together, this gives you tools that plain email and file sharing do
not:

- **Confidential email and attachments.** A message or an attached file
  encrypted to your recipient's public key is unreadable to their email
  provider, to anyone who breaches a mail server along the way, and to
  anyone who intercepts your network traffic — only the intended reader
  can open it.
- **Verified senders.** A signed message lets the recipient confirm it
  genuinely came from you, not from someone spoofing your address —
  a common phishing technique that a valid signature defeats outright.
- **Tamper detection.** A signature breaks the moment even one character
  of the signed content changes after the fact, so a recipient knows
  immediately if a message was altered in transit.
- **Verifying software downloads.** Many open-source projects sign their
  release files; checking that signature against the project's published
  key confirms you downloaded exactly what the maintainers published, not
  a tampered copy from a compromised mirror.

PBNightingale itself only manages the keys — creating them, adding
identities, signing others', publishing and fetching from keyservers, and
so on. Actually sending encrypted or signed mail happens in your email
client, configured to use the keys you manage here; see
:doc:`email_clients` for how the two fit together.
