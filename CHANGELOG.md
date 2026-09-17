# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Sortable main key list: clicking a column header (Name, Email, Key ID,
  Expires) sorts the keys inside each group, clicking it again reverses the
  order. The "My keys" and "Other keys" groups themselves keep their fixed
  order, and keys that never expire always sort last in the Expires column.
  The list is sorted by name ascending on first launch, and the chosen sort
  column and direction are remembered across sessions
- Numpydoc docstring convention adopted project-wide (`core/`, `platform/`,
  top-level modules, and every `ui/*.py` except `*_ui.py` layout files),
  documented in CODING.md
- `pydocstyle` (ruff `D`, `numpy` convention) enforced in lint, scoped to
  match the documented docstring convention

### Fixed

- Sphinx docs: `napoleon_numpy_docstring` was disabled, so numpydoc
  sections in docstrings were never actually parsed or rendered
- CI: bumped `codecov-action` to v7 to pick up its own Node 24 runtime
  (it was pinned to a deprecated Node 20 build via `actions/github-script`)

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
