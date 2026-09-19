"""Índice das entradas dos WADs do jogo instalado.

Responder "esse caminho existe no jogo?" hoje exige varrer os WADs: 392 arquivos e
31,5 GB na instalação medida. O índice troca isso por um arquivo de ~7 MB com os
898 mil hashes ordenados, construído uma vez por patch e consultado por busca
binária sobre ``mmap`` — sem carregar nada em memória.

Só lê o cabeçalho e a tabela de conteúdo de cada WAD, nunca os dados, e nunca
escreve dentro da pasta do jogo.

Todas as funções públicas são à prova de falha: qualquer problema devolve ``None``
ou ``False`` e registra log, para o chamador seguir pelo caminho antigo. Nada aqui
pode impedir o Rose de subir.
"""

from __future__ import annotations

import json
import mmap
import struct
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from utils.core.atomic_file import atomic_write
from utils.core.logging import get_logger

log = get_logger()

_MAGIC = b"ROSEWIDX"
_FORMAT_VERSION = 1
_HEADER_STRUCT = struct.Struct("<8sIII")  # magic, versão, nº de entradas, tam. fingerprint
_HEADER_SIZE = _HEADER_STRUCT.size  # 20 -> alinhado para 24 abaixo
_HEADER_PADDED = 24  # múltiplo de 8: garante que os u64 comecem alinhados

# Formato WAD v3, iguais aos de injection/classic/classic_skin_builder.py
_WAD_TOC_OFFSET = 272
_WAD_ENTRY_SIZE = 32
_WAD_GLOB = "*.wad.client"

_CONTENT_METADATA = "content-metadata.json"


@dataclass(frozen=True)
class IndexStats:
    """Resultado de uma construção bem-sucedida."""

    entries: int
    wads_read: int
    wads_skipped: int
    bytes_written: int


def _patch_fingerprint(game_dir: Path) -> str:
    """Identifica o patch instalado.

    Usa a versão do ``content-metadata.json`` quando existe. Se faltar, cai para a
    contagem e o tamanho somado dos WADs, que mudam a cada patch — pior que a
    versão, mas melhor que não invalidar nunca.
    """
    metadata = game_dir / _CONTENT_METADATA
    try:
        version = json.loads(metadata.read_text(encoding="utf-8")).get("version")
        if isinstance(version, str) and version:
            return f"version:{version}"
    except (OSError, ValueError, AttributeError) as e:
        log.debug("[WADIDX] %s indisponível, usando tamanho dos WADs: %s", _CONTENT_METADATA, e)

    try:
        count = 0
        total = 0
        for wad in game_dir.rglob(_WAD_GLOB):
            count += 1
            total += wad.stat().st_size
        return f"size:{count}:{total}"
    except OSError as e:
        log.warning("[WADIDX] Não foi possível identificar o patch instalado: %s", e)
        return ""


def _read_wad_hashes(wad_path: Path) -> Optional[array]:
    """Devolve os hashes da tabela de conteúdo de um WAD, ou None se não der para ler."""
    try:
        with open(wad_path, "rb") as wad:
            header = wad.read(_WAD_TOC_OFFSET)
            if len(header) < _WAD_TOC_OFFSET or header[:2] != b"RW" or header[2] != 3:
                return None
            (count,) = struct.unpack_from("<I", header, _WAD_TOC_OFFSET - 4)
            if count <= 0:
                return array("Q")
            toc = wad.read(count * _WAD_ENTRY_SIZE)
            if len(toc) < count * _WAD_ENTRY_SIZE:
                return None
    except (OSError, struct.error) as e:
        log.debug("[WADIDX] %s ilegível: %s", wad_path.name, e)
        return None

    hashes = array("Q")
    view = memoryview(toc)
    for offset in range(0, count * _WAD_ENTRY_SIZE, _WAD_ENTRY_SIZE):
        hashes.append(int.from_bytes(view[offset:offset + 8], "little"))
    return hashes


def build_index(game_dir: Path, index_path: Path) -> Optional[IndexStats]:
    """Constrói o índice de *game_dir* em *index_path*. Devolve None se falhar.

    Pensada para rodar em background. Nunca levanta: um jogo ausente, um WAD
    corrompido ou um disco cheio viram log e None.
    """
    game_dir = Path(game_dir)
    if not game_dir.is_dir():
        log.warning("[WADIDX] Pasta do jogo não encontrada: %s", game_dir)
        return None

    fingerprint = _patch_fingerprint(game_dir)
    if not fingerprint:
        return None

    hashes = array("Q")
    read = skipped = 0
    try:
        for wad in sorted(game_dir.rglob(_WAD_GLOB)):
            entries = _read_wad_hashes(wad)
            if entries is None:
                skipped += 1
                continue
            hashes.extend(entries)
            read += 1
    except OSError as e:
        log.warning("[WADIDX] Varredura dos WADs interrompida: %s", e)
        return None

    if not read:
        log.warning("[WADIDX] Nenhum WAD legível em %s", game_dir)
        return None

    # Ordenar e remover duplicatas: o mesmo caminho aparece em vários WADs.
    unique = array("Q", sorted(set(hashes)))
    del hashes

    payload = fingerprint.encode("utf-8")
    padding = b"\x00" * (_HEADER_PADDED - _HEADER_SIZE)
    tail = (-len(payload)) % 8  # mantém os u64 em múltiplo de 8 a partir do início

    try:
        with atomic_write(index_path, "wb", durable=False) as handle:
            handle.write(_HEADER_STRUCT.pack(_MAGIC, _FORMAT_VERSION, len(unique), len(payload)))
            handle.write(padding)
            handle.write(payload)
            handle.write(b"\x00" * tail)
            unique.tofile(handle)
    except (OSError, ValueError) as e:
        log.warning("[WADIDX] Não foi possível gravar o índice: %s", e)
        return None

    written = _HEADER_PADDED + len(payload) + tail + len(unique) * 8
    log.info(
        "[WADIDX] Índice com %d entradas de %d WADs (%d ignorados), %.1f MB",
        len(unique), read, skipped, written / 1e6,
    )
    return IndexStats(entries=len(unique), wads_read=read, wads_skipped=skipped,
                      bytes_written=written)


class WadIndex:
    """Consulta somente-leitura sobre um índice gravado.

    Usar como context manager para liberar o ``mmap``. Um índice de outro patch,
    truncado ou de formato desconhecido faz ``open_index`` devolver None em vez de
    responder errado.
    """

    def __init__(self, handle, mapping: mmap.mmap, fingerprint: str, count: int, offset: int):
        self._handle = handle
        self._mapping = mapping
        self._view = memoryview(mapping)[offset:offset + count * 8].cast("Q")
        self.fingerprint = fingerprint
        self.count = count

    def __enter__(self) -> "WadIndex":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._view.release()
            self._mapping.close()
            self._handle.close()
        except (BufferError, OSError) as e:
            log.debug("[WADIDX] Falha ao fechar o índice: %s", e)

    def __contains__(self, path_hash: int) -> bool:
        """Busca binária sobre o mmap: O(log n), sem carregar o índice."""
        low, high = 0, self.count
        while low < high:
            middle = (low + high) // 2
            value = self._view[middle]
            if value < path_hash:
                low = middle + 1
            elif value > path_hash:
                high = middle
            else:
                return True
        return False

    def missing(self, path_hashes: Iterator[int]) -> list[int]:
        """Dos hashes recebidos, os que o jogo instalado não tem."""
        return [h for h in path_hashes if h not in self]


def open_index(index_path: Path, expected_fingerprint: str) -> Optional[WadIndex]:
    """Abre o índice se ele existir e for do patch esperado. Nunca levanta."""
    index_path = Path(index_path)
    handle = None
    try:
        handle = open(index_path, "rb")
        header = handle.read(_HEADER_PADDED)
        if len(header) < _HEADER_PADDED:
            raise ValueError("cabeçalho truncado")
        magic, version, count, payload_len = _HEADER_STRUCT.unpack_from(header, 0)
        if magic != _MAGIC:
            raise ValueError("assinatura desconhecida")
        if version != _FORMAT_VERSION:
            raise ValueError(f"versão de formato {version}")

        payload = handle.read(payload_len)
        if len(payload) < payload_len:
            raise ValueError("fingerprint truncado")
        fingerprint = payload.decode("utf-8", errors="replace")
        if expected_fingerprint and fingerprint != expected_fingerprint:
            log.info("[WADIDX] Índice é de outro patch (%s), será reconstruído", fingerprint)
            handle.close()
            return None

        offset = _HEADER_PADDED + payload_len + ((-payload_len) % 8)
        if index_path.stat().st_size < offset + count * 8:
            raise ValueError("bloco de hashes truncado")

        mapping = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        return WadIndex(handle, mapping, fingerprint, count, offset)
    except (OSError, ValueError, struct.error) as e:
        log.debug("[WADIDX] Índice indisponível (%s): %s", index_path.name, e)
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        return None


def ensure_index(game_dir: Path, index_path: Path) -> Optional[WadIndex]:
    """Abre o índice do patch atual, construindo-o se estiver ausente ou velho.

    É o ponto de entrada esperado para uso em background. Devolve None se não for
    possível ter um índice válido; o chamador segue pelo caminho antigo.
    """
    fingerprint = _patch_fingerprint(Path(game_dir))
    if not fingerprint:
        return None

    index = open_index(index_path, fingerprint)
    if index is not None:
        return index

    if build_index(game_dir, index_path) is None:
        return None
    return open_index(index_path, fingerprint)
