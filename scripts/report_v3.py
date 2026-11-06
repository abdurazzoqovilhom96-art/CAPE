"""CAPE v3 stage ANALYZE (plan CAPE v3, sections 14, 17, 18): every number from raw run files.

    python scripts/report_v3.py --state analysis/v3_state.json

Outputs (analysis/v3_final/): V3_YAKUNIY_TAHLIL_UZ.md, V3_FINAL_ANALYSIS_EN.md, claim_ledger.csv, primary_family.csv,
tables/*.csv|md|tex, plot_data/*.csv, figures/*.png|svg, v3_summary.json. Exit 0 on success, 2 when an input is missing.
Statuses of the ten questions: PASS / PARTIAL / FAIL / NOT_TESTED. They are never added up into a score.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from v3_common import bootstrap_p, ci_fmt, fmt, holm, load_cells, paired, write_csv  # noqa: E402

OUT = ROOT / "analysis" / "v3_final"
FIG = OUT / "figures"
PD = OUT / "plot_data"
TAB = OUT / "tables"
STOCK = "crackle_pins_opt_corrected_m0"
V21 = "cape_v21_fast_m0"
V3 = "cape_v3_fast_m0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mb_cluster(c):
    return str(c["macroblock_id"] or c["sample_id"])


def dev_cluster(c):
    if str(c["sample_id"]).startswith("scale_"):
        return "scale:" + str(c["source_id"])
    return mb_cluster(c)


# ------------------------------------------------------------------------------------------------ tables
def write_table(name: str, rows: list[dict], cols: list[tuple[str, str]], caption: str) -> str:
    """CSV + Markdown + LaTeX; returns the Markdown."""
    write_csv(TAB / f"{name}.csv", rows)
    md = [f"| {' | '.join(h for _, h in cols)} |", "|" + "---|" * len(cols)]
    for r in rows:
        md.append("| " + " | ".join(str(r.get(k, "")) for k, _ in cols) + " |")
    text = "\n".join(md)
    (TAB / f"{name}.md").write_text(f"{caption}\n\n{text}\n", encoding="utf-8")
    esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")  # noqa: E731
    tex = [r"\begin{table}[t]", r"\centering", r"\small", r"\caption{" + esc(caption) + "}",
           r"\begin{tabular}{" + "l" * len(cols) + "}", r"\hline", " & ".join(esc(h) for _, h in cols) + r" \\", r"\hline"]
    for r in rows:
        tex.append(" & ".join(esc(r.get(k, "")) for k, _ in cols) + r" \\")
    tex += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (TAB / f"{name}.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    return text


def method_table(cells: dict, ref: str, cluster) -> list[dict]:
    rows = []
    methods = sorted({m for _, m in cells})
    samples = sorted({s for s, _ in cells})
    for m in methods:
        cs = [cells[(s, m)] for s in samples if (s, m) in cells]
        st = Counter()
        for c in cs:
            st.update(c["statuses"])
        ok = [c for c in cs if c["n_ok"] and c["total_bytes"] is not None]
        row = {"method": m, "n_ok": len(ok), "n_samples": len(cs),
               "statuses": "; ".join(f"{k}:{v}" for k, v in sorted(st.items()))}
        if ok:
            tb = sum(c["total_bytes"] for c in ok)
            vox = sum(c["voxels"] or 0 for c in ok)
            row.update(total_bytes=tb, bpv=fmt(8 * tb / vox, 4) if vox else "NA",
                       enc_ms_sum=fmt(sum(c["enc_med"] for c in ok) / 1e6, 1),
                       dec_ms_sum=fmt(sum(c["dec_med"] for c in ok) / 1e6, 1),
                       peak_mib_median=fmt(float(np.median([c["peak"] for c in ok if c["peak"]])) / 2**20, 0)
                       if any(c["peak"] for c in ok) else "NA")
            if m != ref and any((c["sample_id"], ref) in cells for c in ok):
                p = paired(cells, m, ref, cluster=cluster, n_boot=2000)
                row.update(ratio_vs_ref=fmt(1 - p.get("G_B", float("nan")), 5) if p.get("n") else "NA",
                           geo_speedup_vs_ref=fmt(p.get("S_T"), 2) if p.get("n") else "NA", n_paired=p.get("n"))
        rows.append(row)
    return rows


# ------------------------------------------------------------------------------------------------ figures
def figures(F: dict) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG.mkdir(parents=True, exist_ok=True)
    PD.mkdir(parents=True, exist_ok=True)
    status = {}

    def save(fig, name, caption, rows):
        write_csv(PD / f"{name}.csv", rows)
        fig.text(0.01, 0.005, caption, fontsize=6.5, wrap=True, va="bottom")
        fig.tight_layout(rect=(0, 0.07, 1, 1))
        for ext in ("png", "svg"):
            fig.savefig(FIG / f"{name}.{ext}", dpi=160)
        plt.close(fig)
        status[name] = {"status": "OK", "rows": len(rows), "caption": caption}

    def guard(name, fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a failed figure is reported, never hidden
            status[name] = {"status": "REPORT_FAILED", "reason": f"{type(exc).__name__}: {exc}"}

    # 1. v3 vs v2.1 paired speed
    def f1():
        rows = []
        for panel, p in (("confirm 32 crops", F["h1"]), ("confirm scale track", F["scale_v3_v21"])):
            for r in p.get("per_sample", []):
                rows.append({"panel": panel, "sample_id": r["sample_id"], "voxels": r["voxels"], "speedup": r["speedup"]})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for panel, mk in (("confirm 32 crops", "o"), ("confirm scale track", "s")):
            xs = [r["voxels"] for r in rows if r["panel"] == panel]
            ys = [r["speedup"] for r in rows if r["panel"] == panel]
            ax.scatter(xs, ys, marker=mk, s=18, label=panel)
        ax.axhline(1.0, color="0.4", lw=0.8)
        ax.set_xscale("log")
        ax.set_xlabel("voxels")
        ax.set_ylabel("encode speed-up v3 FAST / v2.1 FAST (x)")
        ax.legend(fontsize=7)
        h = F["h1"]
        save(fig, "V3_F1_v3_vs_v21_speed",
             f"Fig.1 SNEMI3D confirm (1 source volume; {h.get('n')} crops, {h.get('n_clusters')} macroblock clusters) + scale "
             f"track ({F['scale_v3_v21'].get('n')} volumes, same acquisition). Metric: median-of-repeats encode time ratio "
             f"per sample. Geo S_T = {fmt(h.get('S_T'))} 95% cluster-bootstrap CI {ci_fmt(h.get('S_T_ci'))} (conditional "
             f"on this volume).", rows)

    # 2. size-time Pareto (confirm primary)
    def f2():
        rows = []
        for r in F["main_table"]:
            if r.get("n_ok") and r.get("total_bytes"):
                rows.append({"method": r["method"], "total_bytes": r["total_bytes"], "enc_ms_sum": float(r["enc_ms_sum"])})
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        for r in rows:
            ax.scatter(r["enc_ms_sum"], r["total_bytes"], s=14)
            ax.annotate(r["method"], (r["enc_ms_sum"], r["total_bytes"]), fontsize=5)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("sum of per-crop median encode time (ms)")
        ax.set_ylabel("total stored bytes")
        save(fig, "V3_F2_size_time_pareto", f"Fig.2 SNEMI3D confirm, 32 crops, every method incl. wrappers; raw and "
             f"zstd-wrapped rows together (wrapper in the name). No CI (totals).", rows)

    # 3. matched solver budget-quality
    def f3():
        rows = []
        for src, cells, names in (("dev tracks (CREMI)", F["dev"]["tracks"], ["v3_weighted_greedy_fast_m0",
                                   "v3_greedy_local_fast_m0", "v3_greedy_local_b4_fast_m0", "v3_exact_only_fast_m0",
                                   "cape_v3_all_m0"]),
                                  ("confirm (SNEMI3D)", F["conf"], ["v3_fast_weighted_greedy_m0", "v3_fast_greedy_local_m0",
                                                                   V3])):
            if not cells:
                continue
            base = names[0]
            for m in names:
                p = paired(cells, m, base, n_boot=0)
                if p.get("n"):
                    rows.append({"source": src, "method": m, "bytes_vs_greedy_pct": -p["G_B_pct"],
                                 "time_vs_greedy": 1 / p["S_T"]})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for src, mk in (("dev tracks (CREMI)", "o"), ("confirm (SNEMI3D)", "s")):
            sub = [r for r in rows if r["source"] == src]
            ax.plot([r["time_vs_greedy"] for r in sub], [r["bytes_vs_greedy_pct"] for r in sub], marker=mk, label=src)
            for r in sub:
                ax.annotate(r["method"].replace("_m0", ""), (r["time_vs_greedy"], r["bytes_vs_greedy_pct"]), fontsize=5)
        ax.set_xlabel("encode time / weighted greedy (geo, x)")
        ax.set_ylabel("bytes vs weighted greedy (%)")
        ax.legend(fontsize=7)
        save(fig, "V3_F3_matched_budget_quality", "Fig.3 Matched solvers on the same v3 infrastructure (same runs, "
             "candidates, reductions, components, format rule). Dev: CREMI 36 crops, 3 repeats; confirm: SNEMI3D 32 crops. "
             "Negative = smaller than weighted greedy.", rows)

    # 4. memory vs n
    def f4():
        rows = []
        for src, cells in (("dev scale", F["dev"]["scale"]), ("confirm scale", F["csc"]), ("confirm 32", F["conf"])):
            for (s, m), c in (cells or {}).items():
                if m in (V21, "cape_v3_all_m0", V3, STOCK) and c["peak"]:
                    rows.append({"source": src, "sample_id": s, "method": m, "voxels": c["voxels"],
                                 "peak_mib": c["peak"] / 2**20})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for m in sorted({r["method"] for r in rows}):
            sub = sorted((r for r in rows if r["method"] == m), key=lambda r: r["voxels"])
            ax.scatter([r["voxels"] for r in sub], [r["peak_mib"] for r in sub], s=12, label=m)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("voxels")
        ax.set_ylabel("peak working set (MiB, fresh process)")
        ax.legend(fontsize=6)
        save(fig, "V3_F4_memory_vs_n", "Fig.4 Peak OS working set of one encode+decode in a fresh process (platform "
             "definition: Windows peak working set incl. the input array). Dev scale crops are nested (descriptive); "
             "confirm = SNEMI3D.", rows)

    # 5. reductions / solver stage time
    def f5():
        keys = ["scan_ns", "boundary_ns", "cc_ns", "transpose_ns", "runs_ns", "candidate_ns", "reduction_equal_hash_ns",
                "reduction_equal_sort_ns", "reduction_subset_incidence_ns", "reduction_subset_scan_ns", "component_ns",
                "csr_ns", "pass1_ns", "pass2_ns", "serialize_ns"]
        rows = []
        cells = F["dev"]["scale"] or {}
        big = sorted({s for (s, m) in cells if m == V21}, key=lambda s: -(cells[(s, V21)]["voxels"] or 0))[:4]
        for s in big:
            for m in (V21, "cape_v3_all_m0"):
                c = cells.get((s, m))
                if c:
                    rows.append({"sample_id": s, "method": m, **{k: c["extra"].get(k, 0) / 1e6 for k in keys}})
        fig, ax = plt.subplots(figsize=(7.0, 4.0))
        labels = [f"{r['sample_id'].replace('scale_', '')}\n{'v2.1' if r['method'] == V21 else 'v3'}" for r in rows]
        bottom = np.zeros(len(rows))
        for k in keys:
            vals = np.array([r[k] for r in rows])
            ax.bar(range(len(rows)), vals, bottom=bottom, label=k.replace("_ns", ""))
            bottom += vals
        ax.set_xticks(range(len(rows)))
        ax.set_xticklabels(labels, fontsize=5)
        ax.set_ylabel("ms (one measured encode)")
        ax.legend(fontsize=5, ncol=3)
        save(fig, "V3_F5_stage_time", "Fig.5 Stage times inside one encode (native timers) for the four largest dev "
             "scaling crops, frozen v2.1 vs v3 all bits. Development data (seen), descriptive.", rows)

    # 6. dual pruning benefit / cost
    def f6():
        rows = []
        q = F["dev"]["quality"] or {}
        for (s, m), c in q.items():
            if m in ("cape_v3_regimes_gate_m0", "cape_v3_rc_m0"):
                base = "cape_v3_regimes_m0" if m == "cape_v3_regimes_gate_m0" else "cape_v3_all_m0"
                b = q.get((s, base))
                if b and c["n_ok"] and b["n_ok"]:
                    rows.append({"sample_id": s, "method": m, "time_ratio": c["enc_med"] / b["enc_med"],
                                 "bytes_saved": b["total_bytes"] - c["total_bytes"],
                                 "pruned": c["extra"].get("regime_gate_pruned"), "rc_proven": c["extra"].get(
                                     "rc_components_proven"), "rc_improved": c["extra"].get("rc_components_improved")})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for m, mk in (("cape_v3_regimes_gate_m0", "o"), ("cape_v3_rc_m0", "s")):
            sub = [r for r in rows if r["method"] == m]
            ax.scatter([r["time_ratio"] for r in sub], [r["bytes_saved"] for r in sub], marker=mk, s=16, label=m)
        ax.axvline(1.0, color="0.4", lw=0.8)
        ax.set_xlabel("encode time / base (x)")
        ax.set_ylabel("bytes saved vs base")
        ax.legend(fontsize=7)
        save(fig, "V3_F6_dual_pruning", "Fig.6 M3a regime gate (base: depth regimes) and M3b reduced-cost fixing (base: "
             "FAST) on the dev QUALITY panel (Z>256 group + CREMI A, 3 repeats). Development only.", rows)

    # 7. FAST vs full regimes
    def f7():
        rows = []
        q = F["dev"]["quality"] or {}
        for (s, m), c in q.items():
            if m == "cape_v3_regimes_m0":
                b = q.get((s, "cape_v3_all_m0"))
                if b and c["n_ok"] and b["n_ok"]:
                    rows.append({"sample_id": s, "Z": c["Z"], "saving_pct": 100 * (1 - c["total_bytes"] / b["total_bytes"]),
                                 "time_ratio": c["enc_med"] / b["enc_med"]})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for z in sorted({r["Z"] for r in rows}):
            sub = [r for r in rows if r["Z"] == z]
            ax.scatter([r["time_ratio"] for r in sub], [r["saving_pct"] for r in sub], s=16, label=f"Z={z}")
        ax.axvline(1.5, color="0.6", lw=0.8, ls="--")
        ax.set_xlabel("encode time regimes / FAST (x)")
        ax.set_ylabel("raw saving of the regime search (%)")
        ax.legend(fontsize=7)
        save(fig, "V3_F7_fast_vs_regimes", "Fig.7 Full depth-regime search vs FAST per dev crop (QUALITY panel). Dashed: "
             "the pre-registered 1.5x time gate. Development only.", rows)

    # 8. SAFE-stock / SAFE-CAPE
    def f8():
        rows = []
        cells = F["conf"]
        for s in sorted({s for s, _ in cells}):
            ref = cells.get((s, "crackle_flat_m0+zstd9"))
            if not ref or not ref["n_ok"]:
                continue
            for m in ("safe_v3_fast_m0_zstd9", "safe_stock_m0_zstd9", f"{V3}+zstd9", f"{STOCK}+zstd9"):
                c = cells.get((s, m))
                if c and c["n_ok"]:
                    rows.append({"sample_id": s, "method": m, "ratio_vs_flat_zstd9": c["total_bytes"] / ref["total_bytes"]})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        ms = sorted({r["method"] for r in rows})
        ax.boxplot([[r["ratio_vs_flat_zstd9"] for r in rows if r["method"] == m] for m in ms])
        ax.set_xticks(range(1, len(ms) + 1))
        ax.set_xticklabels(ms, fontsize=6, rotation=15)
        ax.axhline(1.0, color="0.4", lw=0.8)
        ax.set_ylabel("bytes / (flat + zstd9)")
        save(fig, "V3_F8_safe_archive", "Fig.8 Archive track on SNEMI3D confirm (32 crops): SAFE-CAPE = min(zstd9(flat), "
             "zstd9(v3 FAST)); SAFE-stock = min(zstd9(flat), zstd9(corrected stock)); all headers counted.", rows)

    # 9. regressions
    def f9():
        rows = []
        for r in F["h1"].get("per_sample", []):
            rows.append({"comparison": "v3/v2.1 time", "sample_id": r["sample_id"], "ratio": 1 / r["speedup"]})
        for r in F["h2"].get("per_sample", []):
            rows.append({"comparison": "v3/stock bytes", "sample_id": r["sample_id"], "ratio": r["new_bytes"] / r["base_bytes"]})
            rows.append({"comparison": "v3/stock time", "sample_id": r["sample_id"], "ratio": 1 / r["speedup"]})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        comps = sorted({r["comparison"] for r in rows})
        for i, cmp_ in enumerate(comps):
            ys = [r["ratio"] for r in rows if r["comparison"] == cmp_]
            ax.scatter(np.full(len(ys), i) + np.linspace(-0.2, 0.2, len(ys)), ys, s=10)
        ax.axhline(1.0, color="r", lw=0.8)
        ax.set_xticks(range(len(comps)))
        ax.set_xticklabels(comps, fontsize=7)
        ax.set_yscale("log")
        ax.set_ylabel("per-sample ratio (>1 = regression)")
        save(fig, "V3_F9_regressions", "Fig.9 Every SNEMI3D confirm crop: ratios above the red line are regressions "
             "(listed by name in the tables).", rows)

    # 10. oracle / certificate gap
    def f10():
        rows = []
        for src, cells in (("confirm", F["conf"]), ("confirm scale", F["csc"])):
            for (s, m), c in (cells or {}).items():
                if m in ("cape_v3_certified_m0", "v3_fast_weighted_greedy_certified_m0") and c["ub"] and c["lb"] is not None:
                    rows.append({"source": src, "sample_id": s, "method": m, "gap_pct": 100 * (c["ub"] - c["lb"]) / c["ub"],
                                 "valid": all(c["cert_valid"])})
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        ms = sorted({r["method"] for r in rows})
        ax.boxplot([[r["gap_pct"] for r in rows if r["method"] == m] for m in ms])
        ax.set_xticks(range(1, len(ms) + 1))
        ax.set_xticklabels(ms, fontsize=6)
        ax.set_ylabel("(UB - LB) / UB of the whole stream (%)")
        o = F.get("oracle") or {}
        save(fig, "V3_F10_certificate_gap", f"Fig.10 Restricted-model certificate gap on SNEMI3D (candidate family, safe "
             f"reductions, all depth regimes, w_N>=1, all backgrounds). CP-SAT oracle: {o.get('components_audited')} "
             f"components, optimal {o.get('cpsat_optimal')}, contradictions {o.get('contradictions')}.", rows)

    for name, fn in (("V3_F1_v3_vs_v21_speed", f1), ("V3_F2_size_time_pareto", f2),
                     ("V3_F3_matched_budget_quality", f3), ("V3_F4_memory_vs_n", f4), ("V3_F5_stage_time", f5),
                     ("V3_F6_dual_pruning", f6), ("V3_F7_fast_vs_regimes", f7), ("V3_F8_safe_archive", f8),
                     ("V3_F9_regressions", f9), ("V3_F10_certificate_gap", f10)):
        guard(name, fn)
    return status


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="analysis/v3_state.json")
    a = ap.parse_args(argv)
    st = json.loads((ROOT / a.state).read_text(encoding="utf-8"))
    P = st["panels"]
    need = ["core", "scale", "quality", "tracks", "confirm_primary", "confirm_scale"]
    miss = [k for k in need if P.get(k, {}).get("status") != "DONE"]
    if miss:
        print(f"BLOCKED: panels not DONE: {miss}", file=sys.stderr)
        return 2
    for d in (OUT, FIG, PD, TAB):
        d.mkdir(parents=True, exist_ok=True)
    sel = json.loads((ROOT / "analysis" / "v3_select" / "selected_methods.json").read_text(encoding="utf-8"))
    frz = json.loads((ROOT / "analysis" / "v3_freeze" / "freeze.json").read_text(encoding="utf-8"))
    aud = json.loads((ROOT / "analysis" / "v3_audit" / "audit_v3.json").read_text(encoding="utf-8"))
    dev = {k: load_cells(P[k]["run_dir"]) for k in ("core", "scale", "quality", "tracks")}
    if P.get("quality_check", {}).get("run_dir"):
        dev["quality_check"] = load_cells(P["quality_check"]["run_dir"])
    conf = load_cells(P["confirm_primary"]["run_dir"])
    csc = load_cells(P["confirm_scale"]["run_dir"])
    oracle_p = ROOT / P["confirm_primary"]["run_dir"] / "06_solver_certificates" / "oracle_summary.json"
    oracle = json.loads(oracle_p.read_text(encoding="utf-8")) if oracle_p.exists() else None

    # confirm run source hash must equal the freeze
    srcs = {}
    for k in ("confirm_primary", "confirm_scale"):
        rm = json.loads((ROOT / P[k]["run_dir"] / "run_manifest.json").read_text(encoding="utf-8"))
        srcs[k] = rm["source_hash"]
    freeze_ok = all(v == frz["expected_source_hash"] for v in srcs.values())

    # ---------------- primary family (confirm primary, 32 crops, macroblock clusters)
    h1 = paired(conf, V3, V21, cluster=mb_cluster)
    h2 = paired(conf, V3, STOCK, cluster=mb_cluster)
    pv = {"H1": bootstrap_p(conf, V3, V21, "S_T", 1.0, cluster=mb_cluster),
          "H2a": bootstrap_p(conf, V3, STOCK, "G_B", 0.0, cluster=mb_cluster),
          "H2b": bootstrap_p(conf, V3, STOCK, "S_T", 1.0, cluster=mb_cluster)}
    adj = holm(pv)
    fam = [
        {"id": "H1", "metric": "encode time", "new": V3, "base": V21, "effect": "S_T", "estimate": fmt(h1.get("S_T")),
         "ci95": ci_fmt(h1.get("S_T_ci")), "p": fmt(pv["H1"], 4), "p_holm": fmt(adj.get("H1"), 4), "n": h1.get("n"),
         "clusters": h1.get("n_clusters"), "bytes_identical": h1.get("bytes_identical")},
        {"id": "H2a", "metric": "total bytes", "new": V3, "base": STOCK, "effect": "G_B %",
         "estimate": fmt(h2.get("G_B_pct"), 4), "ci95": ci_fmt([100 * x for x in h2["G_B_ci"]] if h2.get("G_B_ci") else None, 4),
         "p": fmt(pv["H2a"], 4), "p_holm": fmt(adj.get("H2a"), 4), "n": h2.get("n"), "clusters": h2.get("n_clusters"),
         "bytes_identical": h2.get("bytes_identical")},
        {"id": "H2b", "metric": "encode time", "new": V3, "base": STOCK, "effect": "S_T", "estimate": fmt(h2.get("S_T")),
         "ci95": ci_fmt(h2.get("S_T_ci")), "p": fmt(pv["H2b"], 4), "p_holm": fmt(adj.get("H2b"), 4), "n": h2.get("n"),
         "clusters": h2.get("n_clusters"), "bytes_identical": h2.get("bytes_identical")},
    ]
    write_csv(OUT / "primary_family.csv", fam)

    # ---------------- secondary comparisons
    def eff(cells, new, base, cl=mb_cluster):
        p = paired(cells, new, base, cluster=cl)
        return {"new": new, "base": base, "n": p.get("n"), "G_B_pct": fmt(p.get("G_B_pct"), 4),
                "G_B_ci": ci_fmt([100 * x for x in p["G_B_ci"]] if p.get("G_B_ci") else None, 4),
                "S_T": fmt(p.get("S_T")), "S_T_ci": ci_fmt(p.get("S_T_ci")), "S_D": fmt(p.get("S_D")),
                "smaller/equal/larger": f"{p.get('smaller')}/{p.get('equal')}/{p.get('larger')}",
                "peak_ratio": fmt(p.get("peak_ratio_median")), "slowdowns>10%": len(p.get("slowdowns_gt10pct") or []),
                "src_w_S_T": fmt(p.get("source_weighted", {}).get("S_T")), "_raw": p}

    sec_pairs = [(V3, "crackle_flat_m0"), (V3, "crackle_pins_opt_m0"), (V3, "crackle_pins_fast_m0"),
                 (V3, "crackle_vendor_pins_opt_m0"), (V3, "v3_fast_weighted_greedy_m0"), (V3, "v3_fast_greedy_local_m0"),
                 ("safe_v3_fast_m0_zstd9", "safe_stock_m0_zstd9"), ("safe_v3_fast_m0_zstd9", "crackle_flat_m0+zstd9"),
                 ("safe_stock_m0_zstd9", "crackle_flat_m0+zstd9"), (f"{V3}+zstd9", f"{STOCK}+zstd9"),
                 (f"{V3}+zstd9", "crackle_flat_m0+zstd9"), ("safe_v3_fast_m0_zstd3", "safe_stock_m0_zstd3"),
                 (f"{V3}+zstd3", "crackle_flat_m0+zstd3"), ("cape_v3_fast_m5", "cape_v21_fast_m5"),
                 ("cape_v3_fast_m5", "crackle_pins_opt_corrected_m5"), ("cape_v3_certified_m0", V3)]
    if sel.get("quality_selected"):
        sec_pairs.insert(0, ("cape_v3_quality_m0", V3))
    if any(m == "cape_v3_memory_m0" for _, m in conf):
        sec_pairs.insert(0, ("cape_v3_memory_m0", V3))
    secondary = [eff(conf, n, b) for n, b in sec_pairs if any(m == n for _, m in conf) and any(m == b for _, m in conf)]
    scale_rows = [eff(csc, n, b) for n, b in ((V3, V21), (V3, STOCK), (V3, "crackle_flat_m0"),
                                              (V3, "v3_fast_weighted_greedy_m0"),
                                              ("safe_v3_fast_m0_zstd9", "safe_stock_m0_zstd9"),
                                              ("cape_v3_quality_m0", V3), ("cape_v3_memory_m0", V3))
                  if any(m == n for _, m in csc) and any(m == b for _, m in csc)]
    scale_v3_v21 = paired(csc, V3, V21, cluster=mb_cluster)
    main_tab = method_table(conf, STOCK, mb_cluster)
    scale_tab = method_table(csc, STOCK, mb_cluster)

    # partition total (non-overlapping quadrants) and whole volume, scale track
    quads = sorted(s for s in {s for s, _ in csc} if "_q_" in s)
    partition = paired(csc, V3, STOCK, samples=quads, n_boot=0)
    partition_v21 = paired(csc, V3, V21, samples=quads, n_boot=0)

    # certificates / oracle
    certs = []
    for src, cells in (("confirm", conf), ("confirm_scale", csc)):
        for (s, m), c in cells.items():
            if c["cert_valid"]:
                certs.append({"source": src, "sample_id": s, "method": m, "ub": c["ub"], "lb": c["lb"],
                              "gap_pct": 100 * (c["ub"] - c["lb"]) / c["ub"] if c["ub"] else None,
                              "valid": all(c["cert_valid"])})
    write_csv(TAB / "certificates_confirm.csv", certs)

    # lossless / status across every v3 run
    every = {"core": dev["core"], "scale": dev["scale"], "quality": dev["quality"], "tracks": dev["tracks"],
             "confirm_primary": conf, "confirm_scale": csc}
    if "quality_check" in dev:
        every["quality_check"] = dev["quality_check"]
    status_rows, failed_cape = [], []
    for run, cells in every.items():
        cnt = Counter()
        for (s, m), c in cells.items():
            cnt.update(c["statuses"])
            if c["statuses"].get("FAILED_LOSSLESS") and (m.startswith("cape") or m.startswith("v3") or m.startswith("safe_v3")):
                failed_cape.append({"run": run, "sample_id": s, "method": m, "reasons": c["reasons"][:2]})
        status_rows.append({"run": run, **dict(cnt)})
    write_csv(TAB / "status_by_run.csv", status_rows)

    F = {"h1": h1, "h2": h2, "scale_v3_v21": scale_v3_v21, "main_table": main_tab, "dev": dev, "conf": conf, "csc": csc,
         "oracle": oracle}
    fig_status = figures(F)

    # ---------------- ten questions
    def verdict(cond_pass, cond_partial):
        return "PASS" if cond_pass else ("PARTIAL" if cond_partial else "FAIL")

    lossless_ok = not failed_cape
    cert_bad = [c for c in certs if not c["valid"] and c["method"].startswith(("cape_v3", "v3_fast"))]
    h1_sig = (adj.get("H1") or 1) < 0.05 and (h1.get("S_T_ci") or [0])[0] > 1
    h2a_sig = (adj.get("H2a") or 1) < 0.05 and (h2.get("G_B_ci") or [0])[0] > 0
    h2b_sig = (adj.get("H2b") or 1) < 0.05 and (h2.get("S_T_ci") or [0])[0] > 1
    greedy = paired(conf, V3, "v3_fast_weighted_greedy_m0", cluster=mb_cluster)
    mods = sel["fast_modules"]
    accepted = [k for k, d in mods.items() if d["verdict"] == "PASS"]
    slow = (h1.get("slowdowns_gt10pct") or []) + (h2.get("slowdowns_gt10pct") or [])
    bad_status = {k: v for r in status_rows for k, v in r.items() if k not in ("run", "OK")}
    Q = [
        ("1. To'g'rilik", verdict(lossless_ok and not cert_bad and freeze_ok, lossless_ok),
         f"CAPE/v3 qatorlarida FAILED_LOSSLESS: {len(failed_cape)}; v3 sertifikatlari yaroqsiz: {len(cert_bad)}; confirm "
         f"run'lari freeze source hash bilan mos: {freeze_ok}. OK bo'lmagan holatlar (barcha usullar): {bad_status or 'yo`q'}. "
         f"Jadval: `tables/status_by_run.csv`, `tables/certificates_confirm.csv`."),
        ("2. v3 ning o'z foydasi (v2.1 ga nisbatan)", verdict(h1_sig and (h1.get("S_T") or 0) >= 1.05, h1_sig),
         f"SNEMI3D 32 crop: S_T {fmt(h1.get('S_T'))} {ci_fmt(h1.get('S_T_ci'))}, Holm p {fmt(adj.get('H1'), 4)}; baytlar "
         f"bir xil: {h1.get('bytes_identical')}; peak nisbati {fmt(h1.get('peak_ratio_median'))}. Masshtab treki: S_T "
         f"{fmt(scale_v3_v21.get('S_T'))} (n={scale_v3_v21.get('n')}, bitta volume). `primary_family.csv`, Fig.1."),
        ("3. Tashqi raqib (tuzatilgan stock, flat)", verdict(h2a_sig and h2b_sig, h2a_sig or h2b_sig),
         f"Tuzatilgan stock'ga: tejash {fmt(h2.get('G_B_pct'), 4)}% (CI {ci_fmt([100 * x for x in h2['G_B_ci']] if h2.get('G_B_ci') else None, 4)}), "
         f"S_T {fmt(h2.get('S_T'))} {ci_fmt(h2.get('S_T_ci'))}; regressiyalar (bayt): {h2.get('larger')}. Flat va boshqalar: "
         f"`tables/secondary_confirm.*`."),
        ("4. Algoritmik hissa (matched greedy / local)", verdict((greedy.get("G_B") or 0) > 0 and (greedy.get("G_B_ci") or [0])[0] > 0,
                                                                 (greedy.get("G_B") or 0) > 0),
         f"Bir xil v3 infratuzilmasida CAPE vs optimallashtirilgan weighted greedy: tejash {fmt(greedy.get('G_B_pct'), 4)}% "
         f"{ci_fmt([100 * x for x in greedy['G_B_ci']] if greedy.get('G_B_ci') else None, 4)}, vaqt S_T {fmt(greedy.get('S_T'))} "
         f"(<1 = CAPE sekinroq). Fig.3."),
        ("5. M1-M5 hissasi", verdict(len(accepted) >= 1, any(d["verdict"] == "INCONCLUSIVE" for d in mods.values())),
         "; ".join(f"{k}: {d['verdict']} (LOO S_T {fmt(d['loo_S_T'])} {ci_fmt(d['loo_S_T_ci'])}, peak {fmt(d['loo_peak_ratio_median'])})"
                   for k, d in mods.items()) + f". M3a: {sel['quality_components']['M3a']['decision']}; M4: "
         f"{sel['quality_components']['M4']['decision']}; QUALITY: {sel.get('quality_gate', {}).get('decision')}."),
        ("6. Kafolat", verdict(not cert_bad and oracle is not None and (oracle or {}).get("contradictions") == 0, not cert_bad),
         f"v3 sertifikat qatorlari: {sum(1 for c in certs if c['method'].startswith(('cape_v3', 'v3_fast')))}, yaroqsiz "
         f"{len(cert_bad)}; oracle: {json.dumps({k: (oracle or {}).get(k) for k in ('components_audited', 'cpsat_optimal', 'contradictions')})}. "
         "Doira: nomzod oilasi, xavfsiz reduksiyalar, barcha depth regime'lar, w_N>=1, barcha background'lar; global "
         "Crackle optimumi emas; zstd uchun bound yo'q. Fig.10."),
        ("7. Umumlashuv", verdict(False, h1_sig or h2a_sig),
         "Mustaqil manba: faqat SNEMI3D (bitta acquisition, 16 klaster). CREMI va Crackle namunalari v3 uchun development. "
         "Shuning uchun natija shu volume'ga shartli; yangi mustaqil holdout (2+ volume) kerak. H01/MICrONS ruxsatsiz."),
        ("8. Masshtab va regressiyalar", verdict(not slow and not bad_status, not bad_status),
         f">10% sekin namunalar: {sorted(set(slow)) or 'yo`q'}; OK bo'lmagan holatlar: {bad_status or 'yo`q'}. Masshtab "
         f"treki (to'liq volume + 4 kvadrant): `tables/scale_track.*`, Fig.4, Fig.9."),
        ("9. Yangilik", "PARTIAL",
         "Hash, CSR, lazy/eager greedy, sparse DP, dual bound, reduced-cost fixing, LNS va min-selector umumiy vositalar. "
         "M2 g'oyasi Crackle issue #19 (2024-07, 2025-01 yopilgan) bilan bir xil. Yangilikka nomzod: Crackle 2D 4-bog'lanish "
         "qoidasidan kelib chiqadigan qo'shni-ustun dedup isboti (M1a) va formatga bog'langan sertifikatdagi w_D siqilish "
         "tuzatishi; prior-art auditi to'liq emas (`docs/V3_NOVELTY_MATRIX.md`)."),
        ("10. Reproduksiya va qaror", verdict(freeze_ok and all(v["status"] == "OK" for v in fig_status.values()), freeze_ok),
         "`run_v3.cmd --stage all --resume`; freeze `analysis/v3_freeze/freeze.json`; paket stage'i checksumlarni yozadi. "
         "Maqolaga: claim ledger'dagi SUPPORTED/CONDITIONAL da'volar doirasi bilan; qolganlari olib tashlanadi."),
    ]

    # ---------------- claim ledger
    def status_of(sig, positive):
        if sig and positive:
            return "CONDITIONAL"  # one independent acquisition: never unconditional
        if sig and not positive:
            return "CONTRADICTED"
        return "UNSUPPORTED"

    ledger = [
        {"claim_id": "L1", "wording": "v3 FAST writes byte-identical streams to the frozen v2.1 FAST on every measured input",
         "track": "raw", "run_id": P["confirm_primary"]["run_dir"], "table": "primary_family.csv",
         "scope": "dev 36+25 crops, SNEMI3D 32 crops + scale track", "limitations": "implementation equivalence only",
         "status": "SUPPORTED" if h1.get("bytes_identical") and scale_v3_v21.get("bytes_identical") else "CONTRADICTED"},
        {"claim_id": "L2", "wording": f"v3 FAST encodes {fmt(h1.get('S_T'), 2)}x faster than v2.1 FAST (geo, SNEMI3D)",
         "track": "raw", "run_id": P["confirm_primary"]["run_dir"], "table": "primary_family.csv",
         "scope": "SNEMI3D one volume, 32 crops / 16 clusters, 1 CPU thread", "limitations": "single acquisition; "
         "Windows/MinGW i7-13700F", "status": status_of(h1_sig, (h1.get("S_T") or 0) > 1)},
        {"claim_id": "L3", "wording": f"v3 FAST is {fmt(h2.get('G_B_pct'), 3)}% smaller than corrected stock pins",
         "track": "raw", "run_id": P["confirm_primary"]["run_dir"], "table": "primary_family.csv",
         "scope": "SNEMI3D one volume", "limitations": "label section only differs; boundary identical",
         "status": status_of(h2a_sig, (h2.get("G_B") or 0) > 0)},
        {"claim_id": "L4", "wording": f"v3 FAST encodes {fmt(h2.get('S_T'), 2)}x faster than corrected stock pins",
         "track": "raw", "run_id": P["confirm_primary"]["run_dir"], "table": "primary_family.csv",
         "scope": "SNEMI3D one volume", "limitations": "stock = pinned upstream + count-width fix, same compiler",
         "status": status_of(h2b_sig, (h2.get("S_T") or 0) > 1)},
        {"claim_id": "L5", "wording": "CAPE solver is smaller than an optimized weighted greedy on the same infrastructure",
         "track": "matched", "run_id": P["confirm_primary"]["run_dir"], "table": "secondary_confirm.csv",
         "scope": "SNEMI3D one volume", "limitations": "gain size in table; time cost listed",
         "status": status_of((greedy.get("G_B_ci") or [0])[0] > 0 or (greedy.get("G_B_ci") or [0, 0])[1] < 0,
                             (greedy.get("G_B") or 0) > 0)},
        {"claim_id": "L6", "wording": "v3 certificates are valid (LB <= written stream) incl. w_D compaction",
         "track": "guarantee", "run_id": P["confirm_primary"]["run_dir"], "table": "certificates_confirm.csv",
         "scope": "restricted model", "limitations": "not a global optimum; raw only",
         "status": "SUPPORTED" if not cert_bad else "CONTRADICTED"},
        {"claim_id": "L7", "wording": "a QUALITY mode gives >= 0.1% raw saving within 1.5x FAST time",
         "track": "quality", "run_id": (P.get("quality_check") or {}).get("run_dir"), "table": "analysis/v3_select",
         "scope": "dev Z>256 group (pre-registered)", "limitations": "development data only",
         "status": "CONDITIONAL" if sel.get("quality_selected") else "UNSUPPORTED"},
        {"claim_id": "L8", "wording": "the regime gate (M3a) saves time", "track": "quality",
         "run_id": P["quality"]["run_dir"], "table": "analysis/v3_select", "scope": "dev",
         "limitations": "scaled-dual bound is weak", "status": "CONDITIONAL" if sel["quality_components"]["M3a"]["keep"]
         else "UNSUPPORTED"},
        {"claim_id": "L9", "wording": "the v3 mechanisms are new algorithms", "track": "novelty", "run_id": "-",
         "table": "docs/V3_NOVELTY_MATRIX.md", "scope": "-", "limitations": "general tools; M2 = Crackle issue #19 idea",
         "status": "UNSUPPORTED"},
        {"claim_id": "L10", "wording": "results generalize beyond the tested volumes", "track": "generalization",
         "run_id": "-", "table": "-", "scope": "-", "limitations": "one independent acquisition", "status": "UNSUPPORTED"},
        {"claim_id": "L11", "wording": "Q1 10/10", "track": "-", "run_id": "-", "table": "-", "scope": "-",
         "limitations": "never derived automatically; not claimed", "status": "UNSUPPORTED"},
    ]
    for k, d in mods.items():
        ledger.append({"claim_id": f"M-{k}", "wording": f"{k} speeds up v3 FAST (leave-one-out S_T {fmt(d['loo_S_T'])})",
                       "track": "raw (dev)", "run_id": f"{P['core']['run_dir']} + {P['scale']['run_dir']}",
                       "table": "analysis/v3_select/SELECT_V3_UZ.md", "scope": "development crops (seen)",
                       "limitations": "development only; nested scaling crops cluster by source",
                       "status": "CONDITIONAL" if d["verdict"] == "PASS" else "UNSUPPORTED"})
    write_csv(OUT / "claim_ledger.csv", ledger)

    # ---------------- tables
    t_main = write_table("main_confirm", [{k: v for k, v in r.items()} for r in main_tab],
                         [("method", "method"), ("n_ok", "n"), ("total_bytes", "bytes"), ("ratio_vs_ref", "/stock"),
                          ("bpv", "bpv"), ("enc_ms_sum", "enc ms"), ("geo_speedup_vs_ref", "x stock"),
                          ("dec_ms_sum", "dec ms"), ("peak_mib_median", "peak MiB"), ("statuses", "statuses")],
                         "Table 1. SNEMI3D confirm, 32 frozen crops: totals (ratio and speed-up vs corrected stock).")
    t_fam = write_table("primary_family", fam, [("id", "ID"), ("metric", "metric"), ("new", "new"), ("base", "base"),
                                                ("effect", "effect"), ("estimate", "estimate"), ("ci95", "95% CI"),
                                                ("p", "p"), ("p_holm", "p Holm"), ("n", "n"), ("clusters", "clusters")],
                        "Table 2. Pre-registered primary family (Holm), SNEMI3D one volume.")
    seccols = [("new", "new"), ("base", "base"), ("n", "n"), ("G_B_pct", "saving %"), ("G_B_ci", "95% CI"),
               ("S_T", "S_T"), ("S_T_ci", "95% CI"), ("S_D", "S_D"), ("smaller/equal/larger", "s/e/l"),
               ("peak_ratio", "peak"), ("slowdowns>10%", ">10% slower")]
    t_sec = write_table("secondary_confirm", [{k: v for k, v in r.items() if k != "_raw"} for r in secondary], seccols,
                        "Table 3. Secondary comparisons on SNEMI3D (cluster bootstrap 10000).")
    t_sc = write_table("scale_track", [{k: v for k, v in r.items() if k != "_raw"} for r in scale_rows], seccols,
                       "Table 4. SNEMI3D scale track (whole volume + 4 quadrants; one acquisition).")
    write_table("scale_track_methods", scale_tab, [("method", "method"), ("n_ok", "n"), ("total_bytes", "bytes"),
                                                   ("ratio_vs_ref", "/stock"), ("enc_ms_sum", "enc ms"),
                                                   ("peak_mib_median", "peak MiB"), ("statuses", "statuses")],
                "Table 5. Scale track totals.")
    mod_rows = [{"module": k, "verdict": d["verdict"], "loo_S_T": fmt(d["loo_S_T"]), "ci": ci_fmt(d["loo_S_T_ci"]),
                 "peak": fmt(d["loo_peak_ratio_median"]), "single_vs_off": fmt(d["single_S_T_vs_off"]),
                 "memory_profile": d["memory_profile"]} for k, d in mods.items()]
    t_mod = write_table("modules_dev", mod_rows, [("module", "module"), ("verdict", "verdict"), ("loo_S_T", "LOO S_T"),
                                                  ("ci", "95% CI"), ("peak", "peak ratio"),
                                                  ("single_vs_off", "single bit S_T"), ("memory_profile", "MEMORY")],
                        "Table 6. Development module decisions (pre-registered gates).")

    summary = {"generated_at": now(), "freeze_ok": freeze_ok, "confirm_sources": srcs, "primary_family": fam,
               "secondary": [{k: v for k, v in r.items() if k != "_raw"} for r in secondary],
               "scale": [{k: v for k, v in r.items() if k != "_raw"} for r in scale_rows],
               "partition_quadrants_vs_stock": {k: partition.get(k) for k in ("n", "G_B_pct", "S_T", "bytes_new", "bytes_base")},
               "partition_quadrants_vs_v21": {k: partition_v21.get(k) for k in ("n", "S_T", "bytes_identical")},
               "questions": [{"q": q, "status": s, "answer": t} for q, s, t in Q], "figures": fig_status,
               "oracle": oracle, "failed_lossless_cape": failed_cape, "selection": {k: sel.get(k) for k in (
                   "fast_impl_mask", "memory_impl_mask", "quality_selected")}}
    (OUT / "v3_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ---------------- Uzbek report
    claims_ok = sum(1 for c in aud["claims"] if c["status"] == "MATCH")
    L = ["# CAPE v3: yakuniy tahlil (avtomatik, `scripts/report_v3.py`)", "",
         f"Yaratilgan: {summary['generated_at']}. Har bir raqam xom run fayllaridan. Holdout = SNEMI3D (bitta volume, "
         "v3 freeze'dan oldin hech qachon siqilmagan). CREMI va Crackle namunalari v3 uchun development. "
         "\"10/10 tahlil\" = to'liq tekshiriladigan tahlil; algoritm balli yoki jurnal qabuli emas.", "",
         "## 0. Nima o'zgardi (v2.1 -> v3)", "",
         f"- FAST: tanlangan impl_mask **{sel['fast_impl_mask']}** (qabul qilingan modullar: {', '.join(accepted) or 'yo`q'}); "
         "barcha byte-preserving o'zgarishlar muzlatilgan v2.1 binari bilan baytma-bayt teng.",
         f"- MEMORY profil: {sel.get('memory_impl_mask')}; QUALITY: {sel.get('quality_gate', {}).get('decision')}.",
         "- Sertifikat tuzatildi: fixed-depth Regime sertifikati endi w_D siqilishini ham chegaralaydi (v2.1 da 12 ta "
         "yaroqsiz qator bor edi, `analysis/v3_audit`).",
         f"- Audit: oldingi {len(aud['claims'])} da'vodan {claims_ok} tasi xom ma'lumotdan aynan qayta hisoblandi.", "",
         "## 1. Asosiy oila (oldindan ro'yxatga olingan, Holm)", "", t_fam, "",
         f"Freeze source hash bilan moslik: **{freeze_ok}** ({json.dumps(srcs)}).", "",
         "## 2. SNEMI3D asosiy jadval", "", t_main, "", "## 3. Ikkilamchi taqqoslashlar", "", t_sec, "",
         "## 4. Masshtab treki (to'liq volume + kvadrantlar)", "", t_sc, "",
         f"Kesishmaydigan 4 kvadrant jami (stock'ga): tejash {fmt(partition.get('G_B_pct'), 4)}%, S_T {fmt(partition.get('S_T'))}; "
         f"v2.1 ga S_T {fmt(partition_v21.get('S_T'))}.", "", "## 5. Development qarorlari", "", t_mod, "",
         "Batafsil: `analysis/v3_select/SELECT_V3_UZ.md`.", "", "## 6. O'nta majburiy savol", "",
         "| Savol | Holat | Javob |", "|---|---|---|"]
    for q, s_, t in Q:
        L.append(f"| {q} | **{s_}** | {t} |")
    L += ["", "## 7. Claim ledger", "", "| ID | Da'vo | Track | Holat | Doira | Cheklov |", "|---|---|---|---|---|---|"]
    for c in ledger:
        L.append(f"| {c['claim_id']} | {c['wording']} | {c['track']} | **{c['status']}** | {c['scope']} | {c['limitations']} |")
    L += ["", "## 8. Grafiklar", ""]
    for k, v in fig_status.items():
        L.append(f"- `figures/{k}.png` - {v['status']}" + (f": {v.get('caption')}" if v["status"] == "OK" else f" ({v.get('reason')})"))
    L += ["", "## 9. Cheklovlar (halol)", "",
          "- Mustaqil holdout bitta volume (SNEMI3D); CI shu volume ichida shartli, fazoviy bog'liqlik klaster bilan "
          "to'liq yo'qolmaydi.",
          "- Vaqtlar: bitta P-core, bitta thread, Windows/MinGW, i7-13700F; boshqa platformada farq qilishi mumkin.",
          "- Nested scaling crop'lar tavsifiy; empirik T~V^a Big-O isboti emas.",
          "- Sertifikat faqat cheklangan model ichida; zstd uchun bound yo'q.",
          "- H01/MICrONS ishlatilmagan (ruxsat yo'q); tibbiy label xaritalari bu bosqichga kirmagan."]
    (OUT / "V3_YAKUNIY_TAHLIL_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    E = ["# CAPE v3: final analysis (generated by `scripts/report_v3.py`)", "",
         f"Generated {summary['generated_at']}. Holdout: SNEMI3D (one volume, never compressed before the v3 freeze).", "",
         "## Primary family (pre-registered, Holm)", "", t_fam, "", "## Ten questions", "", "| Question | Status |", "|---|---|"]
    for q, s_, _ in Q:
        E.append(f"| {q} | {s_} |")
    E += ["", "## Claim ledger", "", "| ID | Claim | Status | Scope |", "|---|---|---|---|"]
    for c in ledger:
        E.append(f"| {c['claim_id']} | {c['wording']} | {c['status']} | {c['scope']} |")
    E += ["", "Details, tables and figures: see the Uzbek report and `tables/`, `figures/`, `plot_data/`."]
    (OUT / "V3_FINAL_ANALYSIS_EN.md").write_text("\n".join(E) + "\n", encoding="utf-8")
    failed_figs = [k for k, v in fig_status.items() if v["status"] != "OK"]
    print(json.dumps({"primary_family": fam, "questions": {q: s_ for q, s_, _ in Q}, "failed_figures": failed_figs},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
