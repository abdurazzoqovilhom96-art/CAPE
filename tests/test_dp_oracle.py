"""Exact DP vs brute force vs independent CP-SAT (spec sections 10, 12 audit, 29)."""

from __future__ import annotations

import numpy as np
import pytest
from ortools.sat.python import cp_model

from cape import reference_model as rm


def random_model(seed: int) -> rm.CoverModel:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(1, 11))
    universe = tuple(range(100, 100 + n))
    pins = []
    for k in range(int(rng.integers(0, 12))):
        size = int(rng.integers(1, n + 1))
        s = frozenset(int(u) for u in rng.choice(universe, size=size, replace=False))
        pins.append((rm.Pin(1, 0, k, 0, len(s)), s))
    return rm.CoverModel(1, universe, pins, int(rng.integers(1, 10)), int(rng.integers(1, 5)))


def cpsat_opt(m: rm.CoverModel) -> int:
    model = cp_model.CpModel()
    xs = [model.NewBoolVar(f"p{i}") for i in range(len(m.pins))]
    ys = {u: model.NewBoolVar(f"u{u}") for u in m.universe}
    for u in m.universe:
        model.Add(sum(x for x, (_, s) in zip(xs, m.pins) if u in s) + ys[u] >= 1)
    model.Minimize(m.pin_cost * sum(xs) + m.single_cost * sum(ys.values()))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 20261105
    status = solver.Solve(model)
    assert status == cp_model.OPTIMAL, "CP-SAT must prove optimality (FEASIBLE is not OPTIMAL)"
    return int(round(solver.ObjectiveValue()))


@pytest.mark.parametrize("seed", range(60))
def test_dp_matches_bruteforce_and_cpsat(seed):
    m = random_model(seed)
    opt_bf, sel_bf = rm.brute_force(m)
    opt_plain, trans_plain = rm.dp_plain(m)
    opt_low, sel_low, trans_low = rm.dp_lowest_bit(m)
    assert opt_bf == opt_plain == opt_low == cpsat_opt(m)
    # lowest-uncovered-bit DP visits a subset of the plain DP's states and actions
    assert trans_low <= trans_plain
    pins = [next(s for p, s in m.pins if p == a) for a in sel_low if isinstance(a, rm.Pin)]
    singles = [a[1] for a in sel_low if isinstance(a, tuple)]
    assert m.is_cover(pins, singles)
    assert m.pin_cost * len(pins) + m.single_cost * len(singles) == opt_low


@pytest.mark.parametrize("seed", range(60))
def test_greedy_is_feasible_and_not_below_optimum(seed):
    m = random_model(seed)
    ub, pins, singles = rm.greedy(m, X=64, Y=64)
    sets = [s for p, s in m.pins if p in set(pins)]
    assert m.is_cover(sets, singles)
    assert ub == m.cost(pins, singles) >= rm.dp_lowest_bit(m)[0]
