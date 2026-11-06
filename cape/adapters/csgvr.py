"""CSGV-R (spec 17.2, S4): Volcanite's `--random-access` encoding ("random access and in-brick
parallelism for the decompression"). Whether this mode is exactly the paper's stop-bit
configuration is recorded as an open audit item; rows carry the mode string."""

from __future__ import annotations

from cape.adapters.csgv import VolcaniteAdapter


class VolcaniteRandomAccessAdapter(VolcaniteAdapter):
    adapter_name = "csgvr"
    random_access = True
