"""Stock Crackle adapters: the PyPI crackle-codec 0.53.0 wheel (`crackle_stock`, primary
baseline) and the pinned-SHA vendor build compiled like CAPE (`crackle_vendor`, timing
reference). `parallel` is always passed explicitly: upstream's default 0 means all cores."""

from __future__ import annotations

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter
from cape.canonical import crackle_view, from_xyz


def _header_diag(payload: bytes) -> dict:
    from cape import crackle_format as cf

    h = cf.parse_header(payload)
    return {"label_format": {0: "FLAT", 1: "PINS_FIXED_WIDTH", 2: "PINS_VARIABLE_WIDTH"}[h.label_format],
            "label_bytes": h.num_label_bytes, "markov_model_order": h.markov_model_order}


class CrackleStockAdapter(CodecAdapter):
    adapter_name = "crackle_stock"
    crackle_format = True

    def _crackle(self):
        try:
            import crackle
        except ImportError as exc:
            raise AdapterUnavailable(f"crackle-codec not installed: {exc}") from exc
        return crackle

    def availability(self) -> dict:
        try:
            self._crackle()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        import importlib.metadata as md

        return f"crackle-codec {md.version('crackle-codec')} (PyPI wheel)"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        crackle = self._crackle()
        o = dict(self.options, **(options or {}))
        buf = crackle.compress(crackle_view(array), allow_pins=int(o.get("allow_pins", 0)),
                               markov_model_order=int(o.get("markov_model_order", 0)), parallel=self.threads)
        self.last_diagnostics = _header_diag(buf)
        self.last_metadata_bytes = 0
        return buf

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        return from_xyz(self._crackle().decompress(payload, parallel=self.threads))

    def secondary_check(self, payload: bytes, array: np.ndarray) -> dict:
        from cape import _crackle_vendor as cv

        return {"vendor_decoder_lossless": bool(np.array_equal(from_xyz(cv.decompress(payload, parallel=1)), array))}


class CrackleVendorAdapter(CodecAdapter):
    adapter_name = "crackle_vendor"
    crackle_format = True

    def _cv(self):
        try:
            from cape import _crackle_vendor as cv
        except ImportError as exc:
            raise AdapterUnavailable(f"_crackle_vendor not built: {exc}") from exc
        return cv

    def availability(self) -> dict:
        try:
            self._cv()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        return f"crackle vendor build {self._cv().VENDOR_SHA[:12]} (g++ -O3, same flags as CAPE)"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        cv = self._cv()
        o = dict(self.options, **(options or {}))
        buf = cv.compress(crackle_view(array), allow_pins=bool(o.get("allow_pins", False)),
                          markov_model_order=int(o.get("markov_model_order", 0)),
                          optimize_pins=bool(o.get("optimize_pins", False)), parallel=self.threads)
        self.last_diagnostics = _header_diag(buf)
        self.last_metadata_bytes = 0
        return buf

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        return from_xyz(self._cv().decompress(payload, parallel=self.threads))

    def secondary_check(self, payload: bytes, array: np.ndarray) -> dict:
        import crackle

        return {"pypi_decoder_lossless": bool(np.array_equal(from_xyz(crackle.decompress(payload, parallel=1)), array))}
