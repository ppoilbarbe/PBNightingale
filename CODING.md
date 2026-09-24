# Developer Guide

This document covers everything you need to contribute to PBNightingale.
For user-facing information see [README.md](README.md).

## Tech stack

| Layer       | Technology                                            |
| ----------- | ----------------------------------------------------- |
| Language    | Python 3.14+                                          |
| GUI         | PySide6 (Qt 6 official Python binding)                |
| UI design   | Hand-written `*_ui.py` (no Qt Designer)               |
| GPG backend | `python-gnupg` wrapping the system `gpg` binary       |
| i18n        | pybabel/gettext — French + English only               |
| Tests       | pytest + pytest-qt                                    |
| Linter      | ruff (line-length 88, target py314)                   |
| Package mgr | pixi — **conda-forge only**                           |
| Build       | Hatchling (`pyproject.toml` + `hatch_build.py`)       |
| CI/CD       | Local only for now (`make ci`) — no GitHub remote yet |

## Project layout

```text
PBNightingale/
├── src/pbnightingale/
│   ├── __init__.py              version / author metadata; builtins._ fallback
│   ├── __main__.py              entry point — `python -m pbnightingale`
│   ├── i18n.py                  gettext bootstrap; language from platform.locale
│   ├── settings.py               config-dir root; configure() override for tests
│   ├── preferences.py            general app preferences (preferred key algorithm, …)
│   ├── locale/                  en/fr catalogues (.po committed, .mo gitignored)
│   ├── core/
│   │   ├── gpg_backend.py       GPGBackend — python-gnupg wrapper, Key/Subkey model,
│   │   │                        configure()/default_backend() override for tests
│   │   └── password_strength.py  zxcvbn-based entropy/quality estimate for a new passphrase
│   ├── platform/
│   │   ├── dirs.py              AppDirs factory: XdgDirs / _MacDirs / _WindowsDirs
│   │   ├── locale.py            system_language()
│   │   └── auto_update.py       perform_auto_update() — GitHub release self-update
│   ├── resources/                bundled SVG/PNG icons; resources.path(name) resolves them
│   └── ui/
│       ├── main_window.py       main window — loads keys, signal wiring
│       ├── main_window_ui.py    main window layout — actions, toolbars, menus
│       ├── key_list_view.py / _ui.py      central widget: key list + detail panel
│       ├── new_key_wizard.py / _ui.py     personal key creation wizard
│       ├── password_strength_meter.py / _ui.py  colored entropy bar for a new passphrase
│       ├── add_subkey_dialog.py / _ui.py  Add Subkey dialog
│       ├── revoke_subkey_dialog.py / _ui.py  Revoke Subkey dialog (strong confirmation)
│       ├── add_uid_dialog.py / _ui.py     Add User ID dialog
│       ├── set_primary_uid_dialog.py / _ui.py  Set Primary User ID dialog
│       ├── revoke_uid_dialog.py / _ui.py  Revoke User ID dialog (strong confirmation)
│       ├── add_photo_dialog.py / _ui.py   Add Photo dialog
│       ├── revoke_photo_dialog.py / _ui.py  Revoke Photo dialog (strong confirmation)
│       ├── set_expiration_dialog.py / _ui.py  Set Expiration dialog (key or subkey)
│       ├── sign_key_dialog.py / _ui.py    Sign Key dialog
│       ├── set_owner_trust_dialog.py / _ui.py  Set Owner Trust dialog
│       ├── about_dialog.py / _ui.py       About dialog
│       ├── settings_dialog.py / _ui.py    Settings dialog (interface language)
│       ├── gpg_worker.py        QThreadPool bridge for GPGBackend calls (run_async)
│       ├── window_state.py      persisted window geometry / splitter sizes (QSettings)
│       └── geometry_mixin.py    GeometryMixin — wires window_state into a window
├── tests/
├── tools/
│   ├── po_check.py              inspect .po files — use instead of grep/msgfmt
│   └── fix_po_files.py          normalise .po files after `pybabel update`/`sphinx-intl update`
├── babel.cfg                    pybabel extraction config
├── hatch_build.py                build hook: compiles .po → .mo into the wheel
├── pyproject.toml                project metadata + [tool.pixi.*] env/deps
└── Makefile                      dev tasks (see `make help`)
```

## Setup

```bash
make venv      # create the pixi environment (installs pixi if missing)
make install   # register pre-commit hooks (editable install already done by `make venv`)
```

### Running without pixi

Every target accepts `NOCONDA=1` to bypass the pixi wrapper and use whatever
`python`/`pytest`/`ruff` are already on `PATH` (e.g. `make test NOCONDA=1`).

## Daily workflow

```bash
make run       # launch the app
make test      # run the test suite
make lint      # ruff check + format --check
make format    # ruff format + ruff check --fix
make hooks     # run all pre-commit hooks on all files
make ci        # local CI gate: lint → hooks → test
```

`make run` and `make test` both depend on `compile-translations` (`pybabel
compile` from the committed `.po` files), so a fresh checkout always has
working catalogues without an extra manual step.

Run `make ci` before considering any change done — there is no GitHub
Actions workflow yet (see CLAUDE.md), so this is the only test gate.

### Quality gates enforced by `make ci`

- **Lint** (`ruff check`): ruff's own default rule set, extended with
  `I`/`PGH`/`UP`/`BLE`/`S`. `S` (flake8-bandit) matters here: this app shells
  out to `gpg` and handles key material, so subprocess/temp-file/secret-
  handling anti-patterns are checked from day one. `tests/*` is exempted
  from `S101` (assert) and `S103` (permissive file mode — tests set standard
  executable bits like `0o755` on fixture files on purpose).
- **Pinned pre-commit ruff version**: `.pre-commit-config.yaml` pins the
  `ruff-pre-commit` rev to match the `ruff` conda-forge package resolved by
  `make venv`, so `make hooks` and `make lint` never disagree on findings —
  bump both together when upgrading ruff.
- **Coverage floor**: `pytest --cov-fail-under=90` — a change that drops
  test coverage below 90% fails `make ci`. GUI entry points that pytest
  cannot reasonably exercise (`_gui_main`, `if __name__ == "__main__":`) are
  marked `# pragma: no cover` rather than counted against the floor.
- **pre-commit hooks**: generic hygiene + `ruff format` + `markdownlint-cli2`.

## Internationalisation

Two languages only, for now: French (`fr`) and English (`en`). Catalogues:
`src/pbnightingale/locale/{en,fr}/LC_MESSAGES/pbnightingale.{po,mo}` — the
`.po` are committed, the `.mo` are gitignored build artifacts.

Python strings: wrap with `_("…")`. `_()` is installed into `builtins` at
runtime by `i18n.setup(app)` (called once in `__main__._gui_main()`, before
any window is created); `pbnightingale/__init__.py` installs a no-op
identity fallback so `_()` is always defined even in code that imports a
module without going through `setup()` (e.g. most unit tests). ruff is told
about it too (`builtins = ["_"]` under `[tool.ruff]`), so `_()` never trips
`F821` in `ui/*.py` — deliberately not a per-file `noqa`/ignore, which would
also hide genuine undefined-name bugs in those files.

**After any user-visible string change:**

1. `make translate` — updates `.pot`, merges `.po`, compiles `.mo`
2. Fill every new `msgstr ""` in `en` and `fr` `.po` files (keyboard
   shortcuts, once there are any, stay empty)
3. `make translate` again to compile the filled entries
4. Verify: `python tools/po_check.py --empty` — nothing should remain
   untranslated

New language: `make new-lang LOCALE=de`, translate every `msgstr` (including
`language_name`, used by `i18n.available_languages()`), then `make translate`
— but see "Two languages only" above before actually adding one.

Language selection: `i18n.setup(app)` uses the persisted override
(`i18n.get_language_override()`/`set_language_override()`, stored via
`settings.py`) when set, else `platform.locale.system_language()`. Changed
from Edit → Settings… (`ui/settings_dialog.py`); takes effect on next
restart.

## GPG backend

`core/gpg_backend.py::GPGBackend` wraps `python-gnupg` (which itself shells
out to the system `gpg` binary) and exposes a `list_keys(*, secret=False)`
method returning a `Key`/`Subkey` dataclass model — never raw python-gnupg
dicts — so the UI never has to know gpg's field-name quirks. A public `Key`
entry carries `has_secret=True` when a matching secret key is also present
(cross-referenced against the secret keyring), so the UI can tell "your
keys" apart from keys you only hold the public part of. `GPGBackendError`
wraps every `python-gnupg` failure (bad `gnupghome`, missing/broken `gpg`
binary) into one exception type. `GPGBackendError.__init__` also strips
gpg's own `[GNUPG:] KEYEXPIRED <timestamp>` status lines from any message
it's given (`_strip_gnupg_noise()`) — purely informational, but it shows
up interleaved with genuine diagnostics often enough (see
`refresh_from_keyserver()` below) to be worth filtering everywhere a
message might end up shown, not just that one call site. The actual
filtering happens even earlier, right where gpg's stderr is captured
(`_traced_run()`, `_run_with_agent_retry()`, and every python-gnupg call
whose result exposes `.stderr` go through `_clean_stderr()` first) so the
exception-level strip is really just a last line of defense.

`_traced_run()`/`_traced_popen()` also feed `core/activity_log.py`'s
in-memory command history unconditionally, not just their existing
`_log.debug()` trace, which only fires under `-d`/`--debug`. See
"Activity (advanced) window" below.

**`core/secret.py::Passphrase`**: every passphrase in this codebase — a
`GPGBackend` method parameter, `NewKeyRequest.passphrase`, what
`core/passphrase_cache.py` stores, what a dialog reads off its
`txtPassphrase` field — is one of these, a frozen dataclass wrapping the
real string, never a bare `str`. `str()`/`repr()` on it always print
`"**********"`, never the real value, closing off a leak that a bare
`str` local variable doesn't: an enhanced traceback tool (or a debugger
breaking on an unhandled exception) that dumps a frame's locals would
otherwise print the passphrase in the clear at every stack frame it
passed through, not just the one that failed. `bool(passphrase)` and `==`
work directly on the wrapper exactly like they would on the underlying
string (`__bool__`/the dataclass-generated `__eq__` compare the wrapped
value), so an emptiness check or a cache-hit comparison never needs to
unwrap one. The one place that must — `.passphrase`, the property named
after the class itself so a call site reads as unwrapping the concept,
not grabbing a random attribute — is right where gpg's own protocol
genuinely needs the raw text: building a `--command-fd` script or
`input=` payload, a python-gnupg keyword argument, or filling the widget
that echoes it back to the user. Interpolating a `Passphrase` into an
f-string *without* unwrapping it first is a real bug, not just a style
nit: with no `__format__` override, `f"{passphrase}"` falls back to
`str()` and sends the literal text `"**********"` to gpg instead of the
actual passphrase — every script-building call site in `GPGBackend`
unwraps explicitly for exactly this reason.

`gpg`'s own `cap` field on a "pub" listing is a **whole-key aggregate**: it
reports a capability as usable if *any* subkey provides it, not just the
primary key itself — e.g. `Key.can_encrypt` is `True` for a primary key
whose own usage is cert+sign only, as long as one of its subkeys can
encrypt. `Subkey.can_*` flags are per-subkey and don't have this quirk.
`Subkey.trust` carries the raw single-letter gpg trust code (`"r"` for a
revoked subkey, etc.) — same code space as `Key.trust`, decoded by
`ui/key_list_view.py::_trust_label()`.

Two algorithm families are supported, chosen via `NewKeyRequest.algorithm`/
`GPGBackend.add_subkey(algorithm=)`: `"RSA"` (`Key-Length` in bits) and
`"ED25519"` (EdDSA for the primary key and any sign/auth subkey, Curve25519/
ECDH for any encrypt subkey — gpg rejects an EdDSA key with `encrypt` in its
`Key-Usage`, so unlike RSA, ED25519 encryption can never be folded into the
primary key). `core/gpg_backend.py::_algo_spec()` centralizes this mapping
for `generate_key()`; `add_subkey()` has the equivalent inline (it only ever
adds one subkey, so a curve is picked straight from *usage*).

The `gnupg` conda-forge package (the `gpg` binary itself) has no win-64
build, so it's a `[tool.pixi.target.<platform>.dependencies]` entry for
Linux/macOS only — Windows relies on a system-wide GnuPG install (e.g.
Gpg4win), same as most GPG-aware desktop apps on that OS. `python-gnupg`
(the Python binding) is noarch and works everywhere.

**Async execution**: `core/` stays framework-agnostic (no PySide6 imports —
see "Coding conventions" below), so `GPGBackend` methods are plain
synchronous calls. `ui/gpg_worker.py::run_async(pool, fn, *args,
on_success=, on_error=, **kwargs)` is the Qt-side bridge: it runs `fn` on a
`QThreadPool` and delivers the result (or exception) back via a queued
signal, so slots connected to it run on the thread that owns them —
normally the GUI thread. A worker is kept in a module-level set until it
finishes; without that, a `GPGWorker` with no other Python reference (the
common call shape, `run_async(pool, fn, on_success=...)` with the return
value discarded) can be garbage-collected the instant `run()` returns,
silently dropping its still-queued signal before the GUI thread delivers it.

Test convention: `tests/test_gpg_backend.py` always constructs `GPGBackend`
with a `tmp_path` `gnupghome` — real (but tiny, ~0.1s) RSA-1024 keys are
generated directly via `gnupg.GPG` (bypassing `GPGBackend`, since key
generation is `generate_key()`'s own concern, see "Personal key creation
wizard" below) as fixture data for the listing/parsing this module covers.
Never the real user's `~/.gnupg` (see CLAUDE.md).
`tests/gpg_test_helpers.py::generate_test_key()` is the shared version of
that helper, used by every test that needs real fixture key material.

`core/gpg_backend.py::configure(gnupghome)`/`default_backend()` mirror
`settings.py`'s `configure()` override exactly: `MainWindow` always goes
through `default_backend()` rather than constructing `GPGBackend()`
directly, so `tests/conftest.py`'s autouse `_isolated_gnupghome` fixture
(backed by the `gnupg_home` fixture, parallel to `config_dir`) can redirect
every test to a temp keyring — the same GNUPGHOME-isolation guarantee as
`test_gpg_backend.py`, but for anything that builds a `MainWindow`.

**Stale gpg-agent recovery**: on a real desktop, a `gpg-agent` from a
different, older GnuPG install (e.g. the distro-packaged one) may already
be running and listening on the same `GNUPGHOME` socket by the time this
app's own (newer, conda-forge) `gpg` tries to use it. gpg then emits a
`[GNUPG:] WARNING server_version_mismatch` status line — usually harmless
on its own (confirmed against real usage: it turned out to be a red
herring in one report, where the actual failure was simply a wrong
passphrase — see "Bad passphrase" below), but defensively worth
recovering from in case some operation genuinely can't complete against a
too-old agent. `generate_key()`, `add_subkey()` and `revoke_subkey()`
detect this marker in `stderr` and, on it, `GPGBackend._restart_agent()`
(`gpgconf --kill gpg-agent`) retries the same operation once — the next
`gpg` call needing the agent autostarts a fresh one matching this install,
per gpg's own suggested remedy. Any other failure is raised immediately,
no retry.

`self._gpg.gnupghome` (python-gnupg's own attribute) is `None` in
production whenever `default_backend()` has no `configure()` override —
i.e. always, outside tests: `gpg` is told to use its own platform default
homedir, and python-gnupg never resolves that to an actual path.
`_restart_agent()` and `revoke_subkey()` both shell out directly and must
build their own `--homedir` argument, so both go through
`GPGBackend._homedir_args()`, which omits the flag entirely when
`gnupghome` is `None` (mirroring python-gnupg's own `make_args()`) instead
of passing `None` straight to `subprocess.run()` — which raises
`TypeError: expected str, bytes or os.PathLike object, not NoneType`.
Reported against real usage (only reachable outside tests, since every
test's `GPGBackend` has a real temp-dir `gnupghome`) — a reminder that a
path parameter defaulting to `None` for "use the platform default" needs
that `None` handled at every point it's later used as a path, not just at
construction time.

**Bad passphrase**: on a wrong passphrase, `GPGBackend` raises
`BadPassphraseError` (a `GPGBackendError` subclass) instead of the generic
one, detected via `_is_bad_passphrase_error()`: it reads the numeric code
off gpg's own `[GNUPG:] ERROR <location> <code>` status line and checks it
against libgpg-error's `GPG_ERR_BAD_PASSPHRASE` (11) — deliberately *not*
string-matching gpg's human-readable "Mauvaise phrase secrète"/"Bad
Passphrase" text, which is localized and would silently stop matching for
anyone not running gpg in French. Every dialog that unlocks a key turns a
`BadPassphraseError` into a short, translated, friendly message this way
instead of gpg's full diagnostic dump (still shown verbatim, and
selectable, for any other failure) — see "Passphrase entry" below for the
shared `KeyOperationDialog` mixin that wires this in once for every such
dialog.

`add_subkey()`/`revoke_subkey()` both need the *primary* key's passphrase
to unlock it, which is easy for a beginner to confuse with a subkey
passphrase (GPG keys don't really have "subkey passphrases" — the primary
key's secret material protects everything under it) — the passphrase
field in both `AddSubkeyDialog` and `RevokeSubkeyDialog` (see "Subkey
management" below) is labelled "Primary key passphrase:" precisely to
head that off.

## Key list & detail view

`ui/key_list_view.py::KeyListView` is the main window's central widget: a
`QTreeWidget` grouping keys into "My keys" / "Other keys" by
`Key.has_secret`, plus a detail panel (fingerprint, algorithm, capabilities,
dates, trust, UIDs, subkeys table) for the current selection. It knows
nothing about `GPGBackend` or threading — `set_keys(list[Key])` is its only
input, which keeps it testable with plain fixture `Key`/`Subkey` objects
(`tests/test_key_list_view.py`), no GPG or async involved.

`MainWindow` owns the orchestration: a `QThreadPool` plus
`actionKeyRefresh` (Keys toolbar/menu, `F5`) both call `refresh_keys()`,
which runs `gpg_backend.default_backend().list_keys()` via
`gpg_worker.run_async()` and routes the result to
`KeyListView.set_keys()` or a status-bar error message
(`GPGBackendError` and friends never crash the window — see
`_on_keys_load_failed`). Also loaded once automatically on startup.

`KeyListView.selected_key()`/`selected_subkey()` (backed by a
`selectionChanged` Qt signal, emitted on either tree's selection changing)
let `MainWindow` read the current selection to enable/disable the
subkey-management actions below — the subkeys table's rightmost "Status"
column shows each subkey's trust label too, so an already-revoked subkey is
visible at a glance (and `MainWindow` won't let you revoke it again).

A "Copy" button next to the fingerprint (`btnCopyFingerprint`) copies the
displayed, space-grouped fingerprint text to the clipboard via
`QApplication.clipboard()` — handy for a key-signing party, where
fingerprints get pasted around a lot for cross-checking. It has a
thicker-than-default `:focus` border (`palette(highlight)`, so it stays
correct in both light and dark themes) — easy to miss otherwise when
tabbing to it, since it's a small button off to the side of the
fingerprint text.

`KeyListView.select_key(fingerprint, subkey_keyid=None)` re-selects a key
(and optionally one of its subkeys) by identifier after `set_keys()` has
rebuilt the tree from scratch — otherwise every reload (including the one
after a subkey add/revoke) drops the selection back to nothing.
`MainWindow.refresh_keys()` records the current selection just before
kicking off the (async) reload and restores it in `_on_keys_loaded()`, so
the wizard/dialogs' own `refresh_keys()` call after a successful operation
keeps the affected key selected rather than dropping the user back to "no
selection". A no-op if the fingerprint isn't found (e.g. the key was
deleted) — deliberately silent, since falling back to "no selection" is
already the right behavior for that case.

### Passphrase lock/unlock column

`treeKeys` has a fifth, unlabeled column (between "Name" and "Email",
`_LOCK_COLUMN = 1` in `key_list_view.py`) showing a lock icon for any key
with a secret part: `unlocked-black.svg` while its passphrase is in
`core.passphrase_cache` (see "Passphrase entry" below), `locked-black.svg`
otherwise. A key without a secret part gets no icon at all — there's no
passphrase to know or forget. Double-clicking that column on a row whose
passphrase is currently cached forgets it (`passphrase_cache.forget()`)
and updates just that icon; double-clicking any other column is a no-op,
handled by `KeyListView._on_key_item_double_clicked()` checking the
column index Qt's `itemDoubleClicked` signal reports.

Icons are (re)computed whenever the tree is rebuilt (`set_keys()` →
`_add_group()`), which covers the common case: every dialog that can cache
a passphrase already calls `MainWindow.refresh_keys()` on success. A
30-second `QTimer` (`_refresh_lock_icons()`) additionally re-checks the
cache on its own, so a key whose cached passphrase expires while the user
is doing something else eventually flips back to "locked" without
requiring a manual refresh.

This column stays icon-tight rather than defaulting to Qt's ordinary
header width — verified empirically, not just reasoned about, since
`resizeColumnToContents()`/`setColumnWidth()` alone silently do nothing
useful here: `QHeaderView.minimumSectionSize()` (sized for a sortable
text header on most styles, ~38px) is a *floor* applied after either
call, and a header-less icon column never legitimately needs anything
close to that. `_setup_key_tree()` gives `treeKeys` an explicit small
`iconSize` (`QSize(16, 16)`, rather than the style-default `QSize(-1,
-1)`) and lowers `header().setMinimumSectionSize(24)`; `set_keys()` then
explicitly sets `_LOCK_COLUMN`'s width to `iconSize().width() + 8` after
the usual `resizeColumnToContents()` loop, since that loop's own
per-column computation still lands on the (now-lowered, but still
generic) minimum for a column with no header text and only an icon to
measure.

### Context menus and shared actions

Each of the four selectable sections — the key tree, and the UID/photo/
subkey lists in the detail panel — has a context menu, reachable by
right-click or by pressing 'c' (a `QShortcut` scoped to the widget via
`Qt.ShortcutContext.WidgetShortcut`, so it works without a mouse; it pops
up at the current item's position, computed by `_current_item_pos()`).
Each menu's *content* mirrors that section's own toolbar, established when
the toolbars were split by theme (Keys/Identities/Subkeys/Photos — see
"Window, toolbars, and persisted UI state" below): `MainWindow._wire_context_menu_actions()` hands
`KeyListView` the exact same `QAction` instances used by
`toolbarKeys`/`toolbarIdentities`/`toolbarPhotos`/`toolbarSubkeys` via
`set_key_actions()`/`set_uid_actions()`/`set_photo_actions()`/
`set_subkey_actions()` — so enabling, disabling, or renaming an action
anywhere updates the menu bar, the toolbar, *and* every context menu at
once, never a separately-instantiated copy.

The key and subkey context menus additionally get a "Copy ID" entry
(copying the full fingerprint — `Key.fingerprint`/`Subkey.fingerprint` —
not the shorter key ID column shown in the tree), and the UID context menu
gets "Copy email" (parsed out of the UID string via the same
`_parse_uid()` already used to populate the Name/Email columns). The photo
context menu gets a leading "Show" entry — the same effect as activating
the selected photo (see "Photo viewer" below), for a mouse-only user who'd
otherwise have no way to open it from the menu at all. Unlike the actions
shared with a toolbar/menu, these four are plain `QAction`s owned by
`KeyListView` itself: they have no toolbar/menu-bar equivalent, so there's
nothing to share them with.

### Section exclusivity (UIDs / photos / subkeys)

Only one of the UID list, photo list and subkey tree is ever considered
"selected" at a time — whichever currently has focus — so
`MainWindow._update_action_states()` never has to guess which of two
simultaneously-populated selections the user actually means.
`KeyListView` enforces this with an `eventFilter()` installed on all
three widgets: on `QEvent.Type.FocusIn`, it clears the *other* two
widgets' selection. This has to be a real focus filter rather than
reacting to `itemSelectionChanged` — a plain `Tab` into a section that
still remembers an old selection doesn't fire a selection-changed signal
at all, since Qt doesn't clear a view's selection just because it lost
focus, but the toolbar buttons still need to stop reflecting that stale
selection the moment focus leaves it.

### Contextual help (What's This)

`actionWhatsThis` (Help toolbar/menu, icon `help-contextual.svg`) is built
via `QWhatsThis.createAction(window)` rather than a hand-wired `QAction` —
Qt's factory already provides the standard "click here, then click a
widget" behavior, the Shift+F1 shortcut, and its own translated text/
tooltip (via Qt's bundled `qtbase_*` translations, already loaded by
`i18n.setup()` — see "Internationalisation"), so only the icon needed
overriding. The one-toolbar-per-theme convention (see "Window, toolbars, and
persisted UI state" below) gets a `toolbarHelp` for it, since none of the
pre-existing toolbars fit.

The actual help text lives on individual widgets via `widget.setWhatsThis
(...)`, called from each widget's `_ui.py` right where it's constructed —
currently `KeyListView`'s `treeKeys`, `lstUids`, `lstPhotos`, `treeSubkeys`
and `btnCopyFingerprint`. `key_list_view_ui.py`'s `_section_exclusivity_note()`
holds the sentence about the UID/photo/subkey mutual exclusivity shared by
all three of those lists, so it isn't retyped (and re-translated) three
times over.

Every `QAction` in `main_window_ui.py` (all 26 of them, key/trust/server/
general) also has its own `setWhatsThis(...)` text — since actions are
shared between a toolbar, its menu entry and any context menu (see "Context
menus and shared actions"), setting it once on the action covers all of
them, unlike a plain widget where each one needs its own call. This text is
deliberately longer/more informative than the existing `setStatusTip()`
one-liner shown in the status bar on hover — e.g. explaining *why* an
operation is irreversible, what it requires (a passphrase), or what it
doesn't affect (Export never includes private key material) — rather than
just restating the action's label. `test_every_action_has_whats_this_text`
in `test_main_window.py` guards against a new action being added without
one.

Not every widget in the app has `What's This` text yet — dialogs opened
from these actions (e.g. `AddSubkeyDialog`'s own form fields) don't, only
the actions that open them; extending it to individual dialog widgets is a
separate task.

### Photo viewer

Activating a photo in `lstPhotos` — a double-click *or* pressing Enter/
Return on it, both delivered by Qt's own `itemActivated` signal, no
separate key handling needed — opens `PhotoViewerDialog`
(`ui/photo_viewer_dialog.py`) showing it at its native, unscaled
resolution inside a non-resizable `QScrollArea` (`setWidgetResizable
(False)`), so a photo bigger than the dialog gets scrollbars instead of
being shrunk to fit — a true "1:1 zoom" view, as opposed to the 64×64
thumbnail in the list itself. The photo context menu's "Show" entry
(`_on_show_photo_action()`) opens the same dialog for whichever photo is
currently selected — both paths funnel through `_open_photo_viewer()`.

## Personal key creation wizard

`core/gpg_backend.py::GPGBackend.generate_key(NewKeyRequest)` generates a
certify-only primary key, plus a dedicated signing subkey and/or encryption
subkey — each optional, both proposed by default (unchecking one folds that
usage into the primary key instead, so the result is always fully usable).
Two `python-gnupg` calls: `gen_key_input()`/`gen_key()` for the primary key,
then `add_subkey()` per requested subkey usage. Expiration is always "never"
at creation time; it is set independently afterward — see "Expiration
dates" below.

`add_subkey()`'s `master_passphrase` must be a real string, **never**
`None`, even for an unprotected key (pass `""`): python-gnupg only adds
`--pinentry-mode loopback` when the value is not `None`, and without it
`gpg` tries an interactive pinentry program that doesn't exist in a headless
environment (tests, CI, most servers) — surfacing as a "Pas de pinentry" /
"no pinentry" failure. This was found and fixed empirically; see the git
history for the reproduction.

`ui/new_key_wizard.py::NewKeyWizard` (`QWizard`) collects the request over
four pages (Identity, Parameters, Passphrase, Generate) and runs
`generate_key()` via `gpg_worker.run_async()` on the final page — a busy
indicator while it runs, an error message with the page still open (`Back`
lets the user fix inputs and retry) on failure, `Finish` enabled only once
`generated_key` is set. `MainWindow._on_key_new()` opens it modally and
calls `refresh_keys()` only if the wizard was accepted. Each page exposes
its collected values as small public methods (`name()`, `key_length()`, …)
rather than reaching into sibling pages' widgets directly.

The Parameters page's algorithm combo defaults to `preferences.
get_preferred_algorithm()` (see "Preferences" below) and, when ED25519 is
selected, disables the key-size combo (irrelevant — fixed curve) and forces
the encryption-subkey checkbox checked-and-disabled (see the ED25519
encryption constraint above). `AddSubkeyDialog` (see "Subkey management"
below) mirrors this same algorithm combo and default.

Test convention: most `test_new_key_wizard.py` tests monkeypatch
`gpg_backend.default_backend` to a fake with an instant `generate_key()` —
no real `gpg` call, no `gnupg_home` needed. One end-to-end test does use the
`gnupg_home` fixture with a small (1024-bit) key to verify the real
`GPGBackend.generate_key()` wiring.

## Password strength

`core/password_strength.py::evaluate_password_strength(password)` estimates
a *new* passphrase's strength (entropy in bits + a `PasswordQuality` tier),
via the `zxcvbn` conda-forge package. Both the entropy thresholds and the
`Quality` tiers (`Bad`/`Poor`/`Weak`/`Good`/`Excellent` at 0/40/75/100 bits)
are a direct port of KeePassXC's own `PasswordHealth` class
(`src/core/PasswordHealth.{h,cpp}` — KeePassXC uses its own C port of
zxcvbn, whose scores this Python binding's `guesses_log10` should
approximate closely enough for the same thresholds to make sense).
`entropy_bits = guesses_log10 / log10(2)` — zxcvbn's own "guesses" metric is
a base-10 log, this app reports bits (base-2), like KeePassXC does.

zxcvbn-python has two rough edges KeePassXC's own C port doesn't, both
handled in `_entropy_bits()`: it **crashes** with an `IndexError` on an
empty string (verified empirically) instead of just scoring it 0, and it
**raises** `ValueError` above its own `max_length` parameter (rather than
truncating) — but that parameter defaults to 72 and is *not* a hard
algorithmic ceiling: verified empirically up to at least 1024 characters,
it just gets quadratically slower with input length (this pure-Python
port, unlike KeePassXC's own C implementation) — roughly 200ms worst case
at 256 characters of dictionary-heavy content, ~2s at 1024. That matters
because the strength meter recomputes on every keystroke with no
debounce, so `_MAX_ZXCVBN_LENGTH` is this module's own deliberate 256
threshold (passed explicitly as `max_length=`, since zxcvbn's own default
of 72 would otherwise reject anything longer), matching KeePassXC's real
extrapolation threshold rather than an arbitrary lower one. An empty
password short-circuits to 0.0 bits without calling zxcvbn at all;
anything past 256 characters is scored on its first 256 chars then
linearly extrapolated for the rest — the same idea as KeePassXC's own
extrapolation past that same threshold, just in pure Python.

`ui/password_strength_meter.py::PasswordStrengthMeter` is a small composite
widget (colored `QProgressBar` + a "N bits" label) with one method,
`set_password(text)`, that re-evaluates and repaints on every call — wired
to `txtPassphrase.textChanged` in the wizard's Passphrase page
(`_PassphrasePage._on_text_changed()`), so it updates on every keystroke.
The bar's colors give each of the five tiers its own distinct color, red
to green — `#C43F31` red for Bad, `#E07F16` orange for Poor, `#D4B106`
yellow for Weak, `#5EA10E` light green for Good, `#118F17` green for
Excellent. This used to mirror KeePassXC's own quality bar exactly
(`gui/styles/StateColorPalette.cpp`, light-theme variant), which shares
one red between Bad and Poor — changed on request so all five tiers are
visually distinguishable; Bad/Good/Excellent keep KeePassXC's original
values, only Poor and Weak got new ones.

Used on the wizard's Passphrase page and on `ChangePassphraseDialog`'s new-
passphrase field (see "Changing a key's passphrase" below) — the only two
places a passphrase field holds a *brand-new* value. Every other
passphrase field in the app (`AddSubkeyDialog`/`RevokeSubkeyDialog`/
`AddUidDialog`/`SetPrimaryUidDialog`/`RevokeUidDialog`, and
`ChangePassphraseDialog`'s own *current*-passphrase field) unlocks an
*existing* key instead, so a strength meter there wouldn't mean anything.

## Changing a key's passphrase

`core/gpg_backend.py::GPGBackend.change_passphrase(fingerprint, old, new)`
drives gpg's own **`--change-passphrase`** top-level command (an alias for
`--passwd`) directly via `subprocess.run()` — not python-gnupg, which has
no wrapper for it, and not `--edit-key`'s `passwd` sub-command the way
`revoke_subkey()`/`revoke_key()` script their own operations. Verified
empirically, `--change-passphrase` matters here for one specific reason: a
wrong *old* passphrase surfaces as a proper machine-readable `[GNUPG:]
ERROR keyedit.passwd <code>` status line, so `_is_bad_passphrase_error()`
works unmodified. Scripting `--edit-key`'s `passwd` command for the exact
same failure only ever emits a **localized** "erreur de modification de la
phrase secrète" message with no status-line code at all — which would
force either a locale-dependent text match (exactly what this project's
passphrase-detection convention forbids, see the module-level comment
above `_is_bad_passphrase_error()`) or a wrong blanket "any failure here
means a bad passphrase" assumption.

The script fed over `--command-fd 0` starts as `f"{old}\n{new}\n"` — one
entry each for the old and the new passphrase, **not** twice for the new
one: verified empirically that a *correct* old passphrase only ever needs
two prompts total (old, then new), no matter how many subkeys the key has
— gpg unlocks the primary key once and reuses that for every subkey via
its own agent cache. The familiar "enter it twice to confirm" step is a
real-pinentry-only UX affordance, not part of the underlying assuan
exchange — the UI is what asks twice here, not gpg (see below).

Three more gpg quirks here, all verified empirically and all easy to miss
because they only show up under specific, easy-to-not-think-of conditions:

- **A wrong old passphrase needs one retry per secret-key part.** With
  nothing to cache, gpg retries the old-passphrase prompt once per secret
  part (primary + each subkey) instead of just once, and it cannot be told
  apart from a correct one until each of those has actually played out.
  Reported against a real key with 4 secret parts (primary + 3 subkeys):
  the original 2-line script ran dry partway through that retry sequence,
  and gpg reported the resulting premature EOF as a plain "operation
  canceled" (`[GNUPG:] ERROR keyedit.passwd` code 99, not 11) instead of
  the expected bad-passphrase code — silently defeating
  `_is_bad_passphrase_error()` and dumping gpg's whole raw, multi-attempt,
  French-locale diagnostic output into the dialog's error label instead of
  a clean "Incorrect current passphrase." So the script actually sent is
  `old`, `new`, then `old` again `_MAX_SECRET_KEY_PARTS` (64) more times as
  filler — a generous upper bound no real key's subkey count should ever
  reach. The filler is harmless once a real success or failure is reached:
  gpg simply stops reading and exits without consuming the rest, exactly
  like the trailing `save` line (not a `--edit-key` REPL command — it's
  never actually read either, verified even in the success case).
- **gpg-agent's own passphrase cache.** If the agent already has this key
  cached from some earlier, unrelated operation in the same session (its
  default cache TTL is several minutes — entirely plausible in normal use,
  e.g. right after signing something or opening another dialog whose
  passphrase field the app's own `passphrase_cache` prefilled), gpg
  silently **skips the old-passphrase prompt** and only asks once. Since
  `change_passphrase()`'s script has `old` as its very first line, that one
  remaining prompt then consumes `old_passphrase`'s value as the *new*
  passphrase instead of actually checking it — a silent misfire, not an
  error, and independent of the multi-part retry issue above.
  `change_passphrase()` always calls a small
  `_clear_agent_passphrase_cache()` helper first (`RELOADAGENT` via
  `gpg-connect-agent`) to force a real, fresh check every time. Deliberately
  **not** `_restart_agent()`'s `gpgconf --kill gpg-agent`: a
  kill is asynchronous (it returns before the old process has actually
  exited), so the very next call can still race into the not-yet-dead
  agent and its still-live cache — verified empirically, this reintroduces
  the exact bug it's meant to fix. `RELOADAGENT` reloads the running agent
  in place and only returns once that's done.
- **A never-protected key.** `--change-passphrase` only reliably works
  when *fingerprint* already has a real passphrase. Given `old_passphrase
  = ""` for a key that has never had one (`no_protection=True` at
  generation, still unprotected), it reports success but the key stays
  unprotected — confirmed by re-testing with an empty passphrase
  afterwards. `--edit-key`'s `passwd` sub-command *does* handle that
  transition correctly, but going back to it would reintroduce the very
  problem this whole approach exists to avoid (no machine-readable error
  code for a wrong old passphrase — see above). Since this dialog always
  asks for the *current* passphrase first, which presupposes one exists,
  protecting a previously-bare key is out of scope for it — a separate
  "protect this key" operation would be a different feature.

`ui/change_passphrase_dialog.py::ChangePassphraseDialog` follows the usual
`KeyOperationDialog`/`KeyOperationDialogUiMixin` pattern: `txtPassphrase`
holds the *current* passphrase (prefilled from the cache, like every other
dialog), plus `txtNewPassphrase`/`txtNewPassphraseConfirm` — live-matched
the same way as `NewKeyWizard`'s Passphrase page — next to a
`PasswordStrengthMeter` tracking the new value. Because the whole point of
the operation is that the passphrase the dialog was opened with stops
working, it overrides `_on_operation_success()` entirely instead of
relying on `KeyOperationDialog`'s default post-success caching, which
would cache the now-stale *old* value read from `_passphrase_line_edit()`
— it caches the *new* one instead.

## Preferences

`preferences.py` (top-level, alongside `i18n.py`/`settings.py`) stores
general app preferences beyond language and window geometry:
`get_preferred_algorithm()`/`set_preferred_algorithm()` ("RSA" or
"ED25519", default RSA) and `get_toolbar_icon_size()`/
`set_toolbar_icon_size()` (`"system"` or a pixel size string — `"16"`,
`"24"`, `"32"`, `"48"`, `"64"`, default `"system"`), both edited from
`SettingsDialog`. Same pattern as `i18n.py`: its own tiny `_settings()`
helper building a `QSettings` at `settings.py`'s config directory, so it
shares that file's test isolation automatically. Deliberately one small
module per preference *area* rather than a shared `QSettings` accessor —
see `i18n.py`'s and `ui/window_state.py`'s docstrings for the same
convention.

Toolbar icon size is applied live, unlike the language change (which
needs a restart): `MainWindow._apply_toolbar_icon_size()` runs once at
startup and again whenever `SettingsDialog` is accepted, and calls
`QToolBar.setIconSize()` on all three toolbars. `"system"` resolves to
`self.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarIconSize)` rather
than skipping the call — Qt has no "unset back to default" API for
`QToolBar.iconSize()`, so restoring the system size after a custom one
was set has to go through the style directly, the same value Qt itself
would have used had `setIconSize()` never been called at all.

## Activity (advanced) window

`core/activity_log.py` keeps an in-memory, thread-safe ring buffer of
every external command PBNightingale has run (`gpg`, `gpg-connect-agent`,
…), recorded unconditionally, independently of `logging`'s own `-d`/
`--debug` gate (see "GPG backend" above): the Activity window is meant to
always have something to show, not just when debug logging happens to be
enabled. Framework-agnostic by the same convention as the rest of
`core/` — it notifies subscribers synchronously, on whichever thread
called `record()` (normally a `QThreadPool` worker, via
`ui/gpg_worker.py`), and leaves marshaling back to the GUI thread to its
one real subscriber, `ui/activity_log_dialog.py::ActivityLogDialog`
(re-emits through a `Signal(object)`, which Qt queues across threads
automatically).

Two independent tracing paths feed it, and both matter — a keyserver
search used to be silently invisible here because only one of them
existed at first:

- `_traced_run()`/`_traced_popen()` — every call `core/gpg_backend.py`
  makes by building a raw argv itself and shelling out directly (`gpg
  --edit-key` scripting, `--attribute-file`, `gpg-connect-agent`, …).
- `_TracedGPG._open_subprocess()` — every call made *through*
  python-gnupg's own high-level API instead (`list_keys()`,
  `search_keys()`, `recv_keys()`, `send_keys()`, `gen_key()`,
  `import_keys_file()`, `export_keys()`, …). python-gnupg builds and runs
  its own subprocess internally for these, entirely bypassing
  `_traced_run()`/`_traced_popen()` — `GPGBackend.__init__` uses a
  `_TracedGPG(gnupg.GPG)` subclass instead of `gnupg.GPG` directly
  specifically to close this gap, overriding python-gnupg's own
  `_open_subprocess()` (verified, by reading python-gnupg's source, to be
  the one choke point every high-level method funnels through) to record
  the command before delegating to the real implementation. No
  passphrase redaction is needed there either: python-gnupg's
  `make_args()` never puts a passphrase in argv, only
  `--passphrase-fd 0` — the real value goes to the subprocess's stdin
  afterward, which this override never sees. Relying on a
  leading-underscore method is inherently fragile against a future
  python-gnupg version restructuring it — worth re-checking on a
  version bump, since a silent tracing gap is much harder to notice than
  a loud break.

`ActivityLogDialog` is deliberately non-modal (`setModal(False)`, shown
via `show()` rather than `exec()`) so it never blocks the rest of the
app — reachable via **View → Activity (advanced)** (after a separator, at
the end of the menu) or F12. `MainWindow._on_activity_log()` keeps a
single instance alive for the window's whole lifetime
(`self._activity_log_dialog`) and just raises it on repeat activation,
rather than creating a new one each time — matching how the window
subscribes to `activity_log` once, in `__init__`, and never unsubscribes.
Selecting a row and pressing Ctrl+C (`QShortcut(QKeySequence.StandardKey.
Copy, ...)`) copies that row's raw command text to the clipboard; a
**Clear History** button (`activity_log.clear()`) empties the table and
the underlying ring buffer without dropping the dialog's own subscription
— unlike `activity_log.reset()`, which also clears every subscriber and
exists purely for test teardown (see `tests/conftest.py`'s autouse
`_isolated_activity_log`, mirroring `_isolated_passphrase_cache`).

How many commands are kept is `preferences.get_activity_log_max_entries()`/
`set_activity_log_max_entries()` (default 50, edited from `SettingsDialog`'s
"Activity history:" spin box), applied to the ring buffer via
`activity_log.configure()` at startup and again whenever `SettingsDialog`
is accepted — same pattern as toolbar icon size (see "Preferences" above),
except it also calls the open `ActivityLogDialog.refresh()` (if one
exists) so a just-shrunk buffer's table doesn't keep showing entries that
no longer exist.

The table's leading "#" column is `ActivityEntry.seq`, a counter that only
ever goes up: assigned once, under `activity_log`'s own lock, the moment a
command is recorded, and never reused or renumbered afterward. It
survives **Clear History** on purpose — the next command recorded still
gets the next number in line, not `1` again — so a sequence number stays
a stable reference to one specific command's original run order even once
older rows have aged out of the ring buffer or been cleared. Only
`activity_log.reset()` (test-only teardown) restarts it at `1`, alongside
wiping every entry and subscriber.

A row's number doesn't always mean "one row per command", either: some
commands write their real output to a side file rather than stdout/stderr
(gpg's `--attribute-file`, used to read back photo user IDs — see "Photo
user IDs" below), which the plain argv trace can't show. For those,
`activity_log.record_detail(seq, text)` appends a follow-up line sharing
the triggering command's own sequence number instead of allocating a new
one, so the two rows stay visibly grouped in the table.

**Why refreshing one key used to spam this window with unrelated
`--edit-key` calls**: `GPGBackend.refresh_from_keyserver()`'s before/after
change-detection snapshots used to call `self.list_keys()` with no
filter, which — via `_load_primary_uids()` (see "Editable user IDs"
above) — pays one `--edit-key` subprocess per *every* multi-UID key in
the whole keyring, not just the one being refreshed. `list_keys()` now
takes an optional `fingerprints` filter (threaded straight through to
python-gnupg's own `list_keys(keys=...)`), and `refresh_from_keyserver()`
passes the keys actually being refreshed — refreshing one key out of a
keyring full of multi-UID keys now costs one `--edit-key` call (if that
key itself has more than one UID), not one per multi-UID key in the whole
keyring. `MainWindow.refresh_keys()`'s own full-keyring reload right after
the report dialog closes is unaffected — it deliberately reloads
everything, the same as pressing F5.

Three actions on the Keys toolbar/menu, all reading `KeyListView.
selected_key()`/`selected_subkey()` and enabled only when relevant
(`MainWindow._update_action_states()`, run on every `KeyListView.
selectionChanged`):

- **Add subkey** (`actionKeySubkeyAdd`, needs a key with `has_secret`):
  opens `ui/add_subkey_dialog.py::AddSubkeyDialog`, a single small dialog
  (purpose, algorithm, key size, passphrase) that runs `GPGBackend.
  add_subkey()` via `gpg_worker.run_async()` with the same busy-indicator/
  retry-on-error shape as the wizard's Generate page.
- **Revoke subkey** (`actionKeySubkeyRevoke`, needs a selected subkey that
  isn't already revoked): opens `ui/revoke_subkey_dialog.py::
  RevokeSubkeyDialog` — the **strong confirmation** this operation calls
  for is a checkbox ("I understand this action is permanent…") that gates the
  Revoke button, rather than a plain Yes/No message box, since revocation
  can't be undone. Drives `GPGBackend.revoke_subkey()` (see below) the
  same async way.
- **Export** (`actionKeyExport`, needs any selected key): synchronous (fast)
  — `QFileDialog.getSaveFileName()` then `GPGBackend.export_public_key()`
  writes the ASCII-armored **public** key to the chosen `.asc` file.

**Back up private key…** (`actionKeyBackup`, needs `has_secret` — the whole
point is exporting secret material, unlike the public-only Export above)
opens `ui/backup_private_key_dialog.py::BackupPrivateKeyDialog`: a
passphrase field plus a warning that the resulting file, together with
its passphrase, is enough to fully impersonate the key. Unlike **Export**
this is async (`GPGBackend.export_secret_key()` shells out to real `gpg`,
not an instant local read) and needs a passphrase at all: GnuPG >= 2.1
refuses `--export-secret-keys` without one (confirmed against
python-gnupg's own `export_keys()` docstring). That wrapper only returns
the raw armored bytes and throws away `stderr`, so a wrong passphrase
couldn't be told apart from any other failure through it —
`export_secret_key()` instead drives `gpg --pinentry-mode loopback
--status-fd 2 --passphrase-fd 0 --armor --export-secret-keys` directly,
the same shape as `revoke_key()`'s subprocess call, keeping `BadPassphraseError`
detection working. The dialog asks for the destination file (`QFileDialog.
getSaveFileName()`) only once "Back Up…" is clicked, then runs the export
via `KeyOperationDialog._run_operation()` like every other passphrase-
guarded dialog — but its result is armored text to write to a file, not
an updated `Key`, so it overrides the mixin's `_on_operation_result()`
hook (added for exactly this case) instead of relying on the default
"it's a Key, set `updated_key` and accept" behavior.

**Delete…** (`actionKeyDelete`, needs any selected key) opens
`ui/delete_key_dialog.py::DeleteKeyDialog` — the action started disabled
(`for action in (self.actionKeyDelete,): action.setEnabled(False)`, with a
"not implemented" tooltip) until this flow existed, since every *other*
scaffolded action got its own dedicated implementation before this one
did. Same **strong confirmation** checkbox as the revoke
dialogs, but no passphrase field at all: unlike revoking (which must
produce a valid signature, needing the key unlocked) or backing up
(needs the key unlocked to read it out), deleting is a purely local
keyring-management operation — GnuPG never asks to unlock a secret key
just to erase it. `GPGBackend.delete_key(fingerprint, secret=...)` drives
`gpg --batch --yes` directly with `--delete-secret-and-public-key` (when
`secret=True`) or `--delete-keys` (public-only): no `--edit-key`
scripting needed, no `BadPassphraseError` possible.

A dialog with no passphrase field is new: `KeyOperationDialog.
_passphrase_line_edit()` can now return `None` (in addition to the
default `self._ui.txtPassphrase`), and `_run_operation()`/
`_sync_cached_passphrase()` treat that as "nothing to prefill, read or
cache" rather than crashing on a missing attribute. `DeleteKeyDialog`
also overrides `_on_operation_result()` since `delete_key()` returns
`None`, not an updated `Key` — there's no key left to describe.

Unlike revoking (the key still exists afterward, just untrustworthy) or
Export (never touches the private part), deletion is the one operation
here with no way back short of a separate backup or re-import — the
dialog's warning text says so explicitly, distinct from the revoke
dialogs' wording.

`GPGBackend.revoke_subkey()` is the one operation python-gnupg has no
wrapper for: it drives `gpg --edit-key` directly over its
`--command-fd 0 --status-fd 1 --pinentry-mode loopback` scripting protocol
with a fixed command script (`key <keyid>` — selecting by keyid, not
position, avoids any ordering assumption — then `revkey`, confirm, pick "no
reason given", the passphrase line, `save`). Verified empirically against a
real key before being written; the passphrase must be sent as a scripted
line at the exact point gpg's `GET_HIDDEN passphrase.enter` status appears
in the protocol, which is right after the revocation-reason confirmation —
not wherever seems intuitive in the command sequence. Stale-agent recovery
and bad-passphrase detection work the same way here as for every other
write operation in this module — see "GPG backend" above.

**Revoking the primary key itself** (as opposed to a subkey) was added
later, alongside a toolbar/menu reorganization (see "Window, toolbars, and
persisted UI state" below): `GPGBackend.revoke_key()`
is the exact same `--edit-key` script as `revoke_subkey()`, minus the
leading `key <keyid>\n` selection line — with no subkey selected, `revkey`
targets the primary key instead (verified empirically). `actionKeyRevoke`
(needs `has_secret` and a key that isn't already revoked) opens
`ui/revoke_key_dialog.py::RevokeKeyDialog`, the same checkbox-gated
strong-confirmation shape as `RevokeSubkeyDialog`. Since the target here
*is* the primary key, its passphrase field is just labelled "Passphrase:",
not "Primary key passphrase:" — there's no subkey to disambiguate from —
and its `BadPassphraseError` message is the shorter "Incorrect
passphrase." rather than RevokeSubkeyDialog's "Incorrect primary key
passphrase."

Icon: `key-revoke.svg` (PBIcons) moved from the subkey action to this one
— "key-revoke" describing the *primary* key is the better semantic match,
and it had been the subkey action's icon only because nothing more
specific existed yet, the same kind of too-hasty icon reuse flagged again
for the UID icons below (see "Editable user IDs"). `actionKeySubkeyRevoke`
gets PBIcons' generic `remove.svg` (a red minus) renamed locally to
`subkey-revoke.svg` instead, following the `trust-set.svg`/
`subkey-expire.svg` precedent of borrowing a close-enough generic icon
under a locally-invented name when nothing dedicated exists — PBIcons has
no `subkey-revoke.svg` counterpart to `subkey-add.svg`/`subkey-expire.svg`
yet.

## Editable user IDs

Text UIDs (name/email/comment) and photo IDs are handled as two separate
flows: a photo ID is a materially different flow — image selection/
cropping, JPEG encoding, and a scripted `gpg --edit-key addphoto`, not
just another `--quick-*` command — covered on its own in "Photo user IDs"
below.

Three actions on the Keys toolbar/menu, all reading `KeyListView.
selected_key()`/`selected_uid()` and enabled only when relevant
(`MainWindow._update_action_states()`):

- **Add user ID** (`actionKeyUidAdd`, needs a key with `has_secret`): opens
  `ui/add_uid_dialog.py::AddUidDialog` (name/email/comment/passphrase,
  the same shape as the wizard's identity page) and calls `GPGBackend.
  add_uid()`.
- **Set as primary** (`actionKeyUidSetPrimary`, needs a selected, non-revoked
  UID): opens `ui/set_primary_uid_dialog.py::SetPrimaryUidDialog` (just an
  explanation + passphrase — no strong confirmation, since it's reversible)
  and calls `GPGBackend.set_primary_uid()`.
- **Revoke user ID** (`actionKeyUidRevoke`, needs a selected, non-revoked
  UID *and* more than one valid UID left on the key): opens
  `ui/revoke_uid_dialog.py::RevokeUidDialog`, the same strong-confirmation
  checkbox shape as `RevokeSubkeyDialog`, and calls `GPGBackend.
  revoke_uid()`. Disabled rather than left to fail when it's the last valid
  UID — gpg itself refuses that with a `GPGBackendError` (`keyedit.
  revoke.uid`), but the UI shouldn't invite the user into that wall.

`GPGBackend.add_uid()`/`set_primary_uid()`/`revoke_uid()` all shell out to
gpg's `--quick-add-uid`/`--quick-set-primary-uid`/`--quick-revoke-uid`
(GnuPG 2.1+) via the shared `_run_quick_uid_command()` — unlike subkey
revocation, these take the passphrase non-interactively over
`--passphrase-fd 0` (piped over stdin, never a `--passphrase` argument, so
it never shows up in a process listing), no `--edit-key` scripting needed.
Same stale-agent retry and `BadPassphraseError` detection as every other
quick command (see "GPG backend" above). `format_uid(name, email,
comment)` builds the literal `"Name (Comment) <email>"` string gpg expects
verbatim — `--quick-add-uid` applies no formatting of its own.

**Highlighting the primary UID** — `Uid.primary: bool`. gpg's plain
`--list-keys --with-colons` output never exposes which UID is primary
(field 14, "flag field", is documented as "used in the --edit-key menu
output" — it's genuinely empty in plain listings). UID listing order
looked at first like a usable stand-in (the primary UID's self-signature
timestamp does get bumped forward by `--quick-set-primary-uid`, so it
tends to sort first) but a clean test disproved it: after generating a key
and adding two more UIDs in sequence with no primary ever explicitly set,
`--list-keys` returned them in neither creation order nor timestamp order
(`C, A, B` for UIDs created in order `A, B, C`) — an implementation detail
of gpg's keybox storage, not a documented sort. The *only* place the actual
primary flag (`,p` in the flag field) shows up is `gpg --edit-key`'s own
`--with-colons` listing (`printf 'list\nquit\n' | gpg --command-fd 0
--no-tty --with-colons --edit-key <fpr>`), scripted in
`GPGBackend._primary_uid_value()`.

That costs one extra `gpg` subprocess per key — unlike photo attributes
(`_load_photos()`), which recover in a single pass over the *whole*
keyring since `--attribute-file`'s `ATTRIBUTE` status lines already name
the fingerprint, there is no `--edit-key` equivalent that operates over
more than one key at a time. `_load_primary_uids()` bounds the cost by
only calling `_primary_uid_value()` for keys with more than one UID — a
single-UID key's only UID is trivially primary, no need to ask gpg at
all — which keeps this cheap in aggregate (most keys in a typical keyring
have exactly one UID). A lookup failure (non-zero exit) degrades to no
UID flagged primary rather than raising or guessing.

The key list's Name/Email columns (`KeyListView._add_group()`) now prefer
the primary UID over the previous `key.uids[0]` fallback (kept as the
fallback when no UID is flagged primary, e.g. a lookup failure) — same
underlying data, so there is no reason for the tree's summary columns and
the identities list's checkmark to disagree about which UID is "the" one.
The identities list itself (`_format_uid_label()`) prefixes the primary
UID's label with a checkmark (✓); **Set as primary** (`actionKeyUidSetPrimary`)
is disabled when the selected UID already is the primary one, in addition
to its existing non-revoked requirement.

Icons: `user-add.svg`, `user-default.svg` and `user-delete.svg` are synced
as-is from PBIcons (`make update-icons ARGS="user-add.svg user-default.svg
user-delete.svg"`) — each action (add/set-primary/revoke) has its own
dedicated icon rather than reusing `key-revoke.svg` (an earlier, too-hasty
choice: PBIcons has more per-action icons than an initial glance
suggested — see the same lesson repeated for photo icons below).

## Photo user IDs

A photo is an OpenPGP "user attribute" (colon record type
`uat`, not `uid`) embedding a JPEG. Three things had to be worked out
empirically, since none of it is a `--quick-*` command:

**Adding one** (`GPGBackend.add_photo_uid()`) drives `gpg --edit-key`'s
`addphoto` over the `--command-fd`/`--status-fd` scripting protocol, same
family as `revoke_subkey()`. Two gotchas found by testing against a real
key, both documented in the method's own docstring: `--no-tty` is
*required* — without it `addphoto` tries to open a controlling terminal
and fails outright in any headless or GUI-launched process (verified: it
works fine interactively from a terminal, fails immediately otherwise) —
and the passphrase line in the script goes right after the file path,
*before* `save`, unlike subkey revocation where it goes at the very end:
gpg signs the new self-signature as soon as the photo is accepted, not at
save time. Sending it in the wrong slot doesn't error — it just gets
silently consumed as a bogus `photoid.jpeg.add` retry or `keyedit.prompt`
command, and the passphrase prompt never gets answered.

A third gotcha, found against real usage rather than in testing: gpg asks
an extra `photoid.jpeg.size` yes/no confirmation right after the file path
for a JPEG above some internal size threshold ("this is quite a large
JPEG, use it anyway?", bisected empirically to between 5909 and 6369
bytes, no documented exact value) — a tiny fixture JPEG never triggers it,
but any real photo routinely does. Unlike every other step here, this one
genuinely can't be scripted blindly: the *content* of gpg's next prompt
depends on whether this one fired, and there's no way to know in advance.
The first fix attempt — always answering `y` right after the file path,
on the theory that an unneeded answer is harmlessly absorbed as a bogus
command (true of the passphrase line on an unprotected key) — broke the
opposite case instead: a *protected* key with a *small* photo goes
straight from the file path to the passphrase prompt with nothing in
between, so the unconditional `y` got consumed as the passphrase itself.
There's no option to suppress the prompt and no size threshold safe to
hardcode client-side, so `add_photo_uid()` drives gpg through
`subprocess.Popen` instead of the usual one-shot `subprocess.run(input=
script)`, peeking at its live `--status-fd` output just long enough to
see whether `photoid.jpeg.size` actually appears this time (answering
`y` if so) before sending the passphrase and `save` exactly as before.
Two more things fell out of building that peek loop, both non-obvious
enough to be worth recording: gpg's *very first* prompt is also
`GET_LINE keyedit.prompt` (asking for the `addphoto` command itself) —
identical text to the "back at the main prompt, nothing left to sign"
signal the loop is watching for, so the loop must not start treating that
signal as meaningful until *after* it has already seen the file actually
requested once, or it reads its own end-of-peek condition one exchange
too early and deadlocks. And status output must stay on its own pipe
(`--status-fd 2`, read via `process.stderr`) rather than merged into
stdout via `stderr=subprocess.STDOUT`: gpg's stdout is fully
block-buffered by glibc once it isn't a tty, so merging delays status
lines inside gpg's own internal buffer instead of delivering them —
exactly the deadlock this rewrite was meant to fix, just moved one level
down. `stderr` stays unbuffered in C by default, which is also why every
sibling method here already used `--status-fd 2`.

**Listing them** is its own problem: python-gnupg's `list_keys()` silently
drops `uat` records — its record-type allowlist in `_decode_result()`
(`pub sec fpr sub ssb sig grp uid`) doesn't include them, confirmed by
reading its source, not just observed behavior. `GPGBackend._load_photos()`
instead runs one *extra* raw `gpg --with-colons --status-fd 2
--attribute-file <tmp> --list-keys` for the whole keyring (not one call
per key — the `[GNUPG:] ATTRIBUTE <fpr> <octets> <type> <index> <count>
<timestamp> <expiredate> <flags>` status line names its own fingerprint,
so one pass over the whole keyring is enough) and reads the matching raw
bytes back from the `--attribute-file`. Each block is an RFC 4880 "Image
Attribute" subpacket: a little-endian 16-bit header length, a version
byte, a format byte (1 = JPEG), reserved padding, then the actual JPEG —
the header length is read from the block rather than assumed to be a fixed
16, in case of a future header version. Bit `0x02` of `<flags>` is
"revoked" — read directly off this same status line, no `--edit-key`
round trip needed for that (unlike the "which UID is primary" question
above, gpg *does* expose an attribute's revoked state in a plain listing).

Unlike every other `_traced_run()` call, this one's interesting output
isn't on stdout/stderr — it's the side file at `--attribute-file`'s path,
read only after the command finishes. The plain argv trace in the
Activity window (see "Activity (advanced) window" above) wouldn't show
what the command actually produced, so `_load_photos()` follows it with
`activity_log.record_detail(result.activity_seq, ...)` — a supplementary
line, its command text the raw attribute-file bytes as hex, sharing the
same sequence number as the `--attribute-file` command itself
(`result.activity_seq`, an ordinary attribute `_traced_run()` sets on the
`CompletedProcess` it returns — that class has no `__slots__`, so this
needs no subclass or wrapper). `activity_log.record()` returning its
`ActivityEntry` and the dedicated `record_detail(seq, text)` (append a
line without allocating a new sequence number) exist specifically to
support this.

**Revoking one** (`GPGBackend.revoke_photo_uid()`) has the same problem as
promoting a photo to primary would: `--quick-revoke-uid` needs literal
text to match against, and a photo has none. There is no shortcut — this
drives `gpg --edit-key` directly (`uid <N>` to select, then `revuid`, same
confirmation/reason/passphrase sequence as subkey revocation), after first
resolving *which* `uid N` a given `PhotoUid.index` (1-based, counting only
photos, in the order `_load_photos()` returns them) actually corresponds
to via `_resolve_photo_edit_index()` — a **second**, read-only
`--edit-key` "list" call. Two more things worth recording about that call
specifically: it prints the *entire* key listing twice before quitting
(verified empirically, harmless but easy to double-count photos against if
not handled — `_resolve_photo_edit_index()` stops at the second `sec`/`pub`
line it sees), and each `uat`/`uid` line's own edit-index shows up as the
first comma-separated component of colon field 14 (e.g. `"3,p"`,
`"2,r"`, `"4,"` — the same field that has no `primary`/`revoked` info at
all in a *plain* `--list-keys`, see "Editable user IDs" above; `--edit-key`
listings and plain listings expose genuinely different data through the
same colon format).

The UI: **Add photo…**/**Revoke photo…** on the Keys toolbar/menu open
`ui/add_photo_dialog.py::AddPhotoDialog`/`ui/revoke_photo_dialog.py::
RevokePhotoDialog` — the latter the same strong-confirmation checkbox
shape as every other revoke dialog. `AddPhotoDialog` scales the chosen
image down (240px on the long side, JPEG quality 85) before handing it to
gpg: an OpenPGP photo ID lives inside the key itself and travels with
every exported copy of it forever, so a full-resolution photo would bloat
the key for no benefit — every other OpenPGP tool's photo viewer is tiny
anyway. The scaled JPEG is written to a temp file cleaned up on both
success and cancel (`AddPhotoDialog.reject()` is overridden for this).
`lblPreview` is fixed at exactly this same 240×240 (`MAX_PREVIEW_DIMENSION`
in `add_photo_dialog_ui.py`, imported back into `add_photo_dialog.py`
rather than duplicated) so it shows the *actual* scaled image — a smaller
preview label combined with `QLabel`'s default no-scaling behavior would
center-crop a non-square photo instead of showing what really gets sent.
The key detail panel gained a "Photos" group: `lstPhotos`, a `QListWidget` in
icon mode showing a thumbnail per photo (`KeyListView.selected_photo()`,
mirroring `selected_uid()`/`selected_subkey()`); a revoked photo's item
text reads "Revoked" since there's no room for a label next to a thumbnail
the way `_format_uid_label()` appends "(revoked)" to a text UID's string.

Icons: `photo-add.svg` and `photo-delete.svg` are synced as-is from
PBIcons (`make update-icons ARGS="photo-add.svg photo-delete.svg"`) —
dedicated icons, not reused from elsewhere, so Add Photo/Revoke Photo
look distinct at a glance from Add User ID/Revoke User ID on the same
toolbar.

## Expiration dates

Unlike every other quick-edit feature described above, expiration
management *is* a single gpg command end to end: `--quick-set-expire fpr
expire [*|subfprs]`. Verified empirically against a real key (two-, three- and
`*`-argument forms all tested) since the man page's wording about the
3-argument form is ambiguous about whether it also touches the primary
key — it doesn't:

- Two arguments (`fpr expire`) sets **only** the primary key's expiration,
  subkeys untouched — `GPGBackend.set_key_expiration()`.
- Three arguments with a specific subkey fingerprint (`fpr expire
  subfpr`) sets **only** that one subkey, primary key and every other
  subkey untouched — `GPGBackend.set_subkey_expiration()`. The third
  argument must be the *subkey's own* fingerprint (`Subkey.fingerprint`),
  not its short keyid and not the primary key's fingerprint.
- Three arguments with `*` instead sets every non-revoked, non-expired
  subkey and leaves the primary key alone — not currently exposed in the
  UI (no use case yet: the "Set subkey expiration…" action targets one
  selected subkey at a time, matching how every other subkey action in
  this app already works).

`expire` accepts `"0"` (never expires), a relative duration (`"30d"`,
`"6m"`, `"1y"`, …) or an absolute `"YYYY-MM-DD"` date — all handled
identically by gpg itself, no parsing needed on this app's side beyond
building that string from the dialog's checkbox/date-picker state.

Both methods go through the same `_run_quick_command()` helper as the
UID quick-commands (`add_uid()`/`set_primary_uid()`/`revoke_uid()`, see
"Editable user IDs" above) — generalized from what used to be
`_run_quick_uid_command`
to take a variable number of trailing arguments, since `--quick-set-expire`
needs one more (the optional subkey fingerprint) than any `--quick-*uid`
command does. Same retry-on-stale-agent and `BadPassphraseError` handling
as every other quick command, confirmed empirically: a wrong passphrase
here surfaces as `[GNUPG:] ERROR set_expire 67108875`, same libgpg-error
code as everywhere else.

The UI: **Set key expiration…** and **Set subkey expiration…** on the
Keys toolbar/menu both open the *same* `ui/set_expiration_dialog.py::
SetExpirationDialog` — passing a `Subkey` targets that subkey, passing
none targets the primary key. One dialog class rather than two (unlike
the UID/photo dialogs, which genuinely differ in their input fields):
the only difference between the two flows is which backend method gets
called and a couple of label strings, so a second near-identical dialog
class would just be duplication. The dialog preselects the target's
current expiration (a "Never expires" checkbox, checked by default,
gating a `QDateEdit`) so accepting without changing anything is a no-op
round trip rather than an accidental change.

Icons: `key-expire.svg` (PBIcons' `calendar-day.svg`) and
`subkey-expire.svg` (PBIcons' `calendar-timeline.svg`), both renamed
locally the same way as `subkey-add.svg` (see "Subkey management" above)
— no PBIcons icon
actually depicts "key" or "subkey" expiration specifically, so these are
two different generic calendar glyphs pressed into service, picked apart
just so the two actions read as distinct at a glance on the same
toolbar.

## Key signing & web of trust

Two independent gpg concepts, easy to conflate since they
share the word "trust" and the same colon-format letter codes — worth
being precise about, since this app now surfaces both:

- **Validity** (`Key.trust`, gpg colon field 2): is this key's UID-to-key
  binding considered genuine? Computed from signatures plus the signers'
  ownertrust. This is what the detail panel's "Validity:" row shows
  (renamed from a plain "Trust:" label now that "Owner trust:" exists
  right below it — the old label was already a simplification, and having
  both concepts on screen under near-identical names would be actively
  confusing).
- **Owner trust** (`Key.owner_trust`, gpg colon field 9): how much *you*
  trust this key's owner to correctly certify *other* people's keys — a
  purely local judgment call, not derived from any signature. gpg
  auto-assigns "ultimate" ownertrust to any key you hold the secret part
  of, unless you've explicitly overridden it (verified empirically —
  overriding it, e.g. to "never", sticks and is respected, which is also
  the only reliable way to test signing's effect on validity in isolation
  from that auto-ultimate shortcut).

**Signing a key** (`GPGBackend.sign_key()`) drives `--quick-sign-key`
(exportable) or `--quick-lsign-key` (local-only, non-exportable) — signs
*every* UID on the target key (gpg's own default when no `[names]` are
given). `-u <signing_key_fingerprint>` picks which of the user's own
secret keys performs the signature; `--default-cert-level <0-3>` sets the
certification-check level *before* the quick-sign command itself, since
(unlike every other quick command's arguments) it's an option of gpg
itself, not a positional argument of `--quick-sign-key` — this is what
`_run_quick_command()`'s new `extra_options` parameter is for. Same
stale-agent retry and `BadPassphraseError` handling as every other quick
command (`[GNUPG:] ERROR keysig/keyedit.sign-key <code>`, same libgpg-error
code as everywhere else).

Gotcha worth recording, found while writing the test for it: gpg's own
`--min-cert-level` defaults to **2**, which disregards level-1 ("persona",
not verified) signatures entirely when computing validity — a level-1
signature from an otherwise-perfectly-trusted signer has *no effect* on
the signed key's computed validity. Level 0 ("no particular claim") is
documented as always accepted regardless of `--min-cert-level`, and 2/3
obviously clear the default bar too. `SignKeyDialog`'s verification-level
combo defaults to 0, matching gpg's own `--default-cert-level` default —
which, per the above, is actually a perfectly effective default despite
sounding like the "weakest" option.

**Setting owner trust** (`GPGBackend.set_owner_trust()`) drives
`--quick-set-ownertrust fpr <level>`. Unlike every other write operation
in this module, it needs **no passphrase or secret key at all** — verified
empirically — since it only records a local judgment in the trust
database, not a cryptographic operation. Valid `level` keywords
(`OWNER_TRUST_LEVELS`, verified empirically since gpg's own error message
for an invalid one doesn't list them): `undefined`, `never`, `marginal`,
`full`, `ultimate`.

**Refreshing trust** (`GPGBackend.refresh_trust()`, wired to the
previously-unimplemented `actionTrustRefresh`) drives `--check-trustdb`,
*not* `--update-trustdb` — the latter is interactive (it prompts for
ownertrust on any key that doesn't have one yet) and would hang under
`subprocess.run()`; `--check-trustdb` does the same recomputation without
ever prompting, simply skipping keys with undefined ownertrust. On
success, `MainWindow` calls `refresh_keys()` directly rather than also
showing its own "done" status message first — recomputing trust can
change keys' computed validity, so the list needs reloading anyway, and a
separate status message would just be overwritten within the same event
loop turn by `refresh_keys()`'s own "Loading keys…"/"N key(s) loaded"
sequence.

The UI: **Sign key…** and **Set owner trust…** (Trust toolbar/menu, next
to the now-implemented **Refresh trust**) open
`ui/sign_key_dialog.py::SignKeyDialog` and `ui/set_owner_trust_dialog.py::
SetOwnerTrustDialog` respectively. Both work on *any* selected key, not
just personal ones — signing and trust judgments are things you do to
*other* people's keys, unlike every key-, subkey-, UID-, photo- and
expiration-management action described above, which required
`has_secret`. `SignKeyDialog` needs a list of the user's own certify-
capable keys to populate its "Sign as:" combo; rather than have the
dialog re-fetch the keyring synchronously (blocking the GUI thread) or
have `MainWindow` track a redundant copy of the last-loaded keys,
`KeyListView.my_keys()` returns the personal-keys list `set_keys()` already
computed and cached (`_my_keys`) for the "My keys (N)" group — no extra
`gpg` call needed. The dialog defaults "Local signature only" to checked:
this app's own stated audience is beginners, and a local signature is the
safer default (stays in the local keyring, doesn't require the user to be
careful about identity verification the way a signature they'd publish to
a keyserver would).

Icon: `trust-set.svg` is PBIcons' `ok.svg` (a plain checkmark), renamed
locally the same way as `subkey-add.svg` (see "Subkey management" above)
— there is no PBIcons icon depicting "trust" as a concept beyond
`trust-refresh.svg`, already used.

## Key import

Two independent sources, both non-interactive — unlike most
of this app's `--edit-key` work, python-gnupg already has a thin, usable
wrapper for each:

**From a file** (`GPGBackend.import_from_file()`) is the simple case:
`self._gpg.import_keys_file(path)` reads the file and hands its bytes to
`import_keys()`, which accepts both ASCII-armored and binary key data, a
single key or a whole exported keyring, public or secret. Success is
`result.fingerprints` being non-empty — `ImportResult.__bool__` also
checks `not_imported == 0`, which is stricter than needed here (a
multi-key file where *some* entries import fine and others don't should
still return the ones that worked, not raise), so this checks
`fingerprints` directly rather than truthiness of the result object
itself.

**From a keyserver** (`GPGBackend.import_from_keyserver()`) takes a single
free-form *query* — a fingerprint, key ID, or email address — and a
*keyserver* (no built-in default; every caller supplies one explicitly,
sourced from `preferences.get_checked_keyserver_urls()` — see "The
configured keyserver list" below), and picks the underlying gpg operation
based on which kind of query it looks like:

- **Fingerprint or key ID** (no `@`): `self._gpg.recv_keys(keyserver,
  query)`, i.e. `--keyserver <server> --recv-keys <query>` — a direct,
  exact-match fetch, no ambiguity possible.
- **Email address** (contains `@`): `GPGBackend._locate_key_by_email(email,
  keyserver)`, scripted directly with `subprocess` — i.e. `--keyserver
  <server> --auto-key-locate wkd,keyserver --locate-keys <email>`. This is
  deliberately *not* python-gnupg's own `auto_locate_key()`: that method
  appends its `extra_args` (needed for `--keyserver`) *after* the
  positional `email` argument to `--locate-keys`, which gpg then swallows
  as an extra, bogus user ID to locate instead of parsing as an option
  (verified empirically: gpg's own "« --keyserver » n'est pas considéré
  comme une option"). This silently broke the keyserver fallback whenever
  WKD itself failed — unless the key happened to already be cached in the
  keyring from an earlier lookup, which is exactly why it went unnoticed
  until `preview_import_from_keyserver()` (see "Review before importing"
  below) started exercising a cold lookup against a keyring that never
  has anything cached, and a real bug report surfaced it. Every gpg
  option — not just `--keyserver` — must come *before*
  `--auto-key-locate`/`--locate-keys`, which consumes every argument
  after it as a user ID to locate. This is also deliberately *not*
  `--search-keys` (the one keyserver operation that supports email
  lookup on some servers, `keys.openpgp.org` among them — see
  "Keyserver management" below for what its `op=index` actually
  supports, corrected there after initially being documented wrong):
  its normal use is interactive, presenting a numbered list of matches
  for the user to pick from, with no scriptable non-interactive
  equivalent regardless of what any particular server indexes.
  WKD (Web Key Directory) sidesteps keyservers entirely: it fetches
  straight from the domain's own
  `https://<domain>/.well-known/openpgpkey/...` endpoint, which is what
  most providers that support any form of discovery actually offer, with
  the given keyserver only as a fallback mechanism.

Both raise `GPGBackendError` when nothing came back (`result.fingerprints`
empty, or `_locate_key_by_email()` returning `None` for the email path) —
the underlying `stderr` is used as the message when present, since it
usually carries gpg's own specific reason (key not found, network
failure, etc.).

One specific empty-`fingerprints` case gets a dedicated, friendlier
message instead of gpg's raw stderr dump: importing by fingerprint/key ID
a key that has no user ID at all. Confirmed by direct testing (a fresh
`GNUPGHOME`, `--recv-keys` against `hkps://keys.openpgp.org`) — the
common real-world cause is keys.openpgp.org stripping every UID from a
key whose email was never verified there. gpg's own reaction to this is
itself version-dependent: 2.4.4 just skips it (`--recv-keys` still exits
0), while the conda-forge 2.5.22 this app ships ends the whole operation
with `[GNUPG:] FAILURE gpg-exit ...` — either way, `result.fingerprints`
stays empty. Detected via python-gnupg's `ImportResult.count`/`.imported`/
`.unchanged` (all populated from gpg's numeric, locale-independent
`IMPORT_RES` status line): `count` positive but both `imported` and
`unchanged` zero means gpg fetched something but imported nothing — as
opposed to a genuine "nothing found" (`count == 0`). Deliberately *not*
matched on gpg's own "no user ID" text, which is rendered in the system's
locale (seen in French as "pas d'identité" in a real bug report) — same
principle as `_is_bad_passphrase_error()`'s status-code decoding. Scoped
to the `--recv-keys` (ID/fingerprint) path only: the email/WKD path's own
`_locate_key_by_email()` has no equivalent counts to inspect (see the
`ImportedKey.is_new` note above for the same WKD-path limitation).

The UI: **Import…** (Keys toolbar/menu, previously a disabled placeholder)
opens `ui/import_key_dialog.py::ImportKeyDialog`, a two-tab dialog ("From
file" / "From keyserver") rather than two separate actions — both are
"acquire a key from somewhere new", differing only in *where*, and the
existing action/tooltip already described them as one combined feature.
Unlike every has_secret-gated action described above, this one (like
**Sign key…**/**Set owner trust…**/**Refresh trust**) doesn't depend on
any current key selection at all — it's enabled unconditionally in
`MainWindow.__init__`, importing being how a key gets into the list in
the first place.

Both `import_from_file()` and `import_from_keyserver()` return
`list[ImportedKey]` rather than `list[Key]` — a small wrapper pairing each
`Key` with `is_new: bool`, so `MainWindow` can tell the user something
more useful than a generic "N key(s) loaded" once the import finishes
(reported bug: importing an already-in-keyring key by email showed
nothing but that generic count, with zero indication the key was already
there). `is_new` is computed by snapshotting `{e["fingerprint"] for e in
self._gpg.list_keys(False)}` *before* the underlying gpg call and
checking whether the resulting fingerprint(s) were absent from that
snapshot. This is deliberately existence-based rather than reading gpg's
own per-key import reason codes (`ImportResult.results[i]["ok"]`, which
distinguish "entirely new" from "new UID/sig/subkey merged into an
existing key" from "no-op duplicate"): the WKD/email path's own
`_locate_key_by_email()` exposes no such data at all (it's a locate, not
an import-status object), so relying on gpg's codes would need a separate
fallback for that path anyway. A key that
already existed and merely picked up a new UID/signature/subkey is
therefore reported the same as a total no-op — both read as "already
present" — which matches what a user actually needs to know here (did
importing get me something new or not), not a full merge audit.

`MainWindow._describe_import()` turns a `list[ImportedKey]` into a
status-bar message and a fingerprint to select, and `refresh_keys()`
gained two optional keyword-only params (`status_message`,
`select_fingerprint`) so that message/selection survive the async
`list_keys()` reload that follows — previously `_on_keys_loaded()`
always overwrote the status bar with the generic count and
`_pending_selection` only ever restored the *previous* selection, never
an externally requested one (two other call sites,
`_on_trust_refreshed`/`_on_server_refreshed`, have code comments
explicitly accepting that same limitation — this is the first fix for
it, applied narrowly to the two import entry points rather than
retrofitting all ~19 `refresh_keys()` call sites). `SearchKeyDialog`'s
own "Import" step (**Rechercher…** → pick a result → Import) had the
identical gap and reuses the same `_describe_import()` helper.

**Review before importing**: `ImportKeyDialog` never imports on the first
click. "Check…" previews every candidate key (identities, full key ID,
fingerprint, and whether it's already in the keyring) in a checkable
`treeCandidates`, and only "Import" (enabled once at least one row is
checked) commits the checked ones. Motivation: a file import can bring in
*several* keys at once (a whole exported keyring) that were previously
merged in blindly with no per-key review.

- `GPGBackend.preview_import_from_file()` uses python-gnupg's
  `scan_keys()`/`scan_keys_mem()`, which drives gpg's own `--dry-run
  --import-options import-show --import` — verified empirically (a real
  multi-key export, `list_keys()` before/after) to leave the keyring
  completely untouched while reporting the same fingerprint/keyid/uids
  shape as a real listing.
- `GPGBackend.preview_import_from_keyserver()` has no such dry-run to lean
  on — `--recv-keys`/`--locate-keys` always merge into whatever keyring
  gpg is pointed at, there is no non-mutating fetch. It fetches into a
  throwaway `GPGBackend(tempfile.mkdtemp(), gpgbinary=self._gpg.gpgbinary)`
  instead (discarded via `shutil.rmtree()` before returning), reusing
  `import_from_keyserver()` on *that* scratch keyring wholesale — its
  WKD-vs-recv-keys branching and error messages (no-user-id, not-found)
  all come along for free. `is_new` is then recomputed against the *real*
  keyring's own pre-fetch snapshot, since the scratch keyring's own
  `is_new` is always `True` (it started empty). This costs a second
  network round-trip if the user approves (fetch once to preview, once
  more for real) — an accepted trade-off, since this path only ever
  surfaces exactly one candidate in this app (`--recv-keys <exact-id>`/
  `--locate-keys <email>` are never ambiguous here), unlike the file path.
- Both preview methods return `list[ImportPreview]` (fingerprint, keyid,
  uids, is_new) — deliberately lighter than `Key`/`ImportedKey`, just
  enough to let the user recognize a candidate.
- Commit (`commit_import_from_file()`/`commit_import_from_keyserver()`)
  calls the real, unfiltered `import_from_file()`/`import_from_keyserver()`
  and then runs the result through `_commit_filtered()`, which deletes
  any resulting key that is **both** unapproved **and** genuinely new
  (`is_new`) — restoring the keyring to exactly what the user approved
  even when a multi-key file brought in more. **A key that was already
  present is never deleted this way**, even if left unchecked: unchecking
  an already-present candidate only means "don't bother re-merging it
  from this source", never "remove my existing copy" — this is the one
  correctness rule the whole feature hinges on, covered by
  `test_commit_import_from_file_never_deletes_an_already_present_key`.
  Both commit methods short-circuit to `[]` with **no import call at
  all** when nothing is approved, so declining the keyserver path's one
  candidate never touches the network or the keyring.
- The candidate tree pre-checks a row exactly when `not candidate.is_new`
  — importing a key you already trust enough to have is low-stakes and
  defaults to "yes"; adding a genuinely new, previously-unknown key
  requires a conscious per-key opt-in. This is the first checkbox-style
  list anywhere in this codebase (`Qt.ItemFlag.ItemIsUserCheckable` on a
  `QTreeWidget` item, consistent with the app's other column-based tree
  widgets rather than a plain `QListWidget`).
- Scope: only `ImportKeyDialog` works this way. `SearchKeyDialog`'s own
  import step already shows a review (identities/algo/length/date) before
  committing and, by construction, can only ever act on one key at a
  time — it doesn't have the "several keys, blindly merged" problem this
  fixes, so it was left as-is (confirmed with the user).

## Keyserver management

A dedicated "Keyservers" toolbar/menu already existed as a scaffolded,
disabled placeholder; the three actions it holds — **Search…**,
**Publish…**, **Refresh** — each do something distinct from a plain
fingerprint/ID/email import (see "Key import" above):

**Search…** (`ui/search_key_dialog.py::SearchKeyDialog`) is the
*ambiguous*-query counterpart to `import_from_keyserver()`: it drives
`GPGBackend.search_keyserver()`, which wraps python-gnupg's
`search_keys()` — the interactive `--search-keys` operation the
email-import path above deliberately avoids for email lookups, because
here that's exactly the point. It returns every match (`SearchResult`: fingerprint, uids, algo,
length, created) for a picker list; selecting one and clicking **Import**
imports it by exact fingerprint through the already-existing
`import_from_keyserver()`, so the dialog is really two independent async
steps (search, then import) sharing one window, `imported_keys` set only
once the second step succeeds. Enabled unconditionally, like **Import…**.
`txtQuery.returnPressed` is wired to the same `_on_search()` as the
**Search** button, so pressing Enter in the query field searches
immediately.

`keys.openpgp.org`'s search support was previously documented here as
"doesn't support `op=index`, never returns a `uid:` record" — wrong on
both counts, corrected after a user directly disputed it. Verified
against Hagrid's own published API docs
(<https://keys.openpgp.org/about/api>) plus a live `op=index` request
(`https://keys.openpgp.org/pks/lookup?op=index&options=mr&search=<email>`)
against a real, verified address, which came back with several `uid:`
lines, full email addresses included:

- `op=index` *is* supported — but "Only exact matches by email address,
  fingerprint or long key id are returned" (Hagrid's own wording): a
  free-text name query (`search=Linus`, no `@`) gets a plain HTTP 400,
  not a match list. `search_keyserver()`'s own `query` parameter doc
  ("a name, email address, fingerprint, or key ID, depending on what
  *keyserver* supports") still holds — keys.openpgp.org just isn't a
  server that supports the "name" case, and a self-hosted keyserver with
  a genuine `op=index` might return several matches (a real
  disambiguation list) where keys.openpgp.org, true to Hagrid's "always
  returns either one or no keys at all", never does.
- UIDs *are* returned in the result — but only for an email address the
  key's owner has verified there (at upload or afterward, via Hagrid's
  own `/vks/v1/request-verify` confirmation-email flow); an unverified
  address stays invisible to search, same as it does to a plain
  `--recv-keys` fetch (see "Key import" above,
  `preview_import_from_keyserver()`'s own "no user ID" case).

`Ui_SearchKeyDialog.lblKeyserverHint` (shown only while `cmbKeyserver`
holds `hkps://keys.openpgp.org` exactly, via `_update_keyserver_hint()`)
surfaces the verification requirement in the dialog itself rather than
leaving it to `CODING.md`, since an unverified address is the one real,
recurring source of a confusing "not found" for an address the user
knows is genuinely on the server.

The HKP index format percent-encodes the `uid` field like a URL component
(a space as `%20`, `<`/`>` as `%3C`/`%3E`) — gpg relays it as-is on its
`uid` status line, and python-gnupg's own uid parsing only unescapes
gpg's *other*, unrelated colon-format escapes (`\xHH`, `\:`), not this
one. `search_keyserver()` runs each uid through `_decode_hkp_uid()`
(`urllib.parse.unquote`) before returning it, or search results show raw
encoded text.

Both dialog buttons have `autoDefault` explicitly turned off. Without
that, pressing Enter in the query field closed the dialog instead of
searching: `QDialogButtonBox` auto-promotes another button to "default"
whenever the current default one is disabled, and "Import" starts
disabled (no result picked yet) — so "Cancel" silently became the
button Enter activated, rejecting the dialog. This only shows up once
the dialog is actually shown on screen (`QDialog`'s own Enter handling
only considers *visible* buttons), which is why a naive test that never
calls `.show()` won't catch it — see `test_pressing_enter_in_the_query_
field_launches_the_search`.

A search with zero matches is a normal outcome (a real user query with no
hits, e.g. a name nobody published), not a backend error — but gpg itself
reports it as a failure: `--search-keys` emits `[GNUPG:] FAILURE
search-keys <code>` with `<code>` packing `GPG_ERR_NOT_FOUND` (27), often
alongside an unrelated `dirmngr` `server_version_mismatch` *warning* (an
older system-packaged `dirmngr` already running, same root cause as the
`gpg-agent` mismatch described under "GPG backend" above — but merely
informational here, since the search itself still completes correctly).
`search_keyserver()` decodes that status line the same locale-independent
way as `_is_bad_passphrase_error()` (never gpg's own human-readable,
system-language "not found" text) and returns an empty list instead of
raising, so the dialog's normal empty-results path ("0 result(s) found.")
handles it — rather than surfacing gpg's full, alarming-looking stderr
dump as if it were a real error.

**Publish…** (`MainWindow._on_server_publish()`, no separate dialog file)
wraps `GPGBackend.publish_to_keyserver()` (`self._gpg.send_keys()`).
python-gnupg's own `SendResult` doesn't track anything from gpg's status
lines (its `handle_status()` is a no-op — verified against its source),
so success/failure here is read off `result.returncode`/`result.stderr`
instead of the `fingerprints`/`fingerprint` checks the import methods use.
Needs a selected key, like **Export…**. Publishing to a public keyserver
is effectively one-way (a key already out there can't be fully retracted,
only revoked), so unlike a plain click-and-go action it's gated behind a
`QMessageBox.question()` confirmation naming the target keyserver — a
lighter touch than the typed-confirmation `RevokeXDialog`s described
above, since publishing doesn't destroy anything about the key itself,
just its visibility.

**Refresh** (`MainWindow._on_server_refresh()`) wraps `GPGBackend.
refresh_from_keyserver()`: re-`recv_keys()`s the selected keys from the
keyring in one call. gpg treats fetching a key it already has as a merge
(new signatures, revocations, expiry changes), which is the whole
point — this is this app's equivalent of gpg's own `--refresh-keys`,
which python-gnupg doesn't wrap directly.

Unlike the other two keyserver actions, this one is a three-step flow
rather than a direct async call, since a full-keyring refresh can take a
while and the user may only want one key refreshed:

1. `ui/refresh_keys_dialog.py::RefreshKeysDialog` asks whether to refresh
   just the selected key or every key in the keyring — its "selected key"
   radio button is disabled (and "every key" pre-checked) when nothing is
   selected, since `actionServerRefresh` is enabled unconditionally and
   doesn't require a selection the way `actionServerPublish` does.
2. A `QProgressDialog` (window-modal, no cancel button, `setMinimumDuration
   (0)` so it appears immediately rather than after Qt's default ~4s
   delay) is shown for the duration of the `run_async()` call — the only
   modal busy indicator in the app; every other long-running action here
   only disables its toolbar action and updates the status bar. Not a
   `QProgressBar` embedded in a dialog's own layout like every add/set/
   revoke dialog's `KeyOperationDialogUiMixin._build_progress_and_status()`
   — a full-keyring refresh has no natural "form" of its own to disable
   around, so a plain modal window fits better here.
3. On success, `ui/refresh_keys_report_dialog.py::RefreshKeysReportDialog`
   lists which of the refreshed keys actually picked up a change, then
   `refresh_keys()` reloads the list the same way `_on_trust_refreshed()`
   does. On failure, `QMessageBox.warning()` — a genuine popup rather than
   a status-bar line, since the progress dialog already committed the
   user's attention to a "please wait" window that needs a definite,
   visible end (success report or error popup), not something that could
   silently be missed underneath it.

`GPGBackend.refresh_from_keyserver(fingerprints=None, keyserver=...)`
takes an optional fingerprint list (`None`, the default, means every key —
computed by the method itself from `list_keys()`) and returns
`list[RefreshedKey]` instead of `None`. "Updated" is decided by snapshotting
`list_keys()` before and after the `recv_keys()` call and comparing each
requested key's full `Key` object (frozen dataclasses compare structurally,
deep through `uids`/`photos`/`subkeys`) — not by trying to interpret gpg's
own per-import status reasons, which are exactly as ambiguous here as the
"no cheap way to tell genuinely unchanged from merged something apart"
limitation `ImportedKey` already documents for `import_from_keyserver()`.
This catches a new/revoked UID, a new subkey, a changed expiration or a
validity change, but not a bare new certification from someone else that
doesn't itself change any of those fields — an accepted, documented gap,
same spirit as `ImportedKey.is_new`. A no-op (returns `[]`) on an empty
*fingerprints* list, same "would otherwise wait on unexpected input"
guard as before, now reachable both from an empty keyring (the `None`
default resolves to `[]`) and, in principle, an explicitly empty list.

`recv_keys()` reports one overall failure for the whole batch — gpg has no
per-key exit status — so refreshing "every key" is only as reliable as the
single flakiest key in the keyring: a keyserver that's since dropped one
fingerprint (deleted, expired off it, never really there) fails the entire
call, and without special-casing that, the user sees gpg's raw multi-
hundred-line status dump (`KEYEXPIRED` for every subkey/UID combination
across every *other*, perfectly fine key, on top of the real error) instead
of a clean message — reported against real usage. `_is_no_data_failure()`
decodes gpg's `[GNUPG:] FAILURE recv-keys <code>` status line for
`GPG_ERR_NO_DATA` (58), the same locale-independent approach as
`_is_not_found_failure()` above; when that's the only problem,
`refresh_from_keyserver()` swallows it and returns the real per-key results
for everything gpg *did* find, silently leaving the missing key exactly as
it already was in the keyring (`RefreshedKey.updated=False`, folded into
the same "unchanged" bucket as any other key nothing happened to). Any
other failure (no network, an unreachable keyserver) still raises
`GPGBackendError` with gpg's full diagnostic, same as before.

None of the three send anything to a real keyserver in tests — the same
concern python-gnupg's own test suite avoids for `send_keys()` (see its
"not practical to test... without sending arbitrary data to live
keyservers" comment): every test monkeypatches `gnupg.GPG.search_keys`/
`send_keys`/`recv_keys` directly, same as the key-import tests above.

### The configured keyserver list (Preferences → Key Servers)

`preferences.get_keyservers()`/`set_keyservers()` persist an ordered
`list[tuple[str, bool]]` (URL, checked) as a `QSettings` array
(`beginReadArray()`/`beginWriteArray()`, group `keyservers/list`) — the
first genuine array this app stores in `QSettings`, everything else here
being scalars. Verified empirically before relying on it:
`beginWriteArray()` does *not* clear entries left over from a longer
previous array (a shrink from 4 items to 2 leaves items 3–4 sitting in the
INI file), but `beginReadArray()` only ever reads back up to the `size`
key it wrote, so the leftovers stay permanently, harmlessly orphaned
rather than resurfacing on a later read.

"Nothing saved yet" (→ fall back to `DEFAULT_KEYSERVERS`) is decided by
`settings.contains("keyservers/list/size")`, not by the read size coming
back `0` — those aren't the same state. A deliberately emptied list
(every keyserver removed and saved, e.g. from the Publish Key dialog's
"nothing configured" edge case) also reads back `size == 0`, and
`get_keyservers()` used to conflate the two, silently resurrecting the
built-in defaults on the very next read after a real "remove everything"
save. `set_keyservers([])` still calls `beginWriteArray()`/`endArray()`
with zero entries, which is enough for `contains()` to see the `size`
key was actually written and tell that case apart from an array that was
never touched at all.

`preferences.DEFAULT_KEYSERVERS` is the fallback `get_keyservers()`
returns before anything's ever been saved, and what `SettingsDialog`'s
"Restore Default List" button resets the (not-yet-saved) in-dialog list
back to: `keys.openpgp.org` and `keyserver.ubuntu.com` (both checked,
both still actively maintained, general-purpose), plus `pgpkeys.eu`,
`the.earth.li` and `keys.mailvelope.com` (unchecked). That third group
was going to be "reliable SKS servers" as originally asked for, but the
classic SKS pool has been dead since 2021 (shut down after GDPR takedown
requests; no HKPS certificate has been issued for it since) and
`pgp.mit.edu` — long the best-known SKS node, and the obvious first guess
for this list — is decommissioned; shipping either as a default, even
unchecked, would just be handing the user a dead URL. The three picked
instead come from the still-synchronising Hockeypuck network documented
at <https://blog.pgpkeys.eu/state-keyservers-2024.html>, and were each
verified directly reachable (`curl .../pks/lookup?op=stats`) before being
hardcoded — not merely because they were once part of SKS. Don't restore
`pgp.mit.edu`/`pool.sks-keyservers.net` here without re-verifying they're
actually back; last checked 2026-09.

`SettingsDialog` only ever edits `Ui_SettingsDialog.lstKeyservers` (a
`QListWidget` of checkable items) in memory — Add/Remove/Move Up/Move
Down/Restore Default List all mutate the widget directly, same as every
other field in this dialog, and only `preferences.set_keyservers()` on
"OK" (`_save_and_accept()`) makes it stick; Cancel leaves the saved list
untouched. `_on_keyserver_add()` reads a new URL via `QInputDialog.
getText()` and always appends it *checked* (the user just asked for it,
unlike the three unchecked entries in the built-in default list, which
exist for reference more than immediate use).

Two invariants this dialog enforces, both requested after the fact —
`get_checked_keyserver_urls()`'s callers (Import, Publish) otherwise have
nothing sane to fall back to:

- The list can never be emptied out completely. `btnKeyserverRemove` is
  disabled whenever `lstKeyservers.count() <= 1`, on top of the existing
  "needs a selection" condition — `_update_keyserver_buttons_enabled()`
  checks both. `_on_keyserver_remove()` re-checks the count itself too,
  a defensive backstop rather than the real guard (the button being
  disabled is what actually stops it in the UI).
- The dialog's own Ok button — not just Ok *button box* — is disabled
  whenever zero rows are checked, same "keeps a person from confirming a
  broken state" spirit as `ImportKeyDialog`/`SearchKeyDialog`/
  `PublishKeyDialog`'s own Ok-gating. `_update_ok_enabled()` re-evaluates
  `any(checked for _url, checked in self._keyservers())` on
  `lstKeyservers.itemChanged` (a checkbox toggle) and is also called
  explicitly after Add/Remove/Restore Default List, none of which fire
  `itemChanged` on their own (that signal only fires for a mutation to an
  item already in the list, never for `addItem()`/`takeItem()`/`clear()`
  themselves — verified against Qt's behavior, not assumed). This one
  Ok button gates *every* field in the dialog, not just the keyserver
  list — a real but accepted trade-off: unrelated changes (language,
  passphrase cache, …) can't be saved either while the keyserver list is
  in a state that would leave `get_checked_keyserver_urls()` empty.

### From keyserver → multiple checked servers, not one field

`ImportKeyDialog`'s "From keyserver" tab used to have its own `txtKeyserver`
field; it's gone now; instead it queries `preferences.
get_checked_keyserver_urls()` at Check-time and only checked servers
matching zero of them is itself an editing-time error ("No keyserver is
checked…"), same spot the empty-query check already lived. The actual
fetch fans out across every checked server through two new
`GPGBackend` methods, `preview_import_from_keyservers()`/
`commit_import_from_keyservers()`, mirroring the existing singular
`preview_import_from_keyserver()`/`commit_import_from_keyserver()` (which
stay as they are — still directly useful, and still directly tested, as
a one-server primitive) rather than replacing them.

The "merge every instance of the key" requirement behind this is just
gpg's own import behavior, used deliberately rather than reimplemented:
`GPGBackend._import_from_every_keyserver()` calls the existing
`import_from_keyserver()` once per server, always against the *same*
keyring, so a key that picked up a signature or a UID revocation on one
server but not another comes back as their union — no separate merge
logic needed. A server with no match (or simply unreachable) isn't fatal
on its own, only when every server in the list fails does the caller see
an error (the collected per-server messages, joined) — otherwise a user
with five checked servers would get an ugly failure the moment the first
one happens to be flaky. `preview_import_from_keyservers()` runs that same
fan-out against one throwaway scratch keyring (same pattern as
`preview_import_from_keyserver()`'s own scratch keyring, just fed by every
server instead of one) so the merge being previewed is the literal one
`commit_import_from_keyservers()` would later perform against the real
keyring, not an approximation of it.

### Search Keyserver dialog: a combobox, not free text

`SearchKeyDialog.txtKeyserver` is now `cmbKeyserver`, a non-editable
`QComboBox` populated from `preferences.get_keyservers()` — every
configured server, checked or not, since here a single explicit keyserver
is the whole point (unlike Import's "use everything checked" fan-out) and
an unchecked one someone kept around for occasional use is still a
reasonable thing to search against by hand. The first entry is
preselected, a "just works with no typing" default. `_update_keyserver_
hint()` (the keys.openpgp.org identity-verification notice above) keys
off `cmbKeyserver.currentText()` against `_KEYS_OPENPGP_ORG` (a private
literal local to this dialog — see "No default keyserver" below) and
fires on `currentTextChanged`. An empty combobox (every configured server
removed) is handled the same way as Import's "no keyserver checked" case
— a status-line error at Search-time, not a permanently disabled form.

### Import Key dialog: keyserver tab first

`Ui_ImportKeyDialog.tabs` now adds the "From keyserver" tab before "From
file" (it used to be the other way round), so it's the one shown by
default. `import_key_dialog.py`'s `_FILE_TAB` constant moved from `0` to
`1` to match — the one place in that file that has to track the tab
order, since `_on_check()` branches on `tabs.currentIndex() == _FILE_TAB`
rather than a hardcoded index of its own.

`self.tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.
Fixed)` pins the tab widget to its own `sizeHint()` height — without it, a
vertical resize of the dialog grew the tabs as much as (or more than)
`treeCandidates` below them, verified empirically before fixing it: a
420→800px resize grew the tabs by 229px and the tree by only 151px, each
tab page's own layout apparently reporting an expanding size hint by
default. The one field (or field + Browse button) either tab page holds
never needs more than its natural height, so a taller window should hand
all the extra room to the candidate list instead. `file_tab`'s own
trailing `addStretch()` was removed at the same time — with the tab
widget now capped to its `sizeHint()`, that spacer never had space left
to absorb anyway.

### Publish Key dialog: a picker, not a `QMessageBox.question()`

**Publish…**'s confirmation is `ui/publish_key_dialog.py::PublishKeyDialog`
rather than a raw `QMessageBox`: publishing goes to every *checked*
Preferences keyserver, so the confirmation needs to be an actual picker,
built like `RefreshKeysDialog` on `KeyOperationDialogUiMixin.
_build_button_box()` (Ok relabeled "Publish", starting disabled).

`lstKeyservers` lists every keyserver from `preferences.get_keyservers()`
— checked or not, same "show everything, let this one action's own
checkboxes differ from the saved defaults" spirit as the list itself
being non-reorderable, non-add/removable here (`QAbstractItemView.
SelectionMode.NoSelection`, no drag/drop): only each row's own checkbox
is interactive, never the row set or its order — that's Preferences'
job, not this dialog's. Each row's initial check state mirrors what's
checked in Preferences, letting the user turn some off (or on) for just
this one publish without touching their saved defaults. "Publish" starts
disabled and toggles on `lstKeyservers.itemChanged`, exactly the "Import"/
"Check" button pattern already used in `ImportKeyDialog`/`SettingsDialog`
— never enabled while `selected_keyservers()` (every checked row's URL,
in display order) would be empty, including the edge case of zero
keyservers configured at all (`lstKeyservers` itself then has zero rows).

The fan-out is `GPGBackend.publish_to_keyservers(fingerprint,
keyservers)`, same shape and the same "partial failure isn't fatal, total
failure is" philosophy as `_import_from_every_keyserver()`: it calls the
existing single-server `publish_to_keyserver()` once per server, collects
which ones actually accepted the key, and only raises `GPGBackendError`
(the joined per-server messages) when *none* did — a key already
published to two servers out of three from one click shouldn't be
reported as a failure. `MainWindow._on_server_published()`'s status-bar
message lists every keyserver actually published to
(`", ".join(keyservers)`).

### No default keyserver

No method in `GPGBackend` defaults a *keyserver*/*keyservers* parameter
to any particular server — every one of them is a plain required
parameter, forcing the caller to source it from somewhere real:
`preferences.get_checked_keyserver_urls()` (Import, Refresh, Download
Unknown Keys), `PublishKeyDialog.selected_keyservers()` (Publish), or
`cmbKeyserver.currentText()` (Search). `import_from_keyserver()`,
`preview_import_from_keyserver()`, `search_keyserver()`,
`publish_to_keyserver()` and `commit_import_from_keyserver()` are
single-server primitives, each directly tested with an explicit
keyserver.

**Refresh** and **Download Unknown Keys** follow the same "every checked
Preferences keyserver, fan out and merge" pattern as Import:

- `GPGBackend.refresh_from_keyserver(fingerprints=None, *, keyservers)`
  — `keyservers` is keyword-only and required (every call site already
  used keywords, so this was a free way to force it explicit without
  breaking argument order). Still one batched `recv_keys(keyserver,
  *fingerprints)` call per server rather than one call per key (that
  choice predates this change, see the method's own docstring) — now
  just repeated once per server in *keyservers*, each merging into the
  same keyring. A server's batch failing outright (not just one key
  being `_is_no_data_failure()`-missing from it) isn't fatal on its own;
  `GPGBackendError` only raises when *every* server's batch genuinely
  failed, same "collected per-server messages, joined" shape as
  `_import_from_every_keyserver()`. Empty *keyservers* is a no-op
  (returns `[]`), same treatment as empty *fingerprints*.
- `GPGBackend.download_unknown_signatures(identifiers, keyservers)` —
  each identifier is tried against every server in turn (never stopping
  at the first hit, so a later server's extra signatures still merge
  in), same fan-out as everything else here, just nested one level
  deeper (per-identifier, per-server) since the method already
  looped per-identifier for its own reasons (see its own docstring on
  why "one at a time").

Both call sites in `main_window.py` (`_on_server_refresh()`,
`_on_download_unknown_signatures()`) now start with
`MainWindow._checked_keyservers_or_warn(title)`: reads
`preferences.get_checked_keyserver_urls()`, and if empty, shows a
`QMessageBox.warning()` with the exact same string ImportKeyDialog's own
"no keyserver checked" status line uses (translation reused, not
duplicated) and returns `None`, which both callers treat as "abort
before doing anything" — neither of these two actions has a servers-
picker dialog of its own to embed the message in (unlike Publish's
`PublishKeyDialog`), so a warning popup is the next best thing. Publish
doesn't need this guard: `PublishKeyDialog`'s own Ok button already stays
disabled while nothing's checked, checked or not gated by Preferences.

`SearchKeyDialog`'s own `_KEYS_OPENPGP_ORG` (a private module-level
literal, `"hkps://keys.openpgp.org"`) is what's left of the old constant
there — it isn't "the app's default" anymore, just the one specific
keyserver `_update_keyserver_hint()` needs to recognize for its
identity-verification notice, regardless of where that server sits (or
doesn't sit) in the user's configured list.

## Key signatures (who signed a key)

Added once the app already had signing (`sign_key()`) but no way to see
the *result*: which keys have certified a given key's user IDs.

`ui/key_list_view_ui.py`'s detail pane is now a `QTabWidget` (`tabDetail`)
with two tabs, **Details** (the pre-existing form + `detailSplitter` of
UIDs/Photos/Subkeys, unchanged) and **Signatures** — a new tab rather than
a fourth box stacked into `detailSplitter`, since that splitter is already
a three-way UID/Photo/Subkey split and a signatures list is a different
kind of information (about the key, not part of its identity) rather than
a sibling of those three.

`GPGBackend.list_key_signatures(fingerprint)` drives a raw `--with-colons
--list-sigs` listing (not python-gnupg's own `list_keys(sigs=True)`,
whose `sig()` handler keeps only the signer's key ID and a display
string, dropping the signer's full fingerprint gpg lists right alongside
it). That fingerprint is colon field 13 of the `sig` record — verified
empirically to come from the signature packet's own "Issuer Fingerprint"
subpacket (embedded by GnuPG in every signature it makes since 2.1),
**not** a live keyring lookup: deleting the signing key from the keyring
entirely still leaves field 13 populated on the target key's own
signatures. `KeySignature.fingerprint` is `None` only for a signature old
enough to predate that subpacket, leaving `keyid` (the classic
16-character long key ID) as the sole identifier — this is also why
`download_unknown_signatures()`'s *identifier* falls back to `keyid` when
`fingerprint` is unavailable. Self-certifications (the key signing its
own user IDs, always present) are excluded by matching against the `pub`/
`sec` record's own key ID; several user IDs signed by the same key
collapse to one entry.

`GPGBackend.download_unknown_signatures(identifiers, keyserver=...)`
fetches each identifier **one at a time**, not as a single batched
`--recv-keys` call — same reasoning as `refresh_from_keyserver()`'s own
`_is_no_data_failure()` note: a batch reports one overall pass/fail for
everything requested, which can't tell a genuine per-key miss apart from
another identifier in the same request merely failing for an unrelated
reason, and the whole point of the "Download Unknown Keys" report is to
say exactly which ones were found. Success/failure is read off
`result.fingerprints` (empty means not found), same check
`import_from_keyserver()` already uses.

`KeyListView`'s Signatures tab is populated lazily: switching to the tab
(`tabDetail.currentChanged`) or changing the selected key while already on
it emits `signaturesRequested(fingerprint)` rather than eagerly fetching
signatures for every key on every `list_keys()` refresh, which would cost
one extra `gpg` subprocess call per key in the keyring for a tab most
sessions never open. `MainWindow` runs the actual `list_key_signatures()`
call through the usual `run_async()`/`QThreadPool` bridge and hands the
result to `KeyListView.set_key_signatures(fingerprint, signatures)`,
which checks the fingerprint still matches the current selection before
applying it — a slow fetch for a key the user has since clicked away from
must not clobber what's shown for the new selection. A known signer is
rendered the same way as the main key list on the left (name/email from
its primary UID, key ID, expiry); an unknown one shows only its
identifier with "Unknown locally" in the name column, and enables the
**Download Unknown Keys** button beneath the list.

Clicking that button drives the same "modal `QProgressDialog`, then a
report dialog" flow as `_on_server_refresh()` (see "Keyserver
management" above), reusing the pattern rather than the code: a
dedicated `ui/download_signatures_report_dialog.py::
DownloadSignaturesReportDialog` lists downloaded keys and not-found
identifiers in two separate group boxes (unlike `RefreshKeysReportDialog`'s
single list), since the whole point here is telling the two categories
apart, not just flagging what changed. On success, `MainWindow.
refresh_keys()` reloads the keyring and reselects the same key — which,
as a side effect (no special-casing needed), re-triggers the Signatures
tab's own fetch and picks up any signer key that was just downloaded.

## Passphrase entry: show/hide, caching, and de-duplicating the dialogs

Every dialog that unlocks a secret key (add/set/revoke a subkey, UID,
photo, expiration, signature, or the primary key itself) had grown
nearly identical boilerplate: a `txtPassphrase` field, a busy
indicator/status label, a `buttonBox`, a `_set_form_enabled()`, an
`_on_success()`/`_on_error()` pair, and a module-level `_error_message()`
telling a `BadPassphraseError` apart from anything else. Three things
prompted tackling all of it together: a show/hide toggle needed adding to
every one of those passphrase fields, a new in-memory passphrase cache
needed wiring into every one of them the same way, and the duplication
itself had become worth factoring out regardless — so this did all three
in one pass rather than touching each dialog three separate times.

**Show/hide toggle**: `ui/password_line_edit.py::PasswordLineEdit`
subclasses `QLineEdit` and adds a trailing `QAction`
(`QLineEdit.addAction(icon, TrailingPosition)`) rather than a separate
`QToolButton` next to the field — no extra layout, and it's the
conventional way Qt itself expects a "reveal" control to be built. The
action is checkable; unchecked shows `password-view.svg` (an eye — click
to reveal) and switches `echoMode` to `Password`, checked shows
`password-mask.svg` and switches to `Normal`. Every `txtPassphrase` field
in the app (and the new-key wizard's passphrase/confirm pair, which needs
the toggle but not the cache below) was switched from a plain
`QLineEdit` to this.

**Passphrase cache** (`core/passphrase_cache.py`): a module-level
`{fingerprint: (Passphrase, expires_at)}` dict, nothing more — no
encryption, no disk persistence, cleared automatically when the process
exits along with everything else in memory. `store()` records a
passphrase and a `time.monotonic()`-based expiry (deliberately monotonic,
not wall-clock, so a clock adjustment can't extend or shrink the window);
`get()` returns it if still within that window, dropping (and forgetting)
it otherwise — so a passphrase entered more than `preferences.
get_passphrase_cache_minutes()` minutes ago behaves exactly as if it had
never been cached, per its own docstring. The duration defaults to 10 and
is user-configurable in Settings (`spinPassphraseCache`, 0–120, 0 meaning
"never cache" via the special-value text "Never" — `store()` already
treats a non-positive TTL as a no-op, so 0 needs no separate flag). This
is a deliberate convenience/security trade-off appropriate for this app's
stated beginner audience: a passphrase only gets cached after a
*successful* operation (never a failed attempt, so a mistyped guess is
never remembered), and only in memory for a short, user-controlled
window — never written to disk, never logged. Tests must never let a
cached passphrase leak between them: `tests/conftest.py`'s autouse
`_isolated_passphrase_cache` clears the module-level cache before and
after every test, the same isolation discipline as `GNUPGHOME`/config.

**`ui/key_operation_dialog.py::KeyOperationDialog`** is the mixin
factoring out the behavior: `_init_key_operation()` (called once, after
`self._ui.setupUi()`) sets up the thread pool and `updated_key`, and
pre-fills the passphrase field from the cache; `_run_operation(call,
busy_text=…, error_template=…)` replaces each dialog's own `_on_add()`/
`_on_revoke()`/`_on_set()` body — it disables the form, shows the busy
indicator, and runs `call` (a zero-arg callable returning a `Key`) via
`gpg_worker.run_async()`; on success it caches the passphrase that was
actually used (captured *before* the call, since the field gets disabled
during it) against `_cache_fingerprint()` and accepts the dialog; on
failure it restores the form and shows `error_template.format(error=…)`,
where the `{error}` text comes from `_format_error()` — `_bad_passphrase_
message()`, overridable, supplies the `BadPassphraseError`-specific
wording (defaults to "Incorrect primary key passphrase.", the common
case; `RevokeKeyDialog` overrides it to "Incorrect passphrase." and
`SignKeyDialog` to "…for the selected signing key."). Each dialog still
owns `_set_form_enabled()` (which widgets to disable is genuinely
dialog-specific) and its own `_on_accept()`-equivalent method that builds
the actual `GPGBackend` call and hands it to `_run_operation()`.

`_cache_fingerprint()` defaults to `self._fingerprint` — set by every
dialog but one. **`SignKeyDialog`** is the exception: the passphrase
there belongs to whichever key is chosen in "Sign as:", not the key being
signed, so it overrides `_cache_fingerprint()` to read
`cmbSignAs.currentData()`, and reconnects `cmbSignAs.currentIndexChanged`
to `_sync_cached_passphrase()` so switching the signer re-syncs the field
(to that signer's cached passphrase, or clears it if none) instead of
leaving behind whatever was typed for the previous selection.

**`ui/key_operation_dialog_ui.py::KeyOperationDialogUiMixin`** mirrors
this on the layout side, since the `Ui_XxxDialog.setupUi()` methods were
just as duplicated: `_build_confirm_checkbox()` (the "strong
confirmation" checkbox the four revoke dialogs share),
`_build_passphrase_field()` (takes an existing `QFormLayout` to add a row
to, e.g. Add Subkey's purpose/algorithm/size form, or builds its own
one-row form otherwise), `_build_progress_and_status()`, and
`_build_button_box()`. Every dialog's `setupUi()` now builds only what's
actually specific to it, then calls whichever of these it needs for the
common tail.

## Window, toolbars, and persisted UI state

The toolbars are organized one per thing an action operates on: **Keys**
(primary-key-level actions: refresh, new, expire, revoke, import, export,
delete), **Identities** (UID actions), **Subkeys** (subkey actions),
**Photos** (photo actions), **Trust** (sign/set owner trust/refresh
trust), and **Keyservers**. This split — replacing an earlier single
crowded "Keys" toolbar — was introduced alongside primary-key revocation
(see "Subkey management" above), which is also why subkey revocation
lives in **Subkeys** rather than **Trust** despite being a trust-adjacent
operation. The Keys *menu* keeps a single flat list (with separators,
unlike the toolbars), with each entry grouped next to the other actions
on its own target (primary key, subkey, …) for consistency with the
toolbars.

`ui/window_state.py` persists window geometry and `QSplitter` sizes as
`QByteArray` blobs (`saveGeometry()`/`QSplitter.saveState()`) in the same
`QSettings` INI file as `i18n.py`'s language override — one settings file
for the whole app, rooted at `settings.py`'s config directory, so it is
covered by the same `_isolated_config` test fixture automatically.

`ui/geometry_mixin.py::GeometryMixin` wires this into a window: call
`self._init_geometry(state_key, splitters={...})` once, after `setupUi()`,
in `__init__`. It restores geometry on the first `showEvent` and saves it on
`finished` (`QDialog`/`QWizard`) or `closeEvent` (a plain `QWidget`, e.g.
`QMainWindow` — no `finished` signal). Used by `MainWindow` (with two of
`KeyListView`'s splitters — see below — persisted alongside its own
geometry), `SettingsDialog` and `NewKeyWizard`; apply it to every new
top-level window and dialog going forward. `AboutDialog` is deliberately
excluded (small, fixed-purpose, nothing worth remembering).

`KeyListView` exposes each `QSplitter` it owns as a read-only property
(`.splitter`, `.detailSplitter`) delegating to the corresponding
`Ui_KeyListView` attribute, rather than `MainWindow` reaching into
`keyListView._ui` directly — `_ui` is meant to stay private to the widget
that owns it. Two splitters: `.splitter` (horizontal — the key tree
against the detail panel, the original one) and `.detailSplitter`
(vertical — the identities/photos/subkeys group boxes stacked in the
detail panel, added later so each can be resized independently instead of
photos being hard-capped at a fixed 110px height). Both are registered in
`MainWindow.__init__()`'s `_init_geometry(..., splitters={"keys": ...,
"detail": ...})` call, under different keys — `window_state.py` persists
each `QSplitter.saveState()` blob independently, keyed by
`(state_key, splitter_key)`.

**Toolbar position and visibility** (`MainWindow` only) is opted into
separately via `_init_geometry(..., toolbars=True)`, persisting
`QMainWindow.saveState()` (position, order, floating state and visibility
of every toolbar/dock widget) alongside geometry, restored the same way on
first show. **View → Reset toolbars** (`actionResetToolbars`, icon
PBIcons' `previous.svg`) restores the pristine, first-run layout: a copy
of `self.saveState()` is captured in `MainWindow.__init__()` right after
`setupUi()` — before `_init_geometry()` gets a chance to `restoreState()`
a previously-saved (possibly customized) layout over it — and
`_on_reset_toolbars()` calls `self.restoreState()` with that capture and
immediately persists it too, so the reset sticks even if the window is
never otherwise moved before being closed. Deliberately a menu entry only,
no toolbar button: a toolbar button for "reset toolbars" would disappear
along with everything else if a user hid the very toolbar it lived on.

**Main key list column widths** (`treeKeys`, not the Signatures tab's own
list — not worth the extra persisted state for a lazily-loaded tab most
sessions never open) are persisted the same way, but not through
`GeometryMixin`'s generic `splitters`/`toolbars` knobs: restoring a column
width needs `KeyListView` told about it (see next paragraph), which a
plain dict of raw `QHeaderView`s handed to `_init_geometry()` couldn't
express. `MainWindow` instead overrides `_restore_geometry()`/
`_save_geometry()`, calling `super()` first and then handling
`window_state.save_header_state()`/`load_header_state()` (mirroring
`save_splitter_state()`/`load_splitter_state()`'s
`(window_key, sub_key)` shape) itself — still driven by the exact same
`showEvent`/`closeEvent` hooks `GeometryMixin` already wires up, just one
more thing persisted from within them.

`KeyListView.set_keys()` unconditionally called `resizeColumnToContents()`
on every column on every refresh (a keyring reload happens after almost
every key operation) — which would otherwise silently undo a just-restored
width the very first time the keyring reloads after startup, since that
reload's `set_keys()` call runs *after* `_restore_geometry()` (the
keyserver/gpg listing behind it is asynchronous, restoration is not).
`KeyListView.restore_column_widths()` sets an internal `_columns_restored`
flag precisely to suppress that auto-sizing going forward once a real
restore has happened; a column resized by hand mid-session *without* ever
going through `restore_column_widths()` is **not** protected this way and
still gets silently re-auto-sized on the next refresh — an accepted,
narrower gap than the one actually reported, and consistent with how the
lock/unlock column's width is *always* force-set on every `set_keys()`
call regardless (see "Key list & detail view" above), unaffected by this
flag either way since it was never meant to be user-resized in the first
place. A signal-based alternative (detect any resize via `QHeaderView.
sectionResized`) was tried and abandoned: verified empirically that
`restoreState()` does not emit it at all, so it can't distinguish "a
state was restored" from "nothing happened yet".

## Auto-update

`platform/auto_update.py::perform_auto_update()` downloads the latest GitHub
release for the running OS/arch and replaces the current executable in
place (single-file swap on Linux/Windows, `.app` bundle swap on macOS).

**Only meaningful for a PyInstaller-frozen executable**:
`perform_auto_update()` immediately refuses with an error when
`sys.frozen` is falsy, which is always the case for a source checkout, a
`pip`/PyPI install, or under pytest. The `--auto-update` CLI flag itself
is only *registered* when frozen (`_build_parser(frozen=...)`), so a
source/dev run doesn't even see it in `--help`.

The GitHub repo it checks (`_REPO` in `auto_update.py`) is a placeholder —
this project isn't published yet (see CLAUDE.md). The whole feature stays
inert until this project is actually published and real releases exist;
the CLI surface and packaging naming convention (`pbnightingale-<version>-
<os>-<arch>`, see "Packaging" below) were settled ahead of time to match.

## Packaging

`pbnightingale.spec` drives PyInstaller: `make dist` builds a standalone
executable for the *current* platform only — PyInstaller doesn't
cross-compile, so a Linux/Windows/macOS release means running `make dist`
natively on each — and `make srcdist` builds a matching source archive via
`git archive`.

Both derive their version through `tools/git_version.sh`, per CLAUDE.md's
PyInstaller rule: the exact tag stripped of its `v` prefix when `HEAD` is
tagged *and* the working tree is clean, else `dev`. `make dist` passes it
to the spec file via the `PBNIGHTINGALE_VERSION` env var; a direct
`pyinstaller pbnightingale.spec` (no env var set) falls back to the static
`project.version` in `pyproject.toml`. Output naming:

- Linux: `dist/pbnightingale-<version>-linux-<arch>` (single file)
- Windows: `dist/pbnightingale-<version>-windows-<arch>.exe` (single file)
- macOS: `dist/pbnightingale-<version>-macos-<arch>.app` (bundle; also
  collected as a plain directory of the same name alongside it)
- Source archive (either OS): `dist/pbnightingale-<version>-src.tar.gz`

This naming is not cosmetic — `platform/auto_update.py::_find_asset()`
matches GitHub release assets against this exact `pbnightingale-<prefix>`/
`<suffix>` shape (see "Auto-update" above), so the spec file and the
updater's `_ARCH_MAP`/`asset_suffix()` must stay in lockstep.

Two known PyInstaller gotchas, both empirically verified and not
re-derived here:

- **Fonts, Linux only.** PyInstaller bundles the conda env's fonts
  (`fonts-conda-ecosystem`, added as a pixi dependency purely for this —
  the app itself never imports it) so rendering is identical regardless of
  what's installed on the target machine, but the `fontconfig` config
  PyInstaller captures at build time hard-codes the *build* machine's own
  conda prefix path, which doesn't exist on the target machine. Two layers,
  both needed — verified against a real machine with no conda install at
  all, not just reasoned about: the runtime hook alone was not enough,
  fontconfig itself (or the `libfontconfig.so.1` PyInstaller bundles) can
  be missing or behave unpredictably on the target, and Qt then silently
  falls back to whatever generic font it finds instead of erroring:
  - `hooks/pyi_rth_fonts.py` writes a fresh, portable `fonts.conf` into
    the frozen app's temp dir at startup (pointing at the bundled
    `fonts/` plus the target's own system fonts) and forces
    `libfontconfig` to reinitialize against it before Qt's font database
    is populated. First line of defense, not sufficient by itself.
  - `__main__.py::_load_bundled_fonts()` (frozen builds only, called right
    after `QApplication` is constructed) registers every bundled `.ttf`
    directly into Qt's font database via `QFontDatabase.addApplicationFont()`
    — this bypasses fontconfig entirely — then explicitly sets the
    application's default font to "Ubuntu" (one of the bundled families)
    so rendering is deterministic even when fontconfig fails outright on
    the target. This is the fix that actually holds; the runtime hook is
    a nicety on top of it, not a substitute for it.
- **OpenSSL, Linux only.** PyInstaller's binary scan can resolve
  `libssl.so.3`/`libcrypto.so.3` to the *system* copy (found via the
  default `ld.so.cache` search path) instead of the conda env's own copy
  that `_ssl`/`_hashlib` were actually linked against. The mismatched
  system copy can be missing symbols the bundled extensions need, which
  breaks `--auto-update`'s HTTPS request at runtime with "unknown url
  type: https" — not caught by `make ci` (that runs unfrozen). The spec
  file force-substitutes the conda env's own `libssl.so.3`/`libcrypto.so.3`
  into `Analysis.binaries` after the scan, before building the `PYZ`.

`ssl` is also listed explicitly in `hiddenimports`: `urllib.request` (used
by `--auto-update`) imports it lazily inside a `try`/`except`, which
PyInstaller's static analysis misses.

## Documentation

Sphinx docs under `docs/`, published on Read the Docs, using
`sphinx_rtd_theme` with an at-build-time CHANGELOG.md → `changelog.rst`
conversion (see its own docstring in `conf.py`), plus **narrative-only
i18n** for the user manual.

**Scope split.** Only `index.rst` and everything under `manual/` (the
user manual — GPG/PGP concepts for a complete beginner, then a per-feature
walkthrough of the app) is translated. `api.rst` (autodoc reference) and
`changelog.rst` (generated, English-only per CLAUDE.md's own CHANGELOG
rule) never are — there's no reader-facing value in a translated API
reference or a translated changelog, and translating either would just be
upkeep with no payoff.

**i18n wiring** (`conf.py`): `locale_dirs = ["locale/"]` +
`gettext_compact = False` (one `.po` per source file, not one giant
catalog — makes the narrative-only scope enforceable, since a source
file's own path is what `make docs-translate` filters on) and
`language = os.environ.get("READTHEDOCS_LANGUAGE", "en")` — RTD injects
`READTHEDOCS_LANGUAGE` per project (see below), and a local build with no
such env var falls back to English, this project's source language
(`full-en` mode). Locally, `make docs LANG=fr` sets it for you and builds
into `docs/_build/html-fr/` (English stays in `docs/_build/html/`). `LANG`
is only honored on the make command line, never from the environment,
where it is the user's own locale (`fr_FR.UTF-8`): a plain `make docs`
always builds English. The recipe also drops `LANG` from sphinx-build's
environment in that case, since make exports command-line variables to
recipes and sphinx-build crashes in `locale.setlocale()` on `LANG=fr`.
`make docs-translate` (`sphinx-build -b gettext` scoped
to `docs/index.rst docs/manual/*.rst`, then `sphinx-intl update -d
docs/locale -l fr`) extracts/syncs; `make docs-stats` (`sphinx-intl stat`)
reports per-file translated/fuzzy/untranslated counts. Both are genuinely
separate from `make translate`/`tools/po_check.py` (the app's own UI
string catalog, pybabel-based, single domain) — different toolchain,
different files, no shared code between them despite both being ".po
files for PBNightingale."

Gotcha found empirically: `sphinx-build -b gettext <src> <out> <paths>`
takes individual **files**, not a directory — passing `docs/manual` as a
trailing path is silently ignored (with only a warning, easy to miss),
extracting nothing from it. `DOCS_NARRATIVE` in the Makefile expands to
an explicit `$(wildcard docs/manual/*.rst)` file list instead.

**autodoc vs. PySide6/shiboken**: `autodoc_mock_imports` mocks `PySide6`
itself plus every `*_ui.py` module, to dodge shiboken's own
import hook choking on `inspect.getsource()` against a `MagicMock` — but
computed from the source tree (`_UI_ROOT.glob("*_ui.py")`) rather than
hardcoded, since this app has ~25 dialogs. Three real (non-`_ui`) modules still can't
be autodoc'd even so: `key_list_view.py` and `import_key_dialog.py` each
define a module-level `Qt.ItemDataRole.UserRole [+ N]` constant (custom
`QTreeWidgetItem` data roles), and `search_key_dialog.py` transitively
imports from `key_list_view`. Evaluating `+` against the mock standing in
for `Qt.ItemDataRole.UserRole` doesn't fail cleanly — it raises from
*inside* PySide6's own shiboken import hook, which then poisons every
other module's otherwise-correctly-mocked import for the rest of the
process with a spurious "wrapper loop when unwrapping" `ValueError`.
Verified empirically, reproducibly, isolated to exactly these three
across repeated clean builds. Their `automodule` sections are simply left
out of `api.rst` (with a `.. note::` explaining why) rather than added to
`autodoc_mock_imports` — mocking a real logic module would only render an
empty section, no better than omitting it. `autosummary_generate` stays
`True` (unused — no `.. autosummary::` tables in `api.rst`) deliberately:
flipping it to `False` was tried and made things
*worse* (the same poisoning cascades to every module processed after the
first `_ui.py` mock instead of staying isolated to the three offenders) —
not fully root-caused, kept as found since it demonstrably works.

**Logo**: PBNightingale's only app icon is the raster
`resources/pbnightingale.png` — `conf.py` copies it into `_static/`
byte-for-byte at build time; no `viewBox`-derived `width`/`height` fixup
needed, unlike a vector app icon would require.

**Read the Docs**: `.readthedocs.yaml` builds via `pip install .[dev]`
(the `dev` extra now carries `sphinx`/`sphinx-rtd-theme`/
`sphinx-autobuild`/`sphinx-intl` alongside the existing lint/test tools)
rather than a separate `docs/requirements.txt` install step (kept anyway, for a docs-only build
outside the full dev extra). One RTD *project* per language, all
pointing at this same repo, each with its own language set under
Admin → Settings → Language (this is what injects `READTHEDOCS_LANGUAGE`,
consumed above) — the main (English) project then lists each language
project under Admin → Translations to turn on the flyout switcher. Manual
dashboard steps, no repo-side automation possible for this part.

**License**: the documentation text is CC BY-NC-SA 4.0 — a separate
license from the code (GPL-3.0-only) and a *different* CC BY-NC-SA
grantor than the icons (PBIcons' own, via `LICENSE-ICONS`), even though
both happen to use the same license terms. `LICENSE-DOCS` at the repo
root carries the full text (a duplicate of `LICENSE-ICONS`' — same
license, unrelated material); `pyproject.toml`'s `license-files` lists
it alongside the other two, and `docs/index.rst` states it in the
published manual itself (narrative content, so it gets the same French
translation as everything else under "Scope split" above) rather than
leaving it as a repo-only README/CODING.md footnote a reader of the
hosted site would never see.

## Coding conventions

- `full-en` mode: identifiers, comments, docstrings and commit messages in
  English (see CLAUDE.md).
- All icons are SVG files under `src/pbnightingale/resources/`, resolved via
  `resources.path(name)` and wrapped in `QIcon(...)` — never embed icon data
  inline or reference a system icon theme (keeps rendering identical across
  Linux/Windows/macOS). The application/packaging icon is the raster
  `pbnightingale.png`/`.ico`/`.icns` set instead (a full-color illustration,
  not a flat toolbar glyph).
- Icons are sourced from the shared **PBIcons** asset repository, not
  designed ad hoc per project. `make update-icons` (wraps
  `tools/update_icons.py`) syncs `resources/*.svg` and the app icon files
  from a local PBIcons checkout (sibling of this project's root) or,
  failing that, PBIcons' GitHub repo. Run it with no arguments
  (`make update-icons`) to sync everything (icons this app invented, like
  the GPG-specific toolbar glyphs, aren't in PBIcons and are reported as
  errors — that's expected, not a bug), `make update-icons ARGS="--dry-run"`
  to preview, or `make update-icons ARGS="quit.svg"` to sync specific files.
  These icon files are licensed CC BY-NC-SA 4.0, not GPL-3.0-only like the
  rest of the codebase — see "License" below and [LICENSE-ICONS](LICENSE-ICONS).
- All OS-specific code goes in `pbnightingale/platform/`.
- `core/` stays framework-agnostic — no PySide6 imports there.
- GPG operations must never touch the real user's `~/.gnupg` — every test
  uses an isolated temporary `GNUPGHOME` (see "GPG backend" above and
  `tests/conftest.py`'s autouse fixtures).
- Never read/write the real user's settings either. `tests/conftest.py`'s
  `_isolated_config` fixture (autouse) redirects `settings.py`'s
  `configure()` to a fresh temp dir for every test automatically.
- Docstrings are [numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html)
  style, parsed via `sphinx.ext.napoleon` (`docs/conf.py`:
  `napoleon_numpy_docstring = True`, `napoleon_google_docstring = False`).
  Every function/method/class in `core/`, `platform/` and top-level modules,
  and every `ui/*.py` module except `*_ui.py` layout files (pure
  declarative widget construction, nothing to document), gets one —
  `*_ui.py` files are skipped entirely. Since every signature is already type-hinted and
  `autodoc_typehints = "description"` pulls those into the rendered docs
  automatically, a docstring must not repeat a type:
  - `Parameters`: just the bare parameter name, no `: type` suffix.
  - `Returns`: a bare `:` in place of the type, then the description
    indented below it (numpydoc's syntax for "no type").
  - Trivial members (no parameters, no return value, nothing non-obvious)
    keep a one-line summary only — an empty `Parameters`/`Returns` section
    is noise, not documentation.
  - Class/dataclass **attributes** are documented with a `#:` comment
    immediately above the field (Sphinx's own convention for
    autodoc-documented attributes), not inside the class docstring's body.
  - Public module-level constants (no leading underscore) get the same
    `#:` comment treatment; private (`_`-prefixed) ones keep ordinary `#`
    comments, unchanged.

## Testing

`tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` so the suite runs
headless, and restores `builtins._` after any test that calls
`i18n.setup()` with a non-English catalogue (gettext's `install()` mutates
it process-wide; without this a test could leak translated strings into
unrelated tests). Use `qtbot` (pytest-qt) to instantiate widgets — never a
manual `QApplication`.

**gpg-agent cleanup**: every test's `GNUPGHOME` is its own disposable
directory (never the real user's keyring), but gpg itself autostarts a
`gpg-agent` daemon bound to that directory the first time it needs one —
and unlike the `gpg` subprocess itself, that daemon keeps running long
after the directory (and the test) are gone. Reported after a real
`ps -ef | grep gpg-agen[t]` turned up 300+ stray processes accumulated
from repeated local test runs. `_kill_gpg_agents_under()` (autouse, via
`_kill_gpg_agents_after_test` for the common case — a test's own
`tmp_path`, which is what `GPGBackend(tmp_path / "home")`/`"source"`/
`"dest"` are actually built on — and again in the `gnupg_home` fixture's
own teardown for `default_backend()`-based tests, a *different* root)
walks the directory tree looking for gpg's own telltale files
(`pubring.kbx`, `trustdb.gpg`, …) and runs `gpgconf --homedir <dir>
--kill gpg-agent` for each match — the same graceful-shutdown mechanism
`GPGBackend._restart_agent()` already uses in production. The marker-file
check exists purely to skip the (harmless but not free) subprocess spawn
for the many tests that never touch gpg at all.

## License

Code: GPL-3.0-only — see [LICENSE](LICENSE).

Icons (`src/pbnightingale/resources/*.svg`, `*.png`, `*.ico`, `*.icns`),
sourced from the shared **PBIcons** asset repository: CC BY-NC-SA 4.0 — see
[LICENSE-ICONS](LICENSE-ICONS).

Documentation (`docs/`, published on Read the Docs): CC BY-NC-SA 4.0 — see
[LICENSE-DOCS](LICENSE-DOCS).
