"""Interop with the original upstream decoders (spec sections 6, 14, 29, 39.5).

Any stream CAPE writes must decode losslessly with BOTH the PyPI crackle-codec 0.53.0 wheel
and the vendor build at the pinned SHA. The characterization tests below pin down upstream
behaviours documented in docs/format_audit.md; if upstream changes, they fail on purpose so
the audit is revisited.
"""

from __future__ import annotations

import crackle  # PyPI crackle-codec 0.53.0
import numpy as np
import pytest

from cape import _crackle_vendor as cv
from cape import crackle_format as cf
from cape import synthetic as syn
from conftest import as_xyz

VOLUMES = [
    ("blocky_u16", syn.blocky((32, 64, 64), dtype=np.uint16, seed=1)),
    ("voronoi_u32", syn.dense_drifting_voronoi((24, 48, 40), dtype=np.uint32, seed=2)),
    ("walking_u64", syn.walking_cylinders((20, 40, 48), dtype=np.uint64, seed=3)),
    ("large_ids_u64", syn.large_ids((8, 16, 16), seed=4)),
    ("noise_u32", syn.noise((8, 16, 24), seed=5)),
    ("single_slice", syn.single_slice()),
    ("all_background", syn.all_background()),
    ("single_label", syn.single_label()),
    ("branching_u32", syn.branching((24, 40, 40), seed=6)),
]
SETTINGS = [(0, 0), (1, 0), (2, 0), (0, 5), (2, 5)]  # (allow_pins, markov order)


@pytest.mark.parametrize("allow_pins,markov", SETTINGS)
@pytest.mark.parametrize("name,zyx", VOLUMES, ids=[n for n, _ in VOLUMES])
def test_vendor_build_matches_pypi_and_cross_decodes(name, zyx, allow_pins, markov):
    xyz = as_xyz(zyx)
    pypi = crackle.compress(xyz, allow_pins=allow_pins, markov_model_order=markov)
    vend = cv.compress(xyz, allow_pins=allow_pins > 0, optimize_pins=allow_pins == 2,
                       markov_model_order=markov)
    assert pypi == vend, "vendor SHA and PyPI 0.53.0 encoders diverged"
    out_v = cv.decompress(pypi)
    out_p = crackle.decompress(vend)
    assert out_v.dtype == xyz.dtype and np.array_equal(out_v, xyz)
    assert out_p.dtype == xyz.dtype and np.array_equal(out_p, xyz)


@pytest.mark.parametrize("name,zyx", VOLUMES, ids=[n for n, _ in VOLUMES])
def test_upstream_label_format_rule(name, zyx):
    """compress_helper: pins only if sz > 1 and pixel_pairs >= voxels // 2 (allow_pins does
    not force pins)."""
    xyz = as_xyz(zyx)
    d = cv.format_decision(xyz, True)
    expected = (cf.PINS_VARIABLE_WIDTH
                if zyx.shape[0] > 1 and d["pixel_pairs"] >= d["voxels"] // 2 else cf.FLAT)
    assert d["label_format"] == expected
    for allow_pins in (1, 2):
        buf = crackle.compress(xyz, allow_pins=allow_pins)
        assert cf.parse_header(buf).label_format == expected


def test_allow_pins_does_not_force_pins_on_fragmented_volume():
    zyx = syn.noise((8, 16, 24), n_labels=5, seed=5)
    buf = crackle.compress(as_xyz(zyx), allow_pins=2)
    assert cf.parse_header(buf).label_format == cf.FLAT


def test_upstream_count_width_overflow_corrupts_silently():
    """Characterization: upstream sizes the count field from the pin count *before* short
    pins become explicit CC lists, so a label with 200 depth-1 pins writes 400 CC ids behind
    a 1-byte count. Both decoders return a wrong volume without raising."""
    zyx = syn.count_width_adversarial()
    xyz = as_xyz(zyx)
    for encode, decode in ((lambda v: crackle.compress(v, allow_pins=2), crackle.decompress),
                           (lambda v: cv.compress(v, allow_pins=True, optimize_pins=True), cv.decompress)):
        buf = encode(xyz)
        lay = cf.split_stream(buf)
        sec = cf.parse_pins_section(lay.labels, lay.header)
        assert sec.num_pins_width == 1
        assert sec.consumed_bytes < len(lay.labels)  # the truncated count leaves bytes unread
        out = decode(buf)  # no exception ...
        assert np.count_nonzero(out != xyz) == 256  # ... but 256 voxels come back wrong

    # Root cause check: the same stock selection with a count width that fits max(P_l, Q_l)
    # decodes losslessly with both original decoders. CAPE's strict serializer refuses the
    # overflowing width (spec 39.5 invariant).
    buf = cv.compress(xyz, allow_pins=True, optimize_pins=True)
    lay = cf.split_stream(buf)
    h = lay.header
    sec = cf.parse_pins_section(lay.labels, h)
    sel, per_slice, n_cc, _ = cv.pins_compute(xyz, True)
    rec = cf.upstream_records(sel, sec.bgcolor, h.sx, h.sy, n_cc, h.pin_index_width)
    assert rec["num_pins_width"] == 1 and rec["required_count_width"] == 2
    common = dict(stored_width=h.stored_data_width, bgcolor=sec.bgcolor, labels=rec["labels"],
                  components_per_grid=per_slice, component_width=h.component_width,
                  index_width=h.pin_index_width, depth_width=rec["depth_width"],
                  cc_label_width=rec["cc_label_width"], pins=rec["pins"], cc_ids=rec["cc_ids"])
    with pytest.raises(cf.FormatError):
        cf.serialize_pins_section(num_pins_width=rec["num_pins_width"], strict=True, **common)
    fixed = cf.serialize_pins_section(num_pins_width=rec["required_count_width"], strict=True, **common)
    fixed_stream = cf.replace_labels_section(buf, fixed)
    assert np.array_equal(crackle.decompress(fixed_stream), xyz)
    assert np.array_equal(cv.decompress(fixed_stream), xyz)


def test_upstream_manual_bgcolor_is_truncated_to_bool():
    """Characterization: compress_helper declares manual_bgcolor as bool, so bgcolor=5 is
    stored as background 1. Decoding stays lossless (all other labels are written)."""
    zyx = syn.blocky((32, 64, 64), n_labels=6, dtype=np.uint32, seed=11)
    present = set(np.unique(zyx).tolist())
    assert {1, 5} <= present
    xyz = as_xyz(zyx)
    buf = crackle.compress(xyz, allow_pins=2, bgcolor=5)
    assert cf.parse_header(buf).label_format == cf.PINS_VARIABLE_WIDTH
    assert cv.background_color(buf) == 1
    assert np.array_equal(crackle.decompress(buf), xyz)
