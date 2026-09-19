#!/usr/bin/env python3
"""Build the vendored Pengu Loader source and refresh Rose's runtime loader."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "vendor" / "PenguLoader-1.1.6" / "loader" / "loader.csproj"
BUILD_OUTPUT = ROOT / "build" / "pengu-loader"
RUNTIME_DIR = ROOT / "Pengu Loader"


def _dotnet_with_sdk() -> list[str] | None:
    """Return `dotnet msbuild` only when an SDK is installed.

    A machine with just the .NET runtime also has `dotnet` on PATH, but `dotnet msbuild`
    fails there; returning None lets the Visual Studio MSBuild be tried instead.
    """
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return None
    try:
        result = subprocess.run(
            [dotnet, "--list-sdks"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[WARN] Could not query .NET SDKs: {exc}")
        return None
    if result.returncode != 0 or not result.stdout.strip():
        print("[INFO] dotnet found without an SDK; looking for Visual Studio MSBuild")
        return None
    return [dotnet, "msbuild"]


def _find_msbuild() -> list[str] | None:
    configured = os.environ.get("MSBUILD_EXE")
    if configured and Path(configured).exists():
        return [configured]

    msbuild = shutil.which("msbuild")
    if msbuild:
        return [msbuild]

    # Prefer the .NET SDK over the Visual Studio MSBuild: VS Build Tools without the
    # .NET desktop workload fails with MSB4236 (Microsoft.NET.Sdk not found).
    dotnet = _dotnet_with_sdk()
    if dotnet:
        return dotnet

    vswhere = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        result = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.Component.MSBuild",
                "-find",
                r"MSBuild\**\Bin\MSBuild.exe",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if candidate and Path(candidate).exists():
                return [candidate]

    return None


def _build_environment() -> dict[str, str]:
    """Avoid duplicate case variants of PATH in child .NET processes."""
    environment = dict(os.environ)
    path_value = next((value for key, value in environment.items() if key.lower() == "path"), "")
    for key in list(environment):
        if key.lower() == "path":
            del environment[key]
    environment["Path"] = path_value
    return environment


def build_loader() -> int:
    if not PROJECT.exists():
        print(f"[ERROR] Pengu Loader project not found: {PROJECT}")
        return 1

    msbuild = _find_msbuild()
    if not msbuild:
        print("[ERROR] MSBuild was not found.")
        print("        Install the Visual Studio .NET desktop build tools, or set MSBUILD_EXE.")
        return 1

    if BUILD_OUTPUT.exists():
        shutil.rmtree(BUILD_OUTPUT)
    BUILD_OUTPUT.mkdir(parents=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    output_path = str(BUILD_OUTPUT) + os.sep
    command = msbuild + [
        str(PROJECT),
        # /restore runs NuGet restore in its own evaluation before the build. "/t:Restore,Build"
        # restores and builds in one evaluation, so on a clean checkout (no obj/) the build
        # misses the restored .NET Framework reference assemblies and fails with MSB3644.
        "/restore",
        "/t:Build",
        "/m",
        "/v:minimal",
        "/p:Configuration=Release",
        "/p:Platform=AnyCPU",
        f"/p:OutputPath={output_path}",
        # The upstream project expects a signing key that is not distributed.
        # Signing does not affect loader behavior or the generated executable.
        "/p:SignAssembly=false",
        "/p:UseSharedCompilation=false",
        "/p:NuGetAudit=false",
        "/p:RestoreIgnoreFailedSources=true",
    ]

    print(f"Building Pengu Loader from {PROJECT}")
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT.parent, env=_build_environment(), check=False)
    if result.returncode != 0:
        print(f"[ERROR] Pengu Loader build failed with exit code {result.returncode}.")
        return result.returncode

    generated_exe = BUILD_OUTPUT / "Pengu Loader.exe"
    if not generated_exe.exists():
        print(f"[ERROR] Build succeeded but did not produce {generated_exe}")
        return 1

    copied = []
    try:
        for source in BUILD_OUTPUT.iterdir():
            if source.is_file() and source.suffix.lower() in {".exe", ".config", ".dll"}:
                destination = RUNTIME_DIR / source.name
                shutil.copy2(source, destination)
                copied.append(destination.name)
    except PermissionError as exc:
        print(f"[ERROR] Could not update the runtime loader: {exc}")
        print("        Close Rose/Pengu Loader and run the build again.")
        return 1

    if "Pengu Loader.exe" not in copied:
        print("[ERROR] Generated Pengu Loader.exe was not copied to the runtime directory.")
        return 1

    print(f"[OK] Installed source-built Pengu Loader ({', '.join(sorted(copied))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_loader())