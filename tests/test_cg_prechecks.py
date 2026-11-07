"""B protocol prechecks (docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md, section 9).

T1 candidate coverage: exact set-cover optimum over EVERY interval (length <= h) of every run equals the optimum over
   the CompleteWindows family (and over the LP-reduced instance).
T2 pricing: prefix / sliding-window pricing equals brute-force enumeration (exact integers, deterministic ties).
T3 certificate: L <= OPT <= U with an exact solver; integer feasibility re-checked independently; deliberately
   infeasible float duals are repaired or rejected, never accepted as a certificate.
T4 (synthetic part): the prototype instance built from the native encoder's own CC ids and records reproduces the
   native counts, the Eθ selection (pins + singletons cover every non-background CC) and its payload cost.
Edge cases everywhere: R in {1, h-1, h, h+1, 2h, 3h}, h in {1, 2, 3, 4, 8}, zero weights, ties, large integers."""
import json
from pathlib import Path

import numpy as np
import pytest

from cape.cg import (Q_SCALE, all_intervals, all_windows, best_window, build_instance, cc2d_python,
                     column_generation, enumerate_windows, exact_opt, int_feasible, integer_certificate,
                     max_any_interval, price_runs)

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261107
HS = (1, 2, 3, 4, 8)
COSTS = ((3, 1), (4, 1), (5, 2), (3, 2), (7, 2), (9, 4))


def _id(v):
    return v if isinstance(v, str) else (str(v) if isinstance(v, (int, type(None))) else "vol")


def edge_lengths(h):
    return sorted({x for x in (1, h - 1, h, h + 1, 2 * h, 3 * h) if x >= 1})


# --------------------------------------------------------------------------------------------- volume makers
def column_stack(lengths, X=2, Y=1, twin=True):
    """Columns whose runs have the given lengths (alternating labels); a twin column shares CCs (X=2)."""
    Z = int(sum(lengths))
    col = np.concatenate([np.full(n, 1 + (i % 2), dtype=np.uint16) for i, n in enumerate(lengths)])
    vol = np.zeros((Z, Y, X), dtype=np.uint16)
    vol[:, :, 0] = col[:, None]
    vol[:, :, 1:] = col[:, None, None] if twin else (3 - col)[:, None, None] + 2
    return vol


def random_volume(rng, Zr=(3, 10), Yr=(1, 3), Xr=(1, 3), nl=3):
    Z, Y, X = (int(rng.integers(a, b + 1)) for a, b in (Zr, Yr, Xr))
    base = rng.integers(1, nl + 1, size=(1, Y, X))
    vol = np.repeat(base, Z, axis=0).astype(np.uint16)
    flips = rng.random((Z, Y, X)) < 0.25  # runs of random length
    vol[flips] = rng.integers(1, nl + 1, size=int(flips.sum()))
    return vol


def real_subcrops():
    man = ROOT / "data" / "manifests" / "v3_dev_core.jsonl"
    if not man.exists():
        return []
    rows = [json.loads(x) for x in man.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = []
    for r in rows[:3]:
        p = ROOT / r["path"]
        if not p.exists():
            continue
        a = np.load(p, mmap_mode="r")
        for (z, y, x) in ((0, 0, 0), (20, 37, 81)):
            sub = np.ascontiguousarray(a[z:z + 12, y:y + 4, x:x + 4])
            # remap to small ids (labels only matter by equality)
            _, inv = np.unique(sub, return_inverse=True)
            out.append((r["sample_id"], (inv.reshape(sub.shape) + 1).astype(np.uint16)))
    return out


# -------------------------------------------------------------------------------------- raw model (no filter)
def raw_model(vol, h, background=None):
    """Rows = every non-background CC; families over EVERY non-background run (no usefulness filter)."""
    cc = cc2d_python(vol)
    Z, Y, X = vol.shape
    lab = np.ascontiguousarray(vol.transpose(1, 2, 0)).ravel()
    ccf = np.ascontiguousarray(cc.transpose(1, 2, 0)).ravel()
    V = lab.size
    brk = np.ones(V, dtype=bool)
    zp = np.arange(V) % Z
    brk[1:] = (lab[1:] != lab[:-1]) | (zp[1:] == 0)
    st = np.flatnonzero(brk)
    ln = np.diff(np.append(st, V))
    n_cc = int(cc.max()) + 1
    cc_lab = np.zeros(n_cc, dtype=lab.dtype)
    cc_lab[ccf] = lab
    keep = np.flatnonzero(cc_lab != background) if background is not None else np.arange(n_cc)
    row = {int(u): i for i, u in enumerate(keep)}
    fam_all, fam_cw = set(), set()
    for g, R in zip(st, ln):
        if background is not None and lab[g] == background:
            continue
        rows = [row[int(u)] for u in ccf[g:g + R]]
        for i in range(R):
            for L in range(1, min(h, R - i) + 1):
                fam_all.add(tuple(sorted(rows[i:i + L])))
        for t in ([0] if R <= h else range(R - h + 1)):
            fam_cw.add(tuple(sorted(rows[t:t + min(R, h)])))
    return len(keep), [np.array(x) for x in sorted(fam_all)], [np.array(x) for x in sorted(fam_cw)], cc


# ======================================================================================================= T1
def _t1_cases():
    rng = np.random.default_rng(SEED)
    cases = []
    for h in HS:
        for c, s in COSTS[:4]:
            cases.append((f"edge_h{h}_c{c}_s{s}", column_stack(edge_lengths(h)), h, c, s, None))
            cases.append((f"edge_nontwin_h{h}_c{c}_s{s}", column_stack(edge_lengths(h), twin=False), h, c, s, 1))
    for k in range(60):
        h = int(rng.choice(HS))
        c, s = COSTS[int(rng.integers(len(COSTS)))]
        bg = None if k % 3 else 1
        cases.append((f"random_{k}", random_volume(rng), h, c, s, bg))
    for sid, sub in real_subcrops():
        for h, (c, s) in ((3, (5, 2)), (6, (4, 1)), (12, (9, 4))):
            cases.append((f"real_{sid}_h{h}", sub, h, c, s, None))
    return cases


@pytest.mark.parametrize("name,vol,h,c,s,bg", _t1_cases(), ids=_id)
def test_T1_complete_windows_cover_every_interval(name, vol, h, c, s, bg):
    n, fam_all, fam_cw, cc = raw_model(vol, h, bg)
    opt_all = exact_opt(n, fam_all, c, s)
    opt_cw = exact_opt(n, fam_cw, c, s)
    assert opt_all == opt_cw, (name, opt_all, opt_cw)
    inst = build_instance(vol, cc, bg, h, c, s)  # LP-reduced instance (usefulness filter) must agree too
    opt_inst = exact_opt(inst["n_lp"], all_windows(inst), c, s, inst["n_fixed_single"])
    assert opt_inst == opt_cw, (name, opt_inst, opt_cw)
    opt_inst_all = exact_opt(inst["n_lp"], all_intervals(inst), c, s, inst["n_fixed_single"])
    assert opt_inst_all == opt_cw


# ======================================================================================================= T2
def _t2_arrays():
    rng = np.random.default_rng(SEED + 2)
    out = []
    for h in HS:
        for R in sorted(set(edge_lengths(h)) | {1, 2, 3 * h + 1}):
            out.append((h, np.zeros(R, dtype=np.int64)))                       # zero weights
            out.append((h, np.full(R, 7, dtype=np.int64)))                     # all ties
            out.append((h, rng.integers(0, 5, R).astype(np.int64)))           # many ties
            out.append((h, rng.integers(0, 1 << 40, R).astype(np.int64)))     # large integers
            out.append((h, rng.integers(0, Q_SCALE * 8, R).astype(np.int64)))  # certificate range
            out.append((h, rng.random(R)))                                     # floats
    return out


@pytest.mark.parametrize("h,a", _t2_arrays())
def test_T2_pricing_equals_enumeration(h, a):
    W, t, L = best_window(a, h)
    enum = enumerate_windows(a, h)
    best = max(e[0] for e in enum)
    assert L == min(len(a), h)
    if a.dtype.kind == "f":  # floats: prefix differences vs direct sums differ in the last bits
        assert abs(W - best) <= 1e-9 * max(1.0, abs(best))
        assert abs(sum(a[t:t + L]) - best) <= 1e-9 * max(1.0, abs(best))
        return
    first = min(e[1] for e in enum if e[0] == best)
    assert W == best and t == first
    if a.dtype.kind == "i":
        assert int(W) == max_any_interval([int(v) for v in a], h)  # nonnegative weights: windows dominate intervals


def test_T2_vectorized_pricing_matches_per_run():
    rng = np.random.default_rng(SEED + 3)
    for h in HS:
        lens = np.array(edge_lengths(h) * 3 + list(rng.integers(1, 4 * h + 2, 40)), dtype=np.int64)
        starts = np.concatenate(([0], np.cumsum(lens)[:-1]))
        for w in (rng.integers(0, 1 << 30, int(lens.sum())).astype(np.int64), rng.integers(0, 3, int(lens.sum())),
                  rng.random(int(lens.sum()))):
            w = np.asarray(w)
            if w.dtype.kind == "i":
                w = w.astype(np.int64)
            Wv, Tv = price_runs(w, starts, lens, h)
            for i, (g, R) in enumerate(zip(starts, lens)):
                W, t, _ = best_window(w[g:g + R], h)
                if w.dtype.kind == "f":
                    assert abs(Wv[i] - W) <= 1e-9 * max(1.0, abs(W))
                else:
                    assert Wv[i] == W and Tv[i] == t


def test_T2_overflow_guard():
    with pytest.raises(OverflowError):
        best_window(np.full(4, 1 << 61, dtype=np.int64), 2)


# ======================================================================================================= T3
def _t3_cases():
    rng = np.random.default_rng(SEED + 4)
    cases = []
    for k in range(40):
        h = int(rng.choice(HS))
        c, s = COSTS[int(rng.integers(len(COSTS)))]
        cases.append((f"rand{k}", random_volume(rng, Zr=(4, 12), Yr=(2, 4), Xr=(2, 4)), h, c, s, None if k % 2 else 1))
    for h in (2, 3, 4):
        cases.append((f"edge{h}", column_stack(edge_lengths(h)), h, 5, 2, None))
    return cases


@pytest.mark.parametrize("name,vol,h,c,s,bg", _t3_cases(), ids=_id)
def test_T3_certificate_brackets_the_optimum(name, vol, h, c, s, bg):
    inst = build_instance(vol, cc2d_python(vol), bg, h, c, s)
    opt = exact_opt(inst["n_lp"], all_windows(inst), c, s, inst["n_fixed_single"])
    cg = column_generation(inst, budget_s=60, max_iter=40)
    U = cg["integer"]["U"]
    cert = integer_certificate(inst, cg["lam"])
    assert cert["feasible"], name
    ok, nv = int_feasible(inst, cert["a"])
    assert ok and nv == 0
    assert cert["L"] <= opt <= U, (name, cert["L"], opt, U)
    if cg["converged"] and cg["lam"] is not None:  # LP duality: dual sum <= OPT_LP <= OPT
        assert float(cg["lam"].sum()) + s * inst["n_fixed_single"] <= opt + 1e-6


@pytest.mark.parametrize("name,vol,h,c,s,bg", _t3_cases()[:20], ids=_id)
def test_T3_infeasible_float_duals_are_repaired_never_accepted(name, vol, h, c, s, bg):
    inst = build_instance(vol, cc2d_python(vol), bg, h, c, s)
    if inst["n_lp"] == 0:
        pytest.skip("no LP rows")
    opt = exact_opt(inst["n_lp"], all_windows(inst), c, s, inst["n_fixed_single"])
    bad = np.full(inst["n_lp"], float(s))  # every lambda at its upper bound: violates every useful window
    raw = np.clip(np.floor(bad * Q_SCALE), 0, Q_SCALE * s).astype(np.int64)
    ok_raw, nv_raw = int_feasible(inst, raw)
    assert not ok_raw and nv_raw > 0  # the checker detects the violation
    cert = integer_certificate(inst, bad)
    assert cert["feasible"] and cert["L"] <= opt
    for q in (1 << 10, 1 << 30):  # other scales, incl. large integers
        cq = integer_certificate(inst, bad, q=q)
        assert cq["feasible"] and cq["L"] <= opt


def test_T3_checker_rejects_out_of_range():
    vol = column_stack([3, 5, 2])
    inst = build_instance(vol, cc2d_python(vol), None, 3, 4, 2)
    a = np.zeros(inst["n_lp"], dtype=np.int64)
    a[0] = Q_SCALE * 2 + 1  # above q*s
    assert int_feasible(inst, a) == (False, -1)
    a[0] = -1
    assert int_feasible(inst, a) == (False, -1)


# ================================================================================================ T4 (synthetic)
def _native():
    try:
        from cape import _cape_native
    except ImportError:
        pytest.skip("native module not built")
    return _cape_native


EQ_OPTS = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
           "depth_policy": "fixed_depth_width", "certificate": "off", "impl_mask": 6719, "parallel": 1}


def native_instance(vol):
    from cape.canonical import crackle_view
    cn = _native()
    # force_pins: small random volumes often fall under the stock FLAT rule; T4 checks the instance/selection
    # agreement, which does not depend on the format policy (the dev crops use the exact Eθ options)
    _, diag = cn.encode(crackle_view(vol), dict(EQ_OPTS, format_policy="force_pins", return_cc=True,
                                                collect_records=True))
    assert str(diag.get("label_format", "")).startswith("PINS"), diag.get("label_format")
    c = int(diag["w_I"]) + int(diag["regime_w_D"])
    s = int(diag["w_C"])
    inst = build_instance(vol, np.asarray(diag["cc_volume"]), diag["bgcolor"], int(diag["regime_h"]), c, s)
    return diag, inst


def check_native_selection(vol, diag, inst):
    """Eθ records are valid windows of useful runs, cover every non-background CC, and cost payload_ub_bytes."""
    Z, Y, X = vol.shape
    XY = X * Y
    cc = np.ascontiguousarray(np.asarray(diag["cc_volume"]).transpose(1, 2, 0)).ravel()
    lab = np.ascontiguousarray(vol.transpose(1, 2, 0)).ravel()
    covered = np.zeros(inst["n_cc"], dtype=bool)
    P = Qn = 0
    for rec in diag["records"]:
        for start, depth in rec["pins"]:
            col, z0, L = int(start) % XY, int(start) // XY, int(depth) + 1
            g = col * Z + z0
            seg = lab[g:g + L]
            assert z0 + L <= Z and (seg == rec["label"]).all(), "pin leaves its run"
            assert L <= inst["h"]
            covered[cc[g:g + L]] = True
            P += 1
        for u in rec["singletons"]:
            covered[int(u)] = True
            Qn += 1
    nonbg = inst["cc_label"] != diag["bgcolor"]
    assert covered[nonbg].all(), "Eθ selection leaves a non-background CC uncovered"
    assert P == int(diag["P"]) and Qn == int(diag["Q"])
    assert P * inst["c"] + Qn * inst["s"] == int(diag["payload_ub_bytes"])
    return P, Qn


@pytest.mark.parametrize("seed", range(12))
def test_T4_native_instance_and_selection_agree(seed):
    rng = np.random.default_rng(SEED + 100 + seed)
    vol = random_volume(rng, Zr=(6, 24), Yr=(3, 12), Xr=(3, 12), nl=5)
    if seed % 3 == 0:
        vol = vol.astype(np.uint64) * np.uint64(1 << 40)
    diag, inst = native_instance(vol)
    assert inst["n_cc"] == int(diag["cc_count"])
    assert inst["n_runs"] == int(diag["run_count"])
    check_native_selection(vol, diag, inst)
    opt = exact_opt(inst["n_lp"], all_windows(inst), inst["c"], inst["s"], inst["n_fixed_single"])
    assert int(diag["payload_lb_bytes_fixed_background"]) <= opt <= int(diag["payload_ub_bytes"])
