"""Adapter contract (spec section 25): lossless round trips on canonical arrays, explicit
UNSUPPORTED_DTYPE / UNAVAILABLE states, ROI UnsupportedOperation, consistent accounting."""

from __future__ import annotations

import numpy as np
import pytest

from cape.adapters import UnsupportedDtype, UnsupportedOperation, make_adapter
from cape.config import load_methods, load_run_config
from cape.provenance import ROOT
from cape import synthetic as syn

METHODS = load_methods(ROOT / "configs" / "methods.yaml")  # production registry, even under test hooks
RUN = load_run_config("configs/smoke.yaml", METHODS)
VOLS = {
    "u16": syn.blocky((12, 24, 20), n_labels=9, dtype=np.uint16, seed=1),
    "u32": syn.dense_drifting_voronoi((10, 24, 28), n_seeds=15, dtype=np.uint32, seed=2),
    "u64": syn.large_ids((6, 16, 12), seed=3),
}
# the frozen v2.1 adapter is exercised in a separate process (tests/test_v3_invariants.py): loading two pybind11
# modules with the same C++ exception names into this process would swap their Python exception classes
TESTED = [m for m in METHODS if METHODS[m]["adapter"] not in ("csgv", "csgvr", "cape_frozen_v21", "cape_frozen_v3")]


@pytest.mark.parametrize("vol", sorted(VOLS))
@pytest.mark.parametrize("method_id", TESTED)
def test_adapter_roundtrip(method_id, vol):
    spec = METHODS[method_id]
    arr = VOLS[vol]
    wrappers = ["none"] + (["zstd3", "zstd9"] if spec["wrappable"] else [])
    for wrapper in wrappers:
        ad = make_adapter(method_id, spec, RUN, wrapper)
        assert ad.availability()["status"] == "AVAILABLE"
        try:
            ad.check_dtype(arr.dtype)
        except UnsupportedDtype:
            assert spec["adapter"] == "neuroglancer" and arr.dtype == np.uint16
            continue
        stream = ad.encode(arr)
        assert isinstance(stream, bytes) and len(stream) > 0
        assert 0 <= ad.last_metadata_bytes < len(stream)
        out = ad.decode(stream)
        assert out.shape == arr.shape and out.dtype == arr.dtype and np.array_equal(out, arr)
        assert out.flags.c_contiguous
        for k, v in ad.secondary_check(stream, arr).items():
            assert v is True, k


def test_roi_is_explicitly_unsupported():
    ad = make_adapter("cape_m0", METHODS["cape_m0"], RUN)
    stream = ad.encode(VOLS["u32"])
    with pytest.raises(UnsupportedOperation):
        ad.decode_roi(stream, [[0, 4], [0, 4], [0, 4]])


def test_volcanite_reports_build_status_honestly():
    for mid in ("csgv_rans_b64", "csgvr_sb_b64"):
        av = make_adapter(mid, METHODS[mid], RUN).availability()
        assert av["status"] in ("AVAILABLE", "UNAVAILABLE_BUILD")
        if av["status"] != "AVAILABLE":
            assert av["reason"]


def test_cape_adapter_rejects_unknown_option():
    with pytest.raises(ValueError):
        make_adapter("x", {"adapter": "cape_native", "options": {"bogus": 1}}, RUN)
