"""Smoke-check a PyInstaller build of Rose without running it.

Rose.exe needs admin rights, the tray and a running League client, so CI cannot start
it. This checks what a broken build actually looked like in the past: missing runtime
files (the "Failed to start embedded python interpreter" users see, #66), missing
assets or bundled tools, app modules absent from the frozen archive, and the user
supplied cslol-dll.dll leaking into a distributable build.

Usage:
    python scripts/verify_build.py               # check dist/Rose
    python scripts/verify_build.py --fresh-build # also require that no cslol-dll.dll was bundled
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "Rose"
INTERNAL = DIST / "_internal"

REQUIRED_FILES = [
    DIST / "Rose.exe",
    INTERNAL / "python312.dll",
    INTERNAL / "base_library.zip",
    INTERNAL / "VCRUNTIME140.dll",
    INTERNAL / "certifi" / "cacert.pem",
    INTERNAL / "assets" / "tray_ready.png",
    INTERNAL / "assets" / "tray_starting.png",
    INTERNAL / "injection" / "tools" / "mod-tools.exe",
    INTERNAL / "Pengu Loader" / "Pengu Loader.exe",
    INTERNAL / "Pengu Loader" / "core.dll",
]

PLUGINS = ["ROSE-SkinMonitor", "ROSE-UI", "ROSE-ChromaWheel", "ROSE-SettingsPanel"]

# One module per subsystem: if any is missing from the PYZ the app fails at import time.
REQUIRED_MODULES = [
    "config",
    "main",
    "threads.websocket.websocket_event_handler",
    "threads.utilities.loadout_ticker",
    "pengu.communication.message_handler",
    "injection.core.manager",
    "injection.classic.classic_skin_builder",
    "injection.compat.wad_index",
    "lcu.core.lcu_api",
    "utils.core.logging",
    "xxhash",
    "zstandard",
    "websocket",
    "websockets",
]


def frozen_modules(exe: Path) -> set[str]:
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    archive = CArchiveReader(str(exe))
    with tempfile.TemporaryDirectory() as tmp:
        pyz_path = Path(tmp) / "PYZ-00.pyz"
        pyz_path.write_bytes(archive.extract("PYZ-00.pyz"))
        pyz = ZlibArchiveReader(str(pyz_path))
        names = set(pyz.toc.keys())
        del pyz
    return names


def main() -> int:
    problems: list[str] = []

    for path in REQUIRED_FILES:
        if not path.is_file():
            problems.append(f"missing file: {path.relative_to(ROOT)}")

    plugins_dir = INTERNAL / "Pengu Loader" / "plugins"
    for plugin in PLUGINS:
        if not (plugins_dir / plugin / "index.js").is_file():
            problems.append(f"missing plugin: {plugin}/index.js")

    if "--fresh-build" in sys.argv:
        leaked = list(DIST.rglob("cslol-dll.dll"))
        if leaked:
            problems.append("cslol-dll.dll must never be bundled: " + ", ".join(str(p) for p in leaked))

    exe = DIST / "Rose.exe"
    if exe.is_file():
        try:
            modules = frozen_modules(exe)
        except Exception as exc:
            problems.append(f"could not read the frozen archive: {exc}")
        else:
            for module in REQUIRED_MODULES:
                if module not in modules:
                    problems.append(f"module not frozen into Rose.exe: {module}")
            print(f"Frozen archive has {len(modules)} modules")

    if problems:
        print("Build verification FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Build verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
