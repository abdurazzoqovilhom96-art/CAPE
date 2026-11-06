"""Inputs and option sets shared by tests/test_v3_invariants.py and its frozen-v2.1 helper process.

This module must NOT import cape._cape_native: the helper process (tests/v3_frozen_digests.py) loads only
the frozen v2.1 binary, because two pybind11 modules with the same C++ exception names share pybind11's
exception translators inside one process (the later module's Python exception classes would be raised for
the earlier module's errors).
"""

from __future__ import annotations

import numpy as np

BASE = {"markov_model_order": 0, "format_policy": "force_pins", "selector": "cape", "certificate": "off"}
FAST_STOCK = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
              "depth_policy": "fixed_depth_width", "certificate": "off"}
DIAG_KEYS = ("candidate_count_before", "candidates_after_singleton", "candidates_after_equal", "candidate_count_after",
             "incidence_count", "component_count", "max_component_cc", "cc_count", "label_count", "run_count")


def edge_cases() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20261106)
    out = {
        "zeros_u8": np.zeros((5, 7, 9), np.uint8),
        "single_label_u64": np.full((6, 5, 4), np.iinfo(np.uint64).max, np.uint64),
        "max_u64_mix": np.where(rng.random((8, 9, 10)) < 0.5, np.uint64(0), np.uint64(np.iinfo(np.uint64).max)),
        "z1_u32": rng.integers(0, 4, (1, 16, 16)).astype(np.uint32),
        "many_labels_u32": rng.integers(0, 10_000, (6, 20, 20)).astype(np.uint32),
        "tall_u16": np.repeat(rng.integers(0, 5, (1, 6, 6)), 300, axis=0).astype(np.uint16),
    }
    for dt in (np.uint8, np.uint16, np.uint32, np.uint64):
        blocks = rng.integers(0, 6, (4, 4, 4)).astype(dt)
        out[f"blocks_{np.dtype(dt).name}"] = np.kron(blocks, np.ones((3, 5, 4), dt)).astype(dt)
    return out


def frozen_requests(cases: dict, edge: dict) -> list[tuple[str, str, dict]]:
    """(case set, case name, options) triples whose frozen-v2.1 digests the tests compare against."""
    req = []
    for name in sorted(cases):
        for depth in ("fixed_depth_width", "full_width_first"):
            req.append(("cases", name, dict(BASE, depth_policy=depth)))
        req.append(("cases", name, dict(FAST_STOCK)))
    for name in sorted(edge):
        req.append(("edge", name, dict(BASE, format_policy="same_as_stock", depth_policy="fixed_depth_width")))
    return req


def request_key(case_set: str, name: str, opts: dict) -> str:
    return case_set + "|" + name + "|" + "|".join(f"{k}={opts[k]}" for k in sorted(opts))
