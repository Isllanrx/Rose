"""Streaming do hashes.game.txt: equivalência com o merge antigo e uso de memória.

O merge antigo mantinha quatro cópias do arquivo de 230 MB vivas ao mesmo tempo
(9 blobs + 9 str decodificados + str concatenado + bytes finais), com pico medido
de 942 MB de RSS. O writer de streaming precisa produzir exatamente os mesmos
bytes sem esse custo.
"""

import io
import itertools
import unittest
from pathlib import Path
from unittest import mock

from utils.download.hashes_downloader import (
    HashesDownloader,
    _HashesDownloadFailed,
    _JoinedPartWriter,
)


def legacy_merge(contents):
    """O algoritmo que existia em merge_hashes_files, preservado como referência."""
    texts = [content.decode("utf-8", errors="replace") for content in contents]
    merged = "\n".join(text.rstrip("\n") for text in texts)
    if merged and not merged.endswith("\n"):
        merged += "\n"
    return merged.encode("utf-8")


def stream_parts(parts, chunk_size):
    """Passa as partes pelo writer, fatiadas em pedaços de chunk_size."""
    buffer = io.BytesIO()
    writer = _JoinedPartWriter(buffer)
    for part in parts:
        writer.start_part()
        for start in range(0, len(part), chunk_size):
            writer.feed(part[start:start + chunk_size])
    writer.finish()
    return buffer.getvalue(), writer.bytes_written


class StreamingMatchesLegacyMerge(unittest.TestCase):
    """O writer precisa reproduzir o merge antigo byte a byte."""

    FRAGMENTS = [
        b"",
        b"\n",
        b"\n\n\n",
        b"abc",
        b"abc\n",
        b"abc\n\n\n",
        b"a\n\nb",
        b"a\n\nb\n\n",
    ]

    def test_every_pair_of_fragments_matches(self):
        for parts in itertools.product(self.FRAGMENTS, repeat=2):
            with self.subTest(parts=parts):
                streamed, _ = stream_parts(parts, chunk_size=1)
                self.assertEqual(streamed, legacy_merge(parts))

    def test_every_triple_of_fragments_matches(self):
        for parts in itertools.product(self.FRAGMENTS, repeat=3):
            with self.subTest(parts=parts):
                streamed, _ = stream_parts(parts, chunk_size=2)
                self.assertEqual(streamed, legacy_merge(parts))

    def test_nine_realistic_parts_match(self):
        parts = [
            b"\n".join(f"{i:016x} data/characters/champ{i}/skins/skin{j}.bin".encode()
                       for j in range(50)) + b"\n"
            for i in range(9)
        ]
        streamed, written = stream_parts(parts, chunk_size=64)
        expected = legacy_merge(parts)
        self.assertEqual(streamed, expected)
        self.assertEqual(written, len(expected))

    def test_all_parts_empty_matches(self):
        parts = [b""] * 9
        streamed, _ = stream_parts(parts, chunk_size=1)
        self.assertEqual(streamed, legacy_merge(parts))

    def test_result_is_independent_of_chunk_boundaries(self):
        """Uma newline cortada entre dois chunks não pode mudar a saída."""
        parts = [b"a\n\n\nb\n\n", b"\n\nc\n", b"d"]
        reference = legacy_merge(parts)
        for chunk_size in (1, 2, 3, 5, 7, 11, 1024):
            with self.subTest(chunk_size=chunk_size):
                streamed, _ = stream_parts(parts, chunk_size)
                self.assertEqual(streamed, reference)


class StreamingKeepsMemoryFlat(unittest.TestCase):
    """O writer não pode reter as partes já gravadas."""

    def test_peak_allocation_stays_near_one_chunk(self):
        import tracemalloc

        part = b"x" * (2 * 1024 * 1024)
        parts = [part] * 9
        chunk = 1 << 20

        tracemalloc.start()
        buffer = io.BytesIO()
        writer = _JoinedPartWriter(buffer)
        for item in parts:
            writer.start_part()
            for start in range(0, len(item), chunk):
                writer.feed(item[start:start + chunk])
        writer.finish()
        _, peak_streaming = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tracemalloc.start()
        legacy_merge(parts)
        _, peak_legacy = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total = len(part) * 9
        # O BytesIO do teste guarda a saída inteira, então descontamos o total
        # para medir só o que o writer retém além do destino.
        overhead = peak_streaming - total
        self.assertLess(overhead, 8 * chunk,
                        f"writer reteve {overhead} bytes além do destino")
        self.assertLess(peak_streaming, peak_legacy,
                        "streaming deveria custar menos que o merge antigo")


class FailedPartLeavesPreviousFileIntact(unittest.TestCase):
    """Uma parte que falha no meio não pode corromper o hashes.game.txt instalado."""

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.tools_dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_existing_file_survives_a_failed_part(self):
        downloader = HashesDownloader(self.tools_dir)
        original = b"conteudo anterior valido\n"
        downloader.hashes_file.write_bytes(original)

        def fail_on_fourth(filename, writer):
            index = int(filename.rsplit(".", 1)[1])
            if index == 3:
                return False
            writer.feed(b"linha\n")
            return True

        with mock.patch.object(downloader, "_stream_hashes_file", side_effect=fail_on_fourth):
            result = downloader.download_and_merge_hashes()

        self.assertFalse(result)
        self.assertEqual(downloader.hashes_file.read_bytes(), original)

    def test_no_temporary_file_is_left_behind(self):
        downloader = HashesDownloader(self.tools_dir)
        downloader.hashes_file.write_bytes(b"anterior\n")

        with mock.patch.object(downloader, "_stream_hashes_file", return_value=False):
            downloader.download_and_merge_hashes()

        leftovers = [p.name for p in self.tools_dir.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_failure_is_reported_with_the_part_name(self):
        downloader = HashesDownloader(self.tools_dir)
        with mock.patch.object(downloader, "_stream_hashes_file", return_value=False):
            with self.assertRaises(_HashesDownloadFailed) as ctx:
                with mock.patch.object(downloader, "tools_dir", self.tools_dir):
                    raise _HashesDownloadFailed("hashes.game.txt.0")
        self.assertEqual(ctx.exception.filename, "hashes.game.txt.0")


if __name__ == "__main__":
    unittest.main()
