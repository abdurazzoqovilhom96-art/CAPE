"""Generic byte codecs over the canonical raw array (spec 17.2): raw, Zstandard, LZMA.
Shape/dtype travel in a small uncompressed CAPE container header (counted as metadata)."""

from __future__ import annotations

import lzma

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter, pack_container, unpack_container

CODEC_IDS = {"none": 1, "zstd": 2, "lzma": 3}


class GenericAdapter(CodecAdapter):
    adapter_name = "generic"

    def __init__(self, method_id, options=None, threads=1):
        super().__init__(method_id, options, threads)
        self.codec = self.options.get("codec", "none")
        if self.codec not in CODEC_IDS:
            raise ValueError(f"{method_id}: unknown generic codec {self.codec}")
        self.level = int(self.options.get("level", 3))

    def _zstd(self):
        try:
            import zstandard
        except ImportError as exc:
            raise AdapterUnavailable(f"zstandard missing: {exc}") from exc
        return zstandard

    def availability(self) -> dict:
        if self.codec == "zstd":
            try:
                self._zstd()
            except AdapterUnavailable as exc:
                return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        if self.codec == "zstd":
            return f"zstandard {self._zstd().__version__} (libzstd {'.'.join(map(str, self._zstd().ZSTD_VERSION))})"
        if self.codec == "lzma":
            return f"python lzma (xz) preset {self.level}"
        return "raw"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        raw = memoryview(np.ascontiguousarray(array)).cast("B")
        if self.codec == "zstd":
            body = self._zstd().ZstdCompressor(level=self.level, threads=0, write_checksum=False,
                                               write_content_size=True).compress(raw)
        elif self.codec == "lzma":
            body = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=self.level)
        else:
            body = bytes(raw)
        stream, meta = pack_container(CODEC_IDS[self.codec], array.dtype, array.shape, body)
        self.last_metadata_bytes = meta
        self.last_diagnostics = {}
        return stream

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        dtype, shape, _extra, body = unpack_container(payload, CODEC_IDS[self.codec])
        if self.codec == "zstd":
            raw = self._zstd().ZstdDecompressor().decompress(body)
        elif self.codec == "lzma":
            raw = lzma.decompress(body, format=lzma.FORMAT_XZ)
        else:
            raw = bytes(body)
        return np.frombuffer(raw, dtype=dtype).reshape(shape)
