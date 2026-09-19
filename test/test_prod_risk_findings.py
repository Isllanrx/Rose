"""Regressions found by the production risk review of 2026-09-19.

Each test fails against the code as it was before the corresponding fix.
"""

import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from injection.compat import wad_index as wi
from injection.core.manager import InjectionManager
from utils.download.hashes_downloader import HashesDownloader, _JoinedPartWriter

MANAGER = "injection.core.manager"


def make_manager(game_dir):
    with mock.patch(f"{MANAGER}.ThresholdManager"), mock.patch(f"{MANAGER}.GameMonitor"):
        return InjectionManager(game_dir=game_dir)


class IndexIsBuiltOnceNotOncePerCall(unittest.TestCase):
    """initialize_when_ready() has three call sites and only guards on _initialized.

    While League is closed that flag stays False, so without a guard every call would
    walk the game's 392 WADs again during startup.
    """

    def test_a_second_call_after_success_does_not_rebuild(self):
        manager = make_manager(Path("C:/jogo"))
        with mock.patch(f"{MANAGER}.ensure_index_built", return_value=True) as build:
            manager._prepare_wad_index()
            manager._prepare_wad_index()
            manager._prepare_wad_index()
        self.assertEqual(build.call_count, 1)

    def test_a_failed_build_is_retried(self):
        """A failure must not latch: the game folder may appear later."""
        manager = make_manager(Path("C:/jogo"))
        with mock.patch(f"{MANAGER}.ensure_index_built", return_value=False) as build:
            manager._prepare_wad_index()
            manager._prepare_wad_index()
        self.assertEqual(build.call_count, 2)

    def test_concurrent_calls_build_only_once(self):
        manager = make_manager(Path("C:/jogo"))
        started = threading.Event()
        release = threading.Event()
        calls = []

        def slow_build(*args):
            calls.append(args)
            started.set()
            release.wait(timeout=5)
            return True

        with mock.patch(f"{MANAGER}.ensure_index_built", side_effect=slow_build):
            first = threading.Thread(target=manager._prepare_wad_index)
            first.start()
            self.assertTrue(started.wait(timeout=5))
            manager._prepare_wad_index()  # must return at once, not block
            release.set()
            first.join(timeout=5)

        self.assertEqual(len(calls), 1)

    def test_the_lock_is_released_even_when_the_build_raises(self):
        manager = make_manager(Path("C:/jogo"))
        with mock.patch(f"{MANAGER}.ensure_index_built", side_effect=RuntimeError("boom")):
            manager._prepare_wad_index()
        self.assertFalse(manager._wad_index_lock.locked())


class OpenIndexLeavesNoMappingBehind(unittest.TestCase):
    """A mapping left open stops Windows replacing the file, freezing the index."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / "Game"
        self.game.mkdir()
        (self.game / wi._CONTENT_METADATA).write_text('{"version": "16.18.1"}', encoding="utf-8")
        from test.test_wad_index import make_wad
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        self.index_path = self.root / "wad_index.bin"
        self.assertIsNotNone(wi.build_index(self.game, self.index_path))
        self.fingerprint = wi._patch_fingerprint(self.game)

    def test_a_failing_wadindex_constructor_does_not_leak_the_mapping(self):
        with mock.patch.object(wi, "WadIndex", side_effect=TypeError("cast falhou")):
            self.assertIsNone(wi.open_index(self.index_path, self.fingerprint))

        # If the mapping had leaked, this rebuild would fail on Windows.
        self.assertIsNotNone(wi.build_index(self.game, self.index_path))
        self.index_path.unlink()

    def test_a_failing_constructor_still_returns_none_instead_of_raising(self):
        with mock.patch.object(wi, "WadIndex", side_effect=TypeError("cast falhou")):
            self.assertIsNone(wi.open_index(self.index_path, self.fingerprint))


class TruncatedDownloadIsRefused(unittest.TestCase):
    """A stream that ends early does not always raise; silence here corrupts the table."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.downloader = HashesDownloader(Path(self.tmp.name))

    def _response(self, chunks, content_length):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.raise_for_status.return_value = None
        response.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        response.iter_content.return_value = iter(chunks)
        return response

    def _feed(self, chunks, content_length):
        import io
        writer = _JoinedPartWriter(io.BytesIO())
        writer.start_part()
        with mock.patch.object(self.downloader.session, "get",
                               return_value=self._response(chunks, content_length)):
            return self.downloader._stream_hashes_file("hashes.game.txt.0", writer)

    def test_short_stream_is_reported_as_failure(self):
        self.assertFalse(self._feed([b"abc"], content_length=10))

    def test_complete_stream_succeeds(self):
        self.assertTrue(self._feed([b"abc", b"defg"], content_length=7))

    def test_missing_content_length_is_accepted(self):
        self.assertTrue(self._feed([b"abc"], content_length=None))

    def test_malformed_content_length_is_ignored_not_fatal(self):
        response = self._response([b"abc"], content_length=None)
        response.headers = {"Content-Length": "nao-e-numero"}
        import io
        writer = _JoinedPartWriter(io.BytesIO())
        writer.start_part()
        with mock.patch.object(self.downloader.session, "get", return_value=response):
            self.assertTrue(self.downloader._stream_hashes_file("hashes.game.txt.0", writer))

    def test_a_truncated_part_aborts_the_whole_download(self):
        """The previous table must survive, and no state may be saved."""
        self.downloader.hashes_file.write_bytes(b"tabela anterior\n")
        with mock.patch.object(self.downloader, "_stream_hashes_file", return_value=False), \
             mock.patch.object(self.downloader, "save_local_state") as save:
            self.assertFalse(self.downloader.download_and_merge_hashes())
        save.assert_not_called()
        self.assertEqual(self.downloader.hashes_file.read_bytes(), b"tabela anterior\n")


if __name__ == "__main__":
    unittest.main()
