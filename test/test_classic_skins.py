import struct
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import xxhash
import zstandard

from injection.classic import classic_skin_builder as csb
from injection.core.injector import SkinInjector
from injection.core.manager import InjectionManager
from state import SharedState

REAL_GAME_DIR = Path(r"D:\Riot Games\League of Legends\Game")

SKIN_DATA_TYPE = 0x9B67E9F6
RESOLVER_TYPE = 0xEF3A0F33
PARTICLE_TYPE = 0x45CD899F


def make_prop(links, entries, version=3):
    out = bytearray(b"PROP") + struct.pack("<II", version, len(links))
    for link in links:
        out += struct.pack("<H", len(link)) + link.encode()
    out += struct.pack("<I", len(entries)) + b"".join(struct.pack("<I", t) for t, _, _ in entries)
    for _, key, body in entries:
        out += struct.pack("<II", len(body) + 4, key) + body
    return bytes(out)


def make_wad(files, compress=True):
    """Build a minimal WAD v3 with the given {path: bytes}."""
    header = bytearray(b"RW\x03\x04") + bytes(264) + struct.pack("<I", len(files))
    toc, blobs = bytearray(), bytearray()
    data_offset = len(header) + 32 * len(files)
    for path, data in files.items():
        payload = zstandard.ZstdCompressor().compress(data) if compress else data
        toc += struct.pack(
            "<QIIIBBHQ",
            xxhash.xxh64_intdigest(path.lower().encode()),
            data_offset + len(blobs),
            len(payload),
            len(data),
            3 if compress else 0,
            0,
            0,
            0,
        )
        blobs += payload
    return bytes(header + toc + blobs)


def jade_skin_bin(character, skin):
    prefix = f"Characters/{character}/Skins/Skin{skin}"
    return make_prop(
        [f"DATA/Characters/{character}/Animations/Skin{skin}.bin"],
        [
            (SKIN_DATA_TYPE, csb.fnv1a_32(prefix), b"skin-data-referencing-resources"),
            (PARTICLE_TYPE, 0x12345678, b"particle"),
            (RESOLVER_TYPE, csb.fnv1a_32(f"{prefix}/Resources"), b"resolver"),
        ],
    )


class RetargetSkinBinTests(unittest.TestCase):
    def test_only_entry_keys_change_and_source_bin_is_linked(self):
        source = jade_skin_bin("Jade_Katarina", 30)

        result = csb.retarget_skin_bin(source, "Jade_Katarina", 30, 301)

        version, entries = csb._parse_prop_entries(result)
        self.assertEqual(version, 3)
        self.assertEqual(entries, [
            (SKIN_DATA_TYPE, csb.fnv1a_32("Characters/Jade_Katarina/Skins/Skin301"), b"skin-data-referencing-resources"),
            (RESOLVER_TYPE, csb.fnv1a_32("Characters/Jade_Katarina/Skins/Skin301/Resources"), b"resolver"),
        ])
        self.assertIn(b"DATA/Characters/Jade_Katarina/Skins/Skin30.bin", result)

    def test_missing_skin_entry_is_rejected(self):
        source = make_prop([], [(PARTICLE_TYPE, 1, b"x")])
        with self.assertRaises(csb.ClassicSkinError):
            csb.retarget_skin_bin(source, "Jade_Katarina", 30, 301)

    def test_truncated_bin_is_rejected(self):
        source = jade_skin_bin("Jade_Katarina", 30)
        with self.assertRaises(csb.ClassicSkinError):
            csb.retarget_skin_bin(source[:-10], "Jade_Katarina", 30, 301)

    def test_non_prop_data_is_rejected(self):
        with self.assertRaises(csb.ClassicSkinError):
            csb.retarget_skin_bin(b"NOPE" + bytes(20), "Jade_Katarina", 30, 301)


class WadAndArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_reads_zstd_and_raw_entries(self):
        for compress in (True, False):
            with self.subTest(compress=compress):
                wad = self.root / f"w{compress}.wad.client"
                wad.write_bytes(make_wad({"data/a.bin": b"hello", "data/b.bin": b"world"}, compress))
                reader = csb.WadReader(wad)
                self.assertEqual(reader.read("DATA/B.bin"), b"world")
                self.assertTrue(reader.has("data/a.bin"))
                self.assertIsNone(reader.read("data/missing.bin"))

    def test_rejects_non_wad_file(self):
        bad = self.root / "bad.wad.client"
        bad.write_bytes(b"XX" + bytes(300))
        with self.assertRaises(csb.ClassicSkinError):
            csb.WadReader(bad)

    def test_truncated_table_of_contents_is_rejected(self):
        wad = self.root / "short.wad.client"
        wad.write_bytes(make_wad({"data/a.bin": b"x"})[:280])
        with self.assertRaises(csb.ClassicSkinError):
            csb.WadReader(wad)

    def test_corrupted_compressed_entry_is_rejected(self):
        wad = self.root / "corrupt.wad.client"
        data = bytearray(make_wad({"data/a.bin": b"hello" * 50}))
        data[-5:] = bytes(5)
        wad.write_bytes(bytes(data))
        with self.assertRaises(csb.ClassicSkinError):
            csb.WadReader(wad).read("data/a.bin")

    def test_archive_with_path_like_wad_name_is_rejected(self):
        traversal = self.root / "traversal.fantome"
        with zipfile.ZipFile(traversal, "w") as z:
            z.writestr("WAD/..\\..\\evil.wad.client", b"RW")
        with self.assertRaises(csb.ClassicSkinError):
            csb.champion_alias_from_mod_archive(traversal)

        odd_name = self.root / "odd.fantome"
        with zipfile.ZipFile(odd_name, "w") as z:
            z.writestr("WAD/Ahri..evil.wad.client", b"RW")
        with self.assertRaisesRegex(csb.ClassicSkinError, "invalid champion WAD name"):
            csb.champion_alias_from_mod_archive(odd_name)

    def test_champion_alias_comes_from_skin_archive(self):
        archive = self.root / "21031.fantome"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("META/info.json", "{}")
            z.writestr("WAD/MissFortune.wad.client", b"RW")
        self.assertEqual(csb.champion_alias_from_mod_archive(archive), "MissFortune")

    def test_archive_targeting_several_champions_is_rejected(self):
        archive = self.root / "multi.fantome"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("WAD/Ahri.wad.client", b"RW")
            z.writestr("WAD/Lux.wad.client", b"RW")
        with self.assertRaises(csb.ClassicSkinError):
            csb.champion_alias_from_mod_archive(archive)

    def test_champion_alias_comes_from_any_valid_archive_in_library(self):
        champion_dir = self.root / "1"
        (champion_dir / "1001").mkdir(parents=True)
        (champion_dir / "1001" / "1001.fantome").write_bytes(b"not a zip")
        with zipfile.ZipFile(champion_dir / "1001" / "1002.fantome", "w") as z:
            z.writestr("WAD/Annie.wad.client", b"RW")
        csb.champion_alias_from_library.cache_clear()

        self.assertEqual(csb.champion_alias_from_library(champion_dir), "Annie")

    def test_missing_library_folder_is_reported(self):
        csb.champion_alias_from_library.cache_clear()
        with self.assertRaisesRegex(csb.ClassicSkinError, "no usable skin archive"):
            csb.champion_alias_from_library(self.root / "404")

    def test_skin_number_from_injection_name(self):
        self.assertEqual(csb.skin_number_from_name("skin_55030"), 30)
        self.assertEqual(csb.skin_number_from_name("chroma_21070"), 70)
        with self.assertRaises(csb.ClassicSkinError):
            csb.skin_number_from_name("Miss Fortune T1 MVP")

    def test_classic_client_ids_map_to_regular_ids(self):
        self.assertEqual(csb.to_regular_champion_id(60001), 1)
        self.assertEqual(csb.to_regular_champion_id(62), 62)
        self.assertIsNone(csb.to_regular_champion_id(None))
        self.assertEqual(csb.to_regular_skin_id(60001001), 1001)
        self.assertEqual(csb.to_regular_skin_id(103086), 103086)
        self.assertEqual(csb.to_regular_skin_name("skin_60001001"), "skin_1001")
        self.assertEqual(csb.to_regular_skin_name("chroma_60001022"), "chroma_1022")
        self.assertEqual(csb.to_regular_skin_name("skin_21031"), "skin_21031")
        self.assertEqual(csb.skin_number_from_name(csb.to_regular_skin_name("skin_60062026")), 26)

    def test_game_mode_detection(self):
        self.assertTrue(csb.is_classic_game_mode("JADE"))
        self.assertTrue(csb.is_classic_game_mode("jade"))
        self.assertFalse(csb.is_classic_game_mode("CLASSIC"))
        self.assertFalse(csb.is_classic_game_mode(None))


class BuildClassicModTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.game_dir = Path(self.temp_dir.name) / "Game"
        champions = self.game_dir / "DATA" / "FINAL" / "Champions"
        champions.mkdir(parents=True)
        (champions / "Katarina.wad.client").write_bytes(make_wad({
            "data/characters/jade_katarina/jade_katarina.bin": b"PROP",
            "data/characters/jade_katarina/skins/skin30.bin": jade_skin_bin("Jade_Katarina", 30),
        }))
        (champions / "Annie.wad.client").write_bytes(make_wad({
            "data/characters/jade_annie/jade_annie.bin": b"PROP",
            "data/characters/jade_annie/skins/skin1.bin": jade_skin_bin("Jade_Annie", 1),
            "data/characters/jade_annie_tibbers/jade_annie_tibbers.bin": b"PROP",
            "data/characters/jade_annie_tibbers/skins/skin1.bin": jade_skin_bin("jade_annie_tibbers", 1),
        }))
        (champions / "MonkeyKing.wad.client").write_bytes(make_wad({
            "data/characters/jade_wukong/jade_wukong.bin": b"PROP",
            "data/characters/jade_wukong/skins/skin3.bin": jade_skin_bin("jade_wukong", 3),
        }))
        (champions / "Aatrox.wad.client").write_bytes(make_wad({
            "data/characters/aatrox/skins/skin1.bin": b"PROP",
        }))
        self.jade_index = {"jade_katarina", "jade_annie", "jade_annie_tibbers", "jade_wukong"}
        self.mods_dir = Path(self.temp_dir.name) / "mods"
        self.mods_dir.mkdir()

    def test_companion_characters_are_retargeted_with_the_champion(self):
        folder = csb.build_classic_mod(self.game_dir, "Annie", 1, self.mods_dir, self.jade_index)

        characters = self.mods_dir / folder / "WAD" / "Annie.wad.client" / "data" / "characters"
        self.assertEqual(sorted(p.name for p in characters.iterdir()), ["jade_annie", "jade_annie_tibbers"])
        _, entries = csb._parse_prop_entries((characters / "jade_annie_tibbers" / "skins" / "skin301.bin").read_bytes())
        self.assertEqual(entries[0][1], csb.fnv1a_32("Characters/jade_annie_tibbers/Skins/Skin301"))

    def test_classic_name_different_from_wad_alias_is_found_through_index(self):
        folder = csb.build_classic_mod(self.game_dir, "MonkeyKing", 3, self.mods_dir, self.jade_index)
        slot = self.mods_dir / folder / "WAD" / "MonkeyKing.wad.client" / "data" / "characters" / "jade_wukong" / "skins" / "skin301.bin"
        self.assertTrue(slot.is_file())

        with self.assertRaisesRegex(csb.ClassicSkinError, "no Rift Classic version"):
            csb.build_classic_mod(self.game_dir, "MonkeyKing", 3, self.mods_dir, ())

    def test_champion_without_classic_version_is_reported(self):
        with self.assertRaisesRegex(csb.ClassicSkinError, "no Rift Classic version"):
            csb.build_classic_mod(self.game_dir, "Aatrox", 1, self.mods_dir, self.jade_index)

    def test_invalid_alias_is_rejected(self):
        with self.assertRaisesRegex(csb.ClassicSkinError, "invalid champion alias"):
            csb.build_classic_mod(self.game_dir, "..\\x", 1, self.mods_dir, self.jade_index)

    def test_writes_folder_mod_for_every_classic_base_slot(self):
        folder = csb.build_classic_mod(self.game_dir, "Katarina", 30, self.mods_dir, self.jade_index)

        skins_dir = self.mods_dir / folder / "WAD" / "Katarina.wad.client" / "data" / "characters" / "jade_katarina" / "skins"
        self.assertEqual(sorted(p.name for p in skins_dir.iterdir()), ["skin0.bin", "skin301.bin", "skin302.bin"])
        _, entries = csb._parse_prop_entries((skins_dir / "skin301.bin").read_bytes())
        self.assertEqual(entries[0][1], csb.fnv1a_32("Characters/Jade_Katarina/Skins/Skin301"))
        self.assertTrue((self.mods_dir / folder / "META" / "info.json").is_file())

    def test_skin_missing_from_classic_tree_is_reported(self):
        with self.assertRaisesRegex(csb.ClassicSkinError, "not available"):
            csb.build_classic_mod(self.game_dir, "Katarina", 69, self.mods_dir, self.jade_index)
        self.assertEqual(list(self.mods_dir.iterdir()), [])

    def test_missing_champion_wad_is_reported(self):
        with self.assertRaisesRegex(csb.ClassicSkinError, "champion WAD not found"):
            csb.build_classic_mod(self.game_dir, "Ahri", 1, self.mods_dir, self.jade_index)


class JadeCharacterIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.table = self.root / "hashes.game.txt"
        self.cache = self.root / "state" / "classic_characters.json"

    def write_table(self, *paths):
        lines = [f"{index:016x} {path}\n" for index, path in enumerate(paths)]
        self.table.write_text("".join(lines), encoding="utf-8")

    def test_index_is_built_cached_and_invalidated_when_table_changes(self):
        self.write_table(
            "data/characters/jade_annie/skins/skin1.bin",
            "data/characters/annie/skins/skin1.bin",
            "data/characters/jade_annie_tibbers/skins/skin1.bin",
        )
        self.assertEqual(csb.load_jade_characters(self.table, self.cache), {"jade_annie", "jade_annie_tibbers"})
        self.assertTrue(self.cache.is_file())

        real_open = open

        def forbid_table(path, *args, **kwargs):
            if Path(path) == self.table:
                raise AssertionError("hash table must not be rescanned while cache is valid")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=forbid_table):
            self.assertEqual(csb.load_jade_characters(self.table, self.cache), {"jade_annie", "jade_annie_tibbers"})

        self.write_table("data/characters/jade_wukong/skins/skin3.bin", "data/characters/jade_wukong/jade_wukong.bin", "other/path")
        self.assertEqual(csb.load_jade_characters(self.table, self.cache), {"jade_wukong"})

    def test_missing_table_falls_back_to_empty_index(self):
        with self.assertLogs("tracer", level="WARNING"):
            self.assertEqual(csb.load_jade_characters(self.root / "missing.txt", self.cache), frozenset())


def make_manager(game_mode):
    manager = object.__new__(InjectionManager)
    manager._ensure_initialized = lambda: None
    manager.refresh_injection_threshold = lambda: None
    manager._initialized = True
    manager.injector = MagicMock(game_dir=Path("C:/Game"))
    manager.injector.inject_skin.return_value = True
    manager._injection_in_progress = False
    manager.injection_lock = threading.Lock()
    manager.last_injection_time = 0.0
    manager.injection_threshold = 0.5
    manager.shared_state = SimpleNamespace(current_game_mode=game_mode, ui_skin_thread=None, party_manager=None)
    manager.game_monitor = SimpleNamespace(is_active=False)
    manager._start_monitor = MagicMock()
    manager._stop_monitor = MagicMock()
    return manager


class InjectionManagerClassicRoutingTests(unittest.TestCase):
    def test_classic_game_injects_prepared_mod(self):
        manager = make_manager("JADE")
        manager.injector.prepare_classic_mod.return_value = "classic_jade_katarina_30"

        self.assertTrue(manager.inject_skin_immediately("skin_55030", champion_id=55))

        manager.injector.prepare_classic_mod.assert_called_once()
        self.assertEqual(manager.injector.inject_skin.call_args.kwargs["prepared_mod"], "classic_jade_katarina_30")

    def test_classic_selection_is_forwarded_to_the_builder(self):
        manager = make_manager("JADE")
        manager.injector.prepare_classic_mod.return_value = "classic_annie_60"

        manager.inject_skin_immediately("skin_60001060", champion_id=60001, classic_selected_skin_id=60001301)

        self.assertEqual(manager.injector.prepare_classic_mod.call_args.kwargs["selected_skin_id"], 60001301)
        manager._start_monitor.assert_called_once()

    def test_unavailable_classic_skin_never_suspends_the_game(self):
        manager = make_manager("JADE")
        manager.injector.prepare_classic_mod.return_value = None

        self.assertFalse(manager.inject_skin_immediately("skin_21069", champion_id=21))

        manager._start_monitor.assert_not_called()
        manager.injector.inject_skin.assert_not_called()
        manager._stop_monitor.assert_called_once()  # resumes the game if anything had suspended it
        self.assertFalse(manager._injection_in_progress)
        self.assertFalse(manager.injection_lock.locked())

    def test_regular_games_keep_fantome_flow(self):
        manager = make_manager("CLASSIC")

        self.assertTrue(manager.inject_skin_immediately("skin_21031", champion_id=21))

        manager.injector.prepare_classic_mod.assert_not_called()
        self.assertIsNone(manager.injector.inject_skin.call_args.kwargs["prepared_mod"])


class ClassicSelectionIsNotForcedTests(unittest.TestCase):
    """Rift Classic's skins-pane listens on its own socket; forcing the base skin reset the carousel in-game."""

    def make_trigger(self, game_mode, selected_skin_id):
        from threads.handlers.injection_trigger import InjectionTrigger

        state = SharedState()
        state.current_game_mode = game_mode
        state.locked_champ_id = 60001 if game_mode == "JADE" else 1
        state.local_cell_id = 0
        state.phase = "FINALIZATION"
        lcu = SimpleNamespace(ok=True, session={"myTeam": [{"cellId": 0, "selectedSkinId": selected_skin_id}]})
        manager = MagicMock()
        manager.inject_skin_immediately.return_value = False
        trigger = InjectionTrigger(lcu, state, injection_manager=manager)
        trigger._force_base_skin = MagicMock()
        return trigger, manager

    def run_unowned(self, trigger, name):
        started = []
        real_thread = threading.Thread

        def capture_thread(*args, **kwargs):
            thread = real_thread(*args, **kwargs)
            started.append(thread)
            return thread

        with patch("threads.handlers.injection_trigger.threading.Thread", side_effect=capture_thread):
            trigger._inject_unowned_skin(name, "Annie")
        for thread in started:
            thread.join(timeout=5)

    def test_classic_keeps_selection_and_passes_it_to_the_injector(self):
        trigger, manager = self.make_trigger("JADE", 60001301)

        self.run_unowned(trigger, "skin_60001060")

        trigger._force_base_skin.assert_not_called()
        self.assertEqual(manager.inject_skin_immediately.call_args.kwargs["classic_selected_skin_id"], 60001301)

    def test_regular_games_still_force_the_base_skin(self):
        trigger, manager = self.make_trigger("CLASSIC", 1004)

        self.run_unowned(trigger, "skin_1060")

        trigger._force_base_skin.assert_called_once_with(1000)
        self.assertIsNone(manager.inject_skin_immediately.call_args.kwargs["classic_selected_skin_id"])


class SkinInjectorPreparedModTests(unittest.TestCase):
    def test_prepared_mod_skips_archive_extraction(self):
        injector = object.__new__(SkinInjector)
        injector.last_injection_timing = None
        injector._resolve_skin_archive = MagicMock()
        injector._extract_zip_to_mod = MagicMock()
        injector._clean_mods_dir = MagicMock()
        injector._mk_run_overlay = MagicMock(return_value=0)
        party_callback = MagicMock()

        with patch("injection.core.injector.report_issue"):
            ok = injector.inject_skin("skin_55030", prepared_mod="classic_jade_katarina_30", extra_mods_callback=party_callback)

        self.assertTrue(ok)
        injector._resolve_skin_archive.assert_not_called()
        injector._extract_zip_to_mod.assert_not_called()
        injector._clean_mods_dir.assert_not_called()
        party_callback.assert_not_called()
        self.assertEqual(injector._mk_run_overlay.call_args.args[0], ["classic_jade_katarina_30"])


@unittest.skipUnless((REAL_GAME_DIR / "DATA" / "FINAL" / "Champions" / "Katarina.wad.client").is_file(), "League not installed")
class InstalledGameClassicTests(unittest.TestCase):
    def test_builds_from_installed_patch_data(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = csb.build_classic_mod(REAL_GAME_DIR, "Katarina", 30, Path(temp))
            slot = Path(temp) / folder / "WAD" / "Katarina.wad.client" / "data" / "characters" / "jade_katarina" / "skins" / "skin301.bin"
            _, entries = csb._parse_prop_entries(slot.read_bytes())

        self.assertEqual(
            [key for _, key, _ in entries],
            [csb.fnv1a_32("Characters/Jade_Katarina/Skins/Skin301"), csb.fnv1a_32("Characters/Jade_Katarina/Skins/Skin301/Resources")],
        )

    def test_installed_patch_companions_and_renamed_characters(self):
        hashes = Path(__file__).resolve().parents[1] / "dist" / "Rose" / "_internal" / "injection" / "tools" / "hashes.game.txt"
        if not hashes.is_file():
            self.skipTest("hashes.game.txt not available")
        with tempfile.TemporaryDirectory() as temp:
            index = csb.load_jade_characters(hashes, Path(temp) / "index.json")
            annie = csb.build_classic_mod(REAL_GAME_DIR, "Annie", 1, Path(temp), index)
            annie_chars = sorted(p.name for p in (Path(temp) / annie / "WAD" / "Annie.wad.client" / "data" / "characters").iterdir())
            wukong = csb.build_classic_mod(REAL_GAME_DIR, "MonkeyKing", 3, Path(temp), index)
            wukong_chars = sorted(p.name for p in (Path(temp) / wukong / "WAD" / "MonkeyKing.wad.client" / "data" / "characters").iterdir())

        self.assertEqual(annie_chars, ["jade_annie", "jade_annie_tibbers"])
        self.assertEqual(wukong_chars, ["jade_wukong"])

    def test_prepare_accepts_ids_reported_by_classic_champ_select(self):
        skins = Path(r"C:\Users\Isllan Toso\AppData\Local\Rose\skins")
        tools = Path(__file__).resolve().parents[1] / "dist" / "Rose" / "_internal" / "injection" / "tools"
        if not (skins / "1" / "1001").is_dir() or not (tools / "hashes.game.txt").is_file():
            self.skipTest("skin library or game hash table not available")
        with tempfile.TemporaryDirectory() as temp, patch("injection.core.injector.get_state_dir", return_value=Path(temp)):
            injector = SkinInjector(tools_dir=tools, mods_dir=Path(temp) / "mods", zips_dir=skins, game_dir=REAL_GAME_DIR)
            folder = injector.prepare_classic_mod("skin_60001001", champion_id=60001)

        self.assertEqual(folder, "classic_annie_1")

    def test_currently_selected_owned_skin_slot_is_overridden(self):
        skins = Path(r"C:\Users\Isllan Toso\AppData\Local\Rose\skins")
        tools = Path(__file__).resolve().parents[1] / "dist" / "Rose" / "_internal" / "injection" / "tools"
        if not (skins / "1").is_dir() or not (tools / "hashes.game.txt").is_file():
            self.skipTest("skin library or game hash table not available")
        with tempfile.TemporaryDirectory() as temp, patch("injection.core.injector.get_state_dir", return_value=Path(temp)):
            injector = SkinInjector(tools_dir=tools, mods_dir=Path(temp) / "mods", zips_dir=skins, game_dir=REAL_GAME_DIR)
            folder = injector.prepare_classic_mod("skin_60001060", champion_id=60001, selected_skin_id=60001004)
            skins_dir = Path(temp) / "mods" / folder / "WAD" / "Annie.wad.client" / "data" / "characters" / "jade_annie" / "skins"
            written = sorted(p.name for p in skins_dir.iterdir())
            _, entries = csb._parse_prop_entries((skins_dir / "skin4.bin").read_bytes())

        self.assertEqual(written, ["skin0.bin", "skin301.bin", "skin302.bin", "skin4.bin"])
        self.assertEqual(entries[0][1], csb.fnv1a_32("Characters/Jade_Annie/Skins/Skin4"))

    def test_classic_exclusive_chroma_without_library_archive_is_prepared(self):
        skins = Path(r"C:\Users\Isllan Toso\AppData\Local\Rose\skins")
        tools = Path(__file__).resolve().parents[1] / "dist" / "Rose" / "_internal" / "injection" / "tools"
        if not (skins / "1").is_dir() or (skins / "1" / "1303").exists() or not (tools / "hashes.game.txt").is_file():
            self.skipTest("skin library or game hash table not available")
        with tempfile.TemporaryDirectory() as temp, patch("injection.core.injector.get_state_dir", return_value=Path(temp)):
            injector = SkinInjector(tools_dir=tools, mods_dir=Path(temp) / "mods", zips_dir=skins, game_dir=REAL_GAME_DIR)
            folder = injector.prepare_classic_mod("chroma_60001303", champion_id=60001)

        self.assertEqual(folder, "classic_annie_303")

    def test_regular_only_skin_is_not_available_in_classic(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(csb.ClassicSkinError):
            csb.build_classic_mod(REAL_GAME_DIR, "MissFortune", 69, Path(temp))


if __name__ == "__main__":
    unittest.main()
