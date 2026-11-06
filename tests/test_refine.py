"""Archive-objective refinement and FAST/CERTIFIED modes (plan v2, user task 2a/2e).

Refinement must: decode exactly with the stock decoder, reproduce S0 before searching (self-check),
never be larger than SAFE-ARCHIVE with the same level and Markov order, be deterministic, and reduce
to SAFE-ARCHIVE exactly when the evaluation budget is zero."""

from __future__ import annotations

import crackle  # PyPI crackle-codec 0.53.0
import numpy as np
import pytest
import zstandard

from cape import _cape_native as cn
from cape import crackle_format as cf
from cape.adapters import make_adapter
from cape.adapters.safe_archive import SafeArchiveAdapter
from cape.adapters.safe_refine import SafeRefineAdapter
from cape.config import load_methods
from cape.refine import Records
from golden_cases import real_cases, synthetic_cases

METHODS = load_methods()
CASES = {**synthetic_cases(), **real_cases()}
NAMES = ["syn_dense_voronoi", "syn_branching", "walking_u64", "blocky_u16", "noise", "syn_count_width_adversarial",
         "depth257", "large_ids_u64"] + sorted(n for n in CASES if n.startswith(("cremi", "crackle")))


@pytest.mark.parametrize("level", ["zstd3", "zstd9"])
@pytest.mark.parametrize("markov", [0, 5])
@pytest.mark.parametrize("name", NAMES)
def test_refine_is_lossless_and_never_worse_than_safe(name, markov, level):
    zyx = CASES[name]
    opts = {"zstd": level, "markov_model_order": markov, "depth_policy": "fixed_depth_width", "certificate": "off"}
    safe = SafeArchiveAdapter("s", dict(opts))
    ref = SafeRefineAdapter("r", dict(opts, max_evals=12))
    a, b = safe.encode(zyx), ref.encode(zyx)
    assert len(b) <= len(a)
    d = ref.last_diagnostics
    if d.get("refine_J0") is not None:
        assert d["refine_J"] <= d["refine_J0"] and d["refine_evals"] <= 12
    inner = zstandard.ZstdDecompressor().decompress(b)
    out = crackle.decompress(inner)  # the stock decoder alone, no encoder state
    assert out.dtype == zyx.dtype and np.array_equal(out, np.ascontiguousarray(zyx).T)
    assert np.array_equal(ref.decode(b), zyx)


@pytest.mark.parametrize("name", ["syn_dense_voronoi", "crackle_ws_x0_y384_z320_128x128x64"])
def test_refine_is_deterministic_and_zero_budget_equals_safe(name):
    if name not in CASES:
        pytest.skip("local data file not present")
    zyx = CASES[name]
    opts = {"zstd": "zstd9", "depth_policy": "fixed_depth_width", "certificate": "off"}
    r1 = SafeRefineAdapter("r", dict(opts, max_evals=16)).encode(zyx)
    r2 = SafeRefineAdapter("r", dict(opts, max_evals=16)).encode(zyx)
    assert r1 == r2
    zero = SafeRefineAdapter("r", dict(opts, max_evals=0)).encode(zyx)
    assert zero == SafeArchiveAdapter("s", dict(opts)).encode(zyx)


def test_fast_serializer_equals_reference_serializer():
    rng = np.random.default_rng(5)
    for _ in range(30):
        K = int(rng.integers(1, 6))
        recs = []
        for k in range(K):
            pins = [(int(s), int(d)) for s, d in zip(rng.integers(0, 70000, rng.integers(0, 9)), rng.integers(0, 300, 9))]
            recs.append({"label": 10 + k, "pins": pins, "singletons": sorted(set(int(v) for v in rng.integers(0, 60000, rng.integers(0, 7))))})
        comps = [int(v) for v in rng.integers(0, 900, 5)]
        w = {"w_L": 2, "w_I": 3, "w_G": 2, "w_C": 2}
        r = Records(recs, 3, comps, w)
        got = r.serialize(r.pins, r.singles)
        P = max([len(x["pins"]) for x in recs] + [len(x["singletons"]) for x in recs] + [0])
        D = max([d for x in recs for _, d in x["pins"]] + [0])
        ref = cf.serialize_pins_section(
            stored_width=2, bgcolor=3, labels=[x["label"] for x in recs], components_per_grid=comps,
            component_width=2, index_width=3, num_pins_width=cf.byte_width(P), depth_width=cf.byte_width(D),
            cc_label_width=2, pins=[x["pins"] for x in recs], cc_ids=[x["singletons"] for x in recs])
        assert got == ref


def test_refine_methods_are_registered_with_frozen_budgets():
    for e in (8, 24, 64):
        for m in (0, 5):
            for z in (3, 9):
                ad = make_adapter(f"safe_refine_e{e}_m{m}_zstd{z}", METHODS[f"safe_refine_e{e}_m{m}_zstd{z}"])
                assert ad.cfg.max_evals == e and ad.level == z


@pytest.mark.parametrize("name", ["depth257", "depth258", "walking_u64", "cremi_A_x0_y768_z0_128x128x64"])
def test_certified_stream_equals_fast_stream_and_bounds_it(name):
    if name not in CASES:
        pytest.skip("local data file not present")
    x = np.ascontiguousarray(CASES[name]).T
    base = {"format_policy": "force_pins", "depth_policy": "fixed_depth_width"}
    fast, df = cn.encode(x, dict(base, certificate="off"))
    cert, dc = cn.encode(x, dict(base, certificate="all_regimes"))
    assert fast == cert
    assert "lb_bytes" not in df and "certificate_scope" not in df
    assert dc["lb_bytes"] <= dc["ub_bytes"] == len(cert)
    assert dc["certificate_dual_feasible"] == 1
    full, dfull = cn.encode(x, {"format_policy": "force_pins"})
    assert dc["lb_bytes"] <= len(full)  # the LB also bounds the full depth-regime search
