"""Log noise that buried real problems in user logs (backlog #25 and #64)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from state import SharedState
from threads.handlers.injection_trigger import InjectionTrigger
from threads.websocket.websocket_connection import WebSocketConnection

ROOT = Path(__file__).resolve().parents[1]


class RefusalWarningTests(unittest.TestCase):
    """The ticker retries every tick; a refusal must not repeat its WARNING ~1000 times a second."""

    def setUp(self):
        self.state = SharedState()
        self.state.locked_champ_id = 60055
        self.trigger = InjectionTrigger(MagicMock(), self.state)

    def test_same_refusal_warns_once(self):
        self.state.last_hovered_skin_id = 99009
        with self.assertLogs("tracer", level="WARNING") as logs:
            for _ in range(50):
                self.trigger.trigger_injection("skin_99009", ticker_id=1)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("champion mismatch", logs.output[0])

    def test_new_selection_warns_again(self):
        with self.assertLogs("tracer", level="WARNING") as logs:
            self.state.last_hovered_skin_id = 99009
            self.trigger.trigger_injection("skin_99009", ticker_id=1)
            self.state.last_hovered_skin_id = 98001
            self.trigger.trigger_injection("skin_98001", ticker_id=1)
        self.assertEqual(len(logs.output), 2)

    def test_refusal_still_skips_injection(self):
        manager = MagicMock()
        self.trigger.injection_manager = manager
        self.state.last_hovered_skin_id = 99009
        with self.assertLogs("tracer", level="WARNING"):
            self.trigger.trigger_injection("skin_99009", ticker_id=1)
        manager.inject_skin_immediately.assert_not_called()
        self.assertFalse(self.state.last_hover_written)


class WebSocketRetryReasonTests(unittest.TestCase):
    def test_error_is_kept_for_the_retry_warning(self):
        conn = WebSocketConnection(MagicMock(), SharedState())
        error = ConnectionRefusedError(10061, "refused")
        conn._on_error(None, error)
        self.assertIs(conn._last_error, error)
        self.assertFalse(conn.is_connected)

    def test_library_goodbye_error_is_silenced(self):
        source = (ROOT / "utils" / "core" / "logging.py").read_text(encoding="utf-8")
        self.assertIn('logging.getLogger("websocket").setLevel(logging.CRITICAL)', source)


class SpecHiddenImportTests(unittest.TestCase):
    def test_spec_has_no_nonexistent_websocket_client_import(self):
        spec = (ROOT / "Rose.spec").read_text(encoding="utf-8")
        self.assertNotIn("'websocket_client'", spec)


if __name__ == "__main__":
    unittest.main()
