"""Silent drops on the skin selection path must leave a trace in the log.

Rift Classic players reported `Final name variable: 'None'` with no other clue. These tests
pin the log lines that tell which step lost the selected skin.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from pengu.processing.skin_processor import SkinProcessor
from state import SharedState
from threads.handlers import champion_lock_handler as lock_module
from threads.handlers.champion_lock_handler import ChampionLockHandler
from threads.websocket.websocket_event_handler import WebSocketEventHandler

SESSION_URI = "/lol-champ-select/v1/session"


class WebSocketEventFailureTests(unittest.TestCase):
    def setUp(self):
        self.handler = WebSocketEventHandler(MagicMock(), SharedState())

    def test_handler_failure_is_logged_with_uri(self):
        msg = json.dumps([8, "OnJsonApiEvent", {"uri": SESSION_URI, "data": {}}])

        with (
            patch.object(self.handler, "handle_api_event", side_effect=RuntimeError("lock parse broke")),
            self.assertLogs("tracer", level="ERROR") as logs,
        ):
            self.handler.handle_message(None, msg)

        output = "\n".join(logs.output)
        self.assertIn(f"Failed to handle LCU event {SESSION_URI}", output)
        self.assertIn("lock parse broke", output)

    def test_non_json_message_is_not_an_error(self):
        with (
            patch.object(self.handler, "handle_api_event") as handle,
            self.assertNoLogs("tracer", level="WARNING"),
        ):
            self.handler.handle_message(None, "not json")

        handle.assert_not_called()

    def test_routing_is_unchanged(self):
        event = {"uri": SESSION_URI, "data": {}}
        with patch.object(self.handler, "handle_api_event") as handle:
            self.handler.handle_message(None, json.dumps([8, "OnJsonApiEvent", event]))
            self.handler.handle_message(None, json.dumps(event))
            self.handler.handle_message(None, json.dumps([5, "OnJsonApiEvent", event]))
            self.handler.handle_message(None, json.dumps({"data": {}}))

        self.assertEqual(handle.call_count, 2)
        handle.assert_called_with(event)


class SkinTitleDropTests(unittest.TestCase):
    LOGGER = "pengu.processing.skin_processor"

    def setUp(self):
        self.state = SharedState()
        self.scraper = MagicMock()
        self.processor = SkinProcessor(self.state, skin_scraper=self.scraper)

    def test_title_before_lock_is_logged(self):
        self.state.hovered_champ_id = 60099

        with self.assertLogs(self.LOGGER, level="INFO") as logs:
            result = self.processor._find_skin_id("Lux Corte das Fadas")

        self.assertIsNone(result)
        self.assertIn("no locked champion yet (hovered=60099)", logs.output[0])
        self.scraper.scrape_champion_skins.assert_not_called()

    def test_failed_scrape_is_logged(self):
        self.state.locked_champ_id = 60099
        self.scraper.scrape_champion_skins.return_value = False

        with self.assertLogs(self.LOGGER, level="WARNING") as logs:
            result = self.processor._find_skin_id("Lux Corte das Fadas")

        self.assertIsNone(result)
        self.assertIn("could not load skins for champion 60099", logs.output[0])

    def test_scrape_exception_is_logged_with_traceback(self):
        self.state.locked_champ_id = 60099
        self.scraper.scrape_champion_skins.side_effect = RuntimeError("lcu down")

        with self.assertLogs(self.LOGGER, level="ERROR") as logs:
            result = self.processor._find_skin_id("Lux Corte das Fadas")

        self.assertIsNone(result)
        self.assertIn("lcu down", "\n".join(logs.output))

    def test_match_exception_is_logged_with_traceback(self):
        self.state.locked_champ_id = 60099
        self.scraper.scrape_champion_skins.return_value = True
        self.scraper.find_skin_by_text.side_effect = ValueError("bad name")

        with self.assertLogs(self.LOGGER, level="ERROR") as logs:
            result = self.processor._find_skin_id("Lux Corte das Fadas")

        self.assertIsNone(result)
        self.assertIn("name matching failed", logs.output[0])


class LockDiscardsEarlyTitleTests(unittest.TestCase):
    def setUp(self):
        self.state = SharedState()
        self.state.ui_skin_thread = MagicMock()
        self.handler = ChampionLockHandler(MagicMock(), self.state)
        patcher = patch.object(lock_module, "get_chroma_selector", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_title_received_before_lock_is_reported(self):
        self.state.ui_last_text = "Lux Corte das Fadas"

        with self.assertLogs("tracer", level="WARNING") as logs:
            self.handler.on_own_champion_locked(60099, "#60099")

        self.assertIn("Discarding skin title 'Lux Corte das Fadas'", "\n".join(logs.output))
        self.state.ui_skin_thread.clear_cache.assert_called_once()

    def test_mapped_title_is_not_reported(self):
        self.state.ui_last_text = "Lux Corte das Fadas"
        self.state.last_hovered_skin_id = 60099004

        with self.assertNoLogs("tracer", level="WARNING"):
            self.handler.on_own_champion_locked(60099, "#60099")

        self.state.ui_skin_thread.clear_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
