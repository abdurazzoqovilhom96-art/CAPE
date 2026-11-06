"""Section 7 theorem checks: depth-window candidates keep the optimum of the full family of
valid sub-segments (and so does subset dominance on top). Spec sections 29 and 34."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cape import reference_model as rm

SEED = 20261105


def _total_opt(zyx: np.ndarray, family: str, h: int, pin_cost: int, single_cost: int,
               subset: bool = False) -> int:
    cc, _, _ = rm.cc_label(zyx)
    runs = rm.column_runs(zyx)
    cands = rm.all_subsegments(runs, h) if family == "all" else rm.depth_windows(runs, h)
    total = 0
    for m in rm.build_models(zyx, cc, cands, pin_cost, single_cost).values():
        if subset:
            m = rm.reduce_subset(m)
        total += rm.dp_lowest_bit(m)[0]
    return total


def _section34_cases():
    rng = np.random.default_rng(SEED)
    vols = [rng.integers(0, 2, size=(3, 2, 2)).astype(np.uint32) for _ in range(80)]  # XYZ=(2,2,3)
    return [(i, h, v) for i, v in enumerate(vols) for h in (1, 2, 3)]


SECTION34 = _section34_cases()


def test_section34_case_count():
    assert len(SECTION34) == 240


@pytest.mark.parametrize("idx,h,zyx", SECTION34, ids=[f"v{i}-h{h}" for i, h, _ in SECTION34])
def test_section34_windows_and_dominance_keep_optimum(idx, h, zyx):
    full = _total_opt(zyx, "all", h, 5, 2)
    assert _total_opt(zyx, "windows", h, 5, 2) == full
    assert _total_opt(zyx, "windows", h, 5, 2, subset=True) == full


@pytest.mark.parametrize("k", range(1, 9))
def test_exhaustive_1d_runs(k):
    """One column per label, plus a parallel column sharing the same CCs (a 2-wide tube), for
    every h <= k: windows of length h are as good as every sub-segment."""
    zyx = np.zeros((k, 1, 3), dtype=np.uint32)
    zyx[:, 0, 0:2] = 7  # tube of label 7, 2 columns wide, k slices
    for h in range(1, k + 1):
        for pin_cost, single_cost in ((5, 2), (3, 2), (2, 2), (9, 1)):
            assert _total_opt(zyx, "windows", h, pin_cost, single_cost) == \
                _total_opt(zyx, "all", h, pin_cost, single_cost)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(z=st.integers(1, 5), y=st.integers(1, 3), x=st.integers(1, 3), labels=st.integers(1, 3),
       h=st.integers(1, 5), pin_cost=st.integers(1, 9), single_cost=st.integers(1, 4),
       seed=st.integers(0, 10_000))
def test_property_windows_equal_full_family(z, y, x, labels, h, pin_cost, single_cost, seed):
    zyx = np.random.default_rng(seed).integers(0, labels, size=(z, y, x)).astype(np.uint32)
    h = min(h, z)
    full = _total_opt(zyx, "all", h, pin_cost, single_cost)
    assert _total_opt(zyx, "windows", h, pin_cost, single_cost) == full
    assert _total_opt(zyx, "windows", h, pin_cost, single_cost, subset=True) == full
