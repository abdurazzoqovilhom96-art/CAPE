"""SAFE-ARCHIVE baseline (plan v2 P1.5): an engineering regression guard, NOT a new algorithm.

One CAPE-FAST encode builds BOTH complete Crackle v1 streams (flat and CAPE pins) over one shared
boundary pass (`format_policy: min_exact`, `keep_alternative: true`). Each stream is wrapped with
the same zstd frame settings as `cape/adapters/wrappers.py`, and the smaller wrapped stream is
stored. No selector header is added: the stored object is an ordinary zstd frame containing an
ordinary Crackle stream, decoded by unwrapping and calling the stock PyPI decoder.

Scope of the guarantee: never larger than the INCLUDED flat stream with the SAME zstd level and
Markov order. It says nothing about other codecs, levels or Crackle variants. Encode time contains
both streams and both compressions.
"""

from __future__ import annotations

import time

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter
from cape.adapters.cape_native import NATIVE_KEYS
from cape.adapters.wrappers import WRAPPER_LEVELS
from cape.canonical import crackle_view, from_xyz

OWN_KEYS = {"zstd"}


class SafeArchiveAdapter(CodecAdapter):
    adapter_name = "safe_archive"
    crackle_format = True

    def __init__(self, method_id, options=None, threads=1, base_options: dict | None = None):
        super().__init__(method_id, options, threads)
        opts = dict(self.options)
        wrapper = opts.pop("zstd", None)
        if wrapper not in WRAPPER_LEVELS:
            raise ValueError(f"{method_id}: option zstd must be one of {sorted(WRAPPER_LEVELS)}")
        self.level = WRAPPER_LEVELS[wrapper]
        merged = dict(base_options or {})
        merged.update(opts)
        merged.update({"format_policy": "min_exact", "keep_alternative": True, "parallel": self.threads})
        unknown = set(merged) - NATIVE_KEYS
        if unknown:
            raise ValueError(f"{method_id}: unknown CAPE option(s) {sorted(unknown)}")
        self.native_options = merged

    def _modules(self):
        try:
            import crackle
            import zstandard

            from cape import _cape_native
        except ImportError as exc:
            raise AdapterUnavailable(f"dependency unavailable: {exc}") from exc
        return _cape_native, crackle, zstandard

    def availability(self) -> dict:
        try:
            self._modules()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        from cape import __version__

        return f"cape {__version__} SAFE-ARCHIVE (flat vs CAPE-FAST, zstd level {self.level})"

    def _compress(self, zstandard, data: bytes) -> bytes:
        return zstandard.ZstdCompressor(level=self.level, threads=0, write_checksum=False,
                                        write_content_size=True).compress(data)

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        cn, _crackle, zstandard = self._modules()
        t0 = time.perf_counter_ns()
        buf, diag = cn.encode(crackle_view(array), dict(self.native_options, **(options or {})))
        t1 = time.perf_counter_ns()
        alt = diag.pop("alternative_stream", None)
        raw = {diag["label_format"]: buf}
        if alt is not None:
            raw["FLAT" if diag["label_format"] != "FLAT" else "PINS_VARIABLE_WIDTH"] = alt
        t2 = time.perf_counter_ns()
        wrapped = {k: self._compress(zstandard, v) for k, v in raw.items()}
        # timing only (v2.1): the native call (both streams) and the zstd compressions of both streams
        diag["safe_native_ns"] = t1 - t0
        diag["safe_zstd_ns"] = time.perf_counter_ns() - t2
        # deterministic choice: smaller wrapped size; on a tie the flat stream (the guarded baseline)
        choice = min(wrapped, key=lambda k: (len(wrapped[k]), k != "FLAT"))
        diag.update({
            "safe_choice": choice, "label_format": choice,
            "safe_flat_wrapped_bytes": len(wrapped["FLAT"]) if "FLAT" in wrapped else None,
            "safe_pins_wrapped_bytes": len(wrapped.get("PINS_VARIABLE_WIDTH", b"")) or None,
            "inner_total_bytes": len(raw[choice]),
        })
        if choice != "PINS_VARIABLE_WIDTH":
            # the stored stream is the flat one: pins bounds/certificate describe the discarded
            # stream, so they are kept only under a pins_ prefix (never as this row's certificate)
            diag["label_bytes"] = None
            for k in ("ub_bytes", "lb_bytes", "label_lb_bytes", "certificate_scope", "certificate_dual_feasible"):
                if k in diag:
                    diag["pins_" + k] = diag.pop(k)
        self.last_diagnostics = diag
        self.last_metadata_bytes = 0
        return wrapped[choice]

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        _cn, crackle, zstandard = self._modules()
        return from_xyz(crackle.decompress(zstandard.ZstdDecompressor().decompress(payload), parallel=self.threads))
