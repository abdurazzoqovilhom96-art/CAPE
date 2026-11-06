"""v2.1: where did the v1 -> v2 encode speed-up come from? (plan v2.1, B4.1)

    python scripts/speedup_attribution.py                 # timing factorial + verification + analysis
    python scripts/speedup_attribution.py --memory        # also peak working set, fresh process per cell
    python scripts/speedup_attribution.py --analyze-only  # rebuild tables/figures from raw.csv

Factors (cpp/include/cape/types.hpp ImplBit; every implementation combination writes identical bytes):
  L  column-major chain layout (blocked transpose, z-major CC released) + one-pass runs   [code]
  H  multiply-add chain hash instead of mix64 per element                                  [code]
  T  open-addressing equal-coverage grouping instead of a full sort                        [algorithmic]
  S  exact DP over reachable states only                                                   [algorithmic]
  D  FAST product decision: depth regimes off (fixed full depth width); may change bytes   [search space]
Full 2^5 factorial; extra contrasts: fast without one-pass runs (splits L), and the exact v1 configuration
(legacy, depth regimes on, certificate "regime") to show that the certificate flag itself costs nothing.

Protocol: one process pinned to the timing CPU of cape.resources.timing_cpu() (the run_all policy), gc off
while timing, one warm-up of every cell, then R repeats with the cell order shuffled per repeat (seeded).
Development data only (CREMI A pilot crops and the Crackle width crops). Bytes: every implementation
combination must reproduce the reference stream of its D value (SHA-256); one decode per (sample, D)
with PyPI crackle must be voxel-identical. Analysis: exact Shapley decomposition of log(T_legacy/T_fast)
over the five factors, add-one / drop-one contrasts, per-stage effects, cluster bootstrap over macroblocks.
Output: analysis/v21_speedup/.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import itertools
import json
import math
import os
import statistics as st
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape.canonical import crackle_view, from_xyz  # noqa: E402
from cape.dataset_manifest import load_manifest  # noqa: E402
from cape.io import load_canonical  # noqa: E402

FACTORS = ["L", "H", "T", "S", "D"]
FACTOR_INFO = {
    "L": ("column-major layout + one-pass runs", "code"),
    "H": ("multiply-add chain hash", "code"),
    "T": ("hash-table equal-coverage grouping", "algorithmic"),
    "S": ("reachable-state exact DP", "algorithmic"),
    "D": ("depth regimes off (FAST)", "search_space"),
}
BIT = {"L": 1 | 2, "H": 4, "T": 8, "S": 16}
STAGES = ["scan_ns", "boundary_ns", "cc_ns", "transpose_ns", "runs_ns", "candidate_ns", "reduction_singleton_ns",
          "reduction_equal_hash_ns", "reduction_equal_sort_ns", "reduction_subset_incidence_ns",
          "reduction_subset_scan_ns", "component_ns", "greedy_ns", "dual_ns", "dp_ns", "local_ns", "serialize_ns"]
COUNTS = ["voxels", "cc_count", "run_count", "candidate_count_before", "candidate_count_after", "incidence_count",
          "component_count", "max_component_cc", "dp_components_solved", "dp_transitions", "regime_w_D"]
BASE = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape", "certificate": "off"}
DEFAULT_MANIFESTS = ["data/manifests/pilot.jsonl", "data/manifests/width_sensitivity.jsonl"]
SEED = 20261106


def cells() -> list[dict]:
    out = []
    for bits in itertools.product((0, 1), repeat=5):
        on = {f for f, b in zip(FACTORS, bits) if b}
        mask = sum(BIT[f] for f in on if f in BIT)
        out.append({"cell": "".join(f if f in on else "-" for f in FACTORS), "factors": "".join(sorted(on)),
                    "impl_mask": mask, "depth_policy": "fixed_depth_width" if "D" in on else "full_width_first",
                    "certificate": "off", "kind": "factorial"})
    out.append({"cell": "fast_noR", "factors": "HTSD+L-R", "impl_mask": 31 & ~2, "depth_policy": "fixed_depth_width",
                "certificate": "off", "kind": "contrast"})
    out.append({"cell": "v1_exact", "factors": "", "impl_mask": 0, "depth_policy": "full_width_first",
                "certificate": "regime", "kind": "contrast"})
    return out


def opts_for(c: dict) -> dict:
    return dict(BASE, impl_mask=c["impl_mask"], depth_policy=c["depth_policy"], certificate=c["certificate"])


def group_of(row: dict) -> str:
    return "cremi_A" if row["family_id"] == "cremi" else row["family_id"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------- measurement
def pin() -> dict:
    from cape import resources

    t = resources.timing_cpu()
    ok = resources.pin_current_process(t.get("cpu"))
    return {"cpu": t.get("cpu"), "pinned": ok, "reason": t.get("reason")}


def measure(rows: list[dict], out: Path, rep_small: int, rep_large: int) -> None:
    import crackle

    from cape import _cape_native as cn

    pinning = pin()
    rng = np.random.default_rng(SEED)
    cl = cells()
    raw_f = open(out / "raw.csv", "w", encoding="utf-8", newline="")
    raw_w = None
    ver_rows = []
    for si, r in enumerate(rows):
        arr = load_canonical(ROOT / r["path"])
        view = crackle_view(arr)
        large = arr.size >= (1 << 24)
        reps = rep_large if large else rep_small
        ref_sha: dict[str, str] = {}
        cell_sha: dict[str, str] = {}
        diag_by_cell: dict[str, dict] = {}
        # warm-up of every cell (also: bytes, verification, counts)
        for c in cl:
            buf, diag = cn.encode(view, opts_for(c))
            cell_sha[c["cell"]] = hashlib.sha256(buf).hexdigest()
            diag_by_cell[c["cell"]] = diag
            dkey = c["depth_policy"]
            if c["impl_mask"] == 31 and c["kind"] == "factorial":
                ref_sha[dkey] = cell_sha[c["cell"]]
                dec = from_xyz(crackle.decompress(buf, parallel=1))
                ver_rows.append({"sample_id": r["sample_id"], "depth_policy": dkey, "bytes": len(buf),
                                 "sha256": cell_sha[c["cell"]], "decode_voxel_identical": bool(np.array_equal(dec, arr))})
                del dec
        for c in cl:
            ok = cell_sha[c["cell"]] == ref_sha[c["depth_policy"]]
            ver_rows.append({"sample_id": r["sample_id"], "depth_policy": c["depth_policy"], "cell": c["cell"],
                             "bytes_identical_to_reference": ok})
            if not ok:
                print(f"FAIL bytes: {r['sample_id']} {c['cell']}", file=sys.stderr, flush=True)
        gc.collect()
        gc.disable()
        try:
            for rep in range(reps):
                for k in rng.permutation(len(cl)):
                    c = cl[k]
                    o = opts_for(c)
                    t0 = time.perf_counter_ns()
                    buf, diag = cn.encode(view, o)
                    t1 = time.perf_counter_ns()
                    rec = {"sample_id": r["sample_id"], "group": group_of(r), "macroblock_id": r["macroblock_id"],
                           "shape": "x".join(map(str, r["shape"])), "voxels": arr.size, "cell": c["cell"],
                           "kind": c["kind"], "factors": c["factors"], "impl_mask": c["impl_mask"],
                           "depth_policy": c["depth_policy"], "certificate": c["certificate"], "repeat": rep,
                           "wall_ns": t1 - t0, "bytes": len(buf),
                           "sha_ok": cell_sha[c["cell"]] == ref_sha[c["depth_policy"]],
                           **{s: diag.get(s, 0) for s in STAGES}, "encode_core_ns": diag.get("encode_core_ns"),
                           **{k2: diag.get(k2) for k2 in COUNTS}}
                    if raw_w is None:
                        raw_w = csv.DictWriter(raw_f, fieldnames=list(rec))
                        raw_w.writeheader()
                    raw_w.writerow(rec)
                    del buf
                raw_f.flush()
        finally:
            gc.enable()
        print(f"[{si + 1}/{len(rows)}] {r['sample_id']} reps={reps} done {now()}", flush=True)
        del view, arr
        gc.collect()
    raw_f.close()
    with open(out / "verification.csv", "w", encoding="utf-8", newline="") as fh:
        keys = sorted({k for v in ver_rows for k in v})
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(ver_rows)
    (out / "protocol.json").write_text(json.dumps({
        "generated_at": now(), "pinning": pinning, "repeats_small": rep_small, "repeats_large": rep_large,
        "large_threshold_voxels": 1 << 24, "seed": SEED, "cells": cl, "base_options": BASE,
        "samples": [r["sample_id"] for r in rows]}, indent=2), encoding="utf-8")


MEM_CELLS = ["-----", "L----", "LHTSD", "----D", "LHTS-"]  # legacy, L only, v2 FAST, legacy+D, v2 impl with regimes


def mem_child(path: str, cell: str) -> None:
    from cape import _cape_native as cn
    from cape import resources

    c = next(x for x in cells() if x["cell"] == cell)
    arr = load_canonical(path)
    view = crackle_view(arr)
    before = resources.process_peak_rss()
    buf, _ = cn.encode(view, opts_for(c))
    after = resources.process_peak_rss()
    print(json.dumps({"input_bytes": int(arr.nbytes), "peak_before": before["peak_rss_bytes"],
                      "rss_before": before["rss_bytes"], "peak_after": after["peak_rss_bytes"],
                      "mode": after["mode"], "bytes": len(buf)}))


def measure_memory(rows: list[dict], out: Path) -> None:
    res = []
    for r in rows:
        if int(np.prod(r["shape"])) < (1 << 24):
            continue
        for cell in MEM_CELLS:
            p = subprocess.run([sys.executable, str(Path(__file__)), "--mem-child", r["path"], cell],
                               capture_output=True, text=True, cwd=ROOT, timeout=3600)
            if p.returncode != 0:
                res.append({"sample_id": r["sample_id"], "cell": cell, "status": "FAILED", "reason": p.stderr[-300:]})
                continue
            d = json.loads(p.stdout.strip().splitlines()[-1])
            grew = d["peak_after"] > d["peak_before"]
            res.append({"sample_id": r["sample_id"], "cell": cell, "status": "OK", **d,
                        "encode_extra_peak_bytes": (d["peak_after"] - d["rss_before"]) if grew else None,
                        "peak_grew_during_encode": grew})
            print(f"mem {r['sample_id']} {cell} peak={d['peak_after'] >> 20} MiB", flush=True)
    with open(out / "memory.csv", "w", encoding="utf-8", newline="") as fh:
        keys = sorted({k for v in res for k in v})
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(res)


# --------------------------------------------------------------------------------------- analysis
def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def shapley(f: dict[frozenset, float]) -> dict[str, float]:
    """phi_i = sum_S |S|!(n-|S|-1)!/n! [f(S) - f(S+i)]: positive = factor i lowers log time."""
    n = len(FACTORS)
    phi = {}
    for i in FACTORS:
        others = [x for x in FACTORS if x != i]
        tot = 0.0
        for k in range(n):
            w = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
            for S in itertools.combinations(others, k):
                s = frozenset(S)
                tot += w * (f[s] - f[s | {i}])
        phi[i] = tot
    return phi


def bootstrap_mean(vals_by_cluster: dict[str, list[float]], n: int = 10000, seed: int = SEED):
    keys = sorted(vals_by_cluster)
    if len(keys) < 3:
        return None, None
    rng = np.random.default_rng(seed)
    arrs = [np.asarray(vals_by_cluster[k]) for k in keys]
    means = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        means.append(float(np.mean(np.concatenate([arrs[p] for p in pick]))))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def analyze(out: Path) -> dict:
    rows = list(csv.DictReader(open(out / "raw.csv", encoding="utf-8")))
    ver = list(csv.DictReader(open(out / "verification.csv", encoding="utf-8")))
    bad_bytes = [v for v in ver if v.get("bytes_identical_to_reference") == "False"]
    bad_decode = [v for v in ver if v.get("decode_voxel_identical") == "False"]
    med: dict[tuple, dict] = {}
    by = {}
    for r in rows:
        by.setdefault((r["sample_id"], r["cell"]), []).append(r)
    meta = {}
    for (sid, cell), rs in by.items():
        m = {"wall_ns": st.median(int(x["wall_ns"]) for x in rs), "n": len(rs)}
        for s in STAGES:
            m[s] = st.median(_num(x[s]) or 0 for x in rs)
        med[(sid, cell)] = m
        meta[sid] = {"group": rs[0]["group"], "macroblock_id": rs[0]["macroblock_id"], "shape": rs[0]["shape"],
                     "voxels": int(rs[0]["voxels"]), **{k: _num(rs[0][k]) for k in COUNTS}}
    sids = sorted(meta)
    fact_cells = [c for c in cells() if c["kind"] == "factorial"]
    per_sample = []
    stage_effect = {f: {s: [] for s in STAGES} for f in FACTORS}
    contrasts = []
    for sid in sids:
        f = {frozenset(c["factors"]): math.log(med[(sid, c["cell"])]["wall_ns"]) for c in fact_cells}
        phi = shapley(f)
        total = f[frozenset()] - f[frozenset(FACTORS)]
        resid = total - sum(phi.values())
        rec = {"sample_id": sid, **meta[sid], "t_legacy_ms": med[(sid, "-----")]["wall_ns"] / 1e6,
               "t_fast_ms": med[(sid, "LHTSD")]["wall_ns"] / 1e6,
               "t_v1_exact_ms": med[(sid, "v1_exact")]["wall_ns"] / 1e6,
               "t_v2_impl_regimes_ms": med[(sid, "LHTS-")]["wall_ns"] / 1e6,
               "t_fast_noR_ms": med[(sid, "fast_noR")]["wall_ns"] / 1e6,
               "log_speedup_total": total, "shapley_residual": resid, **{f"phi_{k}": v for k, v in phi.items()}}
        per_sample.append(rec)
        for i in FACTORS:
            add = f[frozenset()] - f[frozenset({i})]
            drop = f[frozenset(FACTORS) - {i}] - f[frozenset(FACTORS)]
            contrasts.append({"sample_id": sid, "group": meta[sid]["group"], "factor": i, "add_one_to_legacy": add,
                              "drop_one_from_fast": drop, "shapley": phi[i]})
            for c in fact_cells:
                if i in c["factors"]:
                    continue
                c2 = next(x for x in fact_cells if set(x["factors"]) == set(c["factors"]) | {i})
                for s in STAGES:
                    stage_effect[i][s].append((meta[sid]["group"], med[(sid, c["cell"])][s] - med[(sid, c2["cell"])][s]))
    groups = sorted({m["group"] for m in meta.values()})
    agg = []
    for g in groups:
        ps = [p for p in per_sample if p["group"] == g]
        for i in FACTORS + ["total"]:
            key = "log_speedup_total" if i == "total" else f"phi_{i}"
            vals = [p[key] for p in ps]
            clusters = {}
            for p in ps:
                clusters.setdefault(p["macroblock_id"], []).append(p[key])
            lo, hi = bootstrap_mean(clusters)
            tot = st.mean(p["log_speedup_total"] for p in ps)
            agg.append({"group": g, "factor": i, "label": FACTOR_INFO.get(i, ("v1 -> v2 FAST", "total"))[0],
                        "class": FACTOR_INFO.get(i, ("", "total"))[1], "n_samples": len(ps),
                        "n_clusters": len(clusters), "mean_log": st.mean(vals), "factor_x": math.exp(st.mean(vals)),
                        "share_of_total": st.mean(vals) / tot if tot else None,
                        "ci_lo_x": math.exp(lo) if lo is not None else None,
                        "ci_hi_x": math.exp(hi) if hi is not None else None})
    stage_rows = []
    for i in FACTORS:
        for g in groups:
            for s in STAGES:
                vals = [v for gg, v in stage_effect[i][s] if gg == g]
                if vals:
                    stage_rows.append({"factor": i, "group": g, "stage": s, "median_saved_ms": st.median(vals) / 1e6,
                                       "mean_saved_ms": st.mean(vals) / 1e6})
    stage_profile = []
    for sid in sids:
        for cell in ("v1_exact", "-----", "L----", "LHTS-", "LHTSD"):
            stage_profile.append({"sample_id": sid, "group": meta[sid]["group"], "cell": cell,
                                  "wall_ms": med[(sid, cell)]["wall_ns"] / 1e6,
                                  **{s: med[(sid, cell)][s] / 1e6 for s in STAGES}})

    def wcsv(name, rs):
        if not rs:
            return
        keys = list(rs[0])
        for r in rs:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with open(out / name, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rs)

    wcsv("per_sample.csv", per_sample)
    wcsv("shapley_summary.csv", agg)
    wcsv("contrasts.csv", contrasts)
    wcsv("stage_effects.csv", stage_rows)
    wcsv("stage_profile.csv", stage_profile)
    summary = {
        "generated_at": now(), "n_samples": len(sids), "groups": groups,
        "bytes_identical_all": not bad_bytes, "bytes_mismatches": len(bad_bytes),
        "decode_voxel_identical_all": not bad_decode, "decode_failures": len(bad_decode),
        "max_abs_shapley_residual": max(abs(p["shapley_residual"]) for p in per_sample) if per_sample else None,
        "shapley": agg,
        "classes": {g: {cls: sum(a["mean_log"] for a in agg if a["group"] == g and a["class"] == cls)
                        for cls in ("code", "algorithmic", "search_space")} for g in groups},
        "certificate_cost_v1_exact_vs_legacy": {
            g: math.exp(st.mean(math.log(p["t_v1_exact_ms"] / p["t_legacy_ms"]) for p in per_sample if p["group"] == g))
            for g in groups},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plots(out, agg, stage_rows, stage_profile, groups)
    return summary


def plots(out: Path, agg, stage_rows, stage_profile, groups) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir, pd_dir = out / "figures", out / "plot_data"
    fig_dir.mkdir(exist_ok=True)
    pd_dir.mkdir(exist_ok=True)
    colors = {"code": "#2a78d6", "algorithmic": "#eb6834", "search_space": "#8a8984"}  # palette slots 1, 2 + neutral
    # F1: Shapley factor per group (x speed-up factor, log axis)
    fig, axes = plt.subplots(1, len(groups), figsize=(5.2 * len(groups), 3.6), squeeze=False)
    rows_pd = []
    for ax, g in zip(axes[0], groups):
        a = [x for x in agg if x["group"] == g and x["factor"] != "total"]
        ys = range(len(a))
        for y, x in zip(ys, a):
            ax.barh(y, x["factor_x"] - 1, left=1, color=colors[x["class"]], height=0.6)
            if x["ci_lo_x"] is not None:
                ax.plot([x["ci_lo_x"], x["ci_hi_x"]], [y, y], color="#222", lw=1)
            ax.text(max(x["factor_x"], 1) * 1.01, y, f"{x['factor_x']:.2f}x", va="center", fontsize=8)
            rows_pd.append({"group": g, **x})
        ax.set_yticks(list(ys), [f"{x['factor']}: {x['label']}" for x in a], fontsize=8)
        tot = next(x for x in agg if x["group"] == g and x["factor"] == "total")
        ax.set_title(f"{g}: v1 legacy -> v2 FAST {tot['factor_x']:.2f}x", fontsize=9)
        ax.axvline(1, color="#888", lw=0.8)
        ax.set_xlabel("speed-up factor attributed (Shapley, geo-mean)", fontsize=8)
        ax.invert_yaxis()
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    fig.legend(handles, ["code optimization", "algorithmic", "search space (FAST)"], loc="lower center", ncol=3,
               fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(fig_dir / "V21_S1_shapley.png", dpi=150)
    plt.close(fig)
    _write_pd(pd_dir / "V21_S1_shapley.csv", rows_pd)
    # F2: stage profile legacy vs fast (median over samples), per group
    fig, axes = plt.subplots(1, len(groups), figsize=(5.2 * len(groups), 3.8), squeeze=False)
    rows_pd = []
    main = ["boundary_ns", "cc_ns", "transpose_ns", "runs_ns", "candidate_ns", "reduction_equal_hash_ns",
            "reduction_equal_sort_ns", "reduction_subset_incidence_ns", "reduction_subset_scan_ns", "component_ns",
            "greedy_ns", "dual_ns", "dp_ns", "local_ns"]
    palette = plt.get_cmap("tab20").colors
    for ax, g in zip(axes[0], groups):
        cells_ = ["v1_exact", "-----", "L----", "LHTS-", "LHTSD"]
        for xi, cell in enumerate(cells_):
            ps = [p for p in stage_profile if p["group"] == g and p["cell"] == cell]
            bottom = 0.0
            for si, s in enumerate(main):
                v = st.median(p[s] for p in ps)
                ax.bar(xi, v, bottom=bottom, color=palette[si % 20], width=0.6,
                       label=s.replace("_ns", "") if xi == 0 else None)
                rows_pd.append({"group": g, "cell": cell, "stage": s, "median_ms": v})
                bottom += v
        ax.set_xticks(range(len(cells_)), ["v1 exact", "legacy\n(-----)", "+L", "v2 impl\n+regimes", "v2 FAST"],
                      fontsize=8)
        ax.set_ylabel("median stage time (ms)", fontsize=8)
        ax.set_title(g, fontsize=9)
    axes[0][-1].legend(fontsize=6, loc="upper right", ncol=2)
    fig.tight_layout()
    fig.savefig(fig_dir / "V21_S2_stage_profile.png", dpi=150)
    plt.close(fig)
    _write_pd(pd_dir / "V21_S2_stage_profile.csv", rows_pd)


def _write_pd(p: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifests", nargs="+", default=DEFAULT_MANIFESTS)
    ap.add_argument("--repeats-small", type=int, default=7)
    ap.add_argument("--repeats-large", type=int, default=3)
    ap.add_argument("--out", default="analysis/v21_speedup")
    ap.add_argument("--memory", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--mem-child", nargs=2, metavar=("PATH", "CELL"))
    args = ap.parse_args(argv)
    if args.mem_child:
        mem_child(*args.mem_child)
        return 0
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in args.manifests:
        rows += [r for r in load_manifest(ROOT / m) if not r["is_synthetic"] and r["split"] == "development"]
    if not rows:
        print("BLOCKED_DATA: no development samples in the manifests", file=sys.stderr)
        return 2
    if not args.analyze_only:
        measure(rows, out, args.repeats_small, args.repeats_large)
        if args.memory:
            measure_memory(rows, out)
    s = analyze(out)
    print(json.dumps({k: s[k] for k in ("n_samples", "bytes_identical_all", "decode_voxel_identical_all",
                                         "max_abs_shapley_residual", "classes")}, indent=1))
    return 0 if s["bytes_identical_all"] and s["decode_voxel_identical_all"] else 1


if __name__ == "__main__":
    sys.exit(main())
