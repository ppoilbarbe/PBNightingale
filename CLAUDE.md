# Mode
`full-en` — code and all communication in English.

# Project: PBNightingale
GUI GPG key manager (Linux/Windows/macOS). Python 3.14+, PySide6 (Qt6), src layout.
Publisher: PBMou | Author: Marcel Spock <mrspock@cardolan.net>
License: GPLv3 (code); icons under `resources/` (sourced from PBIcons) are
CC BY-NC-SA 4.0 instead — see LICENSE-ICONS

## Current state

Published to GitHub (`origin` → `git@github.com:ppoilbarbe/PBNightingale.git`,
`main` tracks `origin/main`). `.github/workflows/ci.yml` runs tests, hooks,
docs build and per-OS PyInstaller builds on every push/PR, and cuts a
GitHub release from `CHANGELOG.md` on semver tags. **Still never push without an explicit request from the user**
(see global CLAUDE.md). `make ci` (lint → hooks → test) remains the local
gate to run before pushing.

Implementation proceeds milestone by milestone; each milestone is validated
(`make ci` green + manual check) before the next one starts.

## Stack

- GUI: PySide6; UI layouts hand-written (`*_ui.py`), no Qt Designer
- GPG backend: `python-gnupg` wrapping the system `gpg` binary (portable;
  avoids compiling GPGME bindings on Windows/macOS)
- Password strength: `zxcvbn` (conda-forge), thresholds/tiers ported from
  KeePassXC's `PasswordHealth` — see CODING.md, "Password strength"
- Tests: pytest + pytest-qt (`qtbot`; never instantiate `QApplication`
  manually) — GPG tests run against an isolated temporary `GNUPGHOME`, never
  the user's real keyring
- Lint: ruff (line-length 88, target py314), default rule set + `I`/`PGH`/
  `UP`/`BLE`/`S`/`D` (no explicit `select` — see pyproject.toml comment);
  `D` uses the `numpy` pydocstyle convention, matching this project's
  numpydoc docstrings (see CODING.md, "Coding conventions")
- Env: pixi (conda-forge channel only) — `make venv`
- CI/CD: GitHub Actions (`.github/workflows/ci.yml`) + `make ci` locally
  before pushing
- i18n: French + English only, pybabel/gettext (see `i18n.py`)
- Auto-update: GitHub-releases self-update, `--auto-update` CLI flag —
  only meaningful (and only registered) in a PyInstaller-frozen executable
  (milestone 15); inert everywhere else

## Layout

```text
src/pbnightingale/
├── __init__.py           version, author metadata; builtins._ no-op fallback
├── __main__.py           entry point; --auto-update dispatch (frozen only)
├── i18n.py               gettext bootstrap (setup(app), language override)
├── settings.py           config-dir root (configure() override for tests)
├── preferences.py        general app preferences (preferred key algorithm, …)
├── locale/               en/fr catalogues (.po committed, .mo gitignored)
├── core/
│   ├── gpg_backend.py    GPGBackend (python-gnupg wrapper) + Key/Subkey model;
│   │                     configure()/default_backend() override for tests
│   ├── secret.py         Passphrase — frozen wrapper hiding a passphrase from
│   │                     str()/repr() (e.g. in a traceback's local-var dump)
│   ├── passphrase_cache.py  in-memory {fingerprint: Passphrase} cache, TTL-based
│   └── password_strength.py  zxcvbn-based entropy/quality for a new passphrase
├── platform/
│   ├── dirs.py           AppDirs factory: XdgDirs / _MacDirs / _WindowsDirs
│   ├── locale.py         system_language()
│   └── auto_update.py    perform_auto_update() — GitHub release self-update
├── resources/            bundled SVG/PNG icons (resources.path(name))
└── ui/
    ├── main_window.py    main window: loads keys, signals
    ├── main_window_ui.py main window layout: actions, toolbars (one per theme), menus
    ├── key_list_view(_ui).py   central widget: key list + detail panel
    ├── new_key_wizard(_ui).py  personal key creation wizard
    ├── password_strength_meter(_ui).py  colored entropy bar for a new passphrase
    ├── add_subkey_dialog(_ui).py     Add Subkey dialog
    ├── revoke_subkey_dialog(_ui).py  Revoke Subkey dialog (strong confirmation)
    ├── change_passphrase_dialog(_ui).py  Change Passphrase dialog
    ├── add_uid_dialog(_ui).py        Add User ID dialog
    ├── set_primary_uid_dialog(_ui).py  Set Primary User ID dialog
    ├── revoke_uid_dialog(_ui).py     Revoke User ID dialog (strong confirmation)
    ├── add_photo_dialog(_ui).py      Add Photo dialog
    ├── revoke_photo_dialog(_ui).py   Revoke Photo dialog (strong confirmation)
    ├── set_expiration_dialog(_ui).py  Set Expiration dialog (key or subkey)
    ├── sign_key_dialog(_ui).py       Sign Key dialog
    ├── set_owner_trust_dialog(_ui).py  Set Owner Trust dialog
    ├── about_dialog(_ui).py
    ├── settings_dialog(_ui).py  language selector
    ├── gpg_worker.py     run_async() — QThreadPool bridge for GPGBackend calls
    ├── window_state.py   persisted window geometry / splitter sizes (QSettings)
    └── geometry_mixin.py GeometryMixin — wires window_state into a window
```

`tools/update_icons.py` syncs `resources/` icons from the shared PBIcons
asset repo (local checkout sibling, else GitHub) — see CODING.md.

## Key conventions

- All OS-specific code goes in `src/pbnightingale/platform/`.
- Never test against the real user's GPG keyring — always an isolated
  `GNUPGHOME`. Enforced automatically:
  `gpg_backend.configure()`/`default_backend()` mirror
  `settings.configure()` exactly, and `tests/conftest.py`'s autouse
  `_isolated_gnupghome`/`_isolated_config` fixtures redirect both to a tmp
  dir for every test — never the real user's keyring or config directory.
- After any user-visible string change: `make translate`, fill every new
  `msgstr ""` in both `en` and `fr` `.po` files, `make translate` again to
  compile. Verify with `python tools/po_check.py --empty` — never grep/msgfmt
  directly on `.po` files (they can have multi-line entries). Run
  `po_check.py --empty` even when a milestone feels string-free — milestones
  6 and 7 both merged without it and left 65 strings untranslated in both
  languages until milestone 8 caught it.
- Every top-level window/dialog persists its geometry (and splitter sizes)
  via `ui/geometry_mixin.py::GeometryMixin` (`self._init_geometry(key,
  splitters={...})` after `setupUi()`) — apply it to new windows too, except
  small fixed-purpose dialogs like `AboutDialog`.
- ED25519 key generation cannot fold `encrypt` usage into the primary key
  (gpg rejects it outright — EdDSA is signature-only); `NewKeyRequest`/
  `add_subkey()` always add a dedicated Curve25519 subkey for encryption
  under ED25519, and the wizard/Add Subkey dialog force-check-and-disable
  that checkbox accordingly. Don't "simplify" this away — RSA's "fold into
  primary" behavior genuinely doesn't generalize to ED25519.
- Subkey revocation has no python-gnupg wrapper — `GPGBackend.
  revoke_subkey()` drives `gpg --edit-key` directly via `--command-fd`/
  `--status-fd` scripting. The passphrase line in that script must be
  positioned exactly where gpg's `GET_HIDDEN passphrase.enter` status
  appears (right after confirming the revocation reason) — anywhere else in
  the sequence gets silently consumed as a bogus `keyedit.prompt` command
  instead. See CODING.md — "Subkey management".
- `self._gpg.gnupghome` is `None` in production (no `configure()`
  override) — never assume it's a usable path. Anything that shells out
  directly (`_restart_agent()`, `revoke_subkey()`) must go through
  `GPGBackend._homedir_args()` rather than building a `--homedir` arg by
  hand; a bare `self._gpg.gnupghome` in a `subprocess.run()` arg list
  crashes with `TypeError: ... not NoneType` in production, since every
  test's `GPGBackend` has a real temp-dir `gnupghome` and never exercises
  the `None` case — this class of bug won't show up in `make ci`.
- `GPGBackend.change_passphrase()` drives gpg's dedicated
  `--change-passphrase` command (never `--edit-key`'s `passwd`
  sub-command): unlike `passwd`, a wrong old passphrase there gets a
  proper machine-readable `[GNUPG:] ERROR keyedit.passwd <code>` status
  line — but only when a wrong passphrase gets exactly the right number of
  retries: gpg retries the old-passphrase prompt once per secret-key part
  (primary + each subkey), and a wrong one can't be told apart from a
  correct one until each retry has played out, so the script sent is
  `old`, `new`, then `old` again `_MAX_SECRET_KEY_PARTS` (64) more times as
  filler. A real 4-subkey-part key with too few retries queued ran the
  script dry mid-sequence, downgrading the failure to gpg's generic
  "operation canceled" code (99, not 11) and dumping its whole raw
  multi-attempt diagnostic text into the dialog instead of a clean
  message — reported against real usage; see CODING.md. A *correct*
  passphrase only ever needs the first two lines (`old`, `new`) — no
  repeat-to-confirm step in the protocol itself, that's the UI's own job
  (`ChangePassphraseDialog`'s `txtNewPassphrase`/`txtNewPassphraseConfirm`).
  Always clears gpg-agent's passphrase cache first via `gpg-connect-agent
  RELOADAGENT` (never `_restart_agent()`'s `gpgconf --kill`, which is async
  and races the next call) — otherwise an already-cached key silently
  skips the old-passphrase check and misapplies its value as the new
  passphrase instead. Only works on a key that already has a real
  passphrase — an
  unprotected key given `old_passphrase=""` reports success but stays
  unprotected (`--edit-key passwd` handles that transition correctly, but
  loses the machine-readable error code). See CODING.md — "Changing a
  key's passphrase".
- Detect a wrong GPG passphrase by the numeric code on gpg's `[GNUPG:]
  ERROR <location> <code>` status line (`& 0xFFFF == 11`, libgpg-error's
  `GPG_ERR_BAD_PASSPHRASE`) — never by matching gpg's own human-readable
  text ("Mauvaise phrase secrète"/"Bad Passphrase"/…), which is localized
  to the system's own language and has nothing to do with this app's own
  `en`/`fr` catalogues. See `GPGBackendError`/`BadPassphraseError` in
  `core/gpg_backend.py`.
- There is no reliable "primary UID" signal in gpg's plain `--list-keys`
  output — verified empirically, don't re-derive it: UID listing order
  looks tempting but isn't a stable stand-in (a clean test with UIDs added
  in order A, B, C came back as `C, A, B`, not creation or timestamp
  order). The real primary flag only shows up in `gpg --edit-key`'s own
  `--with-colons` listing, at the cost of one extra `gpg` subprocess per
  key — not worth paying for a cosmetic label, so `Uid` has no `primary`
  field. See CODING.md — "Editable user IDs".
- python-gnupg's `list_keys()` silently drops photo user IDs ("uat" colon
  records) — its own record-type allowlist doesn't include them (verified
  against its source, not just observed). `GPGBackend._load_photos()`
  works around this with a separate raw `--attribute-file` listing.
  `addphoto` (scripted via `--edit-key`, like subkey revocation) needs
  `--no-tty` or it fails outright in any headless/GUI-launched process,
  and its passphrase line goes right after the file path, *before*
  `save` — unlike every other scripted `--edit-key` flow in this app,
  where the passphrase goes last. See CODING.md — "Photo user IDs".
- `Key.trust` (validity — is the UID/key binding genuine) and
  `Key.owner_trust` (how much you personally trust this owner to certify
  *others*) are different gpg concepts that happen to share colon-format
  letter codes — never conflate them. gpg auto-assigns "ultimate"
  ownertrust to any key you hold the secret part of unless explicitly
  overridden, which masks signing's effect on validity in tests unless you
  override it first. `--min-cert-level` (default 2) disregards level-1
  signatures for validity, but level 0 is always accepted — a signing
  dialog defaulting to cert level 0 is a real default, not a placebo. See
  CODING.md — "Key signing & web of trust".
- Every passphrase in this codebase is a `core/secret.py::Passphrase`
  (frozen dataclass), never a bare `str` — `GPGBackend` method parameters,
  `NewKeyRequest.passphrase`, `passphrase_cache`'s stored values, what a
  dialog reads off `txtPassphrase`. `str()`/`repr()` on it always print
  `"**********"`, closing off a leak a bare `str` local doesn't: an
  enhanced traceback tool or debugger dumping a frame's locals on an
  unhandled exception would otherwise print the real value at every stack
  frame it passed through. `bool(passphrase)`/`==` work on the wrapper
  directly — only unwrap via `.passphrase` at the one point gpg's own
  protocol needs the raw text (a `--command-fd` script, an `input=`
  payload, a python-gnupg kwarg, or the widget echoing it back). Don't
  interpolate a `Passphrase` into an f-string unwrapped — with no
  `__format__` override it falls back to `str()` and sends the literal
  `"**********"` to gpg instead of the real passphrase, a real protocol
  bug, not just a leak. See CODING.md — "GPG backend".
- New external-program calls in `core/gpg_backend.py` must go through
  `_traced_run()`/`_traced_popen()`, never a bare `subprocess.run()`/
  `Popen()` — that's what makes `-d`/`--debug` trace every gpg invocation,
  and it's also where `_clean_stderr()` strips gpg's purely-informational
  `[GNUPG:] KEYEXPIRED …` status lines from `result.stderr` before
  anything (an exception message, a retry check) ever sees them. A
  passphrase fed via `input=`/a script must be listed in `secrets=` so the
  debug trace redacts it — the real value sent to gpg is never affected,
  only what gets logged.
