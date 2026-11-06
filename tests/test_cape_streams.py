"""CAPE streams vs the ORIGINAL decoders (spec sections 6, 14, 19 panel A, 29, 39.5)."""

from __future__ import annotations

import crackle  # PyPI crackle-codec 0.53.0
import numpy as np
import pytest

from cape import _cape_native as cn
from cape import _crackle_vendor as cv
from cape import crackle_format as cf
from cape import synthetic as syn
from conftest import as_xyz

VOLUMES = [
    ("blocky_u8", syn.blocky((16, 32, 32), n_labels=7, dtype=np.uint8, seed=1)),
    ("blocky_u16", syn.blocky((32, 64, 64), dtype=np.uint16, seed=2)),
    ("voronoi_u32", syn.dense_drifting_voronoi((24, 64, 64), n_seeds=50, dtype=np.uint32, seed=3)),
    ("walking_u64", syn.walking_cylinders((20, 48, 48), dtype=np.uint64, seed=4)),
    ("branching_u32", syn.branching((20, 48, 48), seed=5)),
    ("cylinders_u16", syn.vertical_cylinders((30, 50, 50), n=20, dtype=np.uint16, seed=6)),
    ("large_ids_u64", syn.large_ids((8, 16, 16), seed=7)),
    ("disconnected", syn.disconnected_same_id((12, 24, 24), seed=8)),
    ("single_label", syn.single_label((6, 8, 8))),
    ("all_background", syn.all_background((6, 8, 8))),
    ("all_distinct", syn.all_distinct((3, 6, 6))),
    ("checkerboard", syn.checkerboard((4, 8, 8))),
    ("noise", syn.noise((6, 12, 12), seed=9)),
    ("single_slice", syn.single_slice((1, 24, 24))),
    ("isolated_256", syn.isolated_components(256, depth=2)),
    ("depth256", syn.depth_boundary(256)),
    ("depth257", syn.depth_boundary(257)),
    ("depth258", syn.depth_boundary(258)),
]
POLICIES = ["same_as_stock", "force_pins", "min_exact"]


@pytest.mark.parametrize("markov", [0, 5])
@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("name,zyx", VOLUMES, ids=[n for n, _ in VOLUMES])
def test_cape_stream_is_lossless_with_original_decoders(name, zyx, policy, markov):
    xyz = as_xyz(zyx)
    buf, d = cn.encode(xyz, {"format_policy": policy, "markov_model_order": markov})
    out_p = crackle.decompress(buf)
    out_v = cv.decompress(buf)
    assert out_p.dtype == xyz.dtype and np.array_equal(out_p, xyz)
    assert out_v.dtype == xyz.dtype and np.array_equal(out_v, xyz)
    lay = cf.split_stream(buf)  # header crc8, z-index crc, labels crc32c all verified
    assert d["total_bytes"] == len(buf)
    if lay.header.label_format == cf.PINS_VARIABLE_WIDTH:
        sec = cf.parse_pins_section(lay.labels, lay.header)
        assert sec.consumed_bytes == len(lay.labels)
        assert d["label_bytes"] == len(lay.labels)
        assert d["lb_bytes"] <= d["ub_bytes"] == len(buf)
        assert (sec.P, sec.Q) == (d["P"], d["Q"])
        assert sec.num_pins_width == cf.byte_width(max([0] + [max(len(p), len(c)) for p, c in zip(sec.pins, sec.cc_ids)]))
    stock = crackle.compress(xyz, allow_pins=2, markov_model_order=markov)
    assert lay.boundary_payload == cf.split_stream(stock).boundary_payload  # panel A causality
    if policy == "same_as_stock":
        assert lay.header.label_format == cf.parse_header(stock).label_format


def test_flat_path_is_identical_to_stock():
    for seed in range(5):
        xyz = as_xyz(syn.noise((6, 12, 12), seed=100 + seed))
        buf, d = cn.encode(xyz, {})
        assert d["label_format"] == "FLAT"
        assert buf == crackle.compress(xyz, allow_pins=2)


def test_cape_fixes_the_count_width_corruption():
    xyz = as_xyz(syn.count_width_adversarial())
    buf, d = cn.encode(xyz, {})
    assert np.array_equal(crackle.decompress(buf), xyz)
    assert np.array_equal(cv.decompress(buf), xyz)
    assert d["w_N"] == 2
    stock = crackle.compress(xyz, allow_pins=2)
    assert not np.array_equal(crackle.decompress(stock), xyz)  # upstream stream is corrupt


def test_depth_regimes_are_evaluated_beyond_256_slices():
    xyz = as_xyz(syn.depth_boundary(300))
    _, d = cn.encode(xyz, {})
    assert d["regime_section_bytes"] and len(d["regime_section_bytes"]) == 2  # w_D = 2 (full) and 1
    assert "wD2:" in d["regimes"] and "wD1:" in d["regimes"]
    _, fixed = cn.encode(xyz, {"depth_policy": "fixed_depth_width"})
    assert len(fixed["regime_section_bytes"]) == 1


def test_encoding_is_deterministic():
    xyz = as_xyz(syn.dense_drifting_voronoi((16, 48, 48), seed=11))
    assert cn.encode(xyz, {})[0] == cn.encode(xyz, {})[0]
