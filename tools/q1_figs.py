"""CAPE Q1 article figures F01-F08 from the analysis dict (tools/q1_analysis.py) and the raw data volumes.

Every figure: vector PDF + SVG, 300 dpi PNG, the plotted values as CSV, an English caption and an Uzbek note.
Light print theme; categorical slots in fixed order (reference palette): Eθ blue, E0 orange, third series aqua; any
further series is gray and direct-labeled. One y-axis per panel; no truncated axes that exaggerate small differences
(log axes are labeled as such). No generated images: everything is drawn from data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, NullFormatter  # noqa: E402


def _compact(v, _pos=None) -> str:
    if v >= 1e6:
        return f"{v / 1e6:g}M"
    if v >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


def log_axis(ax, which: str, ticks=None) -> None:
    """Log axis with 1-2-5 (or fixed) major ticks, compact plain labels, no minor labels."""
    axis = ax.xaxis if which == "x" else ax.yaxis
    (ax.set_xscale if which == "x" else ax.set_yscale)("log")
    axis.set_major_locator(FixedLocator(ticks) if ticks is not None else LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    axis.set_major_formatter(FuncFormatter(_compact))
    axis.set_minor_formatter(NullFormatter())

ROOT = Path(os.environ.get("CAPE_ROOT") or Path(__file__).resolve().parents[1])  # CAPE_ROOT: run a copy against the repo data
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRAY, INK, INK2, MUTED, GRID, AXIS = "#9a9893", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"], "font.size": 8.5,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlesize": 9, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff", "savefig.facecolor": "#ffffff", "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 1.5, "pdf.fonttype": 42, "svg.fonttype": "none"})


class FigWriter:
    def __init__(self, out: Path):
        self.out = out
        self.records: dict[str, dict] = {}
        for d in ("figures", "plot_data"):
            (out / d).mkdir(parents=True, exist_ok=True)

    def save(self, fig, fid: str, name: str, rows: list[dict], caption_en: str, note_uz: str, scope: str) -> None:
        stem = f"{fid}_{name}"
        for ext in ("pdf", "svg"):
            fig.savefig(self.out / "figures" / f"{stem}.{ext}", bbox_inches="tight")
        fig.savefig(self.out / "figures" / f"{stem}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        csv_path = self.out / "plot_data" / f"{stem}.csv"
        keys: list[str] = []
        for r in rows:
            keys += [k for k in r if k not in keys]
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys or ["empty"])
            w.writeheader()
            for r in rows:
                w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
        self.records[fid] = {"id": fid, "file": f"figures/{stem}", "plot_data": f"plot_data/{stem}.csv",
                             "status": "OK", "caption_en": caption_en, "note_uz": note_uz, "scope": scope,
                             "n_rows": len(rows)}

    def blocked(self, fid: str, name: str, reason: str) -> None:
        self.records[fid] = {"id": fid, "file": f"figures/{fid}_{name}", "status": "BLOCKED", "reason": reason,
                             "caption_en": "", "note_uz": "", "scope": "", "n_rows": 0}


def _fmt_ci(ci, nd=3):
    return "NA" if not ci else f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


# ------------------------------------------------------------------------------------------------ F01
def label_colors(ids: np.ndarray, background: int | None = 0) -> np.ndarray:
    """Deterministic categorical colors from the ID value (visualization only; IDs are not changed)."""
    out = np.zeros(ids.shape + (3,), float)
    flat = ids.reshape(-1)
    uniq, inv = np.unique(flat, return_inverse=True)
    cols = np.zeros((len(uniq), 3))
    for i, u in enumerate(uniq):
        h = hashlib.sha256(int(u).to_bytes(8, "little")).digest()
        cols[i] = 0.25 + 0.7 * np.frombuffer(h[:3], np.uint8) / 255.0
        if background is not None and int(u) == background:
            cols[i] = (0.08, 0.08, 0.08)
    return cols[inv].reshape(out.shape)


def f01_objects(fw: FigWriter, samples: list[dict], decode_check: dict) -> None:
    n = len(samples)
    fig, axes = plt.subplots(2, n, figsize=(2.6 * n, 5.0), squeeze=False)
    rows = []
    for j, s in enumerate(samples):
        vol = np.load(ROOT / s["path"])
        z, y, x = vol.shape
        zc, yc = z // 2, y // 2
        xy, xz = vol[zc], vol[:, yc, :]
        for i, (img, title) in enumerate(((xy, f"XY, z = {zc}"), (xz, f"XZ, y = {yc}"))):
            ax = axes[i][j]
            ax.imshow(label_colors(img), interpolation="nearest", origin="upper",
                      aspect=(s["spacing_z"] / s["spacing_xy"]) if (i == 1 and s.get("spacing_xy")) else "equal")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
            ax.set_title(f"{s['dataset']}: {title}" if i == 0 else title, fontsize=8)
        dc = decode_check.get(s["sample_id"], {})
        axes[1][j].set_xlabel(f"{s['sample_id']}\n{s['dtype']} {x}×{y}×{z} (X×Y×Z), {len(np.unique(vol))} IDs\n"
                              f"decoded = original: mismatch_count = {dc.get('mismatch_count', 'NA')}", fontsize=7)
        rows.append({"dataset": s["dataset"], "sample_id": s["sample_id"], "shape_zyx": [z, y, x], "dtype": s["dtype"],
                     "slice_rule": "geometric centre (z = Z//2 for XY, y = Y//2 for XZ)", "unique_ids": len(np.unique(vol)),
                     "spacing_xyz_nm": s.get("spacing"), "mismatch_count": dc.get("mismatch_count"),
                     "stream_bytes": dc.get("bytes"), "stream_sha256": dc.get("sha256")})
    fig.suptitle("Objects: 3D neuron ID segmentation maps (labels, not EM intensities)", fontsize=9, color=INK)
    fw.save(fig, "F01", "object_examples", rows,
            "Fig. 1. Example inputs: 3D object-ID segmentation maps of neurons (one sample per dataset, the first in "
            "sorted sample order; geometric-centre XY and XZ slices). Colours are a deterministic function of the ID "
            "for display only and may repeat; label 0 (black) is kept as an ordinary ID. Each volume was encoded by Eθ "
            "and decoded by the original Crackle decoder: mismatch_count = 0 means voxel-identical reconstruction.",
            "1-rasm: kirish obyektlari - neyronlarning 3D ID segmentatsiya xaritalari (EM intensivlik emas). Ranglar "
            "faqat ko'rsatish uchun; ID'lar o'zgarmaydi. mismatch_count = 0: Eθ oqimi original dekoder bilan aynan "
            "tiklandi.", "one sample per dataset; display only")


# ------------------------------------------------------------------------------------------------ F02
def f02_pipeline(fw: FigWriter, shares: dict, mask: int) -> None:
    cc_note = "4-connected CC per slice; M5b batch" + (", O3 uint16 chains" if mask & 4096 else "") + \
        (", O1 lean" if mask & 1024 else "")
    stages = [("1 scan", "scan_ns", "max label + pixel pairs"), ("2 boundary", "boundary_ns", "crack codes (upstream)"),
              ("3 2D CC", "cc_ns", cc_note),
              ("4 runs", "runs_ns", "same-label z-runs" + ("; O2 exact allocation" if mask & 2048 else "")),
              ("5 candidates", "candidate_ns", "depth windows; M1a neighbour filter"),
              ("6 reductions", "reduction_ns", "singleton / equal / subset"),
              ("7 components", "component_ns", "independent CC sets"),
              ("8 greedy + dual", "pass1_ns", "UB + integer LB"),
              ("9 exact DP / local", "pass2_ns", "small components"),
              ("10 serialize", "serialize_ns", "PINS section + stream")]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ys = np.arange(len(stages))
    vals = [100 * (shares.get(k) or 0) for _, k, _ in stages]
    ax.barh(ys, vals, height=0.62, color=BLUE)
    for y, (name, key, note), v in zip(ys, stages, vals):
        lab = "NA" if shares.get(key) is None else f"{v:.1f}%"
        ax.text(v + 0.6, y, f"{lab}  ·  {note}", va="center", fontsize=6.8, color=INK2)
    ax.set_yticks(ys)
    ax.set_yticklabels([n for n, _, _ in stages], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals + [1]) * 2.1)
    ax.set_xlabel("share of the native encode time [%] (j0126, summed over samples)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Eθ FAST encoder (impl_mask {mask}): stages in execution order")
    rows = [{"order": i + 1, "stage": n, "diag_key": k, "share_of_encode_core": shares.get(k), "note": t}
            for i, (n, k, t) in enumerate(stages)]
    fw.save(fig, "F02", "encoder_pipeline", rows,
            "Fig. 2. Eθ encoder stages in the order executed by cpp/src/encoder.cpp (FAST: fixed depth width, "
            "certificate off), with the share of the native encode time per stage summed over the j0126 test samples "
            "(native stage timers; the remainder is bookkeeping). Notes name where M1a/M5b (v3) and the accepted Q1 "
            "changes act; every change writes the same bytes as E0.",
            "2-rasm: Eθ bosqichlari koddagi tartibda; foiz - j0126 da har bosqichning native vaqt ulushi.",
            "j0126, Eθ native timers")


# ------------------------------------------------------------------------------------------------ F03
def f03_pareto(fw: FigWriter, totals: list[dict], dataset: str) -> None:
    key = {"cape_q1_fast_m0": ("Eθ (CAPE Q1)", BLUE), "cape_v3frozen_fast_m0": ("E0 (frozen v3)", ORANGE),
           "crackle_pins_opt_corrected_m0": ("corrected stock", AQUA)}
    rows = [t for t in totals if t["total_bytes"] and t["enc_ms_sum_of_medians"] and "_profile" not in t["method"]]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    pts = [(r["enc_ms_sum_of_medians"], r["total_bytes"], r["method"]) for r in rows]
    nondom = set()
    for t, b, m in pts:
        if not any((t2 <= t and b2 <= b) and (t2 < t or b2 < b) for t2, b2, _ in pts):
            nondom.add(m)
    out = []
    for t, b, m in sorted(pts):
        lab, col = key.get(m, (m, GRAY))
        wrapped = "+" in m
        ax.scatter(t, b / 1e6, s=42 if m in key else 22, color=col, marker="s" if wrapped else "o",
                   edgecolor="#ffffff", linewidth=1.2, zorder=3)
        if m in key:
            ax.annotate(lab, (t, b / 1e6), textcoords="offset points", xytext=(6, 6 + 9 * list(key).index(m)),
                        fontsize=6.8, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5))
        out.append({"dataset": dataset, "method": m, "enc_ms_sum_of_medians": t, "total_bytes": b,
                    "pareto_nondominated": m in nondom, "wrapped": wrapped})
    log_axis(ax, "x")
    nd = sorted((r for r in out if r["pareto_nondominated"] and r["method"] not in key),
                key=lambda r: r["total_bytes"])
    for i, r in enumerate(nd[:8]):  # non-dominated points listed in a side box instead of crowded labels
        ax.scatter(r["enc_ms_sum_of_medians"], r["total_bytes"] / 1e6, s=60, facecolor="none", edgecolor=INK2,
                   linewidth=0.8, zorder=4)
    if nd:
        ax.text(1.01, 0.98, "Pareto non-dominated (ringed):\n" + "\n".join(r["method"] for r in nd[:8]),
                transform=ax.transAxes, va="top", ha="left", fontsize=6.3, color=INK2)
    ax.set_xlabel("encode time, sum over samples of the per-sample median [ms] (log scale)")
    ax.set_ylabel("total stored size [MB]")
    ax.set_title(f"Size vs encode time, {dataset} (circles: raw streams; squares: +zstd wrappers)")
    fw.save(fig, "F03", f"size_time_pareto_{dataset}", out,
            f"Fig. 3. Total stored size against total encode time on {dataset} for every method (raw and "
            "zstd-wrapped; SAFE counts both candidate encodes). Labeled grey points are Pareto non-dominated. Eθ and "
            "E0 have identical bytes; they differ only in time. Not a CI plot (totals).",
            f"3-rasm: {dataset} da hajm va encode vaqti; Eθ va E0 baytlari bir xil, faqat vaqt farqli.",
            f"{dataset}, all methods, totals")


# ------------------------------------------------------------------------------------------------ F04
def f04_speedups(fw: FigWriter, res: dict) -> None:
    comps = [("C1", "Eθ vs E0 (C1)"), ("BUILD", "live@575 vs E0 (build)"), ("C2", "Eθ vs v2.1 (C2)"),
             ("C3_wgreedy", "vs weighted greedy"), ("C3_stock_corr", "vs corrected stock"),
             ("C3_flat", "vs Crackle flat")]
    dsets = [d for d in ("j0126", "snemi", "hemibrain") if d in res["datasets"]]
    fig, axes = plt.subplots(1, len(dsets), figsize=(2.9 * len(dsets) + 1.2, 3.6), sharey=True, squeeze=False)
    rows = []
    for ax, ds in zip(axes[0], dsets):
        cc = res["datasets"][ds]["comparisons"]
        for i, (cid, lab) in enumerate(comps):
            p = cc.get(cid)
            if not p or p.get("empty"):
                ax.text(1.0, i, "  N/A (not measured)", va="center", fontsize=6.3, color=MUTED)
                continue
            lo, hi = (p["S_T_ci"] or [p["S_T"], p["S_T"]])
            col = BLUE if cid == "C1" else (ORANGE if cid == "BUILD" else GRAY)
            ax.errorbar(p["S_T"], i, xerr=[[p["S_T"] - lo], [hi - p["S_T"]]], fmt="o", color=col, ms=5, capsize=2,
                        lw=1.2)
            ax.annotate(f"{p['S_T']:.3f}", (p["S_T"], i), textcoords="offset points", xytext=(6, 4), fontsize=6.5,
                        color=INK2)
            rows.append({"dataset": ds, "comparison": cid, "label": lab, "new": p["new"], "base": p["base"],
                         "n": p["n"], "clusters": p["n_clusters"], "S_T": p["S_T"], "ci_lo": lo, "ci_hi": hi,
                         "time_reduction_pct": p["time_reduction_pct"]})
        ax.axvline(1.0, color=AXIS, lw=1)
        log_axis(ax, "x", [0.25, 0.5, 1, 2, 5, 10, 20, 50, 100])
        ax.set_title(ds)
        ax.set_xlabel("S_T (log; >1 = Eθ faster)")
    axes[0][0].set_yticks(range(len(comps)))
    axes[0][0].set_yticklabels([lab for _, lab in comps], fontsize=7)
    axes[0][0].invert_yaxis()
    fig.suptitle("Encode speed-up with 95% paired cluster-bootstrap CI", fontsize=9)
    fw.save(fig, "F04", "speedup_ci", rows,
            "Fig. 4. Geometric-mean encode speed-up S_T = exp(mean log(T_base/T_Eθ)) with 95% paired cluster-bootstrap "
            "CIs (10 000 resamples; clusters: j0126 volume, SNEMI3D macroblock, hemibrain cutout). C1 (Eθ vs frozen v3 "
            "E0) is the new contribution; 'build' isolates compiler/build drift (live binary at the E0 mask); C2 is the "
            "historical v3 gain, not re-counted; the C3 rows compare with different streams (sizes differ).",
            "4-rasm: tezlanish S_T va 95% CI; C1 - yangi hissa, C2 - tarixiy (qayta sanalmaydi).",
            "j0126 primary; SNEMI3D seen; hemibrain descriptive")


# ------------------------------------------------------------------------------------------------ F05
def f05_memory(fw: FigWriter, res: dict, cells_peaks: list[dict], profile: list[dict]) -> None:
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.6, 3.6))
    key = {"cape_q1_fast_m0": ("Eθ", BLUE), "cape_v3frozen_fast_m0": ("E0", ORANGE),
           "crackle_pins_opt_corrected_m0": ("corrected stock", AQUA)}
    rows = []
    for m, (lab, col) in key.items():
        pts = [r for r in cells_peaks if r["method"] == m and r["peak_enc_mib"]]
        if not pts:
            continue
        a.scatter([r["voxels"] for r in pts], [r["peak_enc_mib"] for r in pts], s=18, color=col, label=lab,
                  edgecolor="#ffffff", linewidth=0.8, zorder=3)
        rows += [dict(r, panel="a") for r in pts]
    log_axis(a, "x")
    log_axis(a, "y")
    a.set_xlabel("voxels per volume (log)")
    a.set_ylabel("encode-inclusive peak working set [MiB] (log)")
    a.set_title("(a) peak vs size, all test volumes")
    a.legend(fontsize=7)
    phases = ["start", "scan", "boundary", "cc", "runs", "candidates", "reduction", "components", "solve", "serialize"]
    big = sorted({(r["voxels"] or 0, r["sample_id"]) for r in profile})[-1:] if profile else []
    for (vox, sid) in big:
        for m, (lab, col) in (("cape_q1_fast_profile_m0", ("Eθ", BLUE)),
                              ("cape_q1_base_profile_m0", ("live binary at E0 mask", ORANGE))):
            r = next((x for x in profile if x["sample_id"] == sid and x["method"] == m), None)
            if not r:
                continue
            ys = [r.get(f"peak_{p}_mib") for p in phases]
            b.plot(range(len(phases)), ys, marker="o", ms=4, color=col, label=lab)
            rows.append({"panel": "b", "sample_id": sid, "method": m, **{f"peak_{p}_mib": r.get(f"peak_{p}_mib")
                                                                         for p in phases}})
        b.set_title(f"(b) fresh process, peak after each stage:\n{sid}", fontsize=7.5)
    b.set_xticks(range(len(phases)))
    b.set_xticklabels(phases, rotation=45, ha="right", fontsize=6.5)
    b.set_ylabel("process peak working set [MiB]")
    b.legend(fontsize=7)
    fw.save(fig, "F05", "memory_scale", rows,
            "Fig. 5. (a) Encode-inclusive peak working set (fresh process; Windows PeakWorkingSetSize read after encode "
            "and before decode; includes the Python process and the input array) against volume size for all test "
            "volumes. (b) Instrumented profile (separate run, not timed): process peak after each encoder stage on the "
            "largest profiled volume, Eθ against the live binary at the E0 mask (E0 itself cannot be instrumented). "
            "Absolute MiB; no subtraction is presented as algorithm memory.",
            "5-rasm: (a) encode peak xotira hajmga nisbatan; (b) bosqichlar bo'yicha peak (alohida profil run).",
            "test volumes; instrumented profile separate")


# ------------------------------------------------------------------------------------------------ F06
def f06_ablation(fw: FigWriter, res: dict) -> None:
    dsets = [d for d in ("j0126", "snemi", "hemibrain") if d in res["datasets"] and res["datasets"][d]["ablation"]]
    if not dsets:
        fw.blocked("F06", "ablation", "no ablation rows in the final run")
        return
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4))
    rows = []
    names = sorted({k for d in dsets for k in res["datasets"][d]["ablation"]})
    width = 0.8 / len(dsets)
    cols = [BLUE, ORANGE, AQUA]
    for j, ds in enumerate(dsets):
        ab = res["datasets"][ds]["ablation"]
        for metric, ax in (("S_T", axes[0]), ("R_M", axes[1])):
            for i, k in enumerate(names):
                p = ab.get(k)
                if not p or p.get("empty"):
                    continue
                v = p[metric] if metric == "S_T" else 1 / p[metric]
                ci = p[f"{metric}_ci"]
                lo, hi = (ci if metric == "S_T" else [1 / ci[1], 1 / ci[0]]) if ci else (v, v)
                x = i + (j - (len(dsets) - 1) / 2) * width
                ax.bar(x, v - 1, bottom=1, width=width * 0.92, color=cols[j], label=ds if i == 0 else None)
                ax.errorbar(x, v, yerr=[[v - lo], [hi - v]], fmt="none", ecolor=INK2, lw=0.8, capsize=1.5)
                if metric == "S_T":
                    rows.append({"dataset": ds, "variant": k, "S_T_Etheta_vs_variant": p["S_T"], "S_T_ci": p["S_T_ci"],
                                 "R_M_Etheta_over_variant": p["R_M"], "R_M_ci": p["R_M_ci"], "n": p["n"]})
    for ax, t in ((axes[0], "time: T_variant / T_Eθ (geomean)"), (axes[1], "memory: M_variant / M_Eθ (geomean)")):
        ax.axhline(1, color=AXIS, lw=1)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(["Eθ − " + n.replace("cape_q1_no", "").replace("f_m0", "").replace("_m0", "")
                            for n in names],
                           rotation=30, ha="right", fontsize=7)
        ax.set_ylabel(t)
        ax.legend(fontsize=7)
    fig.suptitle("Ablation: what each mechanism contributes inside Eθ (>1 = the mechanism helps)", fontsize=9)
    fw.save(fig, "F06", "ablation", rows,
            "Fig. 6. Leave-one-mechanism-out ablation on the same binary: ratio of the variant without the mechanism "
            "to the full Eθ, for encode time (left) and encode-inclusive peak (right), geometric means with 95% "
            "cluster-bootstrap CIs. 'Eθ − M1a' is the plain equal-coverage hash dedup on the same infrastructure. All "
            "variants write identical bytes.",
            "6-rasm: ablation - har mexanizmsiz variant / to'liq Eθ (vaqt va xotira).", "same binary, same bytes")


# ------------------------------------------------------------------------------------------------ F07
def f07_size(fw: FigWriter, res: dict) -> None:
    pairs = [("C3_stock_corr", "raw: Eθ vs corrected stock"), ("C3_wgreedy", "raw: Eθ vs weighted greedy"),
             ("C3_flat", "raw: Eθ vs flat"), ("A_z9_flat", "zstd9: Eθ vs flat"),
             ("SAFE9_stock", "SAFE9: Eθ vs stock"), ("SAFE9_flat", "SAFE9 vs flat+zstd9")]
    dsets = [d for d in ("j0126", "snemi", "hemibrain") if d in res["datasets"]]
    fig, axes = plt.subplots(1, len(dsets), figsize=(2.9 * len(dsets) + 1.4, 3.8), sharey=True, squeeze=False)
    rows = []
    for ax, ds in zip(axes[0], dsets):
        cc = res["datasets"][ds]["comparisons"]
        for i, (cid, lab) in enumerate(pairs):
            p = cc.get(cid)
            if not p or p.get("empty"):
                ax.text(0.98, i, "N/A", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6.3,
                        color=MUTED)
                continue
            g = [x["gain_pct"] for x in p["per_sample"]]
            jitter = np.linspace(-0.25, 0.25, len(g)) if len(g) > 1 else [0]
            col = [BLUE if v > 0 else (GRAY if v == 0 else ORANGE) for v in g]
            ax.scatter(g, [i + t for t in jitter], s=10, c=col, zorder=3)
            ax.text(0.98, i - 0.36, f"W/T/L {p['smaller']}/{p['equal']}/{p['larger']}",
                    transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6, color=INK2)
            rows += [{"dataset": ds, "comparison": cid, "sample_id": x["sample_id"], "gain_pct": x["gain_pct"]}
                     for x in p["per_sample"]]
        ax.axvline(0, color=AXIS, lw=1)
        ax.set_xlabel("size gain per sample [%]\n(>0 = Eθ smaller)")
        ax.set_title(ds)
    axes[0][0].set_yticks(range(len(pairs)))
    axes[0][0].set_yticklabels([lab for _, lab in pairs], fontsize=6.8)
    axes[0][0].set_ylim(len(pairs) - 0.5, -0.6)
    fig.suptitle("Size differences per sample (blue: Eθ smaller, gray: equal, orange: Eθ larger)", fontsize=9)
    fw.save(fig, "F07", "size_safe", rows,
            "Fig. 7. Per-sample size gain 100 (B_base - B_Eθ)/B_base for raw streams, zstd9-wrapped streams and SAFE "
            "archives (all headers counted; m0/m5 and zstd levels never mixed). W/T/L counts exact bytes. Raw Eθ "
            "streams are identical to E0, so any gain here is the CAPE selection already present in v3, not a Q1 "
            "change.",
            "7-rasm: namuna bo'yicha hajm farqi; Q1 hajmni o'zgartirmaydi (E0 bilan bir xil).", "raw / archive / SAFE")


# ------------------------------------------------------------------------------------------------ F08
def f08_certificates(fw: FigWriter, res: dict, prop: list[dict]) -> None:
    certs = [dict(c, dataset=ds) for ds, d in res["datasets"].items() for c in d.get("certificates", [])
             if c.get("gap_pct") is not None]
    if not certs:
        fw.blocked("F08", "certificates", "no CERTIFIED rows with LB/UB in the final run")
        return
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.4, 3.4), gridspec_kw={"width_ratios": [2, 1]})
    for i, ds in enumerate(sorted({c["dataset"] for c in certs})):
        g = [c["gap_pct"] for c in certs if c["dataset"] == ds]
        a.scatter([i + t for t in np.linspace(-0.25, 0.25, len(g))], g, s=10, color=[BLUE, ORANGE, AQUA][i % 3],
                  label=ds)
    a.set_xticks(range(len({c["dataset"] for c in certs})))
    a.set_xticklabels(sorted({c["dataset"] for c in certs}))
    a.set_ylabel("certificate gap (UB − LB)/UB of the whole stream [%]")
    a.set_title("(a) restricted-model gap, Eθ CERTIFIED")
    rows = [dict(c, panel="a") for c in certs]
    if prop:
        xs = np.arange(len(prop))
        old = [100 * (r["old_ub"] - r["old_lb"]) / r["old_ub"] for r in prop]
        new = [100 * (r["v3_ub"] - r["v3_lb"]) / r["v3_ub"] for r in prop]
        b.bar(xs - 0.2, old, width=0.38, color=ORANGE, label="v2.1 (invalid: LB > UB)")
        b.bar(xs + 0.2, new, width=0.38, color=BLUE, label="v3/Eθ (valid)")
        b.axhline(0, color=AXIS, lw=1)
        b.set_xticks(xs)
        b.set_xticklabels([r["sample_id"].replace("crackle_", "").split("_")[0] + "\n" +
                           r["sample_id"].rsplit("_", 1)[-1] for r in prop], fontsize=6.3)
        b.set_ylabel("gap [%] (negative = invalid)")
        b.set_title("(b) the 12 old invalid rows (w_D compaction)")
        b.legend(fontsize=6.5)
        rows += [dict(r, panel="b") for r in prop]
    fw.save(fig, "F08", "certificates", rows,
            "Fig. 8. (a) Gap between the written stream (UB) and the restricted-model lower bound (LB) for the Eθ "
            "CERTIFIED rows (same bytes as FAST): candidate family, safe reductions, all depth regimes, all "
            "backgrounds, w_N >= 1; not a global optimum and no bound after zstd. (b) The two development volumes "
            "behind the 12 invalid v2.1 rows: v2.1 reported LB > UB (negative gap); v3/Eθ add the scaled full-width "
            "dual for compacted w_D and are valid. Stream bytes are unchanged.",
            "8-rasm: (a) cheklangan model sertifikat oralig'i; (b) 12 eski noto'g'ri qator va tuzatilgan holat.",
            "restricted model only")
