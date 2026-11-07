"""Neuroglancer compressed_segmentation (spec 17.2, S9), block (8,8,8) in (x,y,z), x fastest.
The raw format has no shape/dtype, so a CAPE container header carries them (metadata).
Only uint32/uint64 are native: other dtypes are UNSUPPORTED_DTYPE (no silent widening).

Q1 amended variant (option widen_to: uint32, method neuroglancer_b8_u32): uint8/uint16 input is widened to uint32
inside encode (counted in the encode time), compressed natively, and narrowed back inside decode (counted in the
decode time). The container stores the ORIGINAL dtype and a one-byte widening flag (counted as metadata bytes). The
widening is lossless and explicit; it is a separate method and never replaces the frozen neuroglancer_b8 rows."""

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

    def _widen(self) -> str | None:
        w = self.options.get("widen_to")
        if w not in (None, "uint32"):
            raise ValueError(f"{self.method_id}: widen_to must be uint32 (got {w})")
        return w

    def check_dtype(self, dtype) -> None:
        if self._widen() and str(np.dtype(dtype)) in ("uint8", "uint16"):
            return
        super().check_dtype(dtype)

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        self.check_dtype(array.dtype)
        block = tuple(int(v) for v in self.options.get("block", (8, 8, 8)))
        widened = bool(self._widen()) and array.dtype.itemsize < 4
        data = array.astype(np.uint32) if widened else array
        body = self._cs().compress(crackle_view(data), block_size=block, order="F")
        extra = struct.pack("<IIIB", *block, 1) if widened else struct.pack("<III", *block)
        stream, meta = pack_container(CODEC_ID, array.dtype, array.shape, bytes(body), extra)
        self.last_metadata_bytes = meta
        self.last_diagnostics = {"block_xyz": list(block), "widened_to_uint32": widened}
        return stream

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        dtype, (z, y, x), extra, body = unpack_container(payload, CODEC_ID)
        widened = len(extra) == 13 and extra[12] == 1
        block = struct.unpack("<III", extra[:12])
        xyz = self._cs().decompress(bytes(body), (x, y, z), np.uint32 if widened else dtype, block_size=block,
                                    order="F")
        out = from_xyz(xyz)
        return out.astype(dtype) if widened else out
