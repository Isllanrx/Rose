import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from injection.config import base_skin_tracker
from main.core import signals
from main.core.state import get_app_state


class ShutdownPenguDeactivationTests(unittest.TestCase):
    """A failed Pengu deactivation leaves plugins loaded in the client, so it must be visible in the log."""

    def setUp(self):
        self.app_state = get_app_state()
        self.addCleanup(setattr, self.app_state, "shutting_down", False)
        self.app_state.shutting_down = False

    def test_signal_handler_logs_failed_deactivation(self):
        with (
            patch.object(signals.pengu_loader, "deactivate_on_exit", side_effect=RuntimeError("cli blocked")),
            self.assertLogs("tracer", level="WARNING") as logs,
            self.assertRaises(KeyboardInterrupt),
        ):
            signals.signal_handler(2, None)

        self.assertIn("Failed to deactivate Pengu Loader during shutdown", logs.output[0])
        self.assertIn("cli blocked", "\n".join(logs.output))


class BaseSkinTrackerFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.samples_path = Path(self.temp_dir.name) / "base_skin_samples.json"
        patcher = patch.object(base_skin_tracker, "_data_path", return_value=self.samples_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_corrupted_samples_file_is_logged_and_ignored(self):
        self.samples_path.write_text("{not json", encoding="utf-8")

        with self.assertLogs("tracer", level="WARNING") as logs:
            samples = base_skin_tracker._load_samples()

        self.assertEqual(samples, [])
        self.assertIn("Could not load base skin samples", logs.output[0])

    def test_valid_samples_file_loads_without_warning(self):
        self.samples_path.write_text('[{"elapsed_ms": 120, "confirmed": true}]', encoding="utf-8")

        with self.assertNoLogs("tracer", level="WARNING"):
            samples = base_skin_tracker._load_samples()

        self.assertEqual(len(samples), 1)


class LauncherLogRoutingTests(unittest.TestCase):
    """Launcher runs before the app log is configured; downloader records must reach the updater log."""

    def test_source_records_reach_target_handlers_only_inside_context(self):
        import logging

        from launcher.core.launcher import _route_logger

        source = logging.getLogger("test.route.source")
        target = logging.getLogger("test.route.target")
        target.propagate = False
        records = []

        class Collect(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        handler = Collect(level=logging.DEBUG)
        target.addHandler(handler)
        self.addCleanup(target.removeHandler, handler)
        source.setLevel(logging.NOTSET)

        with _route_logger(source, target):
            source.info("Remote skin SHA: abc12345")
        source.info("after context")

        self.assertEqual(records, ["Remote skin SHA: abc12345"])
        self.assertNotIn(handler, source.handlers)
        self.assertEqual(source.level, logging.NOTSET)

    def test_trace_records_survive_routing_in_debug_log_mode(self):
        import logging

        from launcher.core.launcher import _route_logger
        from utils.core.logging import TRACE

        parent = logging.getLogger("test.route.trace")
        source = logging.getLogger("test.route.trace.source")
        target = logging.getLogger("test.route.trace.target")
        target.propagate = False
        records = []

        class Collect(logging.Handler):
            def emit(self, record):
                records.append(record.levelno)

        handler = Collect(level=TRACE)
        target.addHandler(handler)
        self.addCleanup(target.removeHandler, handler)
        self.addCleanup(parent.setLevel, parent.level)
        parent.setLevel(TRACE)
        source.setLevel(logging.NOTSET)

        with _route_logger(source, target):
            source.log(TRACE, "hash table chunk 3/5")

        self.assertEqual(records, [TRACE])
        self.assertEqual(source.level, logging.NOTSET)


class UpdateCheckFailureTests(unittest.TestCase):
    def test_failed_release_request_is_logged(self):
        from launcher.update import github_client

        with patch.object(github_client.requests, "get", side_effect=OSError("network down")), self.assertLogs("tracer", level="WARNING") as logs:
            release = github_client.GitHubClient().get_latest_release()

        self.assertIsNone(release)
        self.assertIn("network down", logs.output[0])


class IssueReporterFailureTests(unittest.TestCase):
    def test_write_failure_is_logged_without_raising(self):
        from utils.core import issue_reporter

        with patch.object(issue_reporter, "_issues_path", side_effect=PermissionError("denied")), self.assertLogs("tracer", level="DEBUG") as logs:
            issue_reporter.report_issue("LOW_DISK_SPACE", "error", "disk full", dedupe_window_s=0)

        self.assertIn("Could not write diagnostics entry LOW_DISK_SPACE", logs.output[0])


class SavedModSelectionFailureTests(unittest.TestCase):
    def test_failed_historic_map_lookup_is_logged_and_response_still_sent(self):
        import json
        from types import SimpleNamespace

        from pengu.communication import message_handler as mh
        from utils.core import mod_historic

        handler = object.__new__(mh.MessageHandler)
        handler.mod_storage = SimpleNamespace(CATEGORY_MAPS="maps", list_mods_for_category=lambda category: [])
        handler.shared_state = SimpleNamespace()
        sent = []
        handler._send_response = sent.append

        with patch.object(mod_historic, "get_historic_mod", side_effect=OSError("historic file locked")), self.assertLogs(mh.log.name, level="WARNING") as logs:
            handler._handle_request_maps({})

        self.assertIn("Could not load saved map selection", logs.output[0])
        self.assertEqual(json.loads(sent[0])["historicMod"], None)


if __name__ == "__main__":
    unittest.main()
