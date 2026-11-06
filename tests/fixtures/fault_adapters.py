"""Fault-injection adapters for acceptance tests T3/T4 (spec section 38). Test-only: they are
reachable solely through tests/fixtures/methods_test.yaml, never through configs/methods.yaml."""

from __future__ import annotations

import numpy as np

from cape.adapters.base import CodecAdapter
from cape.adapters.generic import GenericAdapter


class RaisingAdapter(CodecAdapter):
    """T3: every encode raises; other methods must keep running."""

    adapter_name = "test_raising"

    def version(self) -> str:
        return "test-raising-adapter"

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        raise RuntimeError("injected adapter failure (acceptance test T3)")

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        raise RuntimeError("unreachable")


class CorruptingAdapter(GenericAdapter):
    """T4: produces a valid stream but decodes one wrong ID."""

    adapter_name = "test_corrupting"

    def __init__(self, method_id, options=None, threads=1):
        super().__init__(method_id, {"codec": "zstd", "level": 1}, threads)

    def version(self) -> str:
        return "test-corrupting-adapter"

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        arr = super().decode(payload).copy()
        arr.flat[0] = arr.flat[0] + 1
        return arr
