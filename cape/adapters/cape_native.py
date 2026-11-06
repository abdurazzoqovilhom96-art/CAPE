"""CAPE encoder adapter. Streams are Crackle v1 streams: they are decoded with the original
PyPI crackle-codec decoder (the same decoder as the stock rows), and cross-checked with the
vendor build outside the timed region."""

from __future__ import annotations

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter
from cape.canonical import crackle_view, from_xyz

NATIVE_KEYS = {
    "markov_model_order", "format_policy", "selector", "background_policy", "depth_policy", "candidate_policy",
    "reduction_impl", "impl_mask", "debug_hash_bits", "keep_alternative", "return_cc", "certificate",
    "reduce_equal", "reduce_subset", "reduce_singleton", "use_exact", "use_local", "use_dual_gate", "dual_scale",
    "exact_max_cc", "exact_max_transitions_per_component", "exact_max_transitions_total", "exact_memory_mib",
    "local_checks_per_component", "local_checks_total", "subset_checks_total", "memory_cap_bytes", "parallel",
    "collect_records", "export_components_max_cc", "export_components_limit",
    # v3 QUALITY switches (M3 / M4)
    "regime_gate", "rc_fixing", "rc_max_cc", "rc_transitions_total", "rc_transitions_per_component", "rc_max_states",
    "repair", "repair_max_r", "repair_max_pool", "repair_attempts", "repair_transitions_total",
    "repair_transitions_per_attempt", "repair_max_states",
}


class CapeNativeAdapter(CodecAdapter):
    adapter_name = "cape_native"
    crackle_format = True

    def __init__(self, method_id, options=None, threads=1, base_options: dict | None = None):
        super().__init__(method_id, options, threads)
        merged = dict(base_options or {})
        merged.update(self.options)
        merged["parallel"] = self.threads
        unknown = set(merged) - NATIVE_KEYS
        if unknown:
            raise ValueError(f"{method_id}: unknown CAPE option(s) {sorted(unknown)}")
        self.native_options = merged

    def _modules(self):
        try:
            import crackle

            from cape import _cape_native, _crackle_vendor
        except ImportError as exc:
            raise AdapterUnavailable(f"native modules unavailable: {exc}") from exc
        return _cape_native, _crackle_vendor, crackle

    def availability(self) -> dict:
        try:
            self._modules()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        from cape import __version__

        return f"cape {__version__} (upstream bridge 14b39b1)"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        cn, _cv, _c = self._modules()
        opts = dict(self.native_options, **(options or {}))
        buf, diag = cn.encode(crackle_view(array), opts)
        self.last_diagnostics = diag
        self.last_metadata_bytes = 0
        return buf

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        _cn, _cv, crackle = self._modules()
        return from_xyz(crackle.decompress(payload, parallel=self.threads))

    def secondary_check(self, payload: bytes, array: np.ndarray) -> dict:
        _cn, cv, _c = self._modules()
        ok = bool(np.array_equal(from_xyz(cv.decompress(payload, parallel=1)), array))
        return {"vendor_decoder_lossless": ok}
