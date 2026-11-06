"""Compresso (spec 17.2, S2) via the maintained PyPI `compresso` package (seung-lab), window
steps (8, 8, 1) over (x, y, z); optional outer LZMA preset 6 (`compresso_lzma6`). The original
VCG/compresso implementation is cited; the PyPI reimplementation is what is measured."""

from __future__ import annotations

import lzma

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter
from cape.canonical import crackle_view, from_xyz


class CompressoAdapter(CodecAdapter):
    adapter_name = "compresso"

    def _c(self):
        try:
            import compresso
        except ImportError as exc:
            raise AdapterUnavailable(f"compresso missing: {exc}") from exc
        return compresso

    def availability(self) -> dict:
        try:
            self._c()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE", "version": None, "reason": str(exc)}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        import importlib.metadata as md

        return f"compresso {md.version('compresso')} (PyPI, seung-lab)"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        steps = tuple(int(v) for v in self.options.get("steps", (8, 8, 1)))
        buf = self._c().compress(crackle_view(array), steps=steps)
        if self.options.get("outer") == "lzma6":
            buf = lzma.compress(buf, format=lzma.FORMAT_XZ, preset=6)
        self.last_metadata_bytes = 0
        self.last_diagnostics = {"steps": list(steps), "outer": self.options.get("outer")}
        return buf

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        if self.options.get("outer") == "lzma6":
            payload = lzma.decompress(payload, format=lzma.FORMAT_XZ)
        return from_xyz(self._c().decompress(payload))
