"""Public API (cape.api): lossless round trip through the upstream decoder, byte identity with the evaluated method
cape_q1_fast_m0 built from the frozen final-run configs, and the optional lower bound."""

import numpy as np
import pytest

crackle = pytest.importorskip("crackle")
cape_api = pytest.importorskip("cape.api")
pytest.importorskip("cape._cape_native")

from cape.adapters import make_adapter  # noqa: E402
from cape.canonical import from_xyz  # noqa: E402
from cape.config import load_methods, load_run_config  # noqa: E402


def _blocky(shape_xyz, n_labels, seed, dtype):
    """Piecewise-constant labels (many pins), indexed [x, y, z]."""
    rng = np.random.default_rng(seed)
    coarse = rng.integers(0, n_labels, size=tuple(max(1, s // 4) for s in shape_xyz))
    a = np.kron(coarse, np.ones((4, 4, 4), dtype=np.int64))[tuple(slice(0, s) for s in shape_xyz)]
    a[rng.random(a.shape) < 0.01] = n_labels + 1  # a few isolated voxels (singletons)
    return a.astype(dtype)


CASES = [((40, 36, 24), 30, 1, np.uint16), ((64, 64, 16), 200, 2, np.uint32), ((33, 17, 9), 5, 3, np.uint8),
         ((48, 40, 32), 1000, 4, np.uint64)]


@pytest.mark.parametrize("shape,n,seed,dtype", CASES)
def test_round_trip_with_upstream_decoder(shape, n, seed, dtype):
    a = _blocky(shape, n, seed, dtype)
    for arr in (a, np.ascontiguousarray(a), np.asfortranarray(a)):
        out = crackle.decompress(cape_api.compress(arr))
        assert out.dtype == a.dtype and out.shape == a.shape
        assert np.array_equal(out, a)


def test_2d_input_and_dtype_errors():
    a = _blocky((32, 24, 1), 10, 5, np.uint16)[:, :, 0]
    assert np.array_equal(crackle.decompress(cape_api.compress(a))[:, :, 0], a)
    with pytest.raises(TypeError):
        cape_api.compress(a.astype(np.int32))
    with pytest.raises(ValueError):
        cape_api.compress(np.zeros((2, 2, 2, 2), np.uint8))


@pytest.mark.parametrize("shape,n,seed,dtype", CASES)
def test_byte_identical_to_evaluated_method(shape, n, seed, dtype):
    methods = load_methods()
    cfg = load_run_config("configs/q1_final_j0126.yaml", methods)
    adapter = make_adapter("cape_q1_fast_m0", methods["cape_q1_fast_m0"], cfg)
    a = _blocky(shape, n, seed, dtype)
    canon = np.ascontiguousarray(a.T)  # pipeline layout (Z, Y, X) C-order == crackle (X, Y, Z) F-order
    assert np.array_equal(from_xyz(np.asfortranarray(a)), canon)
    assert adapter.encode(canon) == cape_api.compress(a)


def test_bounds_same_stream_and_valid():
    a = _blocky((64, 48, 32), 300, 6, np.uint32)
    plain = cape_api.compress(a)
    stream, info = cape_api.compress_with_info(a, bounds=True)
    assert stream == plain
    assert info["certificate_dual_feasible"] == 1
    assert 0 <= info["label_lb_bytes"] <= info["label_bytes"]
    assert info["label_gap_bytes"] == info["label_bytes"] - info["label_lb_bytes"]
    assert info["total_bytes"] == len(stream)
