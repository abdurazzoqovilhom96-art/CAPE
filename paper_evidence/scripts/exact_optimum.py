"""Exact optimum of the serialized label section for whole test volumes (revision 2026-11-09; no timing).

For every volume the evaluated CAPE configuration is re-run with component export enabled (the written stream is
checked against the SHA-256 of the frozen run). Every exported (non-trivial) component of every label is solved
exactly with CP-SAT on its payload objective; components without candidates are exact by definition (records only),
and their CC count per label comes from the CC labelling returned by the encoder. Components do not depend on the
background, so the components of CAPE's background label are taken from a second run with the other background rule.

    OPT_l   = sum of exact component optima of label l          (payload, regime w_D = 1 because Z <= 256)
    OPT     = min_b [ H(w_N) + sum_{l != b} OPT_l ]  with  b* = argmax_l OPT_l
    H(w)    = w_L + 9 + Z w_G + (K - 1)(w_L + 2 w)

The count width of the assembled optimal selection decides H: if it is 1 byte, OPT is exact; otherwise OPT lies in
[H(1) + payload*, H(w_N*) + payload*] (an interval of 2(K-1)(w_N*-1) bytes). Reductions preserve the payload optimum and
Theorem 1 makes complete windows sufficient, so the component optima are optima over all run intervals.
If w_N* = 2, the interval is resolved by comparing w_N = 2 (component optima) with w_N = 1: every label whose optimal
counts exceed 255 is re-solved jointly with both counts capped at 255, on candidates built from the volume (all maximal
runs of the label, no singleton dominance, which does not preserve optima under a count cap).

    python scripts/exact_optimum.py j0126 [snemi] [hemibrain]     # writes evidence/exact_optimum.json, figure_data
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

MS = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["CAPE_REPO"]) if os.environ.get("CAPE_REPO") else next(
    q for q in Path(__file__).resolve().parents if (q / "cape").is_dir() and (q / "maqola uchun").is_dir())
sys.path.insert(0, str(ROOT))

from ortools.sat.python import cp_model  # noqa: E402

from cape import _cape_native as cn  # noqa: E402
from cape import reference_model as rm  # noqa: E402
from cape.canonical import crackle_view  # noqa: E402

MANIFEST = {"j0126": "data/manifests/q1_external_j0126.jsonl", "snemi": "data/manifests/confirm_snemi3d.jsonl",
            "hemibrain": "data/manifests/q1_external_hemibrain.jsonl"}
EVALUATED = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
             "depth_policy": "fixed_depth_width", "certificate": "all_regimes", "impl_mask": 6719, "parallel": 1}
EXPORT = {"export_components_max_cc": 2**31 - 1, "export_components_limit": 2**62, "collect_records": True,
          "return_cc": True}
TIME_LIMIT = 120.0


def byte_width(v: int) -> int:
    return 1 if v < 2**8 else 2 if v < 2**16 else 4 if v < 2**32 else 8


def solve(n: int, sets: list, c: int, s: int) -> dict:
    m = cp_model.CpModel()
    xs = [m.NewBoolVar("") for _ in sets]
    ys = [m.NewBoolVar("") for _ in range(n)]
    inc = [[] for _ in range(n)]
    for i, st in enumerate(sets):
        for u in st:
            inc[u].append(xs[i])
    for u in range(n):
        m.AddBoolOr(inc[u] + [ys[u]])
    m.Minimize(c * sum(xs) + s * sum(ys))
    sv = cp_model.CpSolver()
    sv.parameters.num_workers = 8
    sv.parameters.random_seed = 20261109
    sv.parameters.max_time_in_seconds = TIME_LIMIT
    st = sv.Solve(m)
    ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return {"status": sv.StatusName(st), "obj": int(round(sv.ObjectiveValue())) if ok else None,
            "bound": int(round(sv.BestObjectiveBound())) if ok else None,
            "P": sum(sv.Value(x) for x in xs) if ok else None, "Q": sum(sv.Value(y) for y in ys) if ok else None}


def capped_label_optimum(comps: list, t: int, s: int, cap: int = 255) -> dict:
    """Minimum payload of one label when its pin count and its record count must both fit a 1-byte count field
    (<= 255). t CCs have no candidate and need a record each. Joint model over all components of the label."""
    if t > cap:
        return {"status": "INFEASIBLE_TRIVIAL", "obj": None, "bound": None}
    m = cp_model.CpModel()
    pins, singles, obj = [], [], []
    for c in comps:
        xs = [m.NewBoolVar("") for _ in c["sets"]]
        ys = [m.NewBoolVar("") for _ in range(c["n"])]
        inc = [[] for _ in range(c["n"])]
        for i, st in enumerate(c["sets"]):
            for u in st:
                inc[u].append(xs[i])
        for u in range(c["n"]):
            m.AddBoolOr(inc[u] + [ys[u]])
        pins += xs
        singles += ys
        obj += [c["pin_cost"] * x for x in xs] + [c["single_cost"] * y for y in ys]
    m.Add(sum(pins) <= cap)
    m.Add(sum(singles) + t <= cap)
    m.Minimize(sum(obj) + s * t)
    sv = cp_model.CpSolver()
    sv.parameters.num_workers = 8
    sv.parameters.random_seed = 20261109
    sv.parameters.max_time_in_seconds = TIME_LIMIT
    st = sv.Solve(m)
    ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return {"status": sv.StatusName(st), "obj": int(round(sv.ObjectiveValue())) if ok else None,
            "bound": int(round(sv.BestObjectiveBound())) if ok else None}


def capped_label_all_intervals(zyx: np.ndarray, cc: np.ndarray, label_value, c: int, s: int, cap: int = 255) -> dict:
    """Minimum payload of one label under a 1-byte count field (pins <= cap and records <= cap), with candidates built
    here from the volume, independently of CAPE's reductions: every maximal z-run of the label in every (y, x) column
    (Z <= 256, so these are the complete windows; by Corollary 2 they suffice also under count limits, because mapping
    a pin to its window never increases a count). Only pins with identical coverage are merged. Singleton dominance
    is NOT applied: under a count cap a dominated pin can pay off by saving records (Section 3.4)."""
    Z = zyx.shape[0]
    cols = zyx.reshape(Z, -1).T
    change = np.ones(cols.shape, dtype=bool)
    change[:, 1:] = cols[:, 1:] != cols[:, :-1]
    rid = (np.cumsum(change.ravel()) - 1).reshape(cols.shape)
    ccc = cc.reshape(Z, -1).T
    m = cols == label_value
    df = pd.DataFrame({"run": rid[m], "cc": ccc[m].astype(np.int64)}).drop_duplicates()
    uniq = np.unique(df.cc.values)
    df["u"] = np.searchsorted(uniq, df.cc.values)
    sets = sorted(set(df.sort_values("u").groupby("run").u.apply(tuple)))
    n = len(uniq)
    r = capped_label_optimum([{"n": n, "sets": [list(t) for t in sets], "pin_cost": c, "single_cost": s}], 0, s, cap)
    r.update({"n_cc": int(n), "n_candidates": len(sets)})
    return r


def label_dual_bound(zyx: np.ndarray, cc: np.ndarray, label_value, c: int, s: int) -> int:
    """Valid lower bound on the payload optimum of one label without its candidate list: a pin covers one CC per slice
    of its run, so lambda_u = min(s, c / (longest run of the label through CC u)) is dual feasible for every run
    interval (sum over a pin of length lam <= lam * c / lam = c) and for records (lambda_u <= s)."""
    Z = zyx.shape[0]
    cols = zyx.reshape(Z, -1).T
    change = np.ones(cols.shape, dtype=bool)
    change[:, 1:] = cols[:, 1:] != cols[:, :-1]
    rid = np.cumsum(change.ravel()) - 1
    runlen = np.bincount(rid)[rid].reshape(cols.shape).T.reshape(zyx.shape)
    mask = zyx == label_value
    ids = cc[mask].astype(np.int64)
    maxcov = np.zeros(int(cc.max()) + 1, dtype=np.int64)
    np.maximum.at(maxcov, ids, runlen[mask])
    u = np.unique(ids)
    lam = np.minimum(float(s), c / maxcov[u].astype(float))
    return int(np.ceil(lam.sum() - 1e-9))


def evaluated_sha(ds: str) -> dict:
    d = pd.read_csv(ROOT / "maqola uchun" / "raw_results" / f"{ds}_results.csv", low_memory=False)
    d = d[(d.status == "OK") & (d.wrapper.fillna("none") == "none") & (d.method_id == "cape_q1_fast_m0")]
    return d.groupby("sample_id").bitstream_sha256.first().to_dict()


def one_volume(row: dict, sha_ref: str) -> dict:
    t0 = time.time()
    zyx = np.load(ROOT / row["path"])
    xyz = crackle_view(zyx)
    buf_a, da = cn.encode(xyz, {**EVALUATED, **EXPORT})
    same = hashlib.sha256(buf_a).hexdigest() == sha_ref
    labels = np.unique(zyx)
    K = len(labels)
    cc = da.get("cc_volume")
    if cc is None:
        cc, _, _ = rm.cc_label(zyx)
    cc = np.asarray(cc)
    dense = np.searchsorted(labels, zyx.ravel())
    lab_of_cc = np.zeros(int(cc.max()) + 1, dtype=np.int64)
    lab_of_cc[cc.ravel()] = dense
    N = np.bincount(lab_of_cc, minlength=K)
    bg_a = int(np.searchsorted(labels, da["bgcolor"]))
    comps = {}
    for c in da["components_export"]:
        comps.setdefault(c["label_index"], []).append(c)
    buf_b, db = cn.encode(xyz, {**EVALUATED, **EXPORT, "background_policy": "stock"})
    bg_b = int(np.searchsorted(labels, db["bgcolor"]))
    bg_comps_from_b = bg_b != bg_a
    if bg_comps_from_b:
        comps[bg_a] = [c for c in db["components_export"] if c["label_index"] == bg_a]
    c_pin = int(da["w_I"]) + 1
    s = int(da["w_C"])
    opt_l, lb_l, P_l, Q_l, n_exported, statuses, ub_written = {}, {}, {}, {}, 0, {}, 0
    heur_excess = 0
    for lab in range(K):
        if lab == bg_a and not bg_comps_from_b:
            continue
        o = lb = p = q = 0
        ncc = 0
        for c in comps.get(lab, []):
            r = solve(c["n"], c["sets"], c["pin_cost"], c["single_cost"])
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
            assert r["obj"] is not None, r
            assert r["bound"] <= c["ub"] and r["bound"] >= c["lb"], (c["ub"], c["lb"], r)
            o += r["obj"]
            lb += r["bound"]
            p += r["P"]
            q += r["Q"]
            ncc += c["n"]
            n_exported += 1
            if lab != bg_a:
                ub_written += c["ub"]
                heur_excess += c["ub"] - r["obj"]
        t = int(N[lab]) - ncc  # CCs in components without candidates: one explicit record each
        assert t >= 0, (lab, N[lab], ncc)
        opt_l[lab], lb_l[lab], P_l[lab], Q_l[lab] = o + s * t, lb + s * t, p, q + t
        if lab != bg_a:
            ub_written += s * t
    assert ub_written == da["payload_ub_bytes"], (ub_written, da["payload_ub_bytes"])  # trivial-CC accounting
    known = list(opt_l)
    lb_bg = None
    if bg_comps_from_b:
        b_star = max(known, key=lambda k: (opt_l[k], k == bg_a))
        payload = sum(opt_l[k] for k in known if k != b_star)
        payload_lb = sum(lb_l[k] for k in known) - max(lb_l[k] for k in known)
        bg_proven = True
    else:
        # CAPE's background b: feasible with payload A = sum_{l != b} OPT_l. Lower side over all backgrounds:
        # min(A, A + OPT_b - max_{l != b} OPT_l) >= min(A, A + LB_b - M), with LB_b a valid dual bound for label b.
        b_star = bg_a
        A_lb = sum(lb_l.values())
        M_lb = max(opt_l.values()) if opt_l else 0
        lb_bg = label_dual_bound(zyx, cc, labels[bg_a], c_pin, s)
        payload = sum(opt_l.values())
        payload_lb = min(A_lb, A_lb + lb_bg - M_lb)
        bg_proven = lb_bg >= M_lb
    wN_star = byte_width(max(max(P_l[k], Q_l[k]) for k in known if k != b_star))
    Z = zyx.shape[0]
    wL, wG = int(da["w_L"]), int(da["w_G"])

    def H(w):
        return wL + 9 + Z * wG + (K - 1) * (wL + 2 * w)

    U, L = int(da["label_bytes"]), int(da["label_lb_bytes"])
    assert U == H(int(da["w_N"])) + int(da["payload_ub_bytes"]), "byte model check"
    opt_hi = min(U, H(wN_star) + payload)
    opt_lo = H(1) + payload_lb if payload_lb is not None else None
    cap_info = None
    if wN_star == 2 and not bg_comps_from_b and opt_lo is not None and opt_lo < opt_hi:
        # Resolve the count width. OPT = min over w_N of H(w_N) + min_b sum_{l != b} X_l(w_N); min_b (sum - max) is
        # nondecreasing in every X_l, so plugging lower bounds gives a valid lower side (background label: lb_bg).
        def lower(lbx: dict) -> int:
            return sum(lbx.values()) + lb_bg - max(lb_bg, max(lbx.values()))
        offending = [k for k in known if max(P_l[k], Q_l[k]) > 255]
        lbx, ubx, cap_status, feasible, reduced_obj, cap_sizes = dict(lb_l), dict(opt_l), [], True, [], []
        for k in offending:
            t = int(N[k]) - sum(c["n"] for c in comps.get(k, []))
            r_red = capped_label_optimum(comps.get(k, []), t, s)  # on CAPE's reduced candidates: upper side only
            reduced_obj.append(r_red["obj"])
            r = capped_label_all_intervals(zyx, cc, labels[k], c_pin, s)  # all run intervals: exact
            cap_sizes.append({"n_cc": r["n_cc"], "n_candidates": r["n_candidates"]})
            cap_status.append(r["status"])
            if r["obj"] is None:
                feasible = False
                break
            assert r_red["obj"] is None or r["obj"] <= r_red["obj"], (r, r_red)
            lbx[k], ubx[k] = r["bound"], r["obj"]
        lo2, hi2 = H(2) + lower(lb_l), H(2) + sum(opt_l.values())
        if feasible:
            lo1, hi1 = H(1) + lower(lbx), H(1) + sum(ubx.values())
            opt_lo, opt_hi = min(lo2, lo1), min(U, hi2, hi1)
        elif cap_status and cap_status[-1] == "INFEASIBLE":
            opt_lo, opt_hi = lo2, min(U, hi2)  # a 1-byte count width is impossible
        cap_info = {"offending_labels": len(offending), "status": cap_status, "one_byte_feasible": feasible,
                    "capped_model_sizes": cap_sizes, "capped_obj_on_reduced_candidates": reduced_obj,
                    "two_byte_lo": lo2, "two_byte_hi": hi2,
                    "one_byte_lo": lo1 if feasible else None, "one_byte_hi": hi1 if feasible else None,
                    # 1-byte count width strictly optimal: its best selection beats every 2-byte selection
                    "one_byte_optimal": bool(feasible and hi1 < lo2)}
    if opt_lo is not None:
        assert L <= opt_lo <= opt_hi <= U, (L, opt_lo, opt_hi, U)
    return {"sample_id": row["sample_id"], "voxels": int(zyx.size), "K": K, "same_stream_as_evaluated": same,
            "U": U, "L": L, "OPT_lo": opt_lo, "OPT_hi": opt_hi, "exact": opt_lo == opt_hi,
            "w_N_cape": int(da["w_N"]), "w_N_opt": 1 if cap_info and cap_info["one_byte_optimal"] else wN_star,
            "w_N_payload_optimal_selection": wN_star, "bg_cape": bg_a, "bg_opt": b_star,
            "bg_components_from_second_run": bg_comps_from_b, "bg_label_dual_bound": lb_bg,
            "bg_optimal_proven": bg_proven, "count_width_resolution": cap_info, "components_solved": n_exported,
            "solver_status": statuses, "heuristic_excess_bytes": heur_excess,
            "excess_hi_pct": 100 * (U - opt_hi) / U, "excess_lo_pct": None if opt_lo is None else 100 * (U - opt_lo) / U,
            "bound_gap_pct": 100 * (U - L) / U, "seconds": round(time.time() - t0, 1)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    out_path = MS / "evidence" / "exact_optimum.json"
    res = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for ds in sys.argv[1:] or ["j0126"]:
        ref = evaluated_sha(ds)
        rows = [json.loads(x) for x in (ROOT / MANIFEST[ds]).read_text(encoding="utf-8").splitlines() if x.strip()]
        rows = [r for r in rows if r["sample_id"] in ref]
        res[ds] = []
        for r in rows:
            v = one_volume(r, ref[r["sample_id"]])
            res[ds].append(v)
            print(ds, v["sample_id"], "U", v["U"], "OPT", v["OPT_lo"], v["OPT_hi"], "L", v["L"], "same", v["same_stream_as_evaluated"],
                  "exc%", round(v["excess_hi_pct"], 3), "gap%", round(v["bound_gap_pct"], 3), v["solver_status"], v["seconds"], "s",
                  flush=True)
            out_path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
