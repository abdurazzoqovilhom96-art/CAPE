"""Blosc2 structured-integer baseline (spec 17.2): bitshuffle + Zstd clevel 5, typesize =
original dtype, chunk target 1 MiB (rounded to whole items), block 256 KiB, single thread."""

from __future__ import annotations

import struct

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter, pack_container, unpack_container

CODEC_ID = 4


class Blosc2Adapter(CodecAdapter):
    adapter_name = "blosc2"

    def _b(self):
        try:
            import blosc2
        except ImportError as exc:
            raise AdapterUnavailable(f"blosc2 missing: {exc}") from exc
        return blosc2

    def availability(self) -> dict:
        try:
            self._b()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        b = self._b()
        return f"python-blosc2 {b.__version__} (c-blosc2 {b.blosclib_version if hasattr(b, 'blosclib_version') else '?'})"

    def _params(self, itemsize: int):
        b = self._b()
        o = self.options
        chunk = max(itemsize, (int(o.get("chunk_bytes", 1 << 20)) // itemsize) * itemsize)
        block = max(itemsize, (int(o.get("block_bytes", 1 << 18)) // itemsize) * itemsize)
        filt = {"bitshuffle": b.Filter.BITSHUFFLE, "shuffle": b.Filter.SHUFFLE, "none": b.Filter.NOFILTER}[o.get("filter", "bitshuffle")]
        codec = {"zstd": b.Codec.ZSTD, "lz4": b.Codec.LZ4}[o.get("codec", "zstd")]
        cparams = {"codec": codec, "clevel": int(o.get("clevel", 5)), "typesize": itemsize, "nthreads": self.threads,
                   "filters": [filt], "filters_meta": [0], "blocksize": block, "splitmode": b.SplitMode.AUTO_SPLIT}
        return chunk, block, cparams

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        b = self._b()
        arr = np.ascontiguousarray(array)
        chunk, block, cparams = self._params(arr.dtype.itemsize)
        schunk = b.SChunk(chunksize=chunk, data=memoryview(arr).cast("B"), cparams=cparams,
                          dparams={"nthreads": self.threads})
        frame = schunk.to_cframe()
        extra = struct.pack("<QQ", chunk, block)
        stream, meta = pack_container(CODEC_ID, arr.dtype, arr.shape, bytes(frame), extra)
        self.last_metadata_bytes = meta
        self.last_diagnostics = {"chunk_bytes_actual": chunk, "block_bytes_actual": block,
                                 "filter": self.options.get("filter", "bitshuffle"), "clevel": cparams["clevel"]}
        return stream

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        b = self._b()
        dtype, shape, _extra, body = unpack_container(payload, CODEC_ID)
        schunk = b.schunk_from_cframe(bytes(body), copy=True)
        schunk.dparams = b.DParams(nthreads=self.threads)
        raw = schunk[:]
        return np.frombuffer(raw, dtype=dtype).reshape(shape)
