"""Index of the entries held by the installed game's WAD archives.

Answering "does this path exist in the game?" means scanning every WAD: 392 files
and 31.5 GB on the measured installation. The index trades that for a ~6.4 MB file
holding the 802,652 path hashes in sorted order, built once per patch and searched
by binary search over ``mmap``, so nothing is loaded into memory.

Only the header and the table of contents of each WAD are read, never the file
data, and nothing is ever written inside the game folder.

Every public function is failure tolerant: any problem returns ``None`` or
``False`` and logs, leaving the caller on its previous path. Nothing here may keep
Rose from starting.
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
_HEADER_STRUCT = struct.Struct("<8sIII")  # magic, format version, entry count, fingerprint length
_HEADER_SIZE = _HEADER_STRUCT.size  # 20, padded to 24 below
_HEADER_PADDED = 24  # multiple of 8, so the u64 block starts aligned

# WAD v3 layout, same values as injection/classic/classic_skin_builder.py
_WAD_TOC_OFFSET = 272
_WAD_ENTRY_SIZE = 32
_WAD_GLOB = "*.wad.client"

_CONTENT_METADATA = "content-metadata.json"
_INDEX_FILENAME = "wad_index.bin"


@dataclass(frozen=True)
class IndexStats:
    """Outcome of a successful build."""

    entries: int
    wads_read: int
    wads_skipped: int
    bytes_written: int


def _patch_fingerprint(game_dir: Path) -> str:
    """Identify the installed patch.

    Uses the version from ``content-metadata.json`` when present. Without it, falls
    back to the WAD count and their summed size, which change every patch: worse
    than the version string, better than never invalidating.
    """
    metadata = game_dir / _CONTENT_METADATA
    try:
        version = json.loads(metadata.read_text(encoding="utf-8")).get("version")
        if isinstance(version, str) and version:
            return f"version:{version}"
    except (OSError, ValueError, AttributeError) as e:
        log.debug("[WADIDX] %s unavailable, falling back to WAD sizes: %s", _CONTENT_METADATA, e)

    try:
        count = 0
        total = 0
        for wad in game_dir.rglob(_WAD_GLOB):
            count += 1
            total += wad.stat().st_size
        return f"size:{count}:{total}"
    except OSError as e:
        log.warning("[WADIDX] Could not identify the installed patch: %s", e)
        return ""


def _read_wad_hashes(wad_path: Path) -> Optional[array]:
    """Return the path hashes in a WAD's table of contents, or None if unreadable."""
    try:
        with open(wad_path, "rb") as wad:
            header = wad.read(_WAD_TOC_OFFSET)
            if len(header) < _WAD_TOC_OFFSET or header[:2] != b"RW" or header[2] != 3:
                log.debug("[WADIDX] %s is not a WAD v3, skipped", wad_path.name)
                return None
            (count,) = struct.unpack_from("<I", header, _WAD_TOC_OFFSET - 4)
            if count <= 0:
                return array("Q")
            toc = wad.read(count * _WAD_ENTRY_SIZE)
            if len(toc) < count * _WAD_ENTRY_SIZE:
                log.warning("[WADIDX] %s has a truncated table of contents "
                            "(%d of %d bytes), skipped",
                            wad_path.name, len(toc), count * _WAD_ENTRY_SIZE)
                return None
    except (OSError, struct.error) as e:
        log.debug("[WADIDX] %s unreadable: %s", wad_path.name, e)
        return None

    hashes = array("Q")
    view = memoryview(toc)
    for offset in range(0, count * _WAD_ENTRY_SIZE, _WAD_ENTRY_SIZE):
        hashes.append(int.from_bytes(view[offset:offset + 8], "little"))
    return hashes


def build_index(game_dir: Path, index_path: Path) -> Optional[IndexStats]:
    """Build the index of *game_dir* at *index_path*. Returns None on failure.

    Meant to run in the background. Never raises: a missing game, a corrupt WAD or a
    full disk all become a log line and None.
    """
    game_dir = Path(game_dir)
    if not game_dir.is_dir():
        log.warning("[WADIDX] Game folder not found: %s", game_dir)
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
        log.warning("[WADIDX] WAD scan interrupted: %s", e)
        return None

    if not read:
        log.warning("[WADIDX] No readable WAD in %s", game_dir)
        return None

    # Sort and deduplicate: the same path shows up in several WADs.
    unique = array("Q", sorted(set(hashes)))
    del hashes

    payload = fingerprint.encode("utf-8")
    padding = b"\x00" * (_HEADER_PADDED - _HEADER_SIZE)
    tail = (-len(payload)) % 8  # keeps the u64 block on an 8 byte boundary

    try:
        with atomic_write(index_path, "wb", durable=False) as handle:
            handle.write(_HEADER_STRUCT.pack(_MAGIC, _FORMAT_VERSION, len(unique), len(payload)))
            handle.write(padding)
            handle.write(payload)
            handle.write(b"\x00" * tail)
            unique.tofile(handle)
    except (OSError, ValueError) as e:
        log.warning("[WADIDX] Could not write the index: %s", e)
        return None

    written = _HEADER_PADDED + len(payload) + tail + len(unique) * 8
    log.info(
        "[WADIDX] Indexed %d entries from %d WADs (%d skipped), %.1f MB, patch %s",
        len(unique), read, skipped, written / 1e6, fingerprint,
    )
    if skipped:
        # Skipped WADs mean the index is incomplete, so a later compatibility check
        # can miss a target the game really has. Say so rather than only counting it.
        log.warning("[WADIDX] %d of %d WADs could not be read; the index is partial",
                    skipped, read + skipped)
    return IndexStats(entries=len(unique), wads_read=read, wads_skipped=skipped,
                      bytes_written=written)


class WadIndex:
    """Read-only lookups over a written index.

    Use as a context manager to release the ``mmap``. An index from another patch, a
    truncated one or an unknown format makes ``open_index`` return None rather than
    answer wrongly.
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
            log.debug("[WADIDX] Failed to close the index: %s", e)

    def __contains__(self, path_hash: int) -> bool:
        """Binary search over the mmap: O(log n), nothing loaded."""
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
        """Of the given hashes, the ones the installed game does not have."""
        return [h for h in path_hashes if h not in self]


def open_index(index_path: Path, expected_fingerprint: str) -> Optional[WadIndex]:
    """Open the index if it exists and belongs to the expected patch. Never raises."""
    index_path = Path(index_path)
    handle = None
    try:
        handle = open(index_path, "rb")
        header = handle.read(_HEADER_PADDED)
        if len(header) < _HEADER_PADDED:
            raise ValueError("truncated header")
        magic, version, count, payload_len = _HEADER_STRUCT.unpack_from(header, 0)
        if magic != _MAGIC:
            raise ValueError("unknown signature")
        if version != _FORMAT_VERSION:
            raise ValueError(f"format version {version}")

        payload = handle.read(payload_len)
        if len(payload) < payload_len:
            raise ValueError("truncated fingerprint")
        fingerprint = payload.decode("utf-8", errors="replace")
        if expected_fingerprint and fingerprint != expected_fingerprint:
            log.info("[WADIDX] Index belongs to another patch (%s), rebuilding", fingerprint)
            handle.close()
            return None

        offset = _HEADER_PADDED + payload_len + ((-payload_len) % 8)
        if index_path.stat().st_size < offset + count * 8:
            raise ValueError("truncated hash block")

        mapping = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            return WadIndex(handle, mapping, fingerprint, count, offset)
        except BaseException:
            # A mapping left open keeps Windows from replacing the file, which would
            # freeze the index at this patch forever without anything being logged.
            mapping.close()
            raise
    except FileNotFoundError:
        # Normal on a first run and after a patch: ensure_index builds it next.
        log.debug("[WADIDX] No index at %s yet", index_path)
        return None
    except (OSError, ValueError, TypeError, struct.error) as e:
        # Anything else means the file exists but is unusable, which is worth seeing
        # in a default INFO log: it repeats every run until the rebuild succeeds.
        log.warning("[WADIDX] Index at %s is unusable (%s), it will be rebuilt",
                    index_path.name, e)
        if handle is not None:
            try:
                handle.close()
            except OSError as close_error:
                log.debug("[WADIDX] Could not close the index handle: %s", close_error)
        return None


def ensure_index(game_dir: Path, index_path: Path) -> Optional[WadIndex]:
    """Open the current patch's index, building it when absent or stale.

    The expected entry point for background use. Returns None when no valid index can
    be had, leaving the caller on its previous path.
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


def default_index_path() -> Path:
    """Where the running app keeps the index: the state directory, never the game folder.

    Imported lazily because get_state_dir() creates the directory, and importing this
    module must stay free of side effects for the tests.
    """
    from utils.core.paths import get_state_dir

    return get_state_dir() / _INDEX_FILENAME


def ensure_index_built(game_dir: Path, index_path: Path) -> bool:
    """Build the index if it is missing or belongs to another patch.

    Returns True when a valid index is on disk. Nothing is kept open, so callers that
    only want the index prepared do not hold an mmap for the whole session.
    """
    index = ensure_index(game_dir, index_path)
    if index is None:
        return False
    index.close()
    return True
