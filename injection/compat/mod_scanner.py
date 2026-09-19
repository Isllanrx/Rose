"""Decide whether a custom mod still fits the installed game, before injecting it.

A mod entry is a whole-file replacement, not a patch. The dangerous case is a PROP
bin whose link list points at a file the game no longer ships: the game resolves its
whole data graph while loading the map, finds nothing, and dies. Measured in-game on
2026-09-18, patch 16.18: ``FATAL ERROR. Missing data: 0x0`` 2.2 seconds after
``Loading Started``, with the same mod loading fine when the overlay arrived too late
to be applied.

The failure is immediate and deterministic, so refusing up front is safe: there is no
partial success to preserve.

The one rule that makes this correct: a link resolves against the game **union the
mod's own entries**, never the game alone. Mods routinely ship their own targets as
new assets, and checking against the game alone inflated one measurement from 110
dangling links to 513 on the same file.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from utils.core.logging import get_logger

from ..classic.classic_skin_builder import ClassicSkinError, WadReader, wad_path_hash
from .wad_index import WadIndex

log = get_logger()

_PROP_MAGIC = b"PROP"
_PATCH_MAGIC = b"PTCH"
_PATCH_HEADER = 12
_WAD_GLOB = "*.wad.client"

# A mod that reports more links than this is almost certainly being misparsed.
_MAX_LINKS_PER_BIN = 100_000

# Well past any real PROP bin; the largest measured in a broken mod was 384 KB.
_MAX_BIN_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class DanglingLink:
    """A link target that neither the game nor the mod provides."""

    wad: str
    entry_hash: int
    target: str


@dataclass(frozen=True)
class CompatReport:
    """What a scan found.

    Two questions, deliberately kept apart. ``has_dangling_links`` is positive
    evidence that the mod will crash the game and is the only sound reason to refuse
    an injection. ``complete`` says whether every entry could actually be inspected:
    over half the entries in a champion WAD are chunked zstd, which this reader has
    never decoded, so a mod can come back clean simply because nothing was looked at.

    Never refuse on ``not complete``. An unchecked mod is unknown, not broken.
    """

    entries: int
    bins: int
    links: int
    dangling: tuple[DanglingLink, ...]
    skipped_entries: int
    unreadable_entries: int
    unreadable_wads: int

    @property
    def has_dangling_links(self) -> bool:
        return bool(self.dangling)

    @property
    def complete(self) -> bool:
        return not (self.skipped_entries or self.unreadable_entries or self.unreadable_wads)

    @property
    def targets(self) -> tuple[str, ...]:
        """The distinct missing targets, which is what a user can act on."""
        return tuple(sorted({link.target for link in self.dangling}))

    def summary(self) -> str:
        if self.has_dangling_links:
            head = (f"{len(self.dangling)} of {self.links} links dangling "
                    f"across {len(self.targets)} targets")
        else:
            head = f"{self.entries} entries, {self.bins} bins, {self.links} links, all resolved"
        if self.complete:
            return head
        return (f"{head} (partial: {self.skipped_entries} entries of an unsupported type, "
                f"{self.unreadable_entries} unreadable, {self.unreadable_wads} bad WADs)")


def parse_prop_links(data: bytes) -> Optional[list[str]]:
    """Return the link list of a PROP bin, or None if *data* is not one.

    Only the header is walked; the entry bodies that follow are left alone.
    """
    try:
        offset = _PATCH_HEADER if data[:4] == _PATCH_MAGIC else 0
        if data[offset:offset + 4] != _PROP_MAGIC:
            return None
        offset += 4
        (version,) = struct.unpack_from("<I", data, offset)
        offset += 4
        if version < 2:
            return None
        (link_count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        if link_count > _MAX_LINKS_PER_BIN:
            log.debug("[COMPAT] Refusing a bin claiming %d links", link_count)
            return None

        links = []
        for _ in range(link_count):
            (length,) = struct.unpack_from("<H", data, offset)
            offset += 2
            links.append(data[offset:offset + length].decode("utf-8", errors="replace"))
            offset += length
        return links
    except (struct.error, IndexError) as e:
        log.debug("[COMPAT] Malformed PROP header: %s", e)
        return None


def iter_mod_wads(mod_dir: Path) -> Iterator[Path]:
    """The WAD archives of an extracted mod folder, in a stable order."""
    wad_root = mod_dir / "WAD"
    root = wad_root if wad_root.is_dir() else mod_dir
    yield from sorted(root.rglob(_WAD_GLOB))


def scan_mod(mod_dir: Path, index: WadIndex,
             extra_known: Optional[Iterable[int]] = None) -> Optional[CompatReport]:
    """Scan an extracted mod folder against the installed game.

    Returns None when the mod cannot be read at all, which is different from a mod
    that reads fine and has no dangling links. Callers must treat None as "unknown",
    never as "incompatible", so an unreadable folder does not block an injection that
    would have worked.
    """
    mod_dir = Path(mod_dir)
    wads = list(iter_mod_wads(mod_dir))
    if not wads:
        log.debug("[COMPAT] No WAD found in %s", mod_dir)
        return None

    readers: list[tuple[Path, WadReader]] = []
    unreadable_wads = 0
    provided: set[int] = set(extra_known or ())

    for wad_path in wads:
        try:
            reader = WadReader(wad_path)
        except (ClassicSkinError, OSError) as e:
            log.debug("[COMPAT] %s unreadable: %s", wad_path.name, e)
            unreadable_wads += 1
            continue
        readers.append((wad_path, reader))
        provided.update(reader.entry_hashes())

    if not readers:
        return None

    entries = len(provided) - len(set(extra_known or ()))
    bins = links = skipped = unreadable = 0
    dangling: list[DanglingLink] = []

    for wad_path, reader in readers:
        for entry_hash in reader.entry_hashes():
            info = reader.entry_info(entry_hash)
            if info is None:
                continue
            uncompressed, entry_type = info
            if not WadReader.is_readable_type(entry_type):
                skipped += 1
                continue
            if uncompressed > _MAX_BIN_BYTES:
                # Far past any real bin, so decompressing it would only cost time.
                skipped += 1
                continue

            try:
                payload = reader.read_hash(entry_hash)
            except (ClassicSkinError, OSError) as e:
                log.debug("[COMPAT] Entry %016x unreadable: %s", entry_hash, e)
                unreadable += 1
                continue
            if not payload:
                continue

            targets = parse_prop_links(payload)
            if targets is None:
                continue  # not a PROP bin: opaque asset, nothing to resolve
            bins += 1
            links += len(targets)

            for target in targets:
                target_hash = wad_path_hash(target)
                # The game union the mod itself: a mod often ships its own targets.
                if target_hash in provided or target_hash in index:
                    continue
                dangling.append(DanglingLink(wad_path.name, entry_hash, target))

    report = CompatReport(entries=entries, bins=bins, links=links,
                          dangling=tuple(dangling), skipped_entries=skipped,
                          unreadable_entries=unreadable, unreadable_wads=unreadable_wads)
    log.info("[COMPAT] %s: %s", mod_dir.name, report.summary())
    return report
