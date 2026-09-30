#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Random access to the entries of a League WAD v3 file."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Optional

import xxhash
import zstandard

WAD_TOC_OFFSET = 272
WAD_ENTRY_SIZE = 32
_WAD_TYPE_RAW = 0
_WAD_TYPE_GZIP = 1
_WAD_TYPE_ZSTD = 3


class WadFormatError(Exception):
    """A WAD file or entry is malformed or uses an unsupported format."""


def wad_path_hash(path: str) -> int:
    return xxhash.xxh64_intdigest(path.lower().encode("utf-8"))


class WadReader:
    """Random access to entries of a League WAD v3 file (table of contents read once)."""

    def __init__(self, path: Path):
        self.path = path
        try:
            with open(path, "rb") as wad:
                header = wad.read(WAD_TOC_OFFSET)
                if len(header) < WAD_TOC_OFFSET or header[:2] != b"RW" or header[2] != 3:
                    raise WadFormatError(f"{path.name} is not a supported WAD v3 file")
                (count,) = struct.unpack_from("<I", header, WAD_TOC_OFFSET - 4)
                toc = wad.read(count * WAD_ENTRY_SIZE)
            self._entries = {}
            for index in range(count):
                path_hash, offset, compressed, uncompressed, type_byte = struct.unpack_from(
                    "<QIIIB", toc, index * WAD_ENTRY_SIZE
                )
                self._entries[path_hash] = (offset, compressed, uncompressed, type_byte & 0x0F)
        except struct.error as e:
            raise WadFormatError(f"{path.name} has a truncated table of contents") from e

    def has(self, entry_path: str) -> bool:
        return wad_path_hash(entry_path) in self._entries

    def entry_hashes(self) -> tuple[int, ...]:
        """Every path hash in the table of contents, for callers with no path list."""
        return tuple(self._entries)

    def entry_info(self, path_hash: int) -> Optional[tuple[int, int]]:
        """(uncompressed size, entry type) of an entry, without reading it."""
        entry = self._entries.get(path_hash)
        return None if entry is None else (entry[2], entry[3])

    @staticmethod
    def is_readable_type(entry_type: int) -> bool:
        """Whether read_hash can decode this entry type at all.

        The game also ships chunked zstd entries (type 4) that this reader has never
        supported; they are over half of the entries in a champion WAD, so callers
        that walk every entry have to expect them rather than treat them as damage.
        """
        return entry_type in (_WAD_TYPE_RAW, _WAD_TYPE_GZIP, _WAD_TYPE_ZSTD)

    def read(self, entry_path: str) -> Optional[bytes]:
        return self.read_hash(wad_path_hash(entry_path), entry_path)

    def read_hash(self, path_hash: int, label: Optional[str] = None) -> Optional[bytes]:
        """Read an entry by its path hash. *label* only improves error messages."""
        entry = self._entries.get(path_hash)
        if entry is None:
            return None
        name = label or f"{path_hash:016x}"
        offset, compressed, uncompressed, entry_type = entry
        with open(self.path, "rb") as wad:
            wad.seek(offset)
            raw = wad.read(compressed)
        try:
            if entry_type == _WAD_TYPE_RAW:
                return raw
            if entry_type == _WAD_TYPE_GZIP:
                return zlib.decompress(raw, 16 + zlib.MAX_WBITS)
            if entry_type == _WAD_TYPE_ZSTD:
                return zstandard.ZstdDecompressor().decompress(raw, max_output_size=uncompressed)
        except (zlib.error, zstandard.ZstdError) as e:
            raise WadFormatError(f"corrupted WAD entry {name} in {self.path.name}") from e
        raise WadFormatError(f"unsupported WAD entry type {entry_type} for {name}")
