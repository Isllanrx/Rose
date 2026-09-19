"""Integridade da biblioteca real contra o jogo instalado.

Valida o que nenhum teste unitário alcança: os `.fantome` que o usuário de fato
injeta ainda resolvem contra o patch instalado agora.

Um mod cujos BINs referenciam arquivo removido pela Riot derruba o jogo no
loading screen com `ALE-… FATAL ERROR. Missing data: 0x0` — validado in-game em
2026-09-18 (ver `.claude/reviews/2026-09-18-compatibilidade-de-mods-custom.md`).

Regras de medição que este teste respeita, e que são fáceis de errar:
  * o hash de caminho é `xxhash64(path.lower())` — determinístico entre patches;
  * um link resolve contra **jogo ∪ próprio mod**: o mod costuma trazer seus
    próprios alvos como assets novos. Medir só contra o jogo inflou a contagem
    de 110 para 513 no mesmo arquivo durante a investigação.

Pesado por natureza: lê TOCs de dezenas de GB de WAD. Pula com mensagem clara
quando o jogo ou a biblioteca não estão disponíveis.
"""

import os
import struct
import sys
import unittest
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import xxhash
    import zstandard
except ImportError:  # pragma: no cover - ambiente sem as deps do Rift Clássico
    xxhash = None
    zstandard = None

from utils.core.paths import get_user_data_dir  # noqa: E402

WAD_HEADER_SIZE = 272
WAD_ENTRY_SIZE = 32
WAD_COUNT_OFFSET = 268
# Entradas acima disso são asset binário puro (textura/malha), nunca PROP.
MAX_BIN_CANDIDATE_BYTES = 4_000_000
# Quantos mods da biblioteca amostrar. A biblioteca tem ~9 mil arquivos.
LIBRARY_SAMPLE_SIZE = 250


def _game_dir() -> Path:
    from config import get_config_option

    configured = get_config_option("General", "leaguepath")
    if configured:
        return Path(configured) / "DATA" / "FINAL"
    return Path(r"D:\Riot Games\League of Legends\Game\DATA\FINAL")


def read_toc(path: Path) -> dict:
    """TOC de um WAD v3: {path_hash: (offset, compressed, uncompressed, type)}."""
    with open(path, "rb") as wad:
        header = wad.read(WAD_HEADER_SIZE)
        if len(header) < WAD_HEADER_SIZE or header[:2] != b"RW":
            raise ValueError(f"{path.name} não é um WAD reconhecível")
        (count,) = struct.unpack_from("<I", header, WAD_COUNT_OFFSET)
        raw = wad.read(count * WAD_ENTRY_SIZE)
    entries = {}
    for index in range(count):
        path_hash, offset, comp, uncomp, type_byte = struct.unpack_from(
            "<QIIIB", raw, index * WAD_ENTRY_SIZE
        )
        entries[path_hash] = (offset, comp, uncomp, type_byte & 0x0F)
    return entries


def read_entry(path: Path, toc: dict, path_hash: int):
    entry = toc.get(path_hash)
    if entry is None:
        return None
    offset, comp, uncomp, kind = entry
    with open(path, "rb") as wad:
        wad.seek(offset)
        raw = wad.read(comp)
    if kind == 0:
        return raw
    if kind in (1, 2):
        return zlib.decompress(raw, 16 + zlib.MAX_WBITS)
    if kind == 3:
        return zstandard.ZstdDecompressor().decompress(raw, max_output_size=uncomp)
    return None


def wad_path_hash(text: str) -> int:
    return xxhash.xxh64(text.lower().encode()).intdigest()


def prop_links(data: bytes):
    """Lista `linked` de um PROP, ou None se não for PROP."""
    try:
        offset = 12 if data[:4] == b"PTCH" else 0
        if data[offset:offset + 4] != b"PROP":
            return None
        offset += 8  # magic + versão
        (link_count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        links = []
        for _ in range(link_count):
            (length,) = struct.unpack_from("<H", data, offset)
            offset += 2
            links.append(data[offset:offset + length].decode("utf-8", "replace"))
            offset += length
        return links
    except (struct.error, IndexError):
        return None


def dangling_links(mod_wad: Path, game_hashes: set) -> list:
    """Links do mod que não resolvem nem no jogo nem no próprio mod."""
    mod_toc = read_toc(mod_wad)
    universe = game_hashes | set(mod_toc)
    dangling = []
    for path_hash, (_, _, uncomp, _) in mod_toc.items():
        if uncomp > MAX_BIN_CANDIDATE_BYTES:
            continue
        try:
            data = read_entry(mod_wad, mod_toc, path_hash)
        except (zlib.error, ValueError, OSError):
            continue
        if not data or data[:4] not in (b"PROP", b"PTCH"):
            continue
        for link in prop_links(data) or []:
            if wad_path_hash(link) not in universe:
                dangling.append(link)
    return dangling


@unittest.skipIf(xxhash is None or zstandard is None, "xxhash/zstandard não instalados")
class SkinLibraryResolvesAgainstInstalledGame(unittest.TestCase):
    """A biblioteca que o usuário injeta precisa resolver contra o patch atual."""

    @classmethod
    def setUpClass(cls):
        cls.game = _game_dir()
        if not cls.game.is_dir():
            raise unittest.SkipTest(f"jogo não encontrado em {cls.game}")
        cls.library = get_user_data_dir() / "skins"
        if not cls.library.is_dir():
            raise unittest.SkipTest(f"biblioteca de skins não encontrada em {cls.library}")

        cls.game_hashes = set()
        for wad in cls.game.rglob("*.wad.client"):
            try:
                cls.game_hashes |= set(read_toc(wad))
            except (ValueError, OSError, struct.error):
                continue
        if not cls.game_hashes:
            raise unittest.SkipTest("nenhum WAD do jogo pôde ser lido")

    def test_game_index_is_plausible(self):
        # Guarda contra um índice vazio ou truncado passar despercebido e fazer
        # todo mod parecer quebrado.
        self.assertGreater(
            len(self.game_hashes),
            100_000,
            f"índice do jogo tem só {len(self.game_hashes)} hashes — leitura incompleta",
        )

    def test_sampled_library_mods_have_no_dangling_links(self):
        archives = sorted(self.library.rglob("*.fantome"))[:LIBRARY_SAMPLE_SIZE]
        if not archives:
            self.skipTest("biblioteca vazia")

        broken = {}
        unreadable = []
        for archive in archives:
            try:
                with zipfile.ZipFile(archive) as bundle:
                    wad_names = [n for n in bundle.namelist() if n.lower().endswith(".wad.client")]
                    for name in wad_names:
                        extracted = Path(os.environ.get("TEMP", ".")) / "rose_heavy_wad.tmp"
                        extracted.write_bytes(bundle.read(name))
                        try:
                            found = dangling_links(extracted, self.game_hashes)
                        finally:
                            extracted.unlink(missing_ok=True)
                        if found:
                            broken[archive.name] = sorted(set(found))[:3]
            except (zipfile.BadZipFile, ValueError, OSError, struct.error) as exc:
                unreadable.append(f"{archive.name}: {exc}")

        self.assertEqual(
            unreadable, [], f"{len(unreadable)} arquivos ilegíveis na biblioteca: {unreadable[:3]}"
        )
        self.assertEqual(
            broken,
            {},
            f"{len(broken)} de {len(archives)} mods têm link pendurado e crashariam o jogo "
            f"no loading. Exemplos: {dict(list(broken.items())[:3])}",
        )

    def test_library_archives_are_valid_zip_with_metadata(self):
        archives = sorted(self.library.rglob("*.fantome"))[:LIBRARY_SAMPLE_SIZE]
        if not archives:
            self.skipTest("biblioteca vazia")

        invalid = []
        for archive in archives:
            try:
                with zipfile.ZipFile(archive) as bundle:
                    names = [n.lower() for n in bundle.namelist()]
                    if not any(n.endswith(".wad.client") for n in names):
                        invalid.append(f"{archive.name}: sem WAD")
                    elif not any("info.json" in n for n in names):
                        invalid.append(f"{archive.name}: sem META/info.json")
            except (zipfile.BadZipFile, OSError) as exc:
                invalid.append(f"{archive.name}: {exc}")

        self.assertEqual(invalid, [], f"{len(invalid)} arquivos inválidos: {invalid[:5]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
