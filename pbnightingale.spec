# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PBNightingale.

The output name embeds the version and the target platform so that builds
for different systems can coexist in the same directory:

  Linux   → dist/pbnightingale-<version>-linux-x86_64
  Windows → dist/pbnightingale-<version>-windows-x86_64.exe
  macOS   → dist/pbnightingale-<version>-macos-arm64.app

Build with:  make dist
"""

import os
import platform
import sys
import tomllib
from pathlib import Path

# ---------------------------------------------------------------------------
# Version — from PBNIGHTINGALE_VERSION env var (set by `make dist` via
# tools/git_version.sh), falling back to pyproject.toml for direct
# `pyinstaller pbnightingale.spec` invocations.
# ---------------------------------------------------------------------------

_version = os.environ.get("PBNIGHTINGALE_VERSION")
if not _version:
    with open("pyproject.toml", "rb") as _f:
        _version = tomllib.load(_f)["project"]["version"]

# ---------------------------------------------------------------------------
# Platform tag  (OS-arch, e.g. linux-x86_64, windows-x86_64, macos-arm64)
# ---------------------------------------------------------------------------

_machine = platform.machine().lower()
_arch = {
    "x86_64": "x86_64",
    "amd64":  "x86_64",   # Windows reports AMD64
    "arm64":  "arm64",    # macOS Apple Silicon
    "aarch64":"arm64",    # Linux ARM 64-bit
}.get(_machine, _machine)

if sys.platform == "linux":
    _os = "linux"
elif sys.platform == "win32":
    _os = "windows"
elif sys.platform == "darwin":
    _os = "macos"
else:
    _os = sys.platform

_artifact_name = f"pbnightingale-{_version}-{_os}-{_arch}"

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------

# Compiled gettext catalogues (.mo).  Source layout:
#   src/pbnightingale/locale/<lang>/LC_MESSAGES/pbnightingale.mo
# Destination inside the frozen app (mirrors the installed package layout):
#   pbnightingale/locale/<lang>/LC_MESSAGES/pbnightingale.mo
_locale_root = Path("src/pbnightingale/locale")
_datas = [
    (str(mo), f"pbnightingale/locale/{mo.parts[-3]}/LC_MESSAGES")
    for mo in sorted(_locale_root.glob("*/LC_MESSAGES/pbnightingale.mo"))
]

# Bundled resources (icons, …).
_datas += [("src/pbnightingale/resources", "pbnightingale/resources")]

# Native per-platform icon (synced from PBIcons via tools/update_icons.py).
_icons = {
    "win32": "src/pbnightingale/resources/pbnightingale.ico",
    "darwin": "src/pbnightingale/resources/pbnightingale.icns",
}
icon = _icons.get(sys.platform)

# Conda fonts: bundled to guarantee identical rendering across machines.
# On Linux, fontconfig resolves fonts via absolute paths written into fonts.conf
# at build time; those paths do not exist on the target machine.
# The runtime hook hooks/pyi_rth_fonts.py generates a portable fonts.conf at startup.
_conda_fonts = Path(sys.prefix) / "fonts"
if _conda_fonts.is_dir():
    _datas += [(str(_conda_fonts), "fonts")]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["src/pbnightingale/__main__.py"],
    # Needed so that `import pbnightingale` resolves against the src tree even
    # without an editable install in the build environment.
    pathex=["src"],
    datas=_datas,
    # The platform sub-package is discovered dynamically; list it explicitly
    # so PyInstaller does not miss any module.
    hiddenimports=[
        "pbnightingale.platform",
        "pbnightingale.platform.dirs",
        "pbnightingale.platform.locale",
        "pbnightingale.platform.auto_update",
        # urllib.request (used by --auto-update) imports ssl lazily inside a
        # try/except, so PyInstaller's static analysis misses it and the
        # frozen build fails HTTPS requests with "unknown url type: https"
        "ssl",
    ],
    hookspath=[],
    runtime_hooks=["hooks/pyi_rth_fonts.py"],
    # Exclude heavy stdlib modules that PBNightingale never uses.
    # http is not excluded: urllib.request (used by --auto-update) imports
    # http.client at module load time.
    excludes=["tkinter", "unittest", "xml", "numpy", "matplotlib"],
    noarchive=False,
)

# ---------------------------------------------------------------------------
# OpenSSL binary resolution (Linux)
# ---------------------------------------------------------------------------

# PyInstaller's binary dependency scan can resolve libssl.so.3 / libcrypto.so.3
# to the system copy (found via the default ld.so.cache search path) instead
# of the conda env's own copy that _ssl/_hashlib were actually linked
# against, silently swapping in an older OpenSSL missing symbols the bundled
# extensions need — this breaks --auto-update's HTTPS request at runtime with
# "unknown url type: https". Force the env's own copies back in.
if sys.platform == "linux":
    _conda_lib = Path(sys.prefix) / "lib"
    for _lib_name in ("libssl.so.3", "libcrypto.so.3"):
        _lib_path = _conda_lib / _lib_name
        if _lib_path.is_file():
            a.binaries = [
                entry for entry in a.binaries if entry[0] != _lib_name
            ] + [(_lib_name, str(_lib_path), "BINARY")]

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Platform-specific packaging
# ---------------------------------------------------------------------------

if sys.platform == "darwin":
    # macOS: directory-based .app bundle (Apple convention).
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=_artifact_name,
        console=False,
        icon=icon,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name=_artifact_name,
    )
    BUNDLE(
        coll,
        name=f"{_artifact_name}.app",
        icon=icon,
        bundle_identifier="net.cardolan.pbnightingale",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": _version,
            "CFBundleName": "PBNightingale",
        },
    )

else:
    # Linux / Windows: single self-contained file.
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name=_artifact_name,
        # No console window on Windows; harmless on Linux.
        console=False,
        icon=icon,
    )
