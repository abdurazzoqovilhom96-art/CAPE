"""Safe reductions keep the optimum (spec sections 8, 29, 39.8)."""

from __future__ import annotations

import numpy as np
import pytest

from cape import reference_model as rm
from cape import synthetic as syn


def _models(zyx, h, pin_cost, single_cost):
    cc, _, _ = rm.cc_label(zyx)
    runs = rm.column_runs(zyx)
    return rm.build_models(zyx, cc, rm.depth_windows(runs, h), pin_cost, single_cost)


CASES = []
_rng = np.random.default_rng(20261105)
for _i in range(40):
    shape = tuple(int(v) for v in _rng.integers(1, 4, size=3))
    shape = (int(_rng.integers(2, 6)), shape[1], shape[2])
    CASES.append((_rng.integers(0, 3, size=shape).astype(np.uint32), int(_rng.integers(1, 6)),
                  int(_rng.integers(2, 9)), int(_rng.integers(1, 4))))
CASES.append((syn.vertical_cylinders((6, 6, 6), n=2, radius=(1, 2), seed=9), 6, 5, 2))
CASES.append((syn.walking_cylinders((6, 7, 7), n=2, radius=(1, 2), seed=10), 6, 5, 2))


@pytest.mark.parametrize("zyx,h,pin_cost,single_cost", CASES)
def test_each_reduction_keeps_optimum(zyx, h, pin_cost, single_cost):
    Z, Y, X = zyx.shape
    h = min(h, Z)
    checked = 0
    for m in _models(zyx, h, pin_cost, single_cost).values():
        if len(m.universe) > 16:  # Python DP limit; native core covers larger cases
            continue
        checked += 1
        opt = rm.dp_lowest_bit(m)[0]
        assert rm.dp_lowest_bit(rm.reduce_equal_coverage(m, X, Y))[0] == opt
        assert rm.dp_lowest_bit(rm.reduce_subset(m))[0] == opt
        assert rm.dp_lowest_bit(rm.reduce_singleton(m))[0] == opt
        assert rm.dp_lowest_bit(rm.reduce_all(m, X, Y))[0] == opt
    assert checked >= 1


def test_forced_hash_collision_never_merges_distinct_coverage():
    zyx = syn.vertical_cylinders((6, 10, 10), n=4, radius=(1, 3), seed=12)
    Z, Y, X = zyx.shape
    for m in _models(zyx, Z, 5, 2).values():
        normal = rm.reduce_equal_coverage(m, X, Y)
        collide = rm.reduce_equal_coverage(m, X, Y, hash_fn=lambda s: 0)  # every set collides
        assert {s for _, s in normal.pins} == {s for _, s in collide.pins} == {s for _, s in m.pins}
        assert [p for p, _ in normal.pins] == [p for p, _ in collide.pins]


def test_equal_coverage_keeps_exactly_one_representative():
    """39.8: two pins with identical coverage and cost must not remove each other."""
    zyx = np.zeros((4, 1, 3), dtype=np.uint32)
    zyx[:, 0, 0:2] = 5  # two columns crossing the same 4 CCs
    Z, Y, X = zyx.shape
    m = _models(zyx, Z, 5, 2)[5]
    assert len(m.pins) > 1
    red = rm.reduce_equal_coverage(m, X, Y)
    full_sets = [s for _, s in red.pins if len(s) == 4]
    assert len(full_sets) == 1  # one representative survives
    assert red.pins[[s for _, s in red.pins].index(full_sets[0])][0].x == 0  # smallest start index
    assert rm.dp_lowest_bit(red)[0] == rm.dp_lowest_bit(m)[0] == 5
