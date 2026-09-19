"""Índice dos WADs: equivalência com varredura linear, invalidação e degradação segura.

O índice só tem valor se responder exatamente o que uma varredura responderia. E como
ele vai rodar em background, nenhum caminho de erro pode levantar para o chamador.
"""

import json
import struct
import tempfile
import unittest
from array import array
from pathlib import Path

from injection.compat import wad_index as wi

REAL_GAME_DIR = Path(r"D:\Riot Games\League of Legends\Game")
GAME_AVAILABLE = (REAL_GAME_DIR / "DATA" / "FINAL" / "Champions" / "Katarina.wad.client").is_file()


def make_wad(path: Path, hashes):
    """Escreve um WAD v3 mínimo: só cabeçalho e tabela de conteúdo."""
    header = bytearray(wi._WAD_TOC_OFFSET)
    header[0:2] = b"RW"
    header[2] = 3
    struct.pack_into("<I", header, wi._WAD_TOC_OFFSET - 4, len(hashes))
    toc = bytearray(len(hashes) * wi._WAD_ENTRY_SIZE)
    for i, h in enumerate(hashes):
        struct.pack_into("<Q", toc, i * wi._WAD_ENTRY_SIZE, h)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(toc))


class FakeGameBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / "Game"
        self.game.mkdir()
        self.index_path = self.root / "wad_index.bin"

    def set_version(self, version):
        (self.game / wi._CONTENT_METADATA).write_text(
            json.dumps({"version": version}), encoding="utf-8")


class IndexAnswersLikeALinearScan(FakeGameBase):
    def test_every_hash_present_is_found_and_absent_is_not(self):
        self.set_version("16.18.1")
        present = [10, 20, 30, 40, 50]
        make_wad(self.game / "DATA" / "a.wad.client", present[:3])
        make_wad(self.game / "DATA" / "b.wad.client", present[3:])

        stats = wi.build_index(self.game, self.index_path)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.entries, 5)
        self.assertEqual(stats.wads_read, 2)

        with wi.open_index(self.index_path, wi._patch_fingerprint(self.game)) as index:
            for h in present:
                self.assertIn(h, index)
            for h in (0, 15, 35, 99, 2**63):
                self.assertNotIn(h, index)

    def test_duplicates_across_wads_are_stored_once(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [7, 8, 9])
        make_wad(self.game / "b.wad.client", [8, 9, 10])

        stats = wi.build_index(self.game, self.index_path)
        self.assertEqual(stats.entries, 4)
        with wi.open_index(self.index_path, wi._patch_fingerprint(self.game)) as index:
            for h in (7, 8, 9, 10):
                self.assertIn(h, index)

    def test_missing_reports_only_absent_hashes(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        wi.build_index(self.game, self.index_path)
        with wi.open_index(self.index_path, wi._patch_fingerprint(self.game)) as index:
            self.assertEqual(index.missing(iter([1, 4, 2, 5])), [4, 5])

    def test_boundary_values_survive_the_u64_round_trip(self):
        self.set_version("16.18.1")
        edge = [0, 1, 2**63 - 1, 2**63, 2**64 - 1]
        make_wad(self.game / "a.wad.client", edge)
        wi.build_index(self.game, self.index_path)
        with wi.open_index(self.index_path, wi._patch_fingerprint(self.game)) as index:
            self.assertEqual(index.count, len(edge))
            for h in edge:
                self.assertIn(h, index)


class IndexIsInvalidatedByPatch(FakeGameBase):
    def test_index_from_another_patch_is_refused(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        wi.build_index(self.game, self.index_path)

        self.set_version("16.19.0")
        self.assertIsNone(wi.open_index(self.index_path, wi._patch_fingerprint(self.game)))

    def test_ensure_index_rebuilds_after_a_patch(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        with wi.ensure_index(self.game, self.index_path) as index:
            self.assertIn(2, index)
            self.assertNotIn(99, index)

        self.set_version("16.19.0")
        make_wad(self.game / "a.wad.client", [1, 2, 3, 99])
        with wi.ensure_index(self.game, self.index_path) as index:
            self.assertIn(99, index)

    def test_falls_back_to_wad_sizes_without_content_metadata(self):
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        fingerprint = wi._patch_fingerprint(self.game)
        self.assertTrue(fingerprint.startswith("size:"))
        self.assertIsNotNone(wi.build_index(self.game, self.index_path))
        with wi.open_index(self.index_path, fingerprint) as index:
            self.assertIn(1, index)


class EveryFailurePathDegradesQuietly(FakeGameBase):
    """Nada aqui pode levantar: o índice roda em background."""

    def test_missing_game_directory_returns_none(self):
        self.assertIsNone(wi.build_index(self.root / "nao-existe", self.index_path))
        self.assertIsNone(wi.ensure_index(self.root / "nao-existe", self.index_path))

    def test_game_without_wads_returns_none(self):
        self.set_version("16.18.1")
        self.assertIsNone(wi.build_index(self.game, self.index_path))

    def test_absent_index_returns_none(self):
        self.assertIsNone(wi.open_index(self.index_path, "version:x"))

    def test_corrupt_index_returns_none(self):
        self.index_path.write_bytes(b"lixo" * 100)
        self.assertIsNone(wi.open_index(self.index_path, "version:x"))

    def test_truncated_hash_block_returns_none(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        wi.build_index(self.game, self.index_path)
        data = self.index_path.read_bytes()
        self.index_path.write_bytes(data[:-8])
        self.assertIsNone(wi.open_index(self.index_path, wi._patch_fingerprint(self.game)))

    def test_unknown_format_version_returns_none(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        wi.build_index(self.game, self.index_path)
        data = bytearray(self.index_path.read_bytes())
        struct.pack_into("<I", data, 8, 99)
        self.index_path.write_bytes(bytes(data))
        self.assertIsNone(wi.open_index(self.index_path, wi._patch_fingerprint(self.game)))

    def test_unreadable_wad_is_skipped_not_fatal(self):
        self.set_version("16.18.1")
        make_wad(self.game / "bom.wad.client", [1, 2, 3])
        (self.game / "ruim.wad.client").write_bytes(b"nao e um wad")

        stats = wi.build_index(self.game, self.index_path)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.wads_read, 1)
        self.assertEqual(stats.wads_skipped, 1)

    def test_truncated_toc_is_skipped(self):
        self.set_version("16.18.1")
        make_wad(self.game / "bom.wad.client", [1, 2, 3])
        bad = self.game / "curto.wad.client"
        make_wad(bad, [4, 5, 6])
        bad.write_bytes(bad.read_bytes()[:wi._WAD_TOC_OFFSET + 8])

        stats = wi.build_index(self.game, self.index_path)
        self.assertEqual(stats.wads_read, 1)
        self.assertEqual(stats.wads_skipped, 1)


class IndexDoesNotTouchTheGame(FakeGameBase):
    def test_build_writes_nothing_inside_the_game_folder(self):
        self.set_version("16.18.1")
        make_wad(self.game / "DATA" / "a.wad.client", [1, 2, 3])
        before = {p: p.stat().st_mtime_ns for p in self.game.rglob("*") if p.is_file()}

        wi.build_index(self.game, self.index_path)

        after = {p: p.stat().st_mtime_ns for p in self.game.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.index_path.is_relative_to(self.game))

    def test_no_temporary_file_survives_a_build(self):
        self.set_version("16.18.1")
        make_wad(self.game / "a.wad.client", [1, 2, 3])
        wi.build_index(self.game, self.index_path)
        leftovers = [p.name for p in self.index_path.parent.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])


@unittest.skipUnless(GAME_AVAILABLE, "League não instalado")
class MatchesLinearScanOnTheRealGame(unittest.TestCase):
    """A prova que importa: mesma resposta que varrer os WADs de verdade."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.index_path = Path(cls.tmp.name) / "wad_index.bin"
        cls.stats = wi.build_index(REAL_GAME_DIR, cls.index_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_index_was_built_from_the_installed_game(self):
        self.assertIsNotNone(self.stats)
        self.assertGreater(self.stats.entries, 100_000)
        self.assertGreater(self.stats.wads_read, 100)

    def test_sampled_real_hashes_are_all_found(self):
        champions = REAL_GAME_DIR / "DATA" / "FINAL" / "Champions"
        sample = sorted(champions.glob("*.wad.client"))[:3]
        self.assertTrue(sample, "nenhum WAD de campeão encontrado")

        fingerprint = wi._patch_fingerprint(REAL_GAME_DIR)
        with wi.open_index(self.index_path, fingerprint) as index:
            for wad in sample:
                hashes = wi._read_wad_hashes(wad)
                self.assertIsNotNone(hashes)
                for h in list(hashes)[:200]:
                    self.assertIn(h, index, f"{wad.name}: hash {h:016x} ausente do índice")

    def test_random_hashes_are_reported_absent(self):
        fingerprint = wi._patch_fingerprint(REAL_GAME_DIR)
        with wi.open_index(self.index_path, fingerprint) as index:
            invented = [0xDEADBEEF00000000 + i for i in range(500)]
            found = [h for h in invented if h in index]
            self.assertEqual(found, [], "índice afirmou conter hashes inventados")

    def test_index_is_small_relative_to_the_game(self):
        self.assertLess(self.stats.bytes_written, 32 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
