# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-16

This program is an evolution (heavily improved) of an older Python
program, itself an evolution of an ancient (~2014) Perl program.

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
- GitHub Actions CI: tests, pre-commit hooks, documentation build, per-OS
  PyInstaller builds, and GitHub Releases cut from this changelog on
  semver tags
- Help menu entry opening the online user manual in the interface's
  current language
- Keyboard shortcuts for standard actions (new, import, export, back up,
  delete, settings, help, quit) and a refresh family (F5 for keys,
  Shift+F5 for trust, Ctrl+F5 for keyservers)
