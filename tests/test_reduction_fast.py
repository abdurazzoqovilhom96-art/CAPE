"""v2 fast implementation == v1 legacy implementation (plan v2, P1.2).

`reduction_impl: fast` changes HOW the selector works (column-major chains, hash-table dedup,
reachable-state DP), never WHAT it selects: every bitstream, cover, cost and transition count must
be identical to `reduction_impl: legacy`.
"""

from __future__ import annotations

import numpy as np
import pytest

from cape import _cape_native as cn
from cape import synthetic as syn
from golden_cases import real_cases, synthetic_cases

VOLUMES = {**synthetic_cases(), **real_cases()}
OPTION_SETS = [
    {"format_policy": "force_pins"},
    {"format_policy": "same_as_stock", "markov_model_order": 5},
    {"format_policy": "force_pins", "reduce_subset": False, "reduce_singleton": False},
    {"format_policy": "force_pins", "use_exact": False},
    {"format_policy": "force_pins", "depth_policy": "fixed_depth_width"},
    {"format_policy": "force_pins", "candidate_policy": "maximal_runs_only"},
]


def _enc(zyx, opts):
    buf, d = cn.encode(np.ascontiguousarray(zyx).T, dict(opts, parallel=1))
    return buf, d


@pytest.mark.parametrize("oi", range(len(OPTION_SETS)))
@pytest.mark.parametrize("name", sorted(VOLUMES))
def test_fast_equals_legacy_bitstream(name, oi):
    zyx = VOLUMES[name]
    legacy, dl = _enc(zyx, dict(OPTION_SETS[oi], reduction_impl="legacy"))
    fast, df = _enc(zyx, dict(OPTION_SETS[oi], reduction_impl="fast"))
    assert fast == legacy
    for k in ("candidate_count_after", "candidates_after_equal", "dp_transitions", "dp_components_solved",
              "local_checks", "lb_bytes"):
        if k in dl:
            assert df[k] == dl[k], k


@pytest.mark.parametrize("bits", [0, 1, 3])
@pytest.mark.parametrize("name", ["syn_dense_voronoi", "syn_branching", "voronoi_u32", "walking_u64"])
def test_forced_hash_collisions_never_merge_distinct_chains(name, bits):
    """With only `bits` hash bits nearly every chain collides; exact confirmation must keep the
    result identical on both implementations, and collisions must actually happen."""
    zyx = VOLUMES[name]
    ref, _ = _enc(zyx, {"format_policy": "force_pins"})
    for impl in ("legacy", "fast"):
        buf, d = _enc(zyx, {"format_policy": "force_pins", "reduction_impl": impl, "debug_hash_bits": bits})
        assert buf == ref, impl
        assert d["equal_hash_collisions"] > 0, impl


def _random_model(rng, n):
    sets = []
    for _ in range(int(rng.integers(n // 2, 3 * n))):
        k = int(rng.integers(2, min(n, 6) + 1))
        sets.append(sorted(int(v) for v in rng.choice(n, size=k, replace=False)))
    return sets


@pytest.mark.parametrize("seed", range(40))
def test_sparse_dp_equals_dense_dp(seed):
    rng = np.random.default_rng(20261106 + seed)
    n = int(rng.integers(13, 21))  # the sparse path is used for n > 12
    sets = _random_model(rng, n)
    c, s = int(rng.integers(3, 9)), int(rng.integers(1, 4))
    base = {"exact_max_cc": 20}
    dense = cn.solve_abstract(n, sets, c, s, dict(base, reduction_impl="legacy"))
    sparse = cn.solve_abstract(n, sets, c, s, dict(base, reduction_impl="fast"))
    assert dense["dp_outcome"] == sparse["dp_outcome"]
    assert dense["dp_transitions"] == sparse["dp_transitions"]
    if dense["dp_outcome"] == 0:
        assert (dense["dp_cost"], dense["dp_pins"], dense["dp_singles"]) == (
            sparse["dp_cost"], sparse["dp_pins"], sparse["dp_singles"])


def test_sparse_dp_respects_the_same_transition_budget():
    rng = np.random.default_rng(7)
    n = 20
    sets = _random_model(rng, n)
    opts = {"exact_max_cc": 20, "exact_max_transitions_per_component": 500}
    dense = cn.solve_abstract(n, sets, 5, 2, dict(opts, reduction_impl="legacy"))
    sparse = cn.solve_abstract(n, sets, 5, 2, dict(opts, reduction_impl="fast"))
    assert (dense["dp_outcome"], dense["dp_transitions"]) == (sparse["dp_outcome"], sparse["dp_transitions"])


def test_cape_fast_profile_equals_cape_m0_when_depth_regimes_do_not_apply():
    """cape_fast differs from cape_m0 only by depth_policy; for Z <= 256 there is one regime."""
    zyx = syn.walking_cylinders((40, 48, 48), dtype=np.uint32, seed=21)
    a, _ = _enc(zyx, {"format_policy": "same_as_stock"})
    b, _ = _enc(zyx, {"format_policy": "same_as_stock", "depth_policy": "fixed_depth_width"})
    assert a == b
