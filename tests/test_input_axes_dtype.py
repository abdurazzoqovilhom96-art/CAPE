"""Input formats, axis order and dtype handling (spec section 2): values are never truncated,
cast to float or relabeled; ambiguous axes/keys are errors."""

from __future__ import annotations

import gzip

import h5py
import numpy as np
import pytest
import tifffile

from cape.canonical import CanonicalError, crackle_view, from_xyz, to_canonical, voxel_sha256
from cape.io import InputError, load_canonical, read_raw, save_canonical


def test_axis_permutations_map_to_zyx():
    zyx = np.arange(2 * 3 * 4, dtype=np.uint32).reshape(2, 3, 4)
    for axes in ("ZYX", "XYZ", "ZXY", "YXZ", "XZY", "YZX"):
        src = np.transpose(zyx, ["ZYX".index(a) for a in axes])
        canon, info = to_canonical(src, axes)
        assert np.array_equal(canon, zyx) and canon.flags.c_contiguous
    with pytest.raises(CanonicalError):
        to_canonical(zyx, "ZYY")
    with pytest.raises(CanonicalError):
        to_canonical(zyx, None)


def test_dtype_rules():
    ok, info = to_canonical(np.array([[[0, 5]]], dtype=np.int32), "ZYX")
    assert ok.dtype == np.uint32 and "value preserving" in info["conversions"][0]
    with pytest.raises(CanonicalError):
        to_canonical(np.array([[[-1, 5]]], dtype=np.int32), "ZYX")
    with pytest.raises(CanonicalError):
        to_canonical(np.zeros((1, 1, 2), dtype=np.float32), "ZYX")
    with pytest.raises(CanonicalError):
        to_canonical(np.zeros((2, 2), dtype=np.uint8), "ZYX")
    be = np.array([[[1, 2**40]]], dtype=">u8")
    canon, info = to_canonical(be, "ZYX")
    assert canon.dtype == np.dtype("<u8") and int(canon[0, 0, 1]) == 2**40


def test_uint64_ids_round_trip_exactly(tmp_path):
    big = np.array([[[2**64 - 1, 2**63 + 1, 9007199254740993]]], dtype=np.uint64)  # > 2**53: float would break it
    save_canonical(tmp_path / "a.npy", big)
    back = load_canonical(tmp_path / "a.npy")
    assert back.dtype == np.uint64 and [int(v) for v in back.ravel()] == [2**64 - 1, 2**63 + 1, 9007199254740993]
    assert voxel_sha256(back) == voxel_sha256(big)
    changed = big.copy()
    changed[0, 0, 2] -= np.uint64(1)
    assert voxel_sha256(changed) != voxel_sha256(big)


def test_crackle_view_is_zero_copy():
    canon = np.arange(24, dtype=np.uint16).reshape(2, 3, 4)
    xyz = crackle_view(canon)
    assert xyz.shape == (4, 3, 2) and np.shares_memory(xyz, canon)
    assert from_xyz(xyz) is not None and np.array_equal(from_xyz(np.asfortranarray(xyz)), canon)


def test_readers_and_bbox(tmp_path):
    zyx = np.random.default_rng(1).integers(0, 9, size=(6, 7, 8)).astype(np.uint32)
    np.save(tmp_path / "v.npy", zyx)
    with h5py.File(tmp_path / "v.h5", "w") as fh:
        fh["volumes/labels/neuron_ids"] = zyx
    tifffile.imwrite(tmp_path / "v.tif", zyx)
    bbox = [[1, 5], [2, 6], [0, 3]]  # half-open x, y, z
    want = zyx[0:3, 2:6, 1:5]
    assert np.array_equal(read_raw(tmp_path / "v.npy", bbox_xyz=bbox, source_axes="ZYX"), want)
    assert np.array_equal(read_raw(tmp_path / "v.h5", "volumes/labels/neuron_ids", bbox, "ZYX"), want)
    assert np.array_equal(read_raw(tmp_path / "v.tif", bbox_xyz=bbox, source_axes="ZYX"), want)
    with pytest.raises(InputError):
        read_raw(tmp_path / "v.h5")  # no key: never guessed
    with pytest.raises(InputError):
        read_raw(tmp_path / "v.npy", bbox_xyz=bbox)  # bbox without axis order
    stack = []
    for z in range(zyx.shape[0]):
        p = tmp_path / f"s{z:02d}.tif"
        tifffile.imwrite(p, zyx[z])
        stack.append(str(p))
    assert np.array_equal(read_raw(tmp_path / "s00.tif", tiff_stack=stack), zyx)


def test_compresso_gzip_sample_format(tmp_path):
    import compresso

    xyz = np.asfortranarray(np.random.default_rng(2).integers(0, 5, size=(8, 9, 4)).astype(np.uint32))
    (tmp_path / "x.npy.cpso.gz").write_bytes(gzip.compress(compresso.compress(xyz)))
    assert np.array_equal(read_raw(tmp_path / "x.npy.cpso.gz"), xyz)
