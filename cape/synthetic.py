"""Deterministic synthetic label volumes (spec section 22) for correctness/adversarial tests.

All generators return canonical arrays: shape (Z, Y, X), C-contiguous, unsigned dtype.
Synthetic data is never used as a stand-in for real data (spec section 18): rows produced
from these volumes carry is_synthetic=True and are excluded from real-result tables.
"""

from __future__ import annotations

import numpy as np

DEFAULT_SEED = 20261105


def _rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(DEFAULT_SEED if seed is None else seed)


def _finish(vol: np.ndarray, dtype) -> np.ndarray:
    return np.ascontiguousarray(vol.astype(dtype, copy=False))


def blocky(shape=(32, 64, 64), n_labels=12, block=(4, 8, 8), dtype=np.uint32, seed=None) -> np.ndarray:
    """Piecewise-constant blocks: long z-runs, pins-friendly."""
    z, y, x = shape
    bz, by, bx = block
    coarse = _rng(seed).integers(0, n_labels, size=(-(-z // bz), -(-y // by), -(-x // bx)))
    vol = np.kron(coarse, np.ones(block, dtype=np.int64))[:z, :y, :x]
    return _finish(vol, dtype)


def vertical_cylinders(shape=(32, 64, 64), n=12, radius=(2, 7), dtype=np.uint32, seed=None) -> np.ndarray:
    rng = _rng(seed)
    z, y, x = shape
    yy, xx = np.mgrid[0:y, 0:x]
    vol = np.zeros(shape, dtype=np.int64)
    for k in range(1, n + 1):
        cy, cx = rng.integers(0, y), rng.integers(0, x)
        r = rng.integers(radius[0], radius[1] + 1)
        z0 = rng.integers(0, max(1, z // 3))
        z1 = rng.integers(min(z, z0 + 1), z + 1)
        disk = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
        vol[z0:z1][:, disk] = k
    return _finish(vol, dtype)


def walking_cylinders(shape=(32, 64, 64), n=10, radius=(2, 6), max_slope=0.6, dtype=np.uint32,
                      seed=None) -> np.ndarray:
    """Slanted tubes whose centre drifts with z (short per-column runs)."""
    rng = _rng(seed)
    z, y, x = shape
    yy, xx = np.mgrid[0:y, 0:x]
    vol = np.zeros(shape, dtype=np.int64)
    for k in range(1, n + 1):
        cy, cx = rng.uniform(0, y), rng.uniform(0, x)
        sy, sx = rng.uniform(-max_slope, max_slope, size=2)
        r = rng.integers(radius[0], radius[1] + 1)
        for zz in range(z):
            disk = (yy - (cy + sy * zz)) ** 2 + (xx - (cx + sx * zz)) ** 2 <= r * r
            vol[zz][disk] = k
    return _finish(vol, dtype)


def branching(shape=(32, 64, 64), n=6, radius=3, dtype=np.uint32, seed=None) -> np.ndarray:
    """Each object is one ID whose trunk splits into two diverging branches (2 CCs/slice)."""
    rng = _rng(seed)
    z, y, x = shape
    yy, xx = np.mgrid[0:y, 0:x]
    vol = np.zeros(shape, dtype=np.int64)
    for k in range(1, n + 1):
        cy, cx = rng.uniform(radius, y - radius), rng.uniform(radius, x - radius)
        split = int(rng.integers(z // 4, max(z // 4 + 1, 3 * z // 4)))
        ang = rng.uniform(0, np.pi)
        dy, dx = np.sin(ang), np.cos(ang)
        for zz in range(z):
            off = max(0, zz - split) * 0.9
            for sgn in ((0,) if zz <= split else (-1, 1)):
                disk = (yy - (cy + sgn * off * dy)) ** 2 + (xx - (cx + sgn * off * dx)) ** 2 <= radius * radius
                vol[zz][disk] = k
    return _finish(vol, dtype)


def dense_drifting_voronoi(shape=(32, 64, 64), n_seeds=40, drift=0.35, dtype=np.uint32, seed=None) -> np.ndarray:
    """Dense, neuron-like segmentation: every voxel labelled; 2D Voronoi cells whose seeds
    drift slowly with z so most labels are z-continuous."""
    rng = _rng(seed)
    z, y, x = shape
    pos = np.stack([rng.uniform(0, y, n_seeds), rng.uniform(0, x, n_seeds)], axis=1)
    vel = rng.normal(0, drift, size=(n_seeds, 2))
    ids = rng.choice(np.arange(1, 50 * n_seeds + 1), size=n_seeds, replace=False)
    yy, xx = np.mgrid[0:y, 0:x]
    vol = np.empty(shape, dtype=np.int64)
    for zz in range(z):
        p = pos + vel * zz
        d = (yy[..., None] - p[:, 0]) ** 2 + (xx[..., None] - p[:, 1]) ** 2
        vol[zz] = ids[np.argmin(d, axis=-1)]
    return _finish(vol, dtype)


def checkerboard(shape=(8, 16, 16), period=1, dtype=np.uint32) -> np.ndarray:
    z, y, x = np.indices(shape)
    return _finish(((x // period + y // period + z // period) % 2) + 1, dtype)


def noise(shape=(8, 16, 16), n_labels=5, dtype=np.uint32, seed=None) -> np.ndarray:
    return _finish(_rng(seed).integers(0, n_labels, size=shape), dtype)


def single_label(shape=(8, 16, 16), value=7, dtype=np.uint32) -> np.ndarray:
    return _finish(np.full(shape, value), dtype)


def all_background(shape=(8, 16, 16), dtype=np.uint32) -> np.ndarray:
    return _finish(np.zeros(shape), dtype)


def all_distinct(shape=(4, 8, 8), dtype=np.uint32) -> np.ndarray:
    """Every voxel its own label (worst case for pins)."""
    v = int(np.prod(shape))
    if v > np.iinfo(dtype).max:
        raise ValueError("dtype too small for all-distinct labels")
    return _finish(np.arange(1, v + 1).reshape(shape), dtype)


def disconnected_same_id(shape=(16, 32, 32), blobs=6, value=9, dtype=np.uint32, seed=None) -> np.ndarray:
    rng = _rng(seed)
    vol = np.zeros(shape, dtype=np.int64)
    z, y, x = shape
    for _ in range(blobs):
        z0, y0, x0 = rng.integers(0, z - 2), rng.integers(0, y - 4), rng.integers(0, x - 4)
        vol[z0:z0 + 2, y0:y0 + 3, x0:x0 + 3] = value
    return _finish(vol, dtype)


def single_slice(shape=(1, 32, 32), n_labels=6, dtype=np.uint32, seed=None) -> np.ndarray:
    return blocky(shape, n_labels=n_labels, block=(1, 4, 4), dtype=dtype, seed=seed)


def depth_boundary(run_length: int, xy=(6, 6), pad=2, dtype=np.uint32) -> np.ndarray:
    """One column object whose z-run has exactly `run_length` voxels (pin depth run_length-1),
    e.g. 256/257/258 to cross the 1-byte depth boundary at depth 255/256."""
    z = run_length + 2 * pad
    vol = np.zeros((z, xy[0], xy[1]), dtype=np.int64)
    vol[pad:pad + run_length, 2:4, 2:4] = 5
    vol[:, 0, 0] = 3  # a second label so the object is not the background
    return _finish(vol, dtype)


def large_ids(shape=(8, 16, 16), dtype=np.uint64, seed=None) -> np.ndarray:
    base = blocky(shape, n_labels=6, block=(2, 4, 4), dtype=np.uint64, seed=seed)
    top = np.uint64(np.iinfo(np.uint64).max)
    lut = np.array([0, top, top - np.uint64(1), np.uint64(2**63), np.uint64(2**63 + 12345), np.uint64(2**32)],
                   dtype=np.uint64)
    return _finish(lut[base.astype(np.int64)], dtype)


def isolated_components(n_components: int, label=4, background=0, depth=1, spacing=2,
                        dtype=np.uint32) -> np.ndarray:
    """`n_components` isolated single-voxel towers (each `depth` slices tall) of one label:
    exercises count-width boundaries (255/256/65535/65536)."""
    side = int(np.ceil(np.sqrt(n_components)))
    y = x = side * spacing + 1
    vol = np.full((depth + 1, y, x), background, dtype=np.int64)
    k = 0
    for i in range(side):
        for j in range(side):
            if k == n_components:
                break
            vol[0:depth, 1 + i * spacing, 1 + j * spacing] = label
            k += 1
    return _finish(vol, dtype)


def count_width_adversarial(dtype=np.uint32) -> np.ndarray:
    """Minimal reproducer for the upstream count-width overflow (docs/format_audit.md):
    label 2 (300 two-voxel towers) becomes the upstream background (most pins); label 1 keeps
    200 depth-1 pins, all converted to explicit CC lists -> 400 CC ids written behind a
    1-byte count (max pin count 200 <= 255)."""
    X = Y = 128
    Z = 32
    vol = np.zeros((Z, Y, X), dtype=np.int64)
    pos = [(yy, xx) for yy in range(2, Y, 4) for xx in range(2, X, 4)]
    for yy, xx in pos[:200]:
        vol[0:2, yy, xx] = 1
    for yy, xx in pos[200:500]:
        vol[0:2, yy, xx] = 2
    return _finish(vol, dtype)


FAMILIES = {
    "blocky": blocky,
    "vertical_cylinders": vertical_cylinders,
    "walking_cylinders": walking_cylinders,
    "branching": branching,
    "dense_drifting_voronoi": dense_drifting_voronoi,
    "checkerboard": checkerboard,
    "noise": noise,
    "single_label": single_label,
    "all_background": all_background,
    "all_distinct": all_distinct,
    "disconnected_same_id": disconnected_same_id,
    "single_slice": single_slice,
    "large_ids": large_ids,
}
