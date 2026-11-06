"""Canonical label arrays (spec section 2): (Z, Y, X), C-contiguous, little-endian, unsigned.

Value-changing conversions are refused: floats, negative signed values and anything that would
truncate or relabel IDs raise CanonicalError. A non-negative signed array is widened to the
unsigned type of the same width (value preserving) and that conversion is reported.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np

UNSIGNED = {np.dtype("uint8"), np.dtype("uint16"), np.dtype("uint32"), np.dtype("uint64")}


class CanonicalError(ValueError):
    pass


def _permutation(axes: str) -> tuple[int, int, int]:
    axes = axes.upper()
    if sorted(axes) != ["X", "Y", "Z"]:
        raise CanonicalError(f"axes must be a permutation of XYZ, got {axes!r}")
    return tuple(axes.index(a) for a in "ZYX")  # type: ignore[return-value]


def to_canonical(arr: np.ndarray, axes: str | None) -> tuple[np.ndarray, dict]:
    """Return (canonical ZYX array, conversion info). axes describes `arr`'s axis order."""
    if axes is None:
        raise CanonicalError("axis order is unknown: the manifest must state it (e.g. ZYX or XYZ)")
    if arr.ndim != 3:
        raise CanonicalError(f"expected a 3D array, got ndim={arr.ndim}")
    t0 = time.perf_counter_ns()
    info = {"source_dtype": str(arr.dtype), "source_axes": axes.upper(), "conversions": []}
    dt = arr.dtype
    if dt.kind == "f" or dt.kind == "c" or dt.kind == "b":
        raise CanonicalError(f"label volumes must be integer, got {dt}")
    if dt.kind == "i":
        if arr.size and int(arr.min()) < 0:
            raise CanonicalError("negative label values cannot be represented without relabeling")
        arr = arr.astype(np.dtype(f"u{dt.itemsize}"), copy=False)
        info["conversions"].append(f"signed {dt} -> unsigned u{dt.itemsize} (value preserving)")
        dt = arr.dtype
    if dt.byteorder == ">" or (dt.byteorder == "=" and not np.little_endian):
        arr = arr.astype(dt.newbyteorder("<"))
        info["conversions"].append("byteswap to little-endian")
    if arr.dtype not in UNSIGNED:
        raise CanonicalError(f"unsupported dtype {arr.dtype}")
    perm = _permutation(axes)
    if perm != (0, 1, 2):
        arr = np.transpose(arr, perm)
        info["conversions"].append(f"axes {axes.upper()} -> ZYX")
    if not arr.flags.c_contiguous:
        arr = np.ascontiguousarray(arr)
        info["conversions"].append("copy to C order")
    info["conversion_ns"] = time.perf_counter_ns() - t0
    info["dtype"] = str(arr.dtype)
    info["shape_zyx"] = list(arr.shape)
    return arr, info


def voxel_sha256(canon: np.ndarray) -> str:
    """Normalized voxel hash: dtype, canonical shape and little-endian C-order bytes."""
    if not canon.flags.c_contiguous:
        raise CanonicalError("voxel hash requires a C-contiguous canonical array")
    h = hashlib.sha256()
    h.update(f"{canon.dtype.str}|{','.join(map(str, canon.shape))}|ZYX|".encode())
    h.update(memoryview(canon).cast("B"))
    return h.hexdigest()


def crackle_view(canon: np.ndarray) -> np.ndarray:
    """Canonical (Z,Y,X) C-order is the same memory as Crackle's (X,Y,Z) Fortran order."""
    xyz = canon.T
    if not xyz.flags.f_contiguous:
        raise CanonicalError("expected a C-contiguous canonical array")
    return xyz


def from_xyz(xyz: np.ndarray) -> np.ndarray:
    """Decoder output in (X, Y, Z) -> canonical (Z, Y, X); a view when the decoder wrote
    Fortran order, otherwise a copy."""
    out = xyz.T
    return out if out.flags.c_contiguous else np.ascontiguousarray(out)
