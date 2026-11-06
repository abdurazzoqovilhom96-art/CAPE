"""Neuroglancer compressed_segmentation (spec 17.2, S9), block (8,8,8) in (x,y,z), x fastest.
The raw format has no shape/dtype, so a CAPE container header carries them (metadata).
Only uint32/uint64 are native: other dtypes are UNSUPPORTED_DTYPE (no silent widening)."""

from __future__ import annotations

import struct

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter, pack_container, unpack_container
from cape.canonical import crackle_view, from_xyz

CODEC_ID = 5


class NeuroglancerAdapter(CodecAdapter):
    adapter_name = "neuroglancer"
    supported_dtypes = ("uint32", "uint64")

    def _cs(self):
        try:
            import compressed_segmentation as cs
        except ImportError as exc:
            raise AdapterUnavailable(f"compressed-segmentation missing: {exc}") from exc
        return cs

    def availability(self) -> dict:
        try:
            self._cs()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        import importlib.metadata as md

        return f"compressed-segmentation {md.version('compressed-segmentation')}"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        self.check_dtype(array.dtype)
        block = tuple(int(v) for v in self.options.get("block", (8, 8, 8)))
        body = self._cs().compress(crackle_view(array), block_size=block, order="F")
        stream, meta = pack_container(CODEC_ID, array.dtype, array.shape, bytes(body), struct.pack("<III", *block))
        self.last_metadata_bytes = meta
        self.last_diagnostics = {"block_xyz": list(block)}
        return stream

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        dtype, (z, y, x), extra, body = unpack_container(payload, CODEC_ID)
        block = struct.unpack("<III", extra)
        xyz = self._cs().decompress(bytes(body), (x, y, z), dtype, block_size=block, order="F")
        return from_xyz(xyz)
