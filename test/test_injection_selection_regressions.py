import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from injection.overlay.overlay_manager import OverlayManager
from injection.overlay.process_manager import ProcessManager
from state import SharedState
from threads.utilities.skin_name_resolver import SkinNameResolver
from ui.chroma.selection_handler import ChromaSelectionHandler


class RandomModeChromaSelectionTests(unittest.TestCase):
    """Log 16-09-2026 18:24: dice drew 21018, user then picked 21069 via chroma wheel, 21018 was injected."""

    def _state_with_random_mode(self) -> SharedState:
        state = SharedState()
        state.locked_champ_id = 21
        state.last_hovered_skin_id = 21069
        state.random_skin_name = "Miss Fortune Feiticeira"
        state.random_skin_id = 21018
        state.random_mode_active = True
        return state

    def test_explicit_chroma_selection_overrides_random_skin(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21069).handle_selection(21069, "Default")

        self.assertFalse(state.random_mode_active)
        self.assertIsNone(state.random_skin_id)
        self.assertEqual(SkinNameResolver(state).resolve_injection_name(), "skin_21069")

    def test_base_skin_selection_overrides_random_skin(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21069).handle_selection(0, "Base")

        self.assertFalse(state.random_mode_active)

    def test_selecting_the_random_skin_keeps_random_mode(self):
        state = self._state_with_random_mode()

        ChromaSelectionHandler(state, current_skin_id=21018).handle_selection(21018, "Default")

        self.assertTrue(state.random_mode_active)
        self.assertEqual(SkinNameResolver(state).resolve_injection_name(), "skin_21018")


class RunOverlayStopTests(unittest.TestCase):
    """Log 16-09-2026 18:27:35: tray quit killed runoverlay (exit 15) and it was logged as INJECTION FAILED."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        (root / "mods").mkdir()
        self.fake_exe = root / "mod-tools.exe"
        self.fake_exe.write_bytes(b"")
        self.process_manager = ProcessManager()
        self.overlay_manager = OverlayManager(root / "tools", root / "mods", root / "game", self.process_manager)

    def _run(self, runoverlay_script: str, while_running=None) -> int:
        real_popen = subprocess.Popen

        def fake_popen(cmd, *args, **kwargs):
            if cmd[1] == "mkoverlay":
                return real_popen([sys.executable, "-c", "print('ok')"], *args, **kwargs)
            return real_popen([sys.executable, "-c", runoverlay_script], *args, **kwargs)

        with patch("injection.tools.tools_manager.ToolsManager.detect_tools", return_value={"modtools": self.fake_exe}), \
                patch("injection.overlay.overlay_manager.subprocess.Popen", side_effect=fake_popen):
            if while_running:
                threading.Thread(target=while_running, daemon=True).start()
            return self.overlay_manager.mk_run_overlay(["skin"], timeout=30)

    def _wait_for_overlay_process(self):
        deadline = time.time() + 10
        while self.process_manager.current_overlay_process is None and time.time() < deadline:
            time.sleep(0.05)
        return self.process_manager.current_overlay_process

    def test_overlay_terminated_by_shutdown_is_not_a_failure(self):
        def quit_rose():
            proc = self._wait_for_overlay_process()
            time.sleep(0.3)
            self.process_manager.stop_requested = True
            import psutil
            psutil.Process(proc.pid).terminate()

        result = self._run("import time; time.sleep(30)", while_running=quit_rose)

        self.assertEqual(result, 0)

    def test_stop_overlay_process_is_not_a_failure(self):
        def stop():
            self._wait_for_overlay_process()
            time.sleep(0.3)
            self.process_manager.stop_overlay_process()

        result = self._run("import time; time.sleep(30)", while_running=stop)

        self.assertEqual(result, 0)

    def test_overlay_crash_is_still_reported(self):
        self.process_manager.stop_requested = True  # stale flag from a previous cleanup must not hide a crash

        result = self._run("import sys; sys.exit(15)")

        self.assertEqual(result, 15)


if __name__ == "__main__":
    unittest.main()
