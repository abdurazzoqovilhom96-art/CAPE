"""Native CAPE core vs the pure-Python reference model (spec sections 5-13, 29).

The native greedy, dual bound, DP and serializer must reproduce the reference exactly; with
exact refinement on small volumes the payload must equal the reference optimum."""

from __future__ import annotations

import numpy as np
import pytest

from cape import _cape_native as cn
from cape import crackle_format as cf
from cape import reference_model as rm
from cape import synthetic as syn
from conftest import as_xyz
from test_dp_oracle import random_model

SMALL_VOLUMES = [
    ("blocky", syn.blocky((10, 16, 16), n_labels=6, block=(2, 4, 4), seed=1)),
    ("voronoi", syn.dense_drifting_voronoi((10, 20, 20), n_seeds=12, seed=2)),
    ("walking", syn.walking_cylinders((12, 20, 20), n=4, radius=(1, 3), seed=3)),
    ("branching", syn.branching((10, 20, 20), n=3, radius=2, seed=4)),
    ("cylinders", syn.vertical_cylinders((12, 20, 20), n=6, radius=(1, 3), seed=5)),
    ("disconnected", syn.disconnected_same_id((8, 16, 16), seed=6)),
]


def reference_plan(zyx: np.ndarray, exact: bool):
    """Reference of the native pipeline: costs from widths, reduce_all, components, greedy
    U/dual L, background = argmax(U, then L, then smallest label), exact refinement."""
    Z, Y, X = zyx.shape
    cc, _, n = rm.cc_label(zyx)
    w_I, w_C, w_D = cf.byte_width(zyx.size), cf.byte_width(n), 1
    models = rm.build_models(zyx, cc, rm.depth_windows(rm.column_runs(zyx), Z), w_I + w_D, w_C)
    labels = sorted(models)
    U, L, OPT, P, Q = {}, {}, {}, {}, {}
    for lab in labels:
        comps = rm.components(rm.reduce_all(models[lab], X, Y))
        U[lab] = L[lab] = OPT[lab] = P[lab] = Q[lab] = 0
        for c in comps:
            g, pins, singles = rm.greedy(c, X, Y)
            U[lab] += g
            L[lab] += rm.dual_ascent(c)[1]
            P[lab] += len(pins)
            Q[lab] += len(singles)
            if exact:
                OPT[lab] += rm.dp_lowest_bit(c)[0] if len(c.universe) <= 20 else g
    bg = labels[0]
    for lab in labels[1:]:
        if (U[lab], L[lab]) > (U[bg], L[bg]):
            bg = lab
    written = [lab for lab in labels if lab != bg]
    return {"bg": bg, "U": sum(U[k] for k in written), "L": sum(L[k] for k in written),
            "OPT": sum(OPT[k] for k in written), "P": sum(P[k] for k in written), "Q": sum(Q[k] for k in written)}


@pytest.mark.parametrize("name,zyx", SMALL_VOLUMES, ids=[n for n, _ in SMALL_VOLUMES])
def test_native_greedy_and_dual_match_reference(name, zyx):
    ref = reference_plan(zyx, exact=False)
    _, d = cn.encode(as_xyz(zyx), {"use_exact": False, "use_local": False, "format_policy": "force_pins"})
    assert d["background_label"] == ref["bg"]
    assert d["payload_ub_bytes"] == ref["U"]
    assert d["payload_lb_bytes_fixed_background"] == ref["L"]
    assert (d["P"], d["Q"]) == (ref["P"], ref["Q"])
    assert d["certificate_dual_feasible"] == 1


@pytest.mark.parametrize("name,zyx", SMALL_VOLUMES, ids=[n for n, _ in SMALL_VOLUMES])
def test_native_exact_matches_reference_optimum(name, zyx):
    ref = reference_plan(zyx, exact=True)
    _, d = cn.encode(as_xyz(zyx), {"use_local": False, "format_policy": "force_pins"})
    assert d["background_label"] == ref["bg"]
    if d["max_component_cc"] <= 20 and d["dp_components_skipped"] == 0 and d["dp_components_budget_exhausted"] == 0:
        assert d["payload_ub_bytes"] == ref["OPT"]
    assert d["payload_ub_bytes"] <= ref["U"]


@pytest.mark.parametrize("seed", range(60))
def test_solve_abstract_matches_reference(seed):
    m = random_model(seed)
    sets = [sorted(u - 100 for u in s) for _, s in m.pins]
    out = cn.solve_abstract(len(m.universe), sets, m.pin_cost, m.single_cost, {})
    # reference with the same tie keys (start index = set index, depth = |set| - 1)
    ref_model = rm.CoverModel(1, tuple(range(len(m.universe))),
                              [(rm.Pin(1, 0, k, 0, len(s)), frozenset(s)) for k, s in enumerate(sets)],
                              m.pin_cost, m.single_cost)
    g, gp, gs = rm.greedy(ref_model, X=1 << 20, Y=1)
    assert out["greedy_cost"] == g
    assert out["greedy_pins"] == sorted(p.x for p in gp)
    assert out["greedy_singles"] == sorted(gs)
    a, lb = rm.dual_ascent(ref_model)
    assert out["dual_lb"] == lb and out["dual_a"] == [a[u] for u in range(len(m.universe))]
    assert out["dual_feasible"]
    opt = rm.brute_force(ref_model)[0]
    assert out["dp_outcome"] == 0 and out["dp_cost"] == opt and out["dp_is_cover"]
    assert out["dp_transitions"] == rm.dp_lowest_bit(ref_model)[2]
    assert out["local_is_cover"] and opt <= out["local_cost"] <= g


def test_native_serializer_matches_reference_and_refuses_overflow():
    rng = np.random.default_rng(20261105)
    for _ in range(40):
        n_labels = int(rng.integers(0, 6))
        labels = sorted(int(v) for v in rng.choice(np.arange(1, 5000), size=n_labels, replace=False))
        recs, pins_l, ccs_l = [], [], []
        for lab in labels:
            pins = [(int(s), int(d)) for s, d in zip(rng.choice(10**6, size=int(rng.integers(0, 8)), replace=False),
                                                       rng.integers(0, 200, size=8))]
            ccs = sorted(int(c) for c in rng.choice(60000, size=int(rng.integers(0, 9)), replace=False))
            recs.append({"label": lab, "pins": pins, "singletons": ccs})
            pins_l.append(pins)
            ccs_l.append(ccs)
        widths = {"w_L": 2, "w_I": 4, "w_G": 2, "w_N": 1, "w_D": 1, "w_C": 2}
        comps = [int(v) for v in rng.integers(0, 3000, size=5)]
        native = cn.serialize_pins_section(9999, recs, comps, widths)
        ref = cf.serialize_pins_section(stored_width=2, bgcolor=9999, labels=labels, components_per_grid=comps,
                                        component_width=2, index_width=4, num_pins_width=1, depth_width=1,
                                        cc_label_width=2, pins=pins_l, cc_ids=ccs_l, strict=True)
        assert native == ref
        assert cn.predict_label_bytes(widths, len(labels), len(comps), sum(map(len, pins_l)),
                                      sum(map(len, ccs_l))) == len(native)
    with pytest.raises(cn.CapeError):
        cn.serialize_pins_section(0, [{"label": 1, "pins": [(0, 300)], "singletons": []}], [1],
                                  {"w_L": 1, "w_I": 4, "w_G": 1, "w_N": 1, "w_D": 1, "w_C": 1})


def test_unknown_option_is_rejected():
    with pytest.raises(ValueError):
        cn.encode(as_xyz(syn.blocky((4, 8, 8))), {"no_such_option": 1})
    with pytest.raises(ValueError):
        cn.encode(as_xyz(syn.blocky((4, 8, 8))), {"format_policy": "magic"})
