"""Recompute every number used in the CAPE manuscript from the local raw results and write
evidence/numbers.json (values) and evidence/evidence_ledger.csv (claim -> source mapping).

Sources (read-only):
  maqola uchun/raw_results/{j0126,snemi,hemibrain}_results.csv   raw per-repeat rows of the final run
  maqola uchun/raw_results/profile_{j0126,hemibrain}_results.csv  separate instrumented profile run
  maqola uchun/supplementary/analysis.json                         cluster-bootstrap CIs of the final analysis
  results/<run>/03_bitstreams/*.bin                                 stored streams (section sizes)
  results/<run>/06_solver_certificates/oracle_audit.csv             CP-SAT component audit
  data/manifests/*.jsonl                                            frozen dataset manifests

Conventions (stated in the paper):
  per volume: median over timed repeats; across volumes: geometric mean of per-volume ratios;
  speed-up S = T_comparator / T_CAPE; peak ratio R = M_CAPE / M_comparator (encode-inclusive process peak);
  pooled size change = 100 * (sum B_CAPE / sum B_comparator - 1)  (negative = CAPE smaller).
"""

from __future__ import annotations

import csv
import json
import os
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ["CAPE_REPO"]) if os.environ.get("CAPE_REPO") else next(
    q for q in Path(__file__).resolve().parents if (q / "cape").is_dir() and (q / "maqola uchun").is_dir())
MS = Path(__file__).resolve().parents[1]
RAW = ROOT / "maqola uchun" / "raw_results"
ANALYSIS = ROOT / "maqola uchun" / "supplementary" / "analysis.json"
OUT = MS / "evidence"
FIGDATA = MS / "figure_data"
NEW, CERT, FLAT = "cape_q1_fast_m0", "cape_q1_certified_m0", "crackle_flat_m0"
DATASETS = {"j0126": "data/manifests/q1_external_j0126.jsonl", "snemi": "data/manifests/confirm_snemi3d.jsonl",
            "hemibrain": "data/manifests/q1_external_hemibrain.jsonl"}
COMPARATORS = {  # analysis.json comparison key -> (method id, label)
    "C3_stock_corr": ("crackle_pins_opt_corrected_m0", "pins_opt, count width corrected"),
    "C3_stock_vendor": ("crackle_vendor_pins_opt_m0", "pins_opt, vendor build"),
    "C3_stock": ("crackle_pins_opt_m0", "pins_opt, PyPI 0.53.0"),
    "C3_pins_fast": ("crackle_pins_fast_m0", "pins_fast, PyPI 0.53.0"),
    "C3_flat": ("crackle_flat_m0", "Crackle flat, PyPI 0.53.0"),
    "C3_wgreedy": ("q1_fast_weighted_greedy_m0", "weighted greedy, CAPE infrastructure"),
    "C3_glocal": ("q1_fast_greedy_local_m0", "greedy + local search, CAPE infrastructure"),
    "C2": ("cape_v21_fast_m0", "CAPE v2.1 (frozen binary)"),
    "C1": ("cape_v3frozen_fast_m0", "CAPE v3 (frozen binary)"),
    "C3_compresso": ("compresso_native", "Compresso"),
    "C3_ng": ("neuroglancer_b8", "neuroglancer compressed segmentation"),
    "C3_zstd9": ("zstd9", "zstd level 9 on raw voxels"),
    "CERT_cost": (NEW, "CAPE with bound computation (new) vs CAPE (base)"),
}

ledger: list[dict] = []


def led(cid, claim, value, source, field, dataset, n, comparator, metric, numden, aggregation, kind="measured",
        conditions="final run, 1 thread, Windows 11, i7-13700F"):
    ledger.append({"claim_id": cid, "claim": claim, "value": value, "source_file": source, "record_or_field": field,
                   "dataset": dataset, "n": n, "comparator_build": comparator, "metric_definition": metric,
                   "numerator_denominator": numden, "aggregation": aggregation, "conditions": conditions,
                   "type": kind})


def gmean(x):
    x = [float(v) for v in x if v is not None and v > 0]
    return math.exp(sum(math.log(v) for v in x) / len(x)) if x else float("nan")


def load(ds):
    d = pd.read_csv(RAW / f"{ds}_results.csv", low_memory=False)
    d = d[(d.status == "OK") & (d.wrapper.fillna("none") == "none") & (d.is_synthetic != True)]  # noqa: E712
    tim = d[d.panel != "MEM"].copy()
    mem = d[d.panel == "MEM"].copy()
    mem["peak_enc"] = [json.loads(x).get("peak_after_encode") if isinstance(x, str) else None for x in mem.extra_json]
    mem["peak_pre"] = [json.loads(x).get("peak_before_encode") if isinstance(x, str) else None for x in mem.extra_json]
    return d, tim, mem


# Methods whose absolute encode time and process peak are reported (revision 2026-11-09).
ABS_METHODS = {"cape": NEW, "corr": "crackle_pins_opt_corrected_m0", "fast": "crackle_pins_fast_m0",
               "flat": FLAT, "wg": "q1_fast_weighted_greedy_m0", "gl": "q1_fast_greedy_local_m0",
               "vtwo": "cape_v21_fast_m0", "vthree": "cape_v3frozen_fast_m0", "cert": CERT,
               "noMa": "cape_q1_noM1a_m0", "noMb": "cape_q1_noM5b_m0", "noOb": "cape_q1_noO2f_m0",
               "noOc": "cape_q1_noO3f_m0"}
ABLATION = {"cape_q1_noM1a_m0": ("Ma", "neighbour-column filter (v3, bit 32)"),
            "cape_q1_noM5b_m0": ("Mb", "batched CC labelling into column-major chains (v3, bit 512)"),
            "cape_q1_noO2f_m0": ("Ob", "exact allocation of runs (Q1, bit 2048)"),
            "cape_q1_noO3f_m0": ("Oc", "compact 16-bit slice-local chains (Q1, bit 4096)")}


def pv(df, col, method):
    return df[df.method_id == method].groupby("sample_id")[col].median()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGDATA.mkdir(parents=True, exist_ok=True)
    an = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    num: dict = {"datasets": {}, "comparisons": {}, "bounds": {}, "profile": {}, "sections": {}, "oracle": {},
                 "lossless": {}, "excess_time": {}, "environment": {}}
    env = json.loads((ROOT / an["datasets"]["j0126"]["run_dir"] / "01_environment" / "environment.json")
                     .read_text(encoding="utf-8"))
    num["environment"] = {"cpu": env["os"]["processor_name"], "ram_gib": round(env["memory"]["total_bytes"] / 2**30, 1),
                          "os": env["os"]["platform"], "compiler": env["native_build"]["compiler"],
                          "flags": " ".join(env["native_build"]["opt_flags"]), "python": env["python"]["version"],
                          "crackle_codec": env["packages"]["crackle-codec"], "ortools": env["packages"]["ortools"],
                          "numpy": env["packages"]["numpy"], "crackle_commit": env["sources"]["crackle"]["commit"],
                          "p_cores": env["cpu"]["performance_cores"], "e_cores": env["cpu"]["efficiency_cores"]}
    pervol_rows = []
    thr_rows: list[dict] = []
    for ds, man in DATASETS.items():
        A = an["datasets"][ds]
        allrows, tim, mem = load(ds)
        manifest = [json.loads(l) for l in (ROOT / man).read_text(encoding="utf-8").splitlines() if l.strip()]
        manifest = {r["sample_id"]: r for r in manifest}
        ids = sorted(pv(tim, "total_bytes", NEW).index)
        shapes = {}
        for s in ids:
            shapes[tuple(manifest[s]["shape"])] = shapes.get(tuple(manifest[s]["shape"]), 0) + 1
        ex = tim[tim.method_id == NEW].drop_duplicates("sample_id").set_index("sample_id").extra_json.map(json.loads)
        labels = [ex[s]["label_count"] for s in ids]
        ccs = [ex[s]["cc_count"] for s in ids]
        reps = tim[tim.method_id == NEW].groupby("sample_id").size()
        num["datasets"][ds] = {
            "n": len(ids), "shapes_zyx": {"x".join(map(str, k)): v for k, v in shapes.items()},
            "dtype": manifest[ids[0]]["dtype"], "spacing_xyz_nm": manifest[ids[0]].get("spacing_xyz"),
            "voxels_total": int(sum(np.prod(manifest[s]["shape"]) for s in ids)),
            "labels_median": st.median(labels), "labels_min": min(labels), "labels_max": max(labels),
            "cc2d_median": st.median(ccs), "cc2d_min": min(ccs), "cc2d_max": max(ccs),
            "timed_repeats_per_volume": sorted(set(int(v) for v in reps.values)),
            "split": manifest[ids[0]].get("split"), "role": A["label"]}
        led(f"D-{ds}", f"{ds} volumes and characteristics", json.dumps(num["datasets"][ds]),
            f"{man}; maqola uchun/raw_results/{ds}_results.csv", "shape, dtype; extra_json.label_count/cc_count",
            ds, len(ids), "-", "label count = distinct labels; cc2d = 4-connected 2D components over all slices",
            "-", "median [min, max] over volumes", "measured")
        # ---- comparisons: CI from analysis.json, recomputed point estimates from raw rows ----
        for key, (mid, label) in COMPARATORS.items():
            if key not in A["comparisons"] or "S_T" not in A["comparisons"][key]:
                num["comparisons"][f"{ds}:{key}"] = {"label": label, "method": mid, "not_evaluated": True,
                                                     "reason": "no paired successful rows (e.g. dtype unsupported "
                                                               "or pre-registered size budget)"}
                continue
            c = A["comparisons"][key]
            new_id = CERT if key == "CERT_cost" else NEW
            t_new, t_b = pv(tim, "encode_ns", new_id), pv(tim, "encode_ns", mid)
            m_new, m_b = pv(mem, "peak_enc", new_id), pv(mem, "peak_enc", mid)
            b_new, b_b = pv(tim, "total_bytes", new_id), pv(tim, "total_bytes", mid)
            common = sorted(set(t_new.index) & set(t_b.index))
            sp = (t_b[common] / t_new[common])
            cm = sorted(set(m_new.index) & set(m_b.index))
            mr = (m_new[cm] / m_b[cm])
            br = (b_new[common] / b_b[common])
            rec = {
                "label": label, "method": mid, "n": len(common), "n_mem": len(cm),
                "speedup_geo": gmean(sp), "speedup_ci": c.get("S_T_ci"), "speedup_geo_analysis": c["S_T"],
                "speedup_min": float(sp.min()), "speedup_max": float(sp.max()),
                "peak_ratio_geo": gmean(mr), "peak_ratio_ci": c.get("R_M_ci"), "peak_ratio_geo_analysis": c["R_M"],
                "peak_ratio_max": float(mr.max()) if len(mr) else None,
                "peak_ratio_min": float(mr.min()) if len(mr) else None,
                "size_change_pooled_pct": 100 * (b_new[common].sum() / b_b[common].sum() - 1),
                "size_gain_ci_pct": c.get("G_B_ci"), "size_gain_analysis_pct": c.get("G_B_pct"),
                "vol_smaller": int((br < 1).sum()), "vol_equal": int((br == 1).sum()), "vol_larger": int((br > 1).sum()),
                "vol_faster": int((sp > 1).sum()), "vol_lower_peak": int((mr < 1).sum()),
                "bytes_identical": bool(c.get("bytes_identical")), "n_clusters": c.get("n_clusters")}
            assert abs(rec["speedup_geo"] - c["S_T"]) / c["S_T"] < 2e-3, (ds, key, rec["speedup_geo"], c["S_T"])
            if len(cm):
                assert abs(rec["peak_ratio_geo"] - c["R_M"]) / c["R_M"] < 2e-3, (ds, key, rec["peak_ratio_geo"], c["R_M"])
            num["comparisons"][f"{ds}:{key}"] = rec
            led(f"C-{ds}-{key}", f"CAPE vs {label}", json.dumps({k: rec[k] for k in (
                "speedup_geo", "speedup_ci", "peak_ratio_geo", "peak_ratio_ci", "size_change_pooled_pct", "vol_smaller",
                "vol_faster", "vol_lower_peak")}),
                f"maqola uchun/raw_results/{ds}_results.csv; maqola uchun/supplementary/analysis.json",
                f"encode_ns, total_bytes, extra_json.peak_after_encode (panel MEM); comparisons.{key}",
                ds, len(common), f"{mid}", "speed-up S=T_comp/T_CAPE; peak ratio R=M_CAPE/M_comp; size change "
                "100(sum B_CAPE/sum B_comp - 1)", "T,M,B per volume = median over repeats",
                "geometric mean over volumes; 95% CI = paired cluster bootstrap (10,000 resamples, seed 20261107)")
            for s in common:
                pervol_rows.append({"dataset": ds, "comparison": key, "sample_id": s, "speedup": float(sp[s]),
                                    "peak_ratio": float(mr[s]) if s in mr.index else None,
                                    "size_ratio": float(br[s])})
        # ---- zstd-3 wrapped CAPE vs wrapped corrected pins_opt (revision: counts behind a text claim) ----
        z3 = A["comparisons"].get("A_z3_stock")
        if z3:
            num.setdefault("wrapped", {})[ds] = {"n": z3["n"], "cape_smaller": z3["smaller"], "cape_larger": z3["larger"],
                                                "size_gain_pct": z3.get("G_B_pct"), "new": z3["new"], "base": z3["base"]}
            led(f"W-{ds}", "zstd-3 wrapped CAPE vs wrapped corrected pins_opt", json.dumps(num["wrapped"][ds]),
                "maqola uchun/supplementary/analysis.json", "comparisons.A_z3_stock", ds, z3["n"], z3["base"],
                "volumes on which the wrapped CAPE file is smaller / larger", "-", "counts", "measured")
        for key in ("A_z9_flat", "A_z3_flat", "A_z9_stock"):  # revision: CAPE+zstd vs flat+zstd (is PINS worth it?)
            w = A["comparisons"].get(key)
            if w and "S_T" in w:
                num.setdefault("wrapped_all", {}).setdefault(ds, {})[key] = {
                    "n": w["n"], "cape_smaller": w["smaller"], "cape_larger": w["larger"], "size_gain_pct": w["G_B_pct"],
                    "speedup": w["S_T"], "new": w["new"], "base": w["base"]}
        if num.get("wrapped_all", {}).get(ds):
            led(f"WA-{ds}", "zstd-wrapped CAPE vs zstd-wrapped flat and pins_opt", json.dumps(num["wrapped_all"][ds]),
                "maqola uchun/supplementary/analysis.json", "comparisons.A_z9_flat, A_z3_flat, A_z9_stock", ds,
                A["comparisons"]["A_z9_flat"]["n"], "flat+zstd, pins_opt+zstd", "pooled size change of the wrapped files",
                "-", "pooled; volumes smaller/larger", "measured")
        # ---- absolute encode time [ms] and process peak [MiB] (revision; median over volumes) ----
        num.setdefault("absolute", {})[ds] = {}
        for nm, mid in ABS_METHODS.items():
            t = pv(tim, "encode_ns", mid) / 1e6
            if not len(t):
                continue
            mm = pv(mem, "peak_enc", mid) / 2**20
            pre = pv(mem, "peak_pre", mid) / 2**20
            inc = (mm - pre).dropna()
            vox = tim[tim.method_id == mid].groupby("sample_id").canonical_shape.first().map(
                lambda s_: float(np.prod(json.loads(s_))))
            thr = (vox[t.index] / (t / 1e3) / 1e6)  # MVoxel/s per volume
            dec = pv(tim, "decode_ns", mid) / 1e6
            for s_ in t.index:
                thr_rows.append({"dataset": ds, "sample_id": s_, "method": nm, "voxels": vox[s_], "t_ms": float(t[s_]),
                                 "mvox_per_s": float(thr[s_])})
            num["absolute"][ds][nm] = {"method": mid, "n": len(t), "t_ms_median": float(t.median()),
                                       "t_ms_min": float(t.min()), "t_ms_max": float(t.max()),
                                       "t_ms_sum": float(t.sum()),
                                       "peak_mib_median": float(mm.median()) if len(mm) else None,
                                       "peak_mib_min": float(mm.min()) if len(mm) else None,
                                       "peak_mib_max": float(mm.max()) if len(mm) else None,
                                       "pre_encode_peak_mib_median": float(pre.median()) if len(pre) else None,
                                       "increment_mib_median": float(inc.median()) if len(inc) else None,
                                       "mvox_per_s_median": float(thr.median()),
                                       "decode_ms_median": float(dec.median()) if len(dec) else None}
        led(f"A-{ds}", "absolute encode time and process peak per method", json.dumps(
            {k: [round(v["t_ms_median"], 1), round(v["peak_mib_median"] or 0, 1)] for k, v in num["absolute"][ds].items()}),
            f"maqola uchun/raw_results/{ds}_results.csv", "encode_ns (panel B); extra_json.peak_after_encode, "
            "peak_before_encode (panel MEM)", ds, len(ids), "see method ids", "T = encode time [ms]; M = peak working "
            "set of a fresh process after encode (interpreter, libraries and input array included; decode excluded) "
            "[MiB]", "-", "per volume median over repeats; then median [min, max] over volumes", "measured")
        # ---- ablation of the output-preserving mechanisms (block A; revision) ----
        num.setdefault("ablation", {})[ds] = {}
        for mid, (nm, what) in ABLATION.items():
            a = A.get("ablation", {}).get(mid)
            if not a:
                continue
            t_new, t_b = pv(tim, "encode_ns", NEW), pv(tim, "encode_ns", mid)
            common = sorted(set(t_new.index) & set(t_b.index))
            sp = gmean(t_b[common] / t_new[common])
            assert abs(sp - a["S_T"]) / a["S_T"] < 2e-3, (ds, mid, sp, a["S_T"])
            sha_new = tim[tim.method_id == NEW].groupby("sample_id").bitstream_sha256.first()
            sha_b = tim[tim.method_id == mid].groupby("sample_id").bitstream_sha256.first()
            same = int(sum(sha_new[s] == sha_b[s] for s in common))
            ps = a["per_sample"]
            num["ablation"][ds][nm] = {
                "method": mid, "mechanism": what, "n": a["n"], "speedup_geo": a["S_T"], "speedup_ci": a["S_T_ci"],
                "peak_ratio_geo": a["R_M"], "peak_ratio_ci": a["R_M_ci"], "sha_identical_volumes": same,
                "time_reduction_pct": 100 * (1 - 1 / a["S_T"]),
                "base_t_ms_median": float(np.median([r["base_enc_ms"] for r in ps])),
                "new_t_ms_median": float(np.median([r["new_enc_ms"] for r in ps])),
                "base_peak_mib_median": float(np.median([r["base_peak_enc_mib"] for r in ps])),
                "new_peak_mib_median": float(np.median([r["new_peak_enc_mib"] for r in ps])),
                "worst_speedup": a["worst_speedup"]["speedup"], "worst_mem_ratio": a["worst_mem_ratio"]["mem_ratio"],
                "speedup_min": float(min(r["speedup"] for r in ps)), "speedup_max": float(max(r["speedup"] for r in ps)),
                "peak_ratio_min": float(min(r["mem_ratio"] for r in ps)),
                "peak_ratio_max": float(max(r["mem_ratio"] for r in ps))}
            led(f"AB-{ds}-{nm}", f"ablation: CAPE vs CAPE without {what}", json.dumps(
                {k: num["ablation"][ds][nm][k] for k in ("speedup_geo", "speedup_ci", "peak_ratio_geo", "peak_ratio_ci",
                                                         "sha_identical_volumes")}),
                f"maqola uchun/raw_results/{ds}_results.csv; maqola uchun/supplementary/analysis.json",
                f"encode_ns, bitstream_sha256, peak_after_encode; ablation.{mid}", ds, a["n"], mid,
                "S = T_without/T_CAPE; R = M_CAPE/M_without; byte identity by SHA-256 of the stream",
                "per volume medians over repeats", "geometric mean; 95% paired cluster bootstrap", "measured")
        cnt = [c for c in A.get("counters", []) if c.get("after_adjacency")]
        if cnt:
            fr = [c["adjacent_dropped"] / (c["adjacent_dropped"] + c["after_adjacency"]) for c in cnt]
            eq = [c["after_equal"] / c["after_adjacency"] for c in cnt if c.get("after_equal")]
            num.setdefault("counters", {})[ds] = {
                "n": len(cnt), "adjacent_dropped_share_median": float(np.median(fr)),
                "adjacent_dropped_share_min": float(min(fr)), "adjacent_dropped_share_max": float(max(fr)),
                "after_equal_over_after_adjacency_median": float(np.median(eq)) if eq else None,
                "compact_chain_volumes": int(sum(1 for c in cnt if c.get("compact_chain") == 1)),
                "runs_match_expected": bool(all(c["run_count"] == c["runs_expected"] for c in cnt))}
            led(f"K-{ds}", "candidate and allocation counters of CAPE", json.dumps(num["counters"][ds]),
                "maqola uchun/supplementary/analysis.json", "counters[]", ds, len(cnt), "-",
                "share of generated windows dropped by the neighbour filter; compact-chain use; exact run count",
                "-", "median [min, max] over volumes", "measured")
        # ---- excess encode time over flat (per volume, then median) ----
        t_flat = pv(tim, "encode_ns", FLAT)
        num["excess_time"][ds] = {}
        for mid in ["crackle_pins_opt_corrected_m0", "crackle_vendor_pins_opt_m0", "crackle_pins_opt_m0",
                    "crackle_pins_fast_m0", NEW]:
            t = pv(tim, "encode_ns", mid)
            if not len(t):
                continue
            cm = sorted(set(t.index) & set(t_flat.index))
            e = 1 - t_flat[cm] / t[cm]
            num["excess_time"][ds][mid] = {"median": float(e.median()), "min": float(e.min()), "max": float(e.max()),
                                           "n": len(cm)}
        led(f"E-{ds}", "share of encode time in excess of Crackle flat", json.dumps(num["excess_time"][ds]),
            f"maqola uchun/raw_results/{ds}_results.csv", "encode_ns", ds, len(ids), "pins_opt / pins_fast / CAPE vs flat",
            "e = 1 - T_flat / T_method", "per volume (medians over repeats)", "median [min, max] over volumes", "derived")
        # ---- bounds (bound-computing mode; same stream as CAPE) ----
        c = tim[tim.method_id == CERT].drop_duplicates("sample_id").set_index("sample_id")
        x = c.loc[ids]
        gap = x.ub_bytes - x.lb_bytes
        labu = x.label_bytes
        llb = x.extra_json.map(lambda s: json.loads(s)["label_lb_bytes"])
        assert ((labu - llb) == gap).all()
        rec_u = x.extra_json.map(lambda s: json.loads(s)["payload_ub_bytes"])
        g_lab = 100 * gap / labu
        g_file = 100 * gap / x.ub_bytes
        g_over_l = 100 * gap / llb
        same = all(x.bitstream_sha256[s] == tim[(tim.method_id == NEW) & (tim.sample_id == s)].bitstream_sha256.iloc[0]
                   for s in ids)
        num["bounds"][ds] = {
            "n": len(ids), "valid": int((x.certificate_valid == True).sum()),  # noqa: E712
            "gap_label_median": float(g_lab.median()), "gap_label_min": float(g_lab.min()),
            "gap_label_max": float(g_lab.max()), "gap_label_q1": float(g_lab.quantile(.25)),
            "gap_label_q3": float(g_lab.quantile(.75)),
            "gap_file_median": float(g_file.median()), "gap_file_max": float(g_file.max()),
            "gap_over_L_label_median": float(g_over_l.median()), "gap_over_L_label_max": float(g_over_l.max()),
            "gap_bytes_median": float(gap.median()), "gap_bytes_total": int(gap.sum()),
            "label_bytes_total": int(labu.sum()), "file_bytes_total": int(x.ub_bytes.sum()),
            "zero_gap_volumes": int((gap == 0).sum()), "same_stream_as_fast": bool(same),
            "gap_records_median": float((100 * gap / rec_u).median()), "gap_records_max": float((100 * gap / rec_u).max()),
            "count_width_slack_bytes_total": int(sum(
                2 * (json.loads(e)["label_count"] - 1) * (json.loads(e)["w_N"] - 1) for e in x.extra_json)),
            "records_share_of_label_median": float((rec_u / labu).median())}
        pd.DataFrame({"dataset": ds, "sample_id": ids, "gap_label_pct": g_lab.values, "gap_file_pct": g_file.values,
                      "label_bytes": labu.values, "label_lb_bytes": llb.values, "file_bytes": x.ub_bytes.values}) \
            .to_csv(FIGDATA / f"gaps_{ds}.csv", index=False)
        led(f"B-{ds}", "bound gap normalised by the label section and by the whole stream",
            json.dumps({k: num["bounds"][ds][k] for k in ("gap_label_median", "gap_label_max", "gap_file_median",
                                                            "gap_file_max", "valid")}),
            f"maqola uchun/raw_results/{ds}_results.csv (method {CERT})",
            "ub_bytes (stream size U_f), lb_bytes (= L_label + non-label bytes), label_bytes (U), extra_json.label_lb_bytes (L)",
            ds, len(ids), "-", "label gap = (U - L)/U; file gap = (U - L)/U_f", "U = written label-section bytes; "
            "U_f = written stream bytes", "per volume, then median / max over volumes", "measured")
        # ---- section shares from stored streams ----
        try:
            import crackle

            shares = {"labels": [], "crack_codes": [], "z_index": [], "crcs": [], "header": []}
            run_dirs = sorted((ROOT / "results").glob("*/03_bitstreams"))
            for s in ids:
                p = tim[(tim.method_id == NEW) & (tim.sample_id == s)].bitstream_path.iloc[0]
                f = next((rd.parent / p for rd in run_dirs if (rd.parent / p).exists()), None)
                if f is None:
                    continue
                cl = crackle.component_lengths(f.read_bytes())
                tot = sum(cl.values())
                for k in shares:
                    shares[k].append(cl[k] / tot)
            num["sections"][ds] = {k: {"median": st.median(v), "min": min(v), "max": max(v), "n": len(v)}
                                   for k, v in shares.items() if v}
            led(f"S-{ds}", "section shares of CAPE streams", json.dumps({k: v["median"] for k, v in
                                                                      num["sections"][ds].items()}),
                "results/<run>/03_bitstreams/*.bin (stored CAPE streams)", "crackle.component_lengths", ds,
                num["sections"][ds]["labels"]["n"], "-", "section bytes / stream bytes", "-", "median over volumes",
                "derived")
        except ImportError:
            num["sections"][ds] = None
        # ---- lossless / byte equality ----
        num["lossless"][ds] = A["lossless"]
        num["oracle"][ds] = A["oracle"]
        # ---- profile ----
        pp = RAW / f"profile_{ds}_results.csv"
        if pp.exists():
            pr = pd.read_csv(pp, low_memory=False)
            exs = [json.loads(e) for e in pr[pr.status == "OK"].extra_json.dropna()]
            tot = sum(e.get("encode_core_ns") or 0 for e in exs)
            groups = {"boundaries": ["scan_ns", "boundary_ns"], "cc2d": ["cc_ns", "transpose_ns"], "runs": ["runs_ns"],
                      "candidates": ["candidate_ns"], "reductions": ["reduction_ns"],
                      "solver": ["component_ns", "greedy_ns", "dual_ns", "pass1_ns", "dp_ns", "local_ns", "pass2_ns"],
                      "serializer": ["serialize_ns"]}
            num["profile"][ds] = {g: sum(sum(e.get(k) or 0 for k in ks) for e in exs) / tot for g, ks in groups.items()}
            num["profile"][ds]["n_rows"] = len(exs)
            led(f"P-{ds}", "CAPE phase shares", json.dumps(num["profile"][ds]),
                f"maqola uchun/raw_results/profile_{ds}_results.csv", "extra_json.*_ns / encode_core_ns", ds, len(exs),
                "-", "phase time / native encode time", "-", "pooled over profile rows", "measured",
                "separate instrumented profile build and run; not the timed rows")
    # ---- CP-SAT oracle details (per run) ----
    for ds in ["j0126", "snemi"]:
        f = ROOT / an["datasets"][ds]["run_dir"] / "06_solver_certificates" / "oracle_audit.csv"
        if f.exists():
            o = pd.read_csv(f)
            h = o[o.cape_status == "Heuristic"]
            num["oracle"][ds] = dict(num["oracle"][ds] or {}, volumes=int(o.sample_id.nunique()),
                                     n_cc_min=int(o.n_cc.min()), n_cc_max=int(o.n_cc.max()),
                                     status_counts=o.cape_status.value_counts().to_dict(),
                                     heuristic_at_opt=int((h.cape_ub == h.cpsat_optimum).sum()),
                                     heuristic_excess_bytes=int((h.cape_ub - h.cpsat_optimum).sum()),
                                     lb_le_opt=bool((o.cape_lb <= o.cpsat_optimum).all()))
            led(f"O-{ds}", "CP-SAT component audit", json.dumps(num["oracle"][ds]), str(f.relative_to(ROOT)),
                "cape_status, cape_ub, cape_lb, cpsat_status, cpsat_optimum", ds, len(o), "OR-Tools CP-SAT 9.15",
                "OPTIMAL = proven optimum within 20 s; checks LB <= OPT, exact components UB == OPT",
                "-", "counts", "measured", "audit run outside timing; first 200 exported components (<= 60 CCs) "
                                           "in sample-id order")
    # ---- scale panel: SNEMI3D full volume and its 4 quadrants (one acquisition; descriptive; revision) ----
    sc_rows = []
    for f in ("scale", "scale_stock"):
        d = pd.read_csv(RAW / f"{f}_results.csv", low_memory=False)
        d = d[(d.status == "OK") & (d.wrapper.fillna("none") == "none")]
        t_ = d[d.panel != "MEM"]
        m_ = d[d.panel == "MEM"].copy()
        m_["peak_enc"] = [json.loads(x).get("peak_after_encode") for x in m_.extra_json]
        m_["peak_pre"] = [json.loads(x).get("peak_before_encode") for x in m_.extra_json]
        for (s_, mid), g in t_.groupby(["sample_id", "method_id"]):
            mm_ = m_[(m_.sample_id == s_) & (m_.method_id == mid)]
            sc_rows.append({"track": f, "sample_id": s_, "method": mid, "voxels": float(np.prod(json.loads(g.canonical_shape.iloc[0]))),
                            "t_ms": float(g.encode_ns.median() / 1e6), "bytes": int(g.total_bytes.median()),
                            "decode_ms": float(g.decode_ns.median() / 1e6),
                            "peak_mib": float(mm_.peak_enc.iloc[0] / 2**20) if len(mm_) else None,
                            "pre_mib": float(mm_.peak_pre.iloc[0] / 2**20) if len(mm_) else None,
                            "repeats": int(len(g)), "sha": g.bitstream_sha256.iloc[0]})
    sc = pd.DataFrame(sc_rows)
    sc.to_csv(FIGDATA / "scale_panel.csv", index=False)
    names = {NEW: "cape", "crackle_pins_opt_corrected_m0": "corr", FLAT: "flat", "cape_v3frozen_fast_m0": "vthree"}
    for _, r in sc[sc.method.isin(names)].iterrows():
        if r.track == "scale_stock" and r.method != "crackle_pins_opt_corrected_m0":
            continue
        thr_rows.append({"dataset": "snemi_scale", "sample_id": r.sample_id, "method": names[r.method],
                         "voxels": r.voxels, "t_ms": r.t_ms, "mvox_per_s": r.voxels / (r.t_ms / 1e3) / 1e6})
    cape_sc = sc[(sc.method == NEW) & (sc.track == "scale")].set_index("sample_id")
    corr_sc = sc[sc.method == "crackle_pins_opt_corrected_m0"].set_index("sample_id")
    flat_sc = sc[(sc.method == FLAT) & (sc.track == "scale")].set_index("sample_id")
    cape_st = sc[(sc.method == NEW) & (sc.track == "scale_stock")].set_index("sample_id")
    quads = sorted(corr_sc.index)
    full = [s_ for s_ in cape_sc.index if "full" in s_][0]
    num["scale"] = {
        "full_sample": full, "full_voxels": float(cape_sc.voxels[full]), "quadrant_voxels": float(cape_sc.voxels[quads[0]]),
        "n_quadrants": len(quads), "repeats": int(cape_sc.repeats.min()),
        "full_cape_t_ms": float(cape_sc.t_ms[full]), "full_flat_t_ms": float(flat_sc.t_ms[full]),
        "full_cape_peak_mib": float(cape_sc.peak_mib[full]), "full_flat_peak_mib": float(flat_sc.peak_mib[full]),
        "full_cape_mvox_s": float(cape_sc.voxels[full] / cape_sc.t_ms[full] * 1e-3),
        "full_size_change_vs_flat_pct": float(100 * (cape_sc.bytes[full] / flat_sc.bytes[full] - 1)),
        "quad_speedup_vs_corr_min": float(min(corr_sc.t_ms[q] / cape_st.t_ms[q] for q in quads)),
        "quad_speedup_vs_corr_max": float(max(corr_sc.t_ms[q] / cape_st.t_ms[q] for q in quads)),
        "quad_peak_ratio_vs_corr_min": float(min(cape_st.peak_mib[q] / corr_sc.peak_mib[q] for q in quads)),
        "quad_peak_ratio_vs_corr_max": float(max(cape_st.peak_mib[q] / corr_sc.peak_mib[q] for q in quads)),
        "quad_cape_mvox_s_median": float(np.median([cape_st.voxels[q] / cape_st.t_ms[q] * 1e-3 for q in quads])),
        "quad_corr_mvox_s_median": float(np.median([corr_sc.voxels[q] / corr_sc.t_ms[q] * 1e-3 for q in quads])),
        "quad_size_change_vs_corr_pct": float(100 * (sum(cape_st.bytes[q] for q in quads) / sum(corr_sc.bytes[q] for q in quads) - 1)),
        "quad_bytes_smaller": int(sum(cape_st.bytes[q] < corr_sc.bytes[q] for q in quads))}
    led("SC", "scale panel: SNEMI3D full volume and quadrants (descriptive, 3 repeats)", json.dumps(num["scale"]),
        "maqola uchun/raw_results/scale_results.csv; scale_stock_results.csv", "encode_ns, total_bytes, peak_after_encode",
        "snemi (scale)", 1 + len(quads), "pins_opt corrected (quadrants only, size budget), flat",
        "speed-up T_comp/T_CAPE; peak ratio M_CAPE/M_comp; throughput voxels/T", "-", "per sample, min/max over quadrants",
        "measured")
    pd.DataFrame(thr_rows).to_csv(FIGDATA / "throughput.csv", index=False)
    # ---- exact whole-volume optimum (revision; scripts/exact_optimum.py, CP-SAT, no timing) ----
    ex_path = OUT / "exact_optimum.json"
    if ex_path.exists():
        EX = json.loads(ex_path.read_text(encoding="utf-8"))
        num["exact"] = {}
        gap_rows = []
        for ds, rows in EX.items():
            exc = [100 * (r["U"] - r["OPT_hi"]) / r["U"] for r in rows]
            gapv = [100 * (r["U"] - r["L"]) / r["U"] for r in rows]
            num["exact"][ds] = {
                "n": len(rows), "exact": sum(r["exact"] for r in rows),
                "same_stream": sum(r["same_stream_as_evaluated"] for r in rows),
                "bg_proven": sum(bool(r["bg_optimal_proven"]) for r in rows),
                "components_solved": sum(r["components_solved"] for r in rows),
                "components_optimal": sum(r["solver_status"].get("OPTIMAL", 0) for r in rows),
                "u_equals_opt": sum(r["U"] == r["OPT_hi"] for r in rows),
                "excess_median": float(np.median(exc)), "excess_max": float(max(exc)),
                "excess_q1": float(np.quantile(exc, .25)), "excess_q3": float(np.quantile(exc, .75)),
                "excess_bytes_total": int(sum(r["U"] - r["OPT_hi"] for r in rows)),
                "label_bytes_total": int(sum(r["U"] for r in rows)),
                "excess_pooled": float(100 * sum(r["U"] - r["OPT_hi"] for r in rows) / sum(r["U"] for r in rows)),
                "count_width_resolved": sum(1 for r in rows if r["count_width_resolution"]),
                "one_byte_cheaper": sum(1 for r in rows if r["count_width_resolution"]
                                        and r["count_width_resolution"]["one_byte_optimal"] and r["w_N_cape"] == 2),
                "count_width_excess_bytes": int(sum(r["count_width_resolution"]["two_byte_hi"] - r["OPT_hi"]
                                                    for r in rows if r["count_width_resolution"]
                                                    and r["count_width_resolution"]["one_byte_optimal"])),
                "bound_share_of_gap_median": float(np.median([(r["U"] - r["OPT_hi"]) / (r["U"] - r["L"])
                                                              for r in rows if r["U"] > r["L"]]))}
            for r, e, gv in zip(rows, exc, gapv):
                gap_rows.append({"dataset": ds, "sample_id": r["sample_id"], "excess_pct": e, "bound_gap_pct": gv,
                                 "U": r["U"], "OPT": r["OPT_hi"], "L": r["L"]})
            led(f"X-{ds}", "exact whole-volume optimum of the serialized label section", json.dumps(num["exact"][ds]),
                "evidence/exact_optimum.json (scripts/exact_optimum.py)", "U, OPT_lo = OPT_hi, L per volume", ds, len(rows),
                "CP-SAT (OR-Tools) on every exported component; trivial components exact; background via dual bound",
                "true excess (U - OPT)/U; bound gap (U - L)/U", "U = written label section", "median [IQR], max over volumes",
                "measured", "re-encoding with component export (stream SHA-256 equal to the frozen run); no timing")
        pd.DataFrame(gap_rows).to_csv(FIGDATA / "exact_gaps.csv", index=False)
    pd.DataFrame(pervol_rows).to_csv(FIGDATA / "per_volume_ratios.csv", index=False)
    (OUT / "numbers.json").write_text(json.dumps(num, indent=1, default=float), encoding="utf-8")
    with open(OUT / "evidence_ledger.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ledger[0]))
        w.writeheader()
        w.writerows(ledger)
    print(f"numbers.json, {len(ledger)} ledger rows, {len(pervol_rows)} per-volume rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
