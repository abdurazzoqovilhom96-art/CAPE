"""Background choice without K re-solves (spec section 13, formula (8)); brute force over
every background candidate."""

from __future__ import annotations

import numpy as np
import pytest

from cape import reference_model as rm
from cape import synthetic as syn

VOLUMES = [syn.blocky((6, 8, 8), n_labels=4, block=(2, 2, 2), seed=s) for s in range(8)]
VOLUMES += [syn.noise((4, 4, 5), n_labels=3, seed=100 + s) for s in range(8)]
VOLUMES += [syn.vertical_cylinders((6, 9, 9), n=3, radius=(1, 2), seed=200 + s) for s in range(4)]


@pytest.mark.parametrize("zyx", VOLUMES)
def test_background_formula_matches_bruteforce(zyx):
    Z, Y, X = zyx.shape
    cc, _, _ = rm.cc_label(zyx)
    models = rm.build_models(zyx, cc, rm.depth_windows(rm.column_runs(zyx), Z), 5, 2)
    opt, ub, lb = {}, {}, {}
    for label, m in models.items():
        comps = rm.components(rm.reduce_all(m, X, Y))
        opt[label] = sum(rm.dp_lowest_bit(c)[0] for c in comps)
        ub[label] = sum(rm.greedy(c, X, Y)[0] for c in comps)
        lb[label] = sum(rm.dual_ascent(c)[1] for c in comps)
        assert lb[label] <= opt[label] <= ub[label]
    H = 37  # any background-independent header
    true_min = min(H + sum(v for k, v in opt.items() if k != b) for b in opt)
    exact_ub, exact_lb, b_star = rm.background_bounds(opt, opt, H)
    assert exact_ub == exact_lb == true_min  # all labels exact -> argmax is optimal
    assert H + sum(v for k, v in opt.items() if k != b_star) == true_min
    heur_ub, heur_lb, _ = rm.background_bounds(ub, lb, H)
    assert heur_lb <= true_min <= heur_ub
