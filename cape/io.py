"""Label volume readers (spec section 2): .npy, .h5/.hdf5/.hdf, 3D TIFF, ordered 2D TIFF stacks
and the Crackle repository sample format (.npy.cpso.gz = gzip(compresso)).

Readers never guess an ambiguous axis order or HDF5 key; they return the raw array plus the
axes the caller must state, and canonical.to_canonical() does the conversion.
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import numpy as np

from cape.canonical import CanonicalError, to_canonical


class InputError(ValueError):
    pass


def file_sha256(path: str | Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def read_raw(path: str | Path, array_key: str | None = None, bbox_xyz=None, source_axes: str | None = None,
             tiff_stack: list[str] | None = None) -> np.ndarray:
    """Read the source array (optionally a half-open bbox given in X,Y,Z source voxels)."""
    p = Path(path)
    name = p.name.lower()
    if name.endswith(".npy.cpso.gz") or name.endswith(".cpso.gz"):
        import compresso

        arr = compresso.decompress(gzip.decompress(p.read_bytes()))
    elif name.endswith(".npy"):
        arr = np.load(p, mmap_mode="r", allow_pickle=False)
    elif name.endswith((".h5", ".hdf5", ".hdf")):
        import h5py

        if not array_key:
            raise InputError(f"{p.name}: HDF5 input needs an explicit array_key")
        with h5py.File(p, "r") as fh:
            if array_key not in fh:
                raise InputError(f"{p.name}: key {array_key!r} not found")
            ds = fh[array_key]
            if bbox_xyz is not None:
                return np.asarray(ds[_slices(bbox_xyz, source_axes, ds.ndim)])
            return np.asarray(ds[...])
    elif name.endswith((".tif", ".tiff")):
        import tifffile

        if tiff_stack:
            arr = np.stack([tifffile.imread(f) for f in tiff_stack], axis=0)
        else:
            arr = tifffile.imread(p)
    else:
        raise InputError(f"unsupported input format: {p.name}")
    if bbox_xyz is not None:
        arr = arr[_slices(bbox_xyz, source_axes, arr.ndim)]
    return np.asarray(arr)


def _slices(bbox_xyz, source_axes: str | None, ndim: int):
    if ndim != 3:
        raise InputError("bbox cropping requires a 3D source")
    if source_axes is None:
        raise InputError("bbox cropping requires the source axis order")
    rng = {"X": bbox_xyz[0], "Y": bbox_xyz[1], "Z": bbox_xyz[2]}
    out = []
    for ax in source_axes.upper():
        lo, hi = int(rng[ax][0]), int(rng[ax][1])
        if not 0 <= lo < hi:
            raise InputError(f"invalid bbox range for {ax}: {lo}..{hi}")
        out.append(slice(lo, hi))
    return tuple(out)


def load_canonical(path: str | Path, axes: str = "ZYX") -> np.ndarray:
    """Load a materialized canonical crop (.npy written by freeze/make_manifest)."""
    arr = np.load(Path(path), allow_pickle=False)
    canon, info = to_canonical(arr, axes)
    if info["conversions"]:
        raise InputError(f"{path}: materialized crop is not canonical ({info['conversions']})")
    return canon


def save_canonical(path: str | Path, canon: np.ndarray) -> None:
    """Atomic write of a canonical crop."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "wb") as fh:
        np.save(fh, canon, allow_pickle=False)
        fh.flush()
        import os

        os.fsync(fh.fileno())
    tmp.replace(p)


__all__ = ["InputError", "CanonicalError", "file_sha256", "read_raw", "load_canonical", "save_canonical"]
