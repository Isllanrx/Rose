import configparser
import json
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import config
import utils.core.paths as paths
from injection.config.config_manager import ConfigManager
from utils.core import historic, mod_historic
from utils.core import atomic_file
from utils.core.atomic_file import atomic_write
from utils.core.safe_extract import is_safe_path
from utils.download.repo_downloader import RepoDownloader


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.tmp = Path(self._temp.name)


class AtomicWriteTests(TempDirTestCase):
    def test_failure_mid_write_keeps_previous_content_and_no_temp_files(self):
        target = self.tmp / "state.json"
        target.write_text('{"kept": true}', encoding="utf-8")

        with self.assertRaises(RuntimeError), atomic_write(target) as handle:
            handle.write('{"partial": ')
            raise RuntimeError("crash while writing")

        self.assertEqual(target.read_text(encoding="utf-8"), '{"kept": true}')
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["state.json"])

    def test_transient_lock_on_replace_is_retried(self):
        target = self.tmp / "config.ini"
        real_replace = atomic_file.os.replace
        attempts = []

        def locked_twice(source, destination):
            attempts.append(destination)
            if len(attempts) <= 2:
                raise PermissionError("file in use by antivirus")
            real_replace(source, destination)

        with patch.object(atomic_file.os, "replace", side_effect=locked_twice), patch.object(atomic_file.time, "sleep"):
            atomic_file.write_text_atomic(target, "[General]\n")

        self.assertEqual(len(attempts), 3)
        self.assertEqual(target.read_text(encoding="utf-8"), "[General]\n")

    def test_bulk_write_skips_fsync(self):
        with patch.object(atomic_file.os, "fsync") as fsync, atomic_write(self.tmp / "skin.fantome", "wb", durable=False) as handle:
            handle.write(b"skin")

        fsync.assert_not_called()

    def test_success_replaces_content(self):
        target = self.tmp / "nested" / "state.bin"

        with atomic_write(target, "wb") as handle:
            handle.write(b"\x00\x01")

        self.assertEqual(target.read_bytes(), b"\x00\x01")


class HistoricPersistenceTests(TempDirTestCase):
    """A failed or concurrent write must never wipe the history of other champions."""

    def setUp(self):
        super().setUp()
        for module in (historic, mod_historic):
            patcher = patch.object(module, "get_user_data_dir", return_value=self.tmp)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_failed_write_keeps_existing_entries(self):
        historic.write_historic_entry(1, 1001)

        with self.assertLogs("tracer", level="WARNING"):
            historic.write_historic_entry(2, object())

        self.assertEqual(historic.load_historic_map(), {"1": 1001})

    def test_failed_target_write_keeps_existing_targets(self):
        historic.write_historic_target(1, 1005)

        with patch.object(historic.json, "dump", side_effect=OSError("disk full")), self.assertLogs("tracer", level="WARNING"):
            historic.write_historic_target(2, 2003)

        self.assertEqual(historic.load_historic_target_map(), {"1": 1005})

    def test_concurrent_writes_keep_every_champion(self):
        real_dump = json.dump

        def slow_dump(*args, **kwargs):
            time.sleep(0.01)
            return real_dump(*args, **kwargs)

        champions = range(1, 13)
        barrier = threading.Barrier(len(champions))

        def write(champion_id):
            barrier.wait()
            historic.write_historic_entry(champion_id, champion_id * 1000 + 1)

        with patch.object(historic.json, "dump", side_effect=slow_dump):
            threads = [threading.Thread(target=write, args=(c,)) for c in champions]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(historic.load_historic_map(), {str(c): c * 1000 + 1 for c in champions})

    def test_clear_entry_still_works(self):
        historic.write_historic_entry(1, 1001)
        historic.write_historic_target(1, 1002)

        historic.clear_historic_entry(1)

        self.assertEqual(historic.load_historic_map(), {})
        self.assertEqual(historic.load_historic_target_map(), {})

    def test_mod_history_failed_write_keeps_existing_entries(self):
        mod_historic.write_historic_mod("map", "maps/summer.fantome")

        with patch.object(mod_historic.json, "dump", side_effect=OSError("locked")), self.assertLogs("tracer", level="WARNING"):
            mod_historic.write_historic_mod("font", "fonts/pixel.fantome")

        self.assertEqual(mod_historic.load_mod_historic(), {"map": "maps/summer.fantome"})

    def test_mod_history_roundtrip(self):
        mod_historic.write_historic_mod("ui", ["ui/a.fantome", "ui/b.fantome"])
        mod_historic.write_historic_mod("map", "maps/summer.fantome")
        mod_historic.clear_historic_mod("map")

        self.assertEqual(mod_historic.load_mod_historic(), {"ui": ["ui/a.fantome", "ui/b.fantome"]})


class ConfigPersistenceTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.config_path = self.tmp / "config.ini"
        patcher = patch.object(config, "get_config_file_path", return_value=self.config_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_unreadable_config_is_not_overwritten(self):
        original = "[General]\nleaguePath = D:\\Riot Games\nanalytics_enabled = false\n[General]\nthreshold = 2\n"
        self.config_path.write_text(original, encoding="utf-8")

        with self.assertLogs(config.log, level="WARNING"):
            config.set_config_option("General", "injection_threshold", "0.5")

        self.assertEqual(self.config_path.read_text(encoding="utf-8"), original)

    def test_valid_config_keeps_other_options(self):
        self.config_path.write_text("[General]\nleaguePath = D:\\Riot Games\n", encoding="utf-8")

        config.set_config_option("General", "injection_threshold", "0.5")

        parser = configparser.ConfigParser()
        parser.read(self.config_path, encoding="utf-8")
        self.assertEqual(parser["General"]["leaguePath"], "D:\\Riot Games")
        self.assertEqual(parser["General"]["injection_threshold"], "0.5")

    def test_config_manager_saves_paths(self):
        manager = ConfigManager()
        manager._config_path = self.config_path
        self.config_path.write_text("[General]\nanalytics_enabled = false\n")

        manager.save_paths("D:\\Riot Games\\League of Legends\\Game", "D:\\Riot Games\\League of Legends")

        self.assertEqual(manager.load_league_path(), "D:\\Riot Games\\League of Legends\\Game")
        self.assertEqual(manager.load_client_path(), "D:\\Riot Games\\League of Legends")
        self.assertIn("analytics_enabled = false", self.config_path.read_text())


class SafePathTests(TempDirTestCase):
    def test_sibling_folder_with_same_prefix_is_rejected(self):
        base = self.tmp / "skins"
        self.assertFalse(is_safe_path(base, self.tmp / "skins-evil" / "payload.dll"))

    def test_traversal_is_rejected_and_children_accepted(self):
        base = self.tmp / "skins"
        self.assertFalse(is_safe_path(base, base / ".." / "payload.dll"))
        self.assertTrue(is_safe_path(base, base / "21" / "21001.fantome"))


class RepoSyncTestCase(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.skins_dir = self.tmp / "data" / "skins"
        self.skins_dir.mkdir(parents=True)
        patcher = patch.object(paths, "get_user_data_dir", return_value=self.tmp / "data")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.downloader = RepoDownloader(target_dir=self.skins_dir)

    def make_zip(self, entries, corrupt=None):
        zip_path = self.tmp / "repo.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        if corrupt is not None:
            raw = bytearray(zip_path.read_bytes())
            index = raw.find(corrupt)
            raw[index] ^= 0xFF
            zip_path.write_bytes(bytes(raw))
        return zip_path


class RepoZipExtractionTests(RepoSyncTestCase):
    def test_entry_escaping_target_folder_is_not_written(self):
        zip_path = self.make_zip({
            "LeagueSkins-main/skins/21/21001.fantome": b"skin",
            "LeagueSkins-main/skins/../../escaped.txt": b"payload",
        })

        self.assertTrue(self.downloader.extract_skins_from_zip(zip_path, overwrite_existing=True, extract_resources=False))

        self.assertFalse((self.tmp / "escaped.txt").exists())
        self.assertEqual((self.skins_dir / "21" / "21001.fantome").read_bytes(), b"skin")

    def test_corrupted_entry_keeps_previous_file_intact(self):
        existing = self.skins_dir / "21" / "21001.fantome"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"previous working skin")
        zip_path = self.make_zip({"LeagueSkins-main/skins/21/21001.fantome": b"NEWSKINDATA" * 50}, corrupt=b"NEWSKINDATA")

        with self.assertLogs("tracer", level="WARNING"):
            self.downloader.extract_skins_from_zip(zip_path, overwrite_existing=True, extract_resources=False)

        self.assertEqual(existing.read_bytes(), b"previous working skin")
        self.assertEqual(self.downloader.last_extraction_failures, 1)


class RepoVersionRecordingTests(RepoSyncTestCase):
    """The recorded commit decides whether files are downloaded again, so it must match what landed on disk."""

    def run_full_sync(self, zip_path, sha_before, sha_after):
        copy = self.tmp / "download.zip"
        shutil.copy(zip_path, copy)
        download = Mock(return_value=copy)
        with (
            patch.object(self.downloader, "download_repo_zip", download),
            patch.object(self.downloader, "fetch_remote_sha", side_effect=lambda: sha_after if download.called else sha_before),
        ):
            return self.downloader.download_and_extract_skins(force_update=True)

    def test_records_commit_resolved_before_download(self):
        zip_path = self.make_zip({"LeagueSkins-main/skins/21/21001.fantome": b"skin"})

        self.assertTrue(self.run_full_sync(zip_path, "sha-before-download", "sha-pushed-during-download"))

        self.assertEqual(self.downloader.get_local_sha(), "sha-before-download")

    def test_incomplete_extraction_does_not_record_commit(self):
        zip_path = self.make_zip({"LeagueSkins-main/skins/21/21001.fantome": b"NEWSKINDATA" * 50}, corrupt=b"NEWSKINDATA")

        with self.assertLogs("tracer", level="WARNING"):
            self.run_full_sync(zip_path, "sha-1", "sha-1")

        self.assertIsNone(self.downloader.get_local_sha())


class IncrementalSyncTests(RepoSyncTestCase):
    def test_file_system_error_is_reported_as_failure(self):
        locked = self.skins_dir / "21" / "21001.fantome"
        locked.mkdir(parents=True)
        response = Mock()
        response.iter_content.return_value = [b"skin"]

        with patch.object(self.downloader.session, "get", return_value=response), self.assertLogs("tracer", level="WARNING"):
            result = self.downloader.download_changed_files([{"filename": "skins/21/21001.fantome", "status": "modified"}])

        self.assertFalse(result)

    def test_changed_file_outside_target_is_skipped(self):
        response = Mock()
        response.iter_content.return_value = [b"payload"]

        with patch.object(self.downloader.session, "get", return_value=response) as get, self.assertLogs("tracer", level="WARNING"):
            self.downloader.download_changed_files([{"filename": "skins/../../escaped.txt", "status": "added"}])

        get.assert_not_called()
        self.assertFalse((self.tmp / "escaped.txt").exists())

    def test_changed_file_is_written(self):
        response = Mock()
        response.iter_content.return_value = [b"new ", b"skin"]

        with patch.object(self.downloader.session, "get", return_value=response):
            result = self.downloader.download_changed_files([{"filename": "skins/21/21001.fantome", "status": "added"}])

        self.assertTrue(result)
        self.assertEqual((self.skins_dir / "21" / "21001.fantome").read_bytes(), b"new skin")


if __name__ == "__main__":
    unittest.main()
