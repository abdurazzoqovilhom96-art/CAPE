"""v2.1 speed-up attribution: every implementation switch combination must write the identical bitstream.

The five v1 -> v2 implementation changes (L layout, R one-pass runs, H hash function, T hash-table
grouping, S reachable-state DP) are measured one by one in scripts/speedup_attribution.py; that is only
valid if no combination changes a byte. Depth regimes (D) may change bytes and are compared per D value.
"""

from __future__ import annotations

import pytest

from golden_cases import digest, real_cases, synthetic_cases

cn = pytest.importorskip("cape._cape_native")

SYN = synthetic_cases()
REAL = real_cases()
CASES = {**SYN, **REAL}
BASE = {"markov_model_order": 0, "format_policy": "force_pins", "selector": "cape", "certificate": "off"}


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("depth", ["fixed_depth_width", "full_width_first"])
def test_every_impl_mask_is_byte_identical(name, depth):
    zyx = CASES[name]
    ref = digest(zyx, dict(BASE, depth_policy=depth, impl_mask=31))
    legacy = digest(zyx, dict(BASE, depth_policy=depth, reduction_impl="legacy"))
    assert legacy == ref, f"{name}: legacy preset differs from the fast preset"
    for mask in range(32):
        got = digest(zyx, dict(BASE, depth_policy=depth, impl_mask=mask))
        assert got == ref, f"{name}/{depth}: impl_mask={mask} changed the bitstream"


def test_impl_mask_is_reported_and_validated():
    zyx = next(iter(SYN.values()))
    from cape.canonical import crackle_view

    _, diag = cn.encode(crackle_view(zyx), dict(BASE, depth_policy="fixed_depth_width", impl_mask=5))
    assert diag["impl_mask"] == 5 and diag["reduction_impl"] == "mixed"
    _, diag = cn.encode(crackle_view(zyx), dict(BASE, depth_policy="fixed_depth_width"))
    assert diag["impl_mask"] == 31 and diag["reduction_impl"] == "fast"
    # v3 extended the switch set to ten bits (types.hpp kImplMaxMask = 1023); 32..1023 are the v3 bits
    with pytest.raises(ValueError):
        cn.encode(crackle_view(zyx), dict(BASE, impl_mask=1024))
