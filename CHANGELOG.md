# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-22

### Added

- Preferences → "Key Servers": a configurable, ordered keyserver list,
  each entry independently checkable, with Add/Remove/Move Up/Move Down
  and "Restore Default List"; the list can never be emptied, and at
  least one server must stay checked to accept the dialog
- Import Key dialog: the "from keyserver" tab is now first and no longer
  takes a keyserver field — it queries every checked keyserver and merges
  whatever each finds
- Search Keyserver dialog: the keyserver is now picked from a combobox
  listing every configured server (checked or not), instead of free text
- Publish Key dialog: a picker listing every configured keyserver as a
  checkbox list, replacing the old single-server confirmation prompt;
  publishing fans out to every checked server
- Keyserver Refresh and "Download Unknown Keys" now query every checked
  keyserver and merge the results, instead of relying on a single
  hardcoded default
- View → "Activity (advanced)…" (also F12): a non-modal window listing
  the most recent external commands PBNightingale has run (`gpg`,
  `gpg-connect-agent`, …), each numbered sequentially. Select a row and
  press Ctrl+C to copy its command; "Clear History" empties the list
  without resetting the numbering. How many commands are kept is
  configurable in Preferences → "Activity history" (default 50)

### Changed

- `GPGBackend.list_keys()` accepts an optional fingerprint filter;
  `refresh_from_keyserver()` uses it, so refreshing one key no longer
  recomputes the primary-UID lookup for every other multi-UID key in the
  keyring
- Every command run through python-gnupg's own API (`list_keys()`,
  `search_keys()`, `recv_keys()`, `send_keys()`, `gen_key()`,
  `import_keys_file()`, `export_keys()`, …), not just PBNightingale's own
  direct subprocess calls, is now traced into the Activity log — a
  keyserver search, for instance, used to be entirely invisible there
- About dialog: the "Author:"/"License:" field labels are now bold

### Fixed

- The Search Keyserver dialog's hint text about keys.openpgp.org was
  corrected: it does support searching by exact email address,
  fingerprint or key ID, and shows identities the key owner has verified
  there

### Removed

- The single hardcoded default keyserver constant — every keyserver
  operation now sources its server list from Preferences

## [0.2.2] - 2026-09-20

### Added

- Makefile targets to build and publish the project to PyPI: `pypi-build`,
  `publish-pypi`, `verify-pypi`, `publish-testpypi`, `verify-testpypi`
- Github/Codecov/Readthedocs badges in the README

## [0.2.1] - 2026-09-20

### Added

- `-d`/`--debug` and `-q`/`--quiet` CLI flags: `--debug` enables debug-level
  logging, including a trace of every operation launched through an
  external program (`gpg`, `gpg-connect-agent`, …); `--quiet` restricts
  logging to warnings and errors
- `--print-completion {bash,zsh,tcsh,fish,powershell}` (via `shtab`), in
  the "tools" option group, to generate a shell completion script

### Changed

- A short program history note added to the README and the user manual

### Fixed

- gpg's purely informational `[GNUPG:] KEYEXPIRED <timestamp>` status
  lines no longer appear in diagnostic/error messages

### Security

- Passphrases are now carried through the application as a dedicated
  `Passphrase` wrapper (`core/secret.py`) instead of a bare string:
  `str()`/`repr()` on it always show a fixed placeholder, so an enhanced
  traceback tool or debugger dumping a stack frame's local variables can
  no longer expose a passphrase in the clear
- Debug-mode tracing of external `gpg` invocations redacts every
  passphrase from the logged command input; the real value sent to gpg is
  unaffected

## [0.2.0] - 2026-09-17

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
