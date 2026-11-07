"""B protocol Stage 0.3 (I13): the runner's dtype gate asks the adapter instance, so an explicit lossless widening
option (neuroglancer_b8_u32) is reachable on uint8/uint16, while the frozen native-only method stays UNSUPPORTED."""
import numpy as np
import pytest

from cape.adapters import make_adapter
from cape.runner import accepted_dtypes

NG = {"adapter": "neuroglancer", "options": {"block": [8, 8, 8]}}
NG_U32 = {"adapter": "neuroglancer", "options": {"block": [8, 8, 8], "widen_to": "uint32"}}


def _adapter(spec, wrapper="none"):
    ad = make_adapter("ng_test", spec, None, wrapper)
    if ad.availability()["status"] != "AVAILABLE":
        pytest.skip("compressed-segmentation not available")
    return ad


def test_native_neuroglancer_rejects_narrow_dtypes():
    acc = accepted_dtypes(_adapter(NG))
    assert "uint16" not in acc and "uint8" not in acc
    assert {"uint32", "uint64"} <= set(acc)


def test_widening_neuroglancer_accepts_narrow_dtypes():
    acc = accepted_dtypes(_adapter(NG_U32))
    assert {"uint8", "uint16", "uint32", "uint64"} <= set(acc)
    assert not {"int8", "int16", "int32", "int64"} & set(acc)


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_widening_roundtrip_is_lossless_and_keeps_dtype(dtype):
    ad = _adapter(NG_U32)
    rng = np.random.default_rng(20261107)
    a = rng.integers(0, np.iinfo(dtype).max, size=(9, 17, 23), dtype=dtype)
    a[0, 0, 0] = np.iinfo(dtype).max
    out = ad.decode(ad.encode(a))
    assert out.dtype == a.dtype and out.shape == a.shape and np.array_equal(out, a)


def test_wrapper_delegates_instance_dtype_check():
    try:
        ad = make_adapter("ng_test", NG_U32, {"benchmark": {"threads": 1}}, "zstd9")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"wrapper not constructible here: {exc}")
    if ad.availability()["status"] != "AVAILABLE":
        pytest.skip("wrapper unavailable")
    assert "uint16" in accepted_dtypes(ad)
