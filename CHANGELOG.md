# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Personal key generation (RSA or ED25519) with a passphrase strength meter
- Subkey management: add, revoke, export, back up, delete
- Editable identities: text and photo user IDs
- Expiration date management for keys and subkeys
- Passphrase changes, with in-memory caching and show/hide fields
- Key signing, owner trust, and trust refresh, including a signatures view
- Key import from a file or a keyserver, with a review step before merging
- Keyserver search, publish, and refresh
- French and English interface, with a preferences dialog
- Packaging (PyInstaller) and Sphinx user documentation
