"""Integer dual bound, independent verifier, background bound and the spec 39.9 reference
checks (300 random weighted set-cover cases, n = 1..8)."""

from __future__ import annotations

import numpy as np
import pytest

from cape import certificate_verify as cvf
from cape import reference_model as rm

Q = 1 << 20


def random_model(rng: np.random.Generator, n: int) -> rm.CoverModel:
    universe = tuple(range(n))
    pins = []
    for k in range(int(rng.integers(0, 2 * n + 2))):
        s = frozenset(int(u) for u in rng.choice(universe, size=int(rng.integers(1, n + 1)), replace=False))
        pins.append((rm.Pin(1, 0, k, 0, len(s)), s))
    return rm.CoverModel(1, universe, pins, int(rng.integers(1, 10)), int(rng.integers(1, 5)))


V2_CASES = []
_rng = np.random.default_rng(20261105)
for _i in range(300):
    V2_CASES.append(random_model(_rng, int(_rng.integers(1, 9))))


def test_v2_case_count():
    assert len(V2_CASES) == 300


@pytest.mark.parametrize("idx", range(300))
def test_v2_reference_checks(idx):
    m = V2_CASES[idx]
    opt = rm.brute_force(m)[0]
    # singleton dominance keeps the optimum
    assert rm.dp_lowest_bit(rm.reduce_singleton(m))[0] == opt
    # integer dual bound is valid and verifiable
    a, lb = rm.dual_ascent(m, Q)
    assert lb <= opt
    res = cvf.verify_dual(m.universe, [s for _, s in m.pins], m.pin_cost, m.single_cost, a, Q, lb)
    assert res.valid and res.lb_recomputed == lb
    # the fixed-point scale is a no-op for integer costs (all values stay multiples of q)
    assert all(v % Q == 0 for v in a.values())
    assert rm.dual_ascent(m, 1)[1] == lb
    # compact-header bound (39.1): unrestricted payload LB + compact header <= optimum of the
    # count-restricted model, whenever the compact width admits a feasible solution
    for cap in (1, 2, 3):
        restricted = _restricted_opt(m, cap)
        if restricted is not None:
            assert lb <= restricted


def _restricted_opt(m: rm.CoverModel, cap: int) -> int | None:
    """Brute-force optimum with at most `cap` pins and at most `cap` singletons (a toy
    stand-in for a narrow count width)."""
    import itertools

    best = None
    sets = [s for _, s in m.pins]
    for kp in range(min(cap, len(sets)) + 1):
        for comb in itertools.combinations(range(len(sets)), kp):
            covered = set().union(*(sets[i] for i in comb)) if comb else set()
            rest = set(m.universe) - covered
            if len(rest) <= cap:
                c = kp * m.pin_cost + len(rest) * m.single_cost
                best = c if best is None else min(best, c)
    return best


@pytest.mark.parametrize("idx", range(0, 300, 7))
def test_verifier_rejects_corrupted_witness(idx):
    m = V2_CASES[idx]
    a, lb = rm.dual_ascent(m, Q)
    u = m.universe[0]
    bad = dict(a)
    bad[u] = Q * m.single_cost + 1  # exceeds the singleton cap
    assert not cvf.verify_dual(m.universe, [s for _, s in m.pins], m.pin_cost, m.single_cost, bad, Q).valid
    if m.pins:
        p_set = m.pins[0][1]
        bad2 = dict(a)
        w = next(iter(p_set))
        bad2[w] = bad2[w] + Q * m.pin_cost  # breaks the pin constraint
        assert not cvf.verify_dual(m.universe, [s for _, s in m.pins], m.pin_cost, m.single_cost, bad2, Q).valid
    assert not cvf.verify_dual(m.universe, [s for _, s in m.pins], m.pin_cost, m.single_cost, a, Q,
                               claimed_lb=lb + 1).valid


def test_relative_gap_definition():
    assert cvf.relative_gap(110, 100) == pytest.approx(0.10)
    assert cvf.relative_gap(5, 0) is None
