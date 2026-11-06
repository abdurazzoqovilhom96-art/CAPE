"""Frozen v1 CAPE outputs (plan v2, P1): every v2 speed change must reproduce the v1 bitstreams
byte for byte. The golden file is written ONCE from the v1 build by scripts/write_golden.py and
never regenerated to make a failing test pass."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "golden_cape_v1.json"
RUN_CONFIG = "configs/benchmark.yaml"

GOLDEN_METHODS = [
    "cape_m0", "cape_m5", "cape_m0_minfmt", "cape_core", "weighted_greedy", "greedy_local", "stock_cover",
    "cape_no_dedup", "cape_no_dominance", "cape_no_exact", "cape_no_local", "cape_no_dual_gate",
    "cape_stock_background", "cape_fixed_depth_width", "cape_maximal_runs_only",
]

REAL_FILES = [
    "data/real/crackle_crops/crackle_connectomics_x384_y0_z320_128x128x64.npy",
    "data/real/crackle_crops/crackle_connectomics_x384_y0_z64_128x128x64.npy",
    "data/real/crackle_crops/crackle_ws_x0_y384_z320_128x128x64.npy",
    "data/real/cremi_crops/cremi_A_x0_y768_z0_128x128x64.npy",
    "data/real/cremi_crops/cremi_A_x512_y0_z0_128x128x64.npy",
]


def synthetic_cases() -> dict[str, np.ndarray]:
    from cape import synthetic as syn

    cases = {
        "blocky_u8": syn.blocky((16, 32, 32), n_labels=7, dtype=np.uint8, seed=1),
        "blocky_u16": syn.blocky((32, 64, 64), dtype=np.uint16, seed=2),
        "voronoi_u32": syn.dense_drifting_voronoi((24, 64, 64), n_seeds=50, dtype=np.uint32, seed=3),
        "walking_u64": syn.walking_cylinders((20, 48, 48), dtype=np.uint64, seed=4),
        "branching_u32": syn.branching((20, 48, 48), seed=5),
        "cylinders_u16": syn.vertical_cylinders((30, 50, 50), n=20, dtype=np.uint16, seed=6),
        "large_ids_u64": syn.large_ids((8, 16, 16), seed=7),
        "disconnected": syn.disconnected_same_id((12, 24, 24), seed=8),
        "noise": syn.noise((6, 12, 12), seed=9),
        "isolated_256": syn.isolated_components(256, depth=2),
        "depth257": syn.depth_boundary(257),
        "depth258": syn.depth_boundary(258),
    }
    for p in sorted((ROOT / "data" / "synthetic").glob("syn_*.npy")):
        cases[p.stem] = np.load(p)
    return cases


def real_cases() -> dict[str, np.ndarray]:
    return {Path(f).stem: np.load(ROOT / f) for f in REAL_FILES if (ROOT / f).exists()}


def native_options(method_id: str, methods: dict, cfg: dict) -> dict:
    from cape.config import cape_native_options

    opts = dict(cape_native_options(cfg))
    opts.update(methods[method_id].get("options", {}))
    opts["parallel"] = 1
    return opts


def digest(zyx: np.ndarray, opts: dict) -> tuple[str, int]:
    from cape import _cape_native as cn

    buf, _ = cn.encode(np.ascontiguousarray(zyx).T, opts)
    return hashlib.sha256(buf).hexdigest(), len(buf)
