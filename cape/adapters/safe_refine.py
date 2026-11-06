"""[EXPERIMENTAL since v2.1] SAFE-ARCHIVE + bounded archive-objective refinement (plan v2, user task 2e/3).

v2.1 decision: +0.013 % (42 B on 24 test crops) for ~2.7x encode time - kept only as an experimental
method; it is never a default, a winner or the "new" method in reports.

Same object as SAFE-ARCHIVE (an ordinary zstd frame around an ordinary Crackle v1 stream, decoded
by the stock decoder), but the CAPE-FAST pins stream is first refined against the TRUE wrapped
file size (`cape.refine`). The stored stream is min(zstd(flat), zstd(refined pins)); because
refinement only accepts strict improvements, it is never larger than SAFE-ARCHIVE with the same
level and Markov order. Encode time includes the CAPE encode, the flat stream, the CC volume
export, every refinement evaluation and both final compressions.

The research question is the difference between this method and `safe_archive_*` (q = 0):
choosing the smaller of two files is NOT the contribution being tested.
"""

from __future__ import annotations

import time

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter
from cape.adapters.cape_native import NATIVE_KEYS
from cape.adapters.wrappers import WRAPPER_LEVELS
from cape.canonical import crackle_view, from_xyz

REFINE_KEYS = {"max_evals", "moves", "unpin_classes", "anchor_scan_cap", "anchor_max_props", "anchor_pin_limit"}


class SafeRefineAdapter(CodecAdapter):
    adapter_name = "safe_refine"
    crackle_format = True

    def __init__(self, method_id, options=None, threads=1, base_options: dict | None = None):
        super().__init__(method_id, options, threads)
        from cape.refine import RefineConfig

        opts = dict(self.options)
        wrapper = opts.pop("zstd", None)
        if wrapper not in WRAPPER_LEVELS:
            raise ValueError(f"{method_id}: option zstd must be one of {sorted(WRAPPER_LEVELS)}")
        self.level = WRAPPER_LEVELS[wrapper]
        rk = {k: opts.pop(k) for k in list(opts) if k in REFINE_KEYS}
        if "moves" in rk:
            rk["moves"] = tuple(rk["moves"])
        self.cfg = RefineConfig(**rk)
        merged = dict(base_options or {})
        merged.update(opts)
        merged.update({"format_policy": "min_exact", "keep_alternative": True, "collect_records": True,
                       "return_cc": True, "certificate": "off", "parallel": self.threads})
        unknown = set(merged) - NATIVE_KEYS
        if unknown:
            raise ValueError(f"{method_id}: unknown option(s) {sorted(unknown)}")
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

        c = self.cfg
        return (f"cape {__version__} SAFE-ARCHIVE+refine [EXPERIMENTAL] (zstd level {self.level}; "
                f"moves {'+'.join(c.moves)}; max_evals {c.max_evals})")

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        from cape.refine import refine

        cn, _crackle, zstandard = self._modules()
        zc = zstandard.ZstdCompressor(level=self.level, threads=0, write_checksum=False, write_content_size=True)
        t0 = time.perf_counter_ns()
        buf, diag = cn.encode(crackle_view(array), dict(self.native_options, **(options or {})))
        diag["refine_native_ns"] = time.perf_counter_ns() - t0  # timing only (v2.1)
        alt = diag.pop("alternative_stream", None)
        cc = diag.pop("cc_volume", None)
        records = diag.pop("records", None)
        bgcolor = diag.pop("bgcolor", None)
        comps = diag.pop("components_per_grid", None)
        raw = {diag["label_format"]: buf}
        if alt is not None:
            raw["FLAT" if diag["label_format"] != "FLAT" else "PINS_VARIABLE_WIDTH"] = alt
        wrapped = {}
        if "FLAT" in raw:
            t1 = time.perf_counter_ns()
            wrapped["FLAT"] = zc.compress(raw["FLAT"])
            diag["refine_flat_zstd_ns"] = time.perf_counter_ns() - t1
        if "PINS_VARIABLE_WIDTH" in raw:
            res = refine(raw["PINS_VARIABLE_WIDTH"], records, int(bgcolor), list(comps),
                         {k: diag[k] for k in ("w_L", "w_I", "w_G", "w_C")}, cc, zc.compress, self.cfg)
            raw["PINS_VARIABLE_WIDTH"] = res.stream
            wrapped["PINS_VARIABLE_WIDTH"] = res.wrapped
            diag.update(res.stats)
        choice = min(wrapped, key=lambda k: (len(wrapped[k]), k != "FLAT"))
        diag.update({
            "safe_choice": choice, "label_format": choice,
            "safe_flat_wrapped_bytes": len(wrapped["FLAT"]) if "FLAT" in wrapped else None,
            "safe_pins_wrapped_bytes": diag.get("refine_J0"),
            "refined_pins_wrapped_bytes": len(wrapped["PINS_VARIABLE_WIDTH"]) if "PINS_VARIABLE_WIDTH" in wrapped else None,
            "inner_total_bytes": len(raw[choice]),
            "label_bytes": None,  # the refined labels section is not the CAPE section; not reported as such
        })
        self.last_diagnostics = diag
        self.last_metadata_bytes = 0
        return wrapped[choice]

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        _cn, crackle, zstandard = self._modules()
        return from_xyz(crackle.decompress(zstandard.ZstdDecompressor().decompress(payload), parallel=self.threads))
