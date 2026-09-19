"""Mod compatibility scan: dangling links, and the union rule that makes it correct.

The rule under test: a link resolves against the game UNION the mod's own entries.
Checking against the game alone once inflated a real measurement from 110 dangling
links to 513 on the same file, which would reject working mods.
"""

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from injection.classic.classic_skin_builder import wad_path_hash
from injection.compat import mod_scanner as ms
from injection.compat import wad_index as wi

_TOC_OFFSET = 272
_ENTRY_SIZE = 32


def make_prop(links, version=3):
    """A minimal PROP bin carrying *links* and no entries."""
    out = bytearray(b"PROP")
    out += struct.pack("<I", version)
    out += struct.pack("<I", len(links))
    for link in links:
        encoded = link.encode("utf-8")
        out += struct.pack("<H", len(encoded)) + encoded
    out += struct.pack("<I", 0)  # entry_count
    return bytes(out)


def build_wad(path, payloads):
    """Write a readable WAD v3 holding {entry_path: payload} as raw entries."""
    items = list(payloads.items())
    header = bytearray(_TOC_OFFSET)
    header[0:2] = b"RW"
    header[2] = 3
    struct.pack_into("<I", header, _TOC_OFFSET - 4, len(items))

    toc = bytearray(len(items) * _ENTRY_SIZE)
    data = bytearray()
    base = _TOC_OFFSET + len(toc)
    for i, (entry_path, payload) in enumerate(items):
        struct.pack_into("<QIIIB", toc, i * _ENTRY_SIZE,
                         wad_path_hash(entry_path), base + len(data),
                         len(payload), len(payload), 0)
        data += payload

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(toc) + bytes(data))


class FakeIndex:
    """Stands in for WadIndex: whatever the installed game is said to have."""

    def __init__(self, paths=()):
        self._hashes = {wad_path_hash(p) for p in paths}

    def __contains__(self, path_hash):
        return path_hash in self._hashes


class ParsePropLinks(unittest.TestCase):
    def test_reads_the_link_list(self):
        links = ["Characters/Annie/Skins/Skin0.bin", "Characters/Annie/Animations/Skin0.bin"]
        self.assertEqual(ms.parse_prop_links(make_prop(links)), links)

    def test_empty_link_list(self):
        self.assertEqual(ms.parse_prop_links(make_prop([])), [])

    def test_patched_bin_is_understood(self):
        data = b"PTCH" + b"\x00" * 8 + make_prop(["a/b.bin"])
        self.assertEqual(ms.parse_prop_links(data), ["a/b.bin"])

    def test_non_prop_payload_returns_none(self):
        for payload in (b"", b"DDS ", b"\x89PNG\r\n\x1a\n", b"randombytes"):
            with self.subTest(payload=payload[:8]):
                self.assertIsNone(ms.parse_prop_links(payload))

    def test_truncated_bin_returns_none(self):
        self.assertIsNone(ms.parse_prop_links(make_prop(["a/b.bin"])[:10]))

    def test_absurd_link_count_is_refused(self):
        data = b"PROP" + struct.pack("<I", 3) + struct.pack("<I", 10**9)
        self.assertIsNone(ms.parse_prop_links(data))

    def test_old_prop_version_returns_none(self):
        self.assertIsNone(ms.parse_prop_links(make_prop(["a/b.bin"], version=1)))


class ScanResolvesAgainstGameUnionMod(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = Path(self.tmp.name) / "mod"

    def test_link_present_in_the_game_resolves(self):
        build_wad(self.mod / "WAD" / "Annie.wad.client",
                  {"characters/annie/skins/skin1.bin": make_prop(["Characters/Annie/Skins/Skin0.bin"])})
        report = ms.scan_mod(self.mod, FakeIndex(["Characters/Annie/Skins/Skin0.bin"]))
        self.assertFalse(report.has_dangling_links)
        self.assertEqual(report.links, 1)
        self.assertEqual(report.bins, 1)

    def test_link_the_mod_ships_itself_resolves(self):
        """The rule that matters: the mod's own entries count as provided."""
        target = "characters/annie/skins/skin7.bin"
        build_wad(self.mod / "WAD" / "Annie.wad.client", {
            "characters/annie/skins/skin1.bin": make_prop([target]),
            target: b"DDS opaque payload",
        })
        report = ms.scan_mod(self.mod, FakeIndex())  # game has nothing
        self.assertFalse(report.has_dangling_links, "mod-provided target was wrongly called dangling")

    def test_link_in_neither_is_dangling(self):
        build_wad(self.mod / "WAD" / "Annie.wad.client",
                  {"characters/annie/skins/skin1.bin": make_prop(["Characters/Annie/Skins/Skin-1.bin"])})
        report = ms.scan_mod(self.mod, FakeIndex(["Characters/Annie/Skins/Skin0.bin"]))
        self.assertTrue(report.has_dangling_links)
        self.assertEqual(report.targets, ("Characters/Annie/Skins/Skin-1.bin",))

    def test_the_known_skin_minus_one_regression(self):
        """Deduplication removed Skins/Skin-1.bin; old mods still link to it."""
        links = [f"Characters/Minion{i}/Skins/Skin-1.bin" for i in range(8)]
        links.append("Characters/Turret/Skins/Skin2.5.bin")
        build_wad(self.mod / "WAD" / "Map.wad.client",
                  {"data/maps/shipping/map11/map11.bin": make_prop(links)})
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertTrue(report.has_dangling_links)
        self.assertEqual(len(report.targets), 9)

    def test_opaque_assets_are_not_counted_as_bins(self):
        build_wad(self.mod / "WAD" / "Map.wad.client", {
            "assets/a.tex": b"opaque texture bytes",
            "assets/b.scb": b"opaque mesh bytes",
        })
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertFalse(report.has_dangling_links)
        self.assertEqual(report.bins, 0)
        self.assertEqual(report.entries, 2)

    def test_extra_known_hashes_are_treated_as_provided(self):
        build_wad(self.mod / "WAD" / "Annie.wad.client",
                  {"characters/annie/skins/skin1.bin": make_prop(["Characters/Annie/Skins/Skin9.bin"])})
        extra = [wad_path_hash("Characters/Annie/Skins/Skin9.bin")]
        self.assertFalse(ms.scan_mod(self.mod, FakeIndex(), extra_known=extra).has_dangling_links)

    def test_several_wads_pool_what_they_provide(self):
        target = "characters/annie/skins/skin7.bin"
        build_wad(self.mod / "WAD" / "A.wad.client",
                  {"characters/annie/skins/skin1.bin": make_prop([target])})
        build_wad(self.mod / "WAD" / "B.wad.client", {target: b"payload"})
        self.assertFalse(ms.scan_mod(self.mod, FakeIndex()).has_dangling_links)


class UnreadableInputIsUnknownNotIncompatible(unittest.TestCase):
    """None means "could not tell", and must never be read as "reject"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = Path(self.tmp.name) / "mod"
        self.mod.mkdir(parents=True)

    def test_folder_without_wads_returns_none(self):
        self.assertIsNone(ms.scan_mod(self.mod, FakeIndex()))

    def test_missing_folder_returns_none(self):
        self.assertIsNone(ms.scan_mod(self.mod / "nao-existe", FakeIndex()))

    def test_every_wad_corrupt_returns_none(self):
        (self.mod / "WAD").mkdir()
        (self.mod / "WAD" / "bad.wad.client").write_bytes(b"nao e um wad")
        self.assertIsNone(ms.scan_mod(self.mod, FakeIndex()))

    def test_one_corrupt_wad_does_not_sink_the_scan(self):
        build_wad(self.mod / "WAD" / "good.wad.client", {"a/b.tex": b"payload"})
        (self.mod / "WAD" / "bad.wad.client").write_bytes(b"nao e um wad")
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertIsNotNone(report)
        self.assertEqual(report.unreadable_wads, 1)

    def test_wads_are_found_without_the_wad_subfolder(self):
        build_wad(self.mod / "loose.wad.client", {"a/b.tex": b"payload"})
        self.assertIsNotNone(ms.scan_mod(self.mod, FakeIndex()))


class ScanAgainstTheRealGame(unittest.TestCase):
    """A link copied out of the installed game must resolve against its own index."""

    REAL_GAME = Path(r"D:\Riot Games\League of Legends\Game")

    @classmethod
    def setUpClass(cls):
        champions = cls.REAL_GAME / "DATA" / "FINAL" / "Champions"
        if not champions.is_dir():
            raise unittest.SkipTest("League não instalado")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.index_path = Path(cls.tmp.name) / "idx.bin"
        if wi.build_index(cls.REAL_GAME, cls.index_path) is None:
            raise unittest.SkipTest("índice do jogo não pôde ser construído")
        cls.fingerprint = wi._patch_fingerprint(cls.REAL_GAME)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_invented_target_is_reported_dangling_against_the_real_index(self):
        with tempfile.TemporaryDirectory() as temp:
            mod = Path(temp) / "mod"
            build_wad(mod / "WAD" / "Fake.wad.client",
                      {"characters/annie/skins/skin1.bin":
                       make_prop(["Characters/NaoExisteMesmo/Skins/Skin-1.bin"])})
            with wi.open_index(self.index_path, self.fingerprint) as index:
                report = ms.scan_mod(mod, index)
        self.assertTrue(report.has_dangling_links)

    def test_real_game_path_resolves_against_the_real_index(self):
        champions = sorted((self.REAL_GAME / "DATA" / "FINAL" / "Champions").glob("*.wad.client"))
        self.assertTrue(champions)
        known_hash = wi._read_wad_hashes(champions[0])[0]

        with tempfile.TemporaryDirectory() as temp:
            mod = Path(temp) / "mod"
            build_wad(mod / "WAD" / "Fake.wad.client", {"a/b.tex": b"payload"})
            with wi.open_index(self.index_path, self.fingerprint) as index:
                self.assertIn(known_hash, index)
                report = ms.scan_mod(mod, index)
        self.assertFalse(report.has_dangling_links)


class WadReaderStillReadsByPath(unittest.TestCase):
    """read() now delegates to read_hash(); its behaviour must not have moved."""

    def test_read_and_read_hash_agree(self):
        from injection.classic.classic_skin_builder import WadReader
        with tempfile.TemporaryDirectory() as temp:
            wad = Path(temp) / "a.wad.client"
            build_wad(wad, {"characters/annie/skins/skin1.bin": b"conteudo"})
            reader = WadReader(wad)
            self.assertEqual(reader.read("characters/annie/skins/skin1.bin"), b"conteudo")
            self.assertEqual(reader.read_hash(wad_path_hash("characters/annie/skins/skin1.bin")),
                             b"conteudo")
            self.assertIsNone(reader.read("nao/existe.bin"))
            self.assertIsNone(reader.read_hash(12345))
            self.assertTrue(reader.has("characters/annie/skins/skin1.bin"))
            self.assertEqual(len(reader.entry_hashes()), 1)


class PartialScansAreNotClaimedAsVerified(unittest.TestCase):
    """Over half the entries in a champion WAD are chunked zstd, which is not decoded.

    A mod may therefore come back with no dangling links simply because nothing was
    inspected. That must be visible, and must never be turned into a refusal.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = Path(self.tmp.name) / "mod"

    def _wad_with_type(self, entry_type, uncompressed=None):
        payload = make_prop(["Characters/NaoExiste/Skins/Skin-1.bin"])
        wad = self.mod / "WAD" / "A.wad.client"
        build_wad(wad, {"characters/annie/skins/skin1.bin": payload})
        raw = bytearray(wad.read_bytes())
        struct.pack_into("<B", raw, _TOC_OFFSET + 20, entry_type)
        if uncompressed is not None:
            struct.pack_into("<I", raw, _TOC_OFFSET + 16, uncompressed)
        wad.write_bytes(bytes(raw))

    def test_clean_simple_mod_is_complete(self):
        build_wad(self.mod / "WAD" / "A.wad.client", {"a/b.tex": b"payload"})
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertTrue(report.complete)
        self.assertEqual(report.skipped_entries, 0)

    def test_unsupported_entry_type_is_skipped_not_dangling(self):
        self._wad_with_type(4)  # chunked zstd
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertEqual(report.skipped_entries, 1)
        self.assertFalse(report.complete)
        self.assertFalse(report.has_dangling_links, "an unread entry must not be called broken")

    def test_oversized_entry_is_skipped(self):
        self._wad_with_type(0, uncompressed=ms._MAX_BIN_BYTES + 1)
        report = ms.scan_mod(self.mod, FakeIndex())
        self.assertEqual(report.skipped_entries, 1)
        self.assertFalse(report.complete)

    def test_summary_says_when_a_scan_was_partial(self):
        self._wad_with_type(4)
        self.assertIn("partial", ms.scan_mod(self.mod, FakeIndex()).summary())

    def test_a_corrupt_wad_also_makes_the_scan_partial(self):
        build_wad(self.mod / "WAD" / "good.wad.client", {"a/b.tex": b"payload"})
        (self.mod / "WAD" / "bad.wad.client").write_bytes(b"nao e um wad")
        self.assertFalse(ms.scan_mod(self.mod, FakeIndex()).complete)


if __name__ == "__main__":
    unittest.main()
