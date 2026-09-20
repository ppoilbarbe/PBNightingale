# PBNightingale

[![Release](https://img.shields.io/github/v/release/ppoilbarbe/PBNightingale)](https://github.com/ppoilbarbe/PBNightingale/releases/latest)
[![CI](https://github.com/ppoilbarbe/PBNightingale/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ppoilbarbe/PBNightingale/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/ppoilbarbe/PBNightingale/branch/main/graph/badge.svg)](https://codecov.io/gh/ppoilbarbe/PBNightingale)
[![PyPI](https://img.shields.io/pypi/v/pbnightingale)](https://pypi.org/project/pbnightingale/)
[![Documentation Status](https://readthedocs.org/projects/pbnightingale/badge/?version=latest)](https://pbnightingale.readthedocs.io/en/latest/?badge=latest)

A cross-platform graphical GPG key management utility built with Qt 6 (PySide6).

## Why

People migrating to Linux tend to shy away from encryption keys because the
tooling — GPG's command line in particular — is too intimidating. PBNightingale
makes everyday GPG key management approachable on Linux, Windows and macOS,
without hiding what it does.

This program is a legacy (heavily improved) from an older Python
program, itself an evolution of an ancient (~2014) Perl program.

## Features

- **Personal keys**: generate an RSA or ED25519 key pair, with a live
  passphrase strength meter
- **Subkeys**: add signing/encryption/authentication subkeys, revoke one
  (strong confirmation), export a key's public part, back up its private
  material, or delete a key from your keyring
- **Identities**: add, set primary, and revoke text user IDs (name, email,
  comment) and photo user IDs
- **Expiration**: set or clear an expiration date on the primary key or on
  an individual subkey
- **Passphrases**: change a key's passphrase; every passphrase field has a
  show/hide toggle and a configurable in-memory cache, with a per-key lock
  indicator in the key list
- **Trust & signing**: sign other people's keys and set owner trust to
  build the web of trust, see who has already signed a given key, and
  fetch signer keys you don't have yet
- **Import & keyservers**: import keys from a file or a keyserver (by
  fingerprint, key ID, or email address) with a review step before
  anything is merged into your keyring, plus search, publish, and refresh
  against a keyserver
- **Interface**: French and English, with a preferences dialog for
  language, preferred key algorithm, toolbar icon size, and passphrase
  cache duration

## Quick start

```bash
make venv   # create the pixi environment
make run    # launch PBNightingale
```

New to GPG, or to PBNightingale? The user manual walks through every
feature above, starting with the underlying GPG concepts. Read it online
at [pbnightingale.readthedocs.io](https://pbnightingale.readthedocs.io/en/latest/)
(also available in French), or locally under
[`docs/manual/`](docs/manual/) (`make docs` builds it as HTML; the `.rst`
sources are also readable as plain text).

See [CODING.md](CODING.md) for the full developer setup and workflow.

## About the name

"Nightingale" translates to French as *rossignol* — the bird. In French
slang, though, *rossignol* also means a lock pick (a skeleton key). Hence
the name, for a program that manages keys.

## Author

Marcel Spock <mrspock@cardolan.net>
PBMou

PBMou is a cross-language pun: "PB" stands for "Poilbarbe", and "Mou" is the
French translation of "Soft" — so PBMou reads like "PBSoft" half-translated
into French.

## License

Code: GPL-3.0-only — see [LICENSE](LICENSE).

Icons (`src/pbnightingale/resources/*.svg`, `*.png`, `*.ico`, `*.icns`),
sourced from the [PBIcons](https://github.com/ppoilbarbe/PBIcons) asset
repository: CC BY-NC-SA 4.0 — see [LICENSE-ICONS](LICENSE-ICONS).

Documentation (`docs/`, published on Read the Docs): CC BY-NC-SA 4.0 —
see [LICENSE-DOCS](LICENSE-DOCS).
