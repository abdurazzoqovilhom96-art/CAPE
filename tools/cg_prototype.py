"""B protocol: one development sample through the column-generation prototype (fresh, pinned process).

    python tools/cg_prototype.py --manifest data/manifests/q1b_dev.jsonl --sample-id ID --out results/.../ID.json

Steps: native diagnostic encode of Eθ (same options + return_cc + collect_records: the native CC ids, records,
background, regime widths and the ascent bound) -> instance -> T4 checks (instance == native; the Eθ selection is a
valid cover with cost payload_ub_bytes) -> bounded CG -> integer greedy -> integer certificate. Writes one JSON.
Nothing here is a stream; the prototype never replaces the encoder."""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import resources  # noqa: E402
from cape.canonical import crackle_view  # noqa: E402
from cape.cg import build_instance, column_generation, components, integer_certificate  # noqa: E402

EQ_OPTS = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
           "depth_policy": "fixed_depth_width", "certificate": "off", "impl_mask": 6719, "parallel": 1}
DIAG_KEYS = ("P", "Q", "w_I", "w_D", "w_C", "w_L", "w_N", "w_G", "regime_h", "regime_w_D", "cc_count", "run_count",
             "label_count", "payload_ub_bytes", "payload_lb_bytes_fixed_background", "total_bytes", "label_bytes",
             "candidate_count_before", "candidates_after_singleton", "candidates_after_adjacency",
             "candidates_after_equal", "candidate_count_after", "incidence_count_before", "incidence_count",
             "component_count", "max_component_cc", "cc_written")


def t4_checks(vol: np.ndarray, diag: dict, inst: dict) -> dict:
    Z, Y, X = vol.shape
    XY = X * Y
    out = {"cc_count_equal": inst["n_cc"] == int(diag["cc_count"]),
           "run_count_equal": inst["n_runs"] == int(diag["run_count"])}
    cc = np.ascontiguousarray(np.asarray(diag["cc_volume"]).transpose(1, 2, 0)).ravel()
    lab = np.ascontiguousarray(vol.transpose(1, 2, 0)).ravel()
    covered = np.zeros(inst["n_cc"], dtype=bool)
    P = Qn = bad_pins = 0
    for rec in diag["records"]:
        for start, depth in rec["pins"]:
            col, z0, L = int(start) % XY, int(start) // XY, int(depth) + 1
            g = col * Z + z0
            if z0 + L > Z or L > inst["h"] or not (lab[g:g + L] == rec["label"]).all():
                bad_pins += 1
                continue
            covered[cc[g:g + L]] = True
            P += 1
        for u in rec["singletons"]:
            covered[int(u)] = True
            Qn += 1
    nonbg = inst["cc_label"] != diag["bgcolor"]
    out.update(pins_valid=bad_pins == 0, selection_covers_all=bool(covered[nonbg].all()),
               pq_equal=(P == int(diag["P"]) and Qn == int(diag["Q"])),
               payload_ub_equal=P * inst["c"] + Qn * inst["s"] == int(diag["payload_ub_bytes"]))
    out["pass"] = all(out.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--sample-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget-s", type=float, default=1800.0)
    ap.add_argument("--max-iter", type=int, default=40)
    ap.add_argument("--k-add", type=int, default=50_000)
    ap.add_argument("--native-total-bytes", type=int, default=None, help="Eθ stream bytes from the timed rows")
    a = ap.parse_args(argv)
    t_all = time.perf_counter()
    rec = {"sample_id": a.sample_id, "status": "ERROR", "budget_s": a.budget_s, "max_iter": a.max_iter,
           "k_add": a.k_add}
    try:
        cpu = resources.timing_cpu()
        rec["cpu"] = cpu.get("cpu")
        rec["pinned"] = resources.pin_current_process(cpu.get("cpu"))
        row = next(r for r in map(json.loads, Path(a.manifest).read_text(encoding="utf-8").splitlines())
                   if r and r["sample_id"] == a.sample_id)
        vol = np.load(ROOT / row["path"])
        rec.update(dtype=str(vol.dtype), shape_zyx=list(vol.shape), voxels=int(vol.size))
        from cape import _cape_native as cn

        t0 = time.perf_counter()
        _buf, diag = cn.encode(crackle_view(vol), dict(EQ_OPTS, return_cc=True, collect_records=True))
        rec["native_diag_encode_s"] = time.perf_counter() - t0
        rec["native"] = {k: int(diag[k]) for k in DIAG_KEYS if k in diag}
        rec["native"]["label_format"] = str(diag.get("label_format"))
        if not rec["native"]["label_format"].startswith("PINS"):
            raise RuntimeError(f"Eθ wrote {rec['native']['label_format']} for this sample: the PINS model does not apply")
        rec["native"]["bgcolor"] = int(diag["bgcolor"])
        if a.native_total_bytes is not None:
            rec["native_stream_equal_timed"] = int(diag["total_bytes"]) == a.native_total_bytes
        c = int(diag["w_I"]) + int(diag["regime_w_D"])
        s = int(diag["w_C"])
        t0 = time.perf_counter()
        inst = build_instance(vol, np.asarray(diag["cc_volume"]), diag["bgcolor"], int(diag["regime_h"]), c, s)
        rec["instance_build_s"] = time.perf_counter() - t0
        rec["instance"] = {k: inst[k] for k in ("h", "c", "s", "n_runs", "n_cc", "n_nonbg_cc", "n_lp",
                                               "n_fixed_single")}
        rec["instance"]["useful_runs"] = int(inst["starts"].shape[0])
        rec["instance"]["useful_positions"] = int(inst["lens"].sum())
        rec["T4"] = t4_checks(vol, diag, inst)
        if a.native_total_bytes is not None:
            rec["T4"]["stream_equal_timed"] = rec["native_stream_equal_timed"]
            rec["T4"]["pass"] = rec["T4"]["pass"] and rec["native_stream_equal_timed"]
        del diag["cc_volume"], diag["records"]
        k_nat, _ = components(inst)
        rec["instance"]["components_lp"] = k_nat
        cg = column_generation(inst, budget_s=a.budget_s, max_iter=a.max_iter, k_add=a.k_add)
        t0 = time.perf_counter()
        cert = integer_certificate(inst, cg["lam"])
        cert_s = time.perf_counter() - t0
        ig = cg["integer"]
        rec["cg"] = {k: cg[k] for k in ("converged", "stop", "iterations", "pricing_passes", "columns", "nnz",
                                       "lp_time_s", "pricing_time_s", "int_time_s", "lp_rss_bytes", "history",
                                       "wall_s")}
        rec["integer"] = {"P": ig["P"], "Q": ig["Q"], "U": ig["U"]}
        rec["certificate"] = {k: cert[k] for k in ("feasible", "violations", "repair_passes", "repaired_windows",
                                                  "L", "n_components", "q")}
        rec["certificate"]["time_s"] = cert_s
        U_e, L_a = int(rec["native"]["payload_ub_bytes"]), int(rec["native"]["payload_lb_bytes_fixed_background"])
        rec["compare"] = {"U_Etheta": U_e, "L_ascent": L_a, "U_CG": ig["U"], "L_CG": cert["L"],
                          "U_CG_le_U_Etheta": ig["U"] <= U_e,
                          "L_CG_ge_L_ascent": cert["L"] is not None and cert["L"] >= L_a,
                          "gap_ascent": U_e - L_a, "gap_CG": (U_e - cert["L"]) if cert["L"] is not None else None}
        rec["status"] = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc()[-4000:]
    rec["process_peak"] = resources.process_peak_rss()
    rec["wall_s"] = time.perf_counter() - t_all
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    tmp.replace(out)
    return 0 if rec["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
