"""Byte model and container rules (spec sections 6, 29: predicted == serialized bytes).

These tests validate the pure-Python reference (cape/crackle_format.py) against real
upstream streams; the native byte model is checked against the same reference in
tests/test_interop.py once CAPE streams exist.
"""

from __future__ import annotations

import numpy as np
import pytest

from cape import _crackle_vendor as cv
from cape import crackle_format as cf
from cape import synthetic as syn
from conftest import as_xyz

PINS_VOLUMES = [
    ("blocky_u16", syn.blocky((32, 64, 64), dtype=np.uint16, seed=21)),
    ("blocky_u64", syn.blocky((17, 40, 56), n_labels=25, dtype=np.uint64, seed=22)),
    ("voronoi_u32", syn.dense_drifting_voronoi((24, 48, 40), dtype=np.uint32, seed=23)),
    ("cylinders_u32", syn.vertical_cylinders((30, 50, 50), dtype=np.uint32, seed=24)),
    ("walking_u32", syn.walking_cylinders((20, 40, 48), dtype=np.uint32, seed=25)),
    ("branching_u16", syn.branching((24, 40, 40), dtype=np.uint16, seed=26)),
    ("large_ids", syn.large_ids((8, 16, 16), seed=27)),
    ("isolated_256", syn.isolated_components(256, depth=2)),
]


def test_crc_reference_matches_upstream():
    assert cf.crc32c(b"123456789") == 0xE3069283 == cv.crc32c(b"123456789")
    for s in (b"", b"a", b"crackle header bytes!!", bytes(range(256)) * 3):
        assert cf.crc8(s) == cv.crc8(s)
        assert cf.crc32c(s) == cv.crc32c(s)


def test_byte_width_boundaries():
    assert [cf.byte_width(v) for v in (0, 255, 256, 65535, 65536, 2**32 - 1, 2**32, 2**64 - 1)] == \
        [1, 1, 2, 2, 4, 4, 8, 8]
    with pytest.raises(cf.FormatError):
        cf.byte_width(2**64)


def test_header_fields_roundtrip_and_crc_guard():
    h = cf.Header(format_version=1, label_format=cf.PINS_VARIABLE_WIDTH, crack_format=1, is_signed=False,
                  data_width=8, stored_data_width=4, sx=300, sy=7, sz=513, grid_size=2**31,
                  num_label_bytes=123456, fortran_order=True, markov_model_order=5, is_sorted=True,
                  is_remapped=False)
    raw = h.to_bytes()
    assert len(raw) == cf.HEADER_SIZE_V1
    back = cf.parse_header(raw)
    assert {k: getattr(back, k) for k in h.__dataclass_fields__ if k != "crc"} == \
        {k: getattr(h, k) for k in h.__dataclass_fields__ if k != "crc"}
    corrupted = bytearray(raw)
    corrupted[9] ^= 0x01
    with pytest.raises(cf.FormatError):
        cf.parse_header(bytes(corrupted))


@pytest.mark.parametrize("markov", [0, 3])
@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("name,zyx", PINS_VOLUMES, ids=[n for n, _ in PINS_VOLUMES])
def test_pins_section_parse_serialize_formula3(name, zyx, optimize, markov):
    xyz = as_xyz(zyx)
    buf = cv.compress(xyz, allow_pins=True, optimize_pins=optimize, markov_model_order=markov)
    lay = cf.split_stream(buf)
    h = lay.header
    assert h.label_format == cf.PINS_VARIABLE_WIDTH, "fixture must exercise the pins format"
    assert h.to_bytes() == buf[: h.header_bytes]
    assert cf.replace_labels_section(buf, lay.labels) == buf
    sec = cf.parse_pins_section(lay.labels, h)
    assert sec.consumed_bytes == len(lay.labels)
    again = cf.serialize_pins_section(
        stored_width=sec.stored_width, bgcolor=sec.bgcolor, labels=sec.labels,
        components_per_grid=sec.components_per_grid, component_width=sec.component_width,
        index_width=sec.index_width, num_pins_width=sec.num_pins_width, depth_width=sec.depth_width,
        cc_label_width=sec.cc_label_width, pins=sec.pins, cc_ids=sec.cc_ids, strict=True)
    assert again == lay.labels
    predicted = cf.predict_pins_section_bytes(
        stored_width=sec.stored_width, n_written_labels=len(sec.labels), num_grids=h.num_grids,
        component_width=sec.component_width, num_pins_width=sec.num_pins_width,
        index_width=sec.index_width, depth_width=sec.depth_width, cc_label_width=sec.cc_label_width,
        P=sec.P, Q=sec.Q)
    assert predicted == len(lay.labels) == h.num_label_bytes


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("name,zyx", PINS_VOLUMES, ids=[n for n, _ in PINS_VOLUMES])
def test_stock_selection_replay_is_byte_identical(name, zyx, optimize):
    """pins_compute() + replayed upstream serializer rules == upstream labels section."""
    xyz = as_xyz(zyx)
    buf = cv.compress(xyz, allow_pins=True, optimize_pins=optimize)
    lay = cf.split_stream(buf)
    h = lay.header
    sec = cf.parse_pins_section(lay.labels, h)
    sel, per_slice, n_cc, crcs = cv.pins_compute(xyz, optimize)
    assert sec.bgcolor in cf.upstream_background_candidates(sel)
    rec = cf.upstream_records(sel, sec.bgcolor, h.sx, h.sy, n_cc, h.pin_index_width)
    replay = cf.serialize_pins_section(
        stored_width=h.stored_data_width, bgcolor=sec.bgcolor, labels=rec["labels"],
        components_per_grid=per_slice, component_width=h.component_width, index_width=h.pin_index_width,
        num_pins_width=rec["num_pins_width"], depth_width=rec["depth_width"],
        cc_label_width=rec["cc_label_width"], pins=rec["pins"], cc_ids=rec["cc_ids"], strict=False)
    assert replay == lay.labels
    assert list(lay.cc_crcs) == list(crcs)


@pytest.mark.parametrize("seed", [31, 32, 33])
def test_flat_section_consistency(seed):
    zyx = syn.noise((6, 20, 18), n_labels=9, seed=seed)
    buf = cv.compress(as_xyz(zyx), allow_pins=False)
    lay = cf.split_stream(buf)
    assert lay.header.label_format == cf.FLAT
    fs = cf.parse_flat_section(lay.labels, lay.header)
    assert fs.uniq == sorted(set(np.unique(zyx).tolist()))
    assert sum(fs.components_per_grid) == len(fs.keys)
    assert max(fs.keys) < len(fs.uniq)
