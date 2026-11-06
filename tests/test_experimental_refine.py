"""v2.1: SAFE+refine is an EXPERIMENTAL method; the SAFE / refine wrappers report their own timers."""

from __future__ import annotations

import numpy as np
import pytest

from cape.config import load_methods


def test_every_refine_method_is_experimental_and_never_new():
    methods = load_methods()
    refine = {k: v for k, v in methods.items() if v["adapter"] == "safe_refine"}
    assert refine, "no safe_refine methods registered"
    for mid, spec in refine.items():
        assert spec["experimental"] is True, mid
        assert spec["role"] != "new", mid
        assert spec["description"].startswith("[EXPERIMENTAL"), mid
    # nothing else became experimental by accident
    assert all(not v["experimental"] for k, v in methods.items() if v["adapter"] != "safe_refine")


def _array():
    rng = np.random.default_rng(7)
    a = np.zeros((8, 24, 24), dtype=np.uint32)
    for i in range(1, 9):
        z, y, x = rng.integers(0, 6), rng.integers(0, 18), rng.integers(0, 18)
        a[z:z + 3, y:y + 6, x:x + 6] = i
    return a


def test_safe_and_refine_timers_present_and_decode_exact():
    pytest.importorskip("cape._cape_native")
    pytest.importorskip("zstandard")
    from cape.adapters import make_adapter

    methods = load_methods()
    arr = _array()
    for mid, keys in (("safe_archive_m0_zstd9", ("safe_native_ns", "safe_zstd_ns")),
                      ("safe_refine_e24_m0_zstd9", ("refine_native_ns", "refine_flat_zstd_ns", "refine_ns",
                                                    "refine_setup_ns", "refine_J0_zstd_ns",
                                                    "refine_eval_serialize_ns", "refine_eval_zstd_ns"))):
        ad = make_adapter(mid, methods[mid], {}, "none")
        payload = ad.encode(arr)
        assert np.array_equal(ad.decode(payload), arr), mid
        diag = ad.last_diagnostics
        for k in keys:
            assert isinstance(diag.get(k), int) and diag[k] >= 0, (mid, k, diag.get(k))
    assert "[EXPERIMENTAL]" in make_adapter("safe_refine_e24_m0_zstd9", methods["safe_refine_e24_m0_zstd9"],
                                            {}, "none").version()
