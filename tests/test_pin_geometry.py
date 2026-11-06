"""Pin geometry invariants and CC-labeling equivalence with upstream (spec sections 4, 29)."""

from __future__ import annotations

import numpy as np
import pytest

from cape import _crackle_vendor as cv
from cape import reference_model as rm
from cape import synthetic as syn
from conftest import as_xyz

VOLUMES = [
    ("blocky", syn.blocky((12, 20, 24), seed=1)),
    ("voronoi", syn.dense_drifting_voronoi((10, 24, 20), seed=2)),
    ("walking", syn.walking_cylinders((10, 24, 24), seed=3)),
    ("branching", syn.branching((10, 24, 24), seed=4)),
    ("noise", syn.noise((5, 9, 11), n_labels=3, seed=5)),
    ("checker", syn.checkerboard((4, 6, 6))),
    ("disconnected", syn.disconnected_same_id((8, 16, 16), seed=6)),
    ("single_slice", syn.single_slice((1, 12, 12))),
    ("large_ids", syn.large_ids((6, 8, 8), seed=7)),
]


@pytest.mark.parametrize("name,zyx", VOLUMES, ids=[n for n, _ in VOLUMES])
def test_cc_labeling_equals_upstream(name, zyx):
    cc, per_slice, n = rm.cc_label(zyx)
    up, up_slices, up_n = cv.connected_components(as_xyz(zyx))
    assert n == up_n
    assert list(per_slice) == list(up_slices)
    assert np.array_equal(cc, up.T.astype(np.int64))


@pytest.mark.parametrize("name,zyx", VOLUMES, ids=[n for n, _ in VOLUMES])
def test_runs_partition_columns_and_pins_stay_in_label(name, zyx):
    Z, Y, X = zyx.shape
    cc, _, n = rm.cc_label(zyx)
    lab = rm.cc_label_values(zyx, cc, n)
    runs = rm.column_runs(zyx)
    per_col: dict[tuple[int, int], list[rm.Pin]] = {}
    for r in runs:
        per_col.setdefault((r.y, r.x), []).append(r)
    assert len(per_col) == Y * X
    for (y, x), rs in per_col.items():
        assert sum(r.length for r in rs) == Z  # runs tile the column
        assert [r.z0 for r in rs] == sorted(r.z0 for r in rs)
        for a, b in zip(rs, rs[1:]):
            assert a.z0 + a.length == b.z0 and a.label != b.label  # maximal
        for r in rs:
            assert np.all(zyx[r.z0:r.z0 + r.length, y, x] == r.label)
    for p in rm.all_subsegments(runs, Z):
        s = rm.coverage(cc, p)
        assert len(set(s)) == p.length == p.depth + 1  # one distinct CC per slice
        assert all(int(lab[u]) == p.label for u in s)  # never crosses another ID
        assert p.start_index(X, Y) == p.x + X * (p.y + Y * p.z0)


def test_depth_windows_shape():
    run = rm.Pin(3, 0, 0, 2, 7)
    assert rm.depth_windows([run], 10) == [run]
    w = rm.depth_windows([run], 3)
    assert len(w) == 7 - 3 + 1 and all(p.length == 3 for p in w)
    assert [p.z0 for p in w] == [2, 3, 4, 5, 6]
