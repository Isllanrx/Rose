import builtins
import ctypes
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import psutil

import main as rose_main
from injection.game import game_monitor
from injection.game.game_monitor import GameMonitor
from main.core import cleanup
from utils.core import logging as rose_logging


class FakeGameProcess:
    pid = 4242

    def __init__(self):
        self.suspended = True
        self.resume_calls = 0

    def status(self):
        return psutil.STATUS_STOPPED if self.suspended else psutil.STATUS_RUNNING

    def resume(self):
        self.resume_calls += 1
        self.suspended = False


class CleanupTestCase(unittest.TestCase):
    def setUp(self):
        for name in ("cleanup_lock_file", "cleanup_console"):
            patcher = patch.object(cleanup, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        patcher = patch.object(cleanup.pengu_loader, "deactivate_on_exit")
        self.deactivate = patcher.start()
        self.addCleanup(patcher.stop)
        self.thread_manager = Mock()
        self.thread_manager.stop_all.return_value = ([], 0.1)

    def run_cleanup(self, injection_manager):
        cleanup.perform_cleanup(Mock(), self.thread_manager, None, injection_manager)


class CleanupResumesSuspendedGameTests(CleanupTestCase):
    """Closing Rose while mkoverlay holds the game suspended must not leave League frozen."""

    def test_game_suspended_by_finished_monitor_is_resumed_on_shutdown(self):
        monitor = GameMonitor(lambda: 60)
        game = FakeGameProcess()
        monitor._suspended_game_process = game
        manager = Mock()
        manager.resume_if_suspended.side_effect = monitor.resume_if_suspended

        with patch.object(game_monitor.time, "sleep"):
            self.run_cleanup(manager)

        self.assertFalse(game.suspended)
        self.assertIsNone(monitor.get_suspended_game_process())

    def test_game_is_resumed_before_mod_tools_are_killed(self):
        manager = Mock()

        self.run_cleanup(manager)

        calls = [c[0] for c in manager.mock_calls]
        self.assertLess(calls.index("resume_if_suspended"), calls.index("kill_all_modtools_processes"))

    def test_no_suspended_game_means_no_resume(self):
        monitor = GameMonitor(lambda: 60)
        manager = Mock()
        manager.resume_if_suspended.side_effect = monitor.resume_if_suspended

        with patch.object(game_monitor, "log") as monitor_log:
            self.run_cleanup(manager)

        monitor_log.info.assert_not_called()
        manager.kill_all_modtools_processes.assert_called_once()


class CleanupStepIsolationTests(CleanupTestCase):
    """One failing shutdown step must not skip killing mod-tools or releasing the lock file."""

    def test_pengu_failure_still_kills_mod_tools_and_releases_lock(self):
        self.deactivate.side_effect = RuntimeError("cli blocked")
        manager = Mock()

        with self.assertLogs("tracer", level="WARNING") as logs:
            self.run_cleanup(manager)

        manager.kill_all_modtools_processes.assert_called_once()
        self.cleanup_lock_file.assert_called()
        self.assertIn("cli blocked", "\n".join(logs.output))

    def test_resume_failure_still_runs_remaining_steps(self):
        manager = Mock()
        manager.resume_if_suspended.side_effect = RuntimeError("access denied")

        with self.assertLogs("tracer", level="WARNING") as logs:
            self.run_cleanup(manager)

        self.deactivate.assert_called_once()
        manager.kill_all_modtools_processes.assert_called_once()
        self.cleanup_lock_file.assert_called()
        self.assertIn("access denied", "\n".join(logs.output))

    def test_cleanup_without_injection_manager(self):
        self.run_cleanup(None)

        self.deactivate.assert_called_once()
        self.cleanup_lock_file.assert_called()


class UncaughtThreadExceptionLoggingTests(unittest.TestCase):
    """The frozen app has no console; a worker thread dying must leave a traceback in the log."""

    def setUp(self):
        self.addCleanup(setattr, threading, "excepthook", threading.excepthook)
        threading.excepthook = lambda args: None

    def run_thread(self, target, name="PhaseThread"):
        thread = threading.Thread(target=target, name=name)
        thread.start()
        thread.join()

    def test_exception_in_thread_is_logged_with_traceback(self):
        rose_logging.install_uncaught_exception_logging()

        def crash():
            raise ValueError("phase handler exploded")

        with self.assertLogs("tracer", level="CRITICAL") as logs:
            self.run_thread(crash)

        output = "\n".join(logs.output)
        self.assertIn("Uncaught exception in thread PhaseThread: ValueError", output)
        self.assertIn("ValueError: phase handler exploded", output)

    def test_installing_twice_logs_once(self):
        rose_logging.install_uncaught_exception_logging()
        rose_logging.install_uncaught_exception_logging()

        with self.assertLogs("tracer", level="CRITICAL") as logs:
            self.run_thread(lambda: 1 / 0)

        self.assertEqual(len(logs.output), 1)

    def test_previous_hook_still_runs(self):
        previous = Mock()
        threading.excepthook = previous
        rose_logging.install_uncaught_exception_logging()

        with self.assertLogs("tracer", level="CRITICAL"):
            self.run_thread(lambda: 1 / 0)

        previous.assert_called_once()

    def test_system_exit_is_not_logged(self):
        rose_logging.install_uncaught_exception_logging()

        with self.assertNoLogs("tracer", level="CRITICAL"):
            self.run_thread(lambda: (_ for _ in ()).throw(SystemExit(0)))


class NativeDllDialogTests(unittest.TestCase):
    """Fallback dialog without tkinter uses MB_OKCANCEL: OK returns IDOK (1), Cancel returns IDCANCEL (2)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        real_import = builtins.__import__

        def import_without_tkinter(name, *args, **kwargs):
            if name == "tkinter" or name.startswith("tkinter."):
                raise ImportError("tkinter unavailable")
            return real_import(name, *args, **kwargs)

        patcher = patch.object(builtins, "__import__", side_effect=import_without_tkinter)
        patcher.start()
        self.addCleanup(patcher.stop)

    def show_dialog(self, button):
        with (
            patch.object(ctypes.windll.user32, "MessageBoxW", return_value=button),
            patch("subprocess.run") as run,
            patch("webbrowser.open") as browser,
        ):
            rose_main._show_dll_dialog_legacy(Path(self.temp_dir.name))
        return run, browser

    def test_ok_opens_tools_folder(self):
        run, browser = self.show_dialog(1)

        run.assert_called_once()
        self.assertEqual(run.call_args[0][0], ["explorer", self.temp_dir.name])
        browser.assert_not_called()

    def test_cancel_does_nothing(self):
        run, browser = self.show_dialog(2)

        run.assert_not_called()
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
