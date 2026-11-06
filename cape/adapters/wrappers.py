"""External Zstandard wrappers (spec 17.2): identical frame settings for every wrapped method
(level 3 or 9, no checksum, content size written, single thread). The wrapped stream is the
inner standalone stream inside one zstd frame."""

from __future__ import annotations

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter

WRAPPER_LEVELS = {"zstd3": 3, "zstd9": 9}


class ZstdWrapper(CodecAdapter):
    adapter_name = "zstd_wrapper"

    def __init__(self, inner: CodecAdapter, wrapper: str):
        super().__init__(f"{inner.method_id}+{wrapper}", inner.options, inner.threads)
        if wrapper not in WRAPPER_LEVELS:
            raise ValueError(f"unknown wrapper {wrapper}")
        self.inner = inner
        self.wrapper = wrapper
        self.level = WRAPPER_LEVELS[wrapper]
        self.crackle_format = inner.crackle_format
        self.supported_dtypes = inner.supported_dtypes

    def _z(self):
        try:
            import zstandard
        except ImportError as exc:
            raise AdapterUnavailable(f"zstandard missing: {exc}") from exc
        return zstandard

    def availability(self) -> dict:
        inner = self.inner.availability()
        if inner["status"] != "AVAILABLE":
            return inner
        try:
            self._z()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        return f"{self.inner.version()} + zstd level {self.level}"

    def check_dtype(self, dtype) -> None:
        self.inner.check_dtype(dtype)

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        inner = self.inner.encode(array, options)
        out = self._z().ZstdCompressor(level=self.level, threads=0, write_checksum=False,
                                       write_content_size=True).compress(inner)
        self.last_diagnostics = dict(self.inner.last_diagnostics, inner_total_bytes=len(inner),
                                     inner_metadata_bytes=self.inner.last_metadata_bytes)
        self.last_metadata_bytes = 0
        return out

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        return self.inner.decode(self._z().ZstdDecompressor().decompress(payload), options)
