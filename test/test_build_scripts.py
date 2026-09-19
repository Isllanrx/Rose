"""Build scripts must work without the local workarounds (MSBUILD_EXE wrapper, venv on PATH)."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pengu = _load("build_pengu_loader")
pyi = _load("build_pyinstaller")


def _completed(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _which(found):
    return lambda name: found.get(name)


class DotnetSdkDetectionTests(unittest.TestCase):
    def test_sdk_present_uses_dotnet_msbuild(self):
        with (
            patch.object(pengu.shutil, "which", _which({"dotnet": "C:/dotnet/dotnet.exe"})),
            patch.object(pengu.subprocess, "run", return_value=_completed("10.0.401 [C:\\sdk]\n")),
        ):
            self.assertEqual(pengu._dotnet_with_sdk(), ["C:/dotnet/dotnet.exe", "msbuild"])

    def test_runtime_only_is_not_used(self):
        with (
            patch.object(pengu.shutil, "which", _which({"dotnet": "C:/dotnet/dotnet.exe"})),
            patch.object(pengu.subprocess, "run", return_value=_completed("")),
        ):
            self.assertIsNone(pengu._dotnet_with_sdk())

    def test_query_failure_is_not_used(self):
        with (
            patch.object(pengu.shutil, "which", _which({"dotnet": "C:/dotnet/dotnet.exe"})),
            patch.object(pengu.subprocess, "run", side_effect=subprocess.TimeoutExpired("dotnet", 30)),
        ):
            self.assertIsNone(pengu._dotnet_with_sdk())

    def test_no_dotnet(self):
        with patch.object(pengu.shutil, "which", _which({})):
            self.assertIsNone(pengu._dotnet_with_sdk())


class FindMsbuildOrderTests(unittest.TestCase):
    def test_explicit_msbuild_exe_wins(self):
        with (
            patch.dict(pengu.os.environ, {"MSBUILD_EXE": sys.executable}),
            patch.object(pengu, "_dotnet_with_sdk", return_value=["dotnet", "msbuild"]),
        ):
            self.assertEqual(pengu._find_msbuild(), [sys.executable])

    def test_dotnet_sdk_preferred_over_visual_studio(self):
        with (
            patch.dict(pengu.os.environ, {"MSBUILD_EXE": ""}),
            patch.object(pengu.shutil, "which", _which({})),
            patch.object(pengu, "_dotnet_with_sdk", return_value=["dotnet", "msbuild"]),
        ):
            self.assertEqual(pengu._find_msbuild(), ["dotnet", "msbuild"])

    def test_without_sdk_falls_back_to_visual_studio(self):
        vs_msbuild = sys.executable  # any existing file stands in for MSBuild.exe
        with (
            patch.dict(pengu.os.environ, {"MSBUILD_EXE": "", "ProgramFiles(x86)": str(ROOT)}),
            patch.object(pengu.shutil, "which", _which({})),
            patch.object(pengu, "_dotnet_with_sdk", return_value=None),
            patch.object(pengu.Path, "exists", return_value=True),
            patch.object(pengu.subprocess, "run", return_value=_completed(vs_msbuild + "\n")),
        ):
            self.assertEqual(pengu._find_msbuild(), [vs_msbuild])


class PenguRestoreTests(unittest.TestCase):
    """Restore must run in its own evaluation, or a clean checkout fails with MSB3644."""

    def test_build_uses_a_separate_restore(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(pengu, "BUILD_OUTPUT", Path(tmp) / "out"),
                patch.object(pengu, "RUNTIME_DIR", Path(tmp) / "runtime"),
                patch.object(pengu, "_find_msbuild", return_value=["msbuild"]),
                patch.object(pengu.subprocess, "run", return_value=_completed(returncode=1)) as run,
            ):
                self.assertEqual(pengu.build_loader(), 1)
        command = run.call_args.args[0]
        self.assertIn("/restore", command)
        self.assertNotIn("/t:Restore,Build", command)
        self.assertIn("/t:Build", command)


class PyInstallerInvocationTests(unittest.TestCase):
    def test_runs_pyinstaller_from_the_current_interpreter(self):
        with patch.object(pyi.subprocess, "run", return_value=_completed()) as run:
            self.assertTrue(pyi.build_with_pyinstaller())
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], [sys.executable, "-m", "PyInstaller"])


if __name__ == "__main__":
    unittest.main()
