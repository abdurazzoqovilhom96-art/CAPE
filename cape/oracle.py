"""Offline optimality audit (spec section 12, stage OPTIONAL_AUDIT).

For each sample, the CAPE encoder exports its written small/medium component models; each is
solved independently with OR-Tools CP-SAT (single worker, fixed seed, time limit). Only an
OPTIMAL status counts as an optimum. Checks: LB <= OPT (certificate soundness) and, for
components CAPE marked exact (DP or LB==UB), UB == OPT. A violation is a correctness failure,
reported loudly; audit time is never part of encode time."""

from __future__ import annotations

import json
import time

from cape.result_store import atomic_write_text

STATUS_NAMES = {0: "Trivial", 1: "LbTight", 2: "ExactDp", 3: "Heuristic"}


def solve_cpsat(n: int, sets: list[list[int]], c: int, s: int, time_limit: float, seed: int) -> dict:
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    xs = [m.NewBoolVar(f"p{i}") for i in range(len(sets))]
    ys = [m.NewBoolVar(f"u{u}") for u in range(n)]
    inc = [[] for _ in range(n)]
    for i, st in enumerate(sets):
        for u in st:
            inc[u].append(xs[i])
    for u in range(n):
        m.Add(sum(inc[u]) + ys[u] >= 1)
    m.Minimize(c * sum(xs) + s * sum(ys))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = float(time_limit)
    t0 = time.perf_counter()
    status = solver.Solve(m)
    return {"status": solver.StatusName(status), "objective": int(round(solver.ObjectiveValue()))
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
            "best_bound": int(round(solver.BestObjectiveBound())) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
            "seconds": time.perf_counter() - t0}


def run_oracle_audit(ctx) -> dict:
    from cape.adapters import make_adapter
    from cape.dataset_manifest import resolve_path
    from cape.io import load_canonical

    oc = ctx.cfg["oracle"]
    spec = ctx.methods[ctx.cfg["primary"]["new"]] if ctx.methods[ctx.cfg["primary"]["new"]]["adapter"] == "cape_native" \
        else ctx.methods["cape_core"]
    rows_out, contradictions, n_opt, n_timeout = [], 0, 0, 0
    budget = oc["max_components"]
    for row in sorted(ctx.rows, key=lambda r: (r["is_synthetic"], r["sample_id"])):
        if budget <= 0:
            break
        ad = make_adapter("oracle_probe", dict(spec, options=dict(spec["options"], format_policy="force_pins")), ctx.cfg)
        arr = load_canonical(resolve_path(row["path"]))
        if arr.shape[0] < 2:
            continue
        ad.encode(arr, {"export_components_max_cc": oc["max_cc"], "export_components_limit": budget})
        comps = ad.last_diagnostics.get("components_export", [])
        for k, comp in enumerate(comps):
            res = solve_cpsat(comp["n"], comp["sets"], comp["pin_cost"], comp["single_cost"], oc["time_limit_s"],
                              ctx.cfg["seed"])
            opt = res["objective"] if res["status"] == "OPTIMAL" else None
            problem = None
            if opt is not None:
                n_opt += 1
                if comp["lb"] > opt:
                    problem = f"LB {comp['lb']} > OPT {opt}: certificate unsound"
                elif STATUS_NAMES[comp["status"]] in ("ExactDp", "LbTight") and comp["ub"] != opt:
                    problem = f"component marked {STATUS_NAMES[comp['status']]} but UB {comp['ub']} != OPT {opt}"
                elif comp["ub"] < opt:
                    problem = f"UB {comp['ub']} < OPT {opt}: infeasible solution claimed"
            else:
                n_timeout += 1
                if res["best_bound"] is not None and res["best_bound"] > comp["ub"]:
                    problem = f"CP-SAT bound {res['best_bound']} > CAPE UB {comp['ub']}"
            contradictions += problem is not None
            rows_out.append({"sample_id": row["sample_id"], "is_synthetic": row["is_synthetic"], "component": k,
                             "n_cc": comp["n"], "n_pins": len(comp["sets"]), "cape_status": STATUS_NAMES[comp["status"]],
                             "cape_ub": comp["ub"], "cape_lb": comp["lb"], "cpsat_status": res["status"],
                             "cpsat_optimum": opt, "cpsat_bound": res["best_bound"],
                             "ub_gap_to_opt": (comp["ub"] - opt) if opt is not None else None,
                             "cpsat_seconds": round(res["seconds"], 4), "problem": problem})
        budget -= len(comps)
    import csv
    import io

    buf = io.StringIO()
    fields = ["sample_id", "is_synthetic", "component", "n_cc", "n_pins", "cape_status", "cape_ub", "cape_lb",
              "cpsat_status", "cpsat_optimum", "cpsat_bound", "ub_gap_to_opt", "cpsat_seconds", "problem"]
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows_out:
        w.writerow({k: "" if r.get(k) is None else r[k] for k in fields})
    atomic_write_text(ctx.path("06_solver_certificates", "oracle_audit.csv"), buf.getvalue())
    heur = [r for r in rows_out if r["cape_status"] == "Heuristic" and r["cpsat_optimum"] is not None]
    summary = {"status": "COMPLETE", "components_audited": len(rows_out), "cpsat_optimal": n_opt,
               "cpsat_not_optimal": n_timeout, "contradictions": contradictions,
               "heuristic_components_with_known_optimum": len(heur),
               "heuristic_components_at_optimum": sum(r["ub_gap_to_opt"] == 0 for r in heur),
               "max_cc": ctx.cfg["oracle"]["max_cc"], "time_limit_s": ctx.cfg["oracle"]["time_limit_s"],
               "note": "audit time is excluded from encode time; FEASIBLE/UNKNOWN never counted as OPTIMAL"}
    atomic_write_text(ctx.path("06_solver_certificates", "oracle_summary.json"), json.dumps(summary, indent=2))
    ctx.store.set_meta("oracle_summary", summary)
    if contradictions:
        ctx.log(f"ORACLE AUDIT: {contradictions} contradictions with CAPE certificates (correctness failure)", "ERROR")
    return summary
