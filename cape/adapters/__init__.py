"""Adapter registry: method id + registry spec -> CodecAdapter (optionally zstd-wrapped)."""

from __future__ import annotations

from cape.adapters.base import AdapterUnavailable, CodecAdapter, UnsupportedDtype, UnsupportedOperation


def make_adapter(method_id: str, spec: dict, run_cfg: dict | None = None, wrapper: str = "none") -> CodecAdapter:
    threads = int(run_cfg["benchmark"]["threads"]) if run_cfg else 1
    name = spec["adapter"]
    opts = spec.get("options", {})
    if name == "cape_native":
        from cape.adapters.cape_native import CapeNativeAdapter
        from cape.config import cape_native_options

        adapter: CodecAdapter = CapeNativeAdapter(method_id, opts, threads,
                                                  base_options=cape_native_options(run_cfg) if run_cfg else None)
    elif name == "safe_archive":
        from cape.adapters.safe_archive import SafeArchiveAdapter
        from cape.config import cape_native_options

        adapter = SafeArchiveAdapter(method_id, opts, threads,
                                     base_options=cape_native_options(run_cfg) if run_cfg else None)
    elif name == "safe_refine":
        from cape.adapters.safe_refine import SafeRefineAdapter
        from cape.config import cape_native_options

        adapter = SafeRefineAdapter(method_id, opts, threads,
                                    base_options=cape_native_options(run_cfg) if run_cfg else None)
    elif name == "crackle_stock":
        from cape.adapters.crackle_stock import CrackleStockAdapter

        adapter = CrackleStockAdapter(method_id, opts, threads)
    elif name == "crackle_vendor":
        from cape.adapters.crackle_stock import CrackleVendorAdapter

        adapter = CrackleVendorAdapter(method_id, opts, threads)
    elif name == "generic":
        from cape.adapters.generic import GenericAdapter

        adapter = GenericAdapter(method_id, opts, threads)
    elif name == "blosc2":
        from cape.adapters.blosc2 import Blosc2Adapter

        adapter = Blosc2Adapter(method_id, opts, threads)
    elif name == "compresso":
        from cape.adapters.compresso import CompressoAdapter

        adapter = CompressoAdapter(method_id, opts, threads)
    elif name == "neuroglancer":
        from cape.adapters.neuroglancer import NeuroglancerAdapter

        adapter = NeuroglancerAdapter(method_id, opts, threads)
    elif name == "csgv":
        from cape.adapters.csgv import VolcaniteAdapter

        adapter = VolcaniteAdapter(method_id, opts, threads)
    elif name == "csgvr":
        from cape.adapters.csgvr import VolcaniteRandomAccessAdapter

        adapter = VolcaniteRandomAccessAdapter(method_id, opts, threads)
    elif name.startswith("python:"):
        # plugin adapter "python:<module>:<Class>" (used by fault-injection acceptance tests)
        import importlib

        _, mod, cls = name.split(":", 2)
        adapter = getattr(importlib.import_module(mod), cls)(method_id, opts, threads)
    else:
        raise ValueError(f"{method_id}: unknown adapter {name}")
    if wrapper != "none":
        from cape.adapters.wrappers import ZstdWrapper

        adapter = ZstdWrapper(adapter, wrapper)
    return adapter


__all__ = ["make_adapter", "AdapterUnavailable", "CodecAdapter", "UnsupportedDtype", "UnsupportedOperation"]
