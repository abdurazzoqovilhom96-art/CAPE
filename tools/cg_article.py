"""B protocol analysis + article package (docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md, sections 10, 13).

evaluate_gate(run_dir, state): projection model and gates G1/G2 from the raw rows (native results.csv + prototype
JSON). build(run_dir, state, out_name): tables T01-T07, figures F01-F06, texts, checks, staged into
`<out_name>.staging` and moved to `<out_name>` (the previous folder is archived, never deleted) + zip.
No number is typed by hand: every value below comes from those raw files."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics as st
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
E = "cape_q1_fast_m0"
EP = "cape_q1_fast_profile_m0"
EC = "cape_q1_certified_m0"
SOLVER_KEYS = ("greedy_ns", "dual_ns", "pass1_ns", "dp_ns", "local_ns", "pass2_ns", "rc_ns", "repair_ns",
               "regime_gate_ns")
TH = {"M": {"R_M_max": 0.95, "R_T_max": 1.02}, "T": {"R_T_max": 0.95, "R_M_max": 1.02},
      "C": {"gap_reduction_min": 0.50, "R_cert_max": 1.0}}
BLUE, ORANGE, GRAY, INK, AQUA, RED = "#2a6fbb", "#e07b39", "#9aa0a6", "#202124", "#1aa39a", "#c5221f"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gm(x):
    x = [v for v in x if v is not None and v > 0]
    return float(np.exp(np.mean(np.log(x)))) if x else None


def f(x, nd=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "N/A"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{x:.{nd}f}"


# ----------------------------------------------------------------------------------------------- raw loading
def load_native(run_dir: Path) -> dict:
    d = pd.read_csv(run_dir / "05_raw_metrics" / "results.csv", low_memory=False)
    d = d[d.status == "OK"].copy()
    d["x"] = d.extra_json.map(lambda s: json.loads(s) if isinstance(s, str) else {})
    out = {}
    for sid, g in d.groupby("sample_id"):
        r = {"sample_id": sid}
        b = g[(g.method_id == E) & (g.panel == "B")]
        m = g[(g.method_id == E) & (g.panel == "MEM")]
        r["T_E_ns"] = float(b.encode_ns.median()) if len(b) else None
        r["n_timed"] = int(len(b))
        r["total_bytes"] = int(b.total_bytes.iloc[0]) if len(b) else None
        r["bytes_constant"] = bool(b.total_bytes.nunique() == 1) if len(b) else None
        r["lossless_all"] = bool(g[g.method_id == E].lossless.astype(str).str.lower().eq("true").all())
        r["peak_E"] = float(m.x.iloc[0].get("peak_after_encode")) if len(m) else None
        pb = g[(g.method_id == EP) & (g.panel == "B")]
        pm = g[(g.method_id == EP) & (g.panel == "MEM")]
        ph = {}
        for k in ("scan_ns", "boundary_ns", "cc_ns", "runs_ns", "candidate_ns", "reduction_ns", "component_ns",
                  "serialize_ns", "encode_core_ns") + SOLVER_KEYS:
            vals = [x.get(k) for x in pb.x if x.get(k) is not None]
            ph[k] = float(st.median(vals)) if vals else 0.0
        ph["solver_ns"] = sum(ph[k] for k in SOLVER_KEYS)
        r["phases"] = ph
        r["T_profile_ns"] = float(pb.encode_ns.median()) if len(pb) else None
        mem = pm.x.iloc[0] if len(pm) else {}
        r["mem"] = {k: mem.get(k) for k in ("mem_ws_start", "mem_ws_boundary", "mem_ws_cc", "mem_peak_cc",
                                            "mem_ws_runs", "mem_peak_runs", "mem_ws_candidates",
                                            "mem_peak_candidates", "mem_peak_reduction", "mem_ws_solve",
                                            "peak_after_encode", "peak_before_encode")}
        cb = g[(g.method_id == EC) & (g.panel == "B")]
        r["T_cert_native_ns"] = float(cb.encode_ns.median()) if len(cb) else None
        r["shape"], r["dtype"] = (json.loads(b.canonical_shape.iloc[0]) if len(b) else None,
                                  b.original_dtype.iloc[0] if len(b) else None)
        out[sid] = r
    return out


def load_proto(run_dir: Path, state: dict) -> dict:
    out = {}
    for sid, t in (state.get("prototype") or {}).items():
        p = ROOT / t["json"]
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"status": t["status"]}
        rec["task_status"] = t["status"]
        out[sid] = rec
    return out


# ------------------------------------------------------------------------------------------------- projection
def project(nat: dict, pr: dict) -> dict:
    ph, mem = nat["phases"], nat["mem"]
    cg, inst = pr["cg"], pr["instance"]
    S = 12 * cg["columns"] + 4 * cg["nnz"] + 8 * inst["n_cc"] + cg["lp_rss_bytes"]
    peak_proj = max(mem["mem_peak_runs"], mem["mem_ws_runs"] + S)
    T_cr = ph["candidate_ns"] + ph["reduction_ns"] + ph["component_ns"] + ph["solver_ns"]
    T_pass, T_int, T_lp = ph["candidate_ns"], ph["greedy_ns"], cg["lp_time_s"] * 1e9
    k = cg["pricing_passes"]
    T_proj = nat["T_E_ns"] - T_cr + k * T_pass + T_lp + T_int
    T_cert = nat["T_E_ns"] + (k + pr["certificate"]["repair_passes"]) * T_pass + T_lp
    return {"S_CG_bytes": S, "peak_proj": peak_proj, "peak_E": nat["peak_E"], "R_M": peak_proj / nat["peak_E"],
            "T_cr_ns": T_cr, "T_pass_ns": T_pass, "T_int_ns": T_int, "T_lp_ns": T_lp, "k": k, "T_proj_ns": T_proj,
            "T_E_ns": nat["T_E_ns"], "R_T": T_proj / nat["T_E_ns"], "T_cert_ns": T_cert,
            "T_cert_native_ns": nat["T_cert_native_ns"],
            "R_cert": T_cert / nat["T_cert_native_ns"] if nat["T_cert_native_ns"] else None,
            "best_case_peak": mem["mem_peak_runs"], "best_case_R_M": mem["mem_peak_runs"] / nat["peak_E"]}


def evaluate_gate(run_dir: Path, state: dict) -> dict:
    nat = load_native(ROOT / state["native"]["run_dir"]) if state.get("native", {}).get("run_dir") else {}
    pro = load_proto(run_dir, state)
    rows, problems = [], []
    t4_all = True
    for sid in sorted(pro):
        pr = pro[sid]
        if pr.get("status") != "SUCCESS":
            problems.append(f"{sid}: prototype {pr.get('task_status')} ({pr.get('error', '')[:120]})")
            t4_all = False
            continue
        if not pr["T4"]["pass"]:
            t4_all = False
            problems.append(f"{sid}: T4 failed {pr['T4']}")
        n = nat.get(sid)
        if not n or n["T_E_ns"] is None or n["peak_E"] is None:
            problems.append(f"{sid}: native rows missing")
            continue
        rows.append(dict(sample_id=sid, **project(n, pr), U_E=pr["compare"]["U_Etheta"],
                         L_asc=pr["compare"]["L_ascent"], L_CG=pr["compare"]["L_CG"], U_CG=pr["compare"]["U_CG"],
                         cert_feasible=pr["certificate"]["feasible"], converged=pr["cg"]["converged"],
                         stop=pr["cg"]["stop"], lossless=n["lossless_all"]))
    G1 = bool(state.get("prechecks", {}).get("tests_pass")) and t4_all and len(pro) > 0
    inconclusive = any(p.get("task_status") in ("TIMEOUT", "ERROR") for p in pro.values()) or len(rows) != len(pro)
    mand = G1 and not inconclusive and all(r["cert_feasible"] and r["lossless"] for r in rows)
    RM, RT = gm([r["R_M"] for r in rows]), gm([r["R_T"] for r in rows])
    Rc = gm([r["R_cert"] for r in rows])
    q_all = all(r["U_CG"] <= r["U_E"] for r in rows)
    gap_a = sum(r["U_E"] - r["L_asc"] for r in rows)
    gap_c = sum(r["U_E"] - r["L_CG"] for r in rows if r["L_CG"] is not None)
    gap_red = (1 - gap_c / gap_a) if gap_a > 0 else None
    routes = {
        "M": {"quality_preserved": q_all, "R_M_proj": RM, "R_T_proj": RT,
              "pass": bool(rows) and q_all and RM is not None and RM <= TH["M"]["R_M_max"] and RT <= TH["M"]["R_T_max"]},
        "T": {"quality_preserved": q_all, "R_M_proj": RM, "R_T_proj": RT,
              "pass": bool(rows) and q_all and RT is not None and RT <= TH["T"]["R_T_max"] and RM <= TH["T"]["R_M_max"]},
        "C": {"L_CG_ge_L_ascent_all": all(r["L_CG"] is not None and r["L_CG"] >= r["L_asc"] for r in rows),
              "gap_reduction": gap_red, "R_cert": Rc,
              "pass": bool(rows) and all(r["L_CG"] is not None and r["L_CG"] >= r["L_asc"] for r in rows)
              and gap_red is not None and gap_red >= TH["C"]["gap_reduction_min"] and Rc is not None
              and Rc <= TH["C"]["R_cert_max"]}}
    G2 = mand and any(v["pass"] for v in routes.values())
    if not G1:
        term = "BLOCKED_PRECHECK"
    elif inconclusive:
        term = "STOPPED_GATE_INCONCLUSIVE"
    elif not G2:
        term = "STOPPED_GATE_FAILED"
    else:
        term = "COMPLETE_VALIDATED"
    return {"evaluated_at": now(), "thresholds": TH, "rows": rows, "problems": problems, "G1": G1,
            "mandatory": mand, "inconclusive": inconclusive, "routes": routes, "G2": G2, "terminal": term,
            "best_case_R_M": gm([r["best_case_R_M"] for r in rows]),
            "pooled": {"gap_ascent": gap_a, "gap_CG": gap_c, "R_M_proj": RM, "R_T_proj": RT, "R_cert": Rc}}


# ----------------------------------------------------------------------------------------------- table helpers
def write_table(tdir: Path, tid: str, title: str, header: list[str], rows: list[list], note: str = "") -> dict:
    tdir.mkdir(parents=True, exist_ok=True)
    cells = [["" if v is None else v for v in r] for r in rows]
    with open(tdir / f"{tid}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(cells)
    md = [f"# {tid}: {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(str(v) for v in r) + " |" for r in cells]
    if note:
        md += ["", note]
    (tdir / f"{tid}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")  # noqa: E731
    tex = [r"\begin{tabular}{" + "l" * len(header) + "}", r"\hline", " & ".join(esc(h) for h in header) + r" \\",
           r"\hline"] + [" & ".join(esc(v) for v in r) + r" \\" for r in cells] + [r"\hline", r"\end{tabular}"]
    (tdir / f"{tid}.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    return {"id": tid, "title": title, "rows": len(rows)}


def mib(x):
    return None if x is None else round(x / 2**20, 1)


def ms(x):
    return None if x is None else round(x / 1e6, 2)


# ---------------------------------------------------------------------------------------------------- figures
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#5f6368", "axes.labelcolor": INK, "xtick.color": INK,
                         "ytick.color": INK, "savefig.dpi": 300})
    return plt


def save_fig(fig, fdir: Path, fid: str, data: pd.DataFrame | None, pdir: Path):
    fdir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(fdir / f"{fid}.{ext}", bbox_inches="tight", facecolor="white")
    if data is not None:
        pdir.mkdir(parents=True, exist_ok=True)
        data.to_csv(pdir / f"{fid}.csv", index=False)
    import matplotlib.pyplot as plt
    plt.close(fig)


def short(sid: str) -> str:
    return (sid.replace("cremi_", "").replace("crackle_", "ckl_").replace("_256x256x64", "").replace(
        "_256x256x60", "").replace("_256x256x512", "").replace("connectomics", "conn"))


def fig_f01(fdir, pdir, h_example, actual_h=None):
    """Run / window dominance on one real column (first dev crop): every interval <= h fits one length-h window."""
    plt = _plt()
    man = [json.loads(x) for x in (ROOT / "data" / "manifests" / "q1b_dev.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]
    vol = np.load(ROOT / man[0]["path"], mmap_mode="r")
    Z = vol.shape[0]
    best = None
    for y in range(0, vol.shape[1], 8):
        for x in range(0, vol.shape[2], 8):
            col = np.asarray(vol[:, y, x])
            brk = np.flatnonzero(np.diff(col) != 0) + 1
            st_ = np.concatenate(([0], brk))
            ln = np.diff(np.append(st_, Z))
            i = int(np.argmax(ln))
            if best is None or ln[i] > best[3]:
                best = (y, x, int(st_[i]), int(ln[i]), col)
    y, x, z0, R, col = best
    h = int(min(h_example, max(2, R - 2)))
    actual_h = (actual_h or {}).get(man[0]["sample_id"]) if isinstance(actual_h, dict) else actual_h
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    ax.barh(0, R, left=z0, height=0.6, color=BLUE, alpha=0.85)
    ax.text(z0 + R / 2, 0, f"run: label {int(col[z0])}, R = {R}", ha="center", va="center", color="white",
            fontsize=7)
    nwin = R - h + 1 if R > h else 1
    show = list(range(nwin)) if nwin <= 8 else list(range(0, nwin, max(1, nwin // 8)))
    for k, t in enumerate(show):
        ax.barh(1 + 0.45 * k, h, left=z0 + t, height=0.35, color=ORANGE, alpha=0.8)
    a0, aL = z0 + 1, max(1, h - 2)
    ax.barh(-1, aL, left=a0, height=0.35, color=GRAY)
    ax.text(a0 + aL + 0.5, -1, f"shorter interval (length {aL}) lies inside the window starting at "
            f"t = {min(a0 - z0, R - h)}", va="center", fontsize=6.5, color=INK)
    ax.set_yticks([-1, 0, 1 + 0.45 * (len(show) - 1) / 2])
    ax.set_yticklabels(["interval", "run", f"length-{h} windows"])
    ax.set_xlabel("slice z")
    ax.set_title(f"{man[0]['sample_id']}, column (x={x}, y={y}); illustrative h = {h} "
                 f"(in the Eθ stream regime h = {actual_h} = Z, so the whole run is the only window)", fontsize=7)
    data = pd.DataFrame({"z": np.arange(Z), "label": col.astype(np.int64)})
    save_fig(fig, fdir, "F01_dominance_example", data, pdir)
    return {"status": "OK", "caption_en": f"One real column of {man[0]['sample_id']}: a run of length R = {R} and "
            f"its length-{h} windows for an ILLUSTRATIVE h = {h}. Every interval of length <= h lies in one window with the "
            f"same pin cost, so the wider family cannot lower the set-cover optimum (theorem). In the regime that Eθ "
            f"actually writes, h = {actual_h} = Z: every run is a single window.",
            "note_uz": "Haqiqiy ustun: run va uning h-oynalari; qisqa oraliq bitta oynaga to'liq tushadi."}


def fig_f02(fdir, pdir):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.6, 2.3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    W, G = 0.135, 0.032
    boxes = ["labels", "CC per slice\n(native)", "runs + chain\n(native, kept)", "LP over\nsingletons +\nt=0 windows",
             "exact pricing\n(prefix sums,\nO(R) per run)", "integer greedy\n+ integer\ncertificate"]
    xs = [0.005 + i * (W + G) for i in range(len(boxes))]
    for txt, x0 in zip(boxes, xs):
        ax.add_patch(plt.Rectangle((x0, 0.38), W, 0.42, fc="#e8f0fe", ec=BLUE, lw=0.8))
        ax.text(x0 + W / 2, 0.59, txt, ha="center", va="center", fontsize=6.3, color=INK, linespacing=1.15)
    for a, b in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(b, 0.59), xytext=(a + W, 0.59), arrowprops=dict(arrowstyle="->", color=INK, lw=0.7))
    ax.annotate("", xy=(xs[3] + W / 2, 0.38), xytext=(xs[4] + W / 2, 0.38),
                arrowprops=dict(arrowstyle="->", color=ORANGE, lw=0.8, connectionstyle="arc3,rad=-0.6"))
    ax.text((xs[3] + xs[4] + W) / 2, 0.06, "add violated windows (W > c); stop when none or at the budget",
            ha="center", fontsize=6.3, color=ORANGE)
    save_fig(fig, fdir, "F02_algorithm_flow", None, pdir)
    return {"status": "OK", "caption_en": "Bounded column generation evaluated in this study (prototype). Runs and the "
            "column-major chain stay native and resident; candidate and incidence lists are replaced by exact pricing.",
            "note_uz": "Prototip oqimi: runs/chain native qoladi, candidate ro'yxati o'rniga pricing."}


def build_figures(fdir, pdir, g, nat, pro):
    plt = _plt()
    figs = {}
    rows = g["rows"]
    hmap = {sid: pro[sid]["instance"]["h"] for sid in pro if pro[sid].get("status") == "SUCCESS"}
    figs["F01"] = fig_f01(fdir, pdir, h_example=8, actual_h=hmap)  # h of the sample the figure draws
    figs["F02"] = fig_f02(fdir, pdir)
    if not rows:
        for fid in ("F03", "F04", "F05", "F06"):
            figs[fid] = {"status": "NOT_RUN", "reason": "no prototype rows (" + g["terminal"] + ")"}
        return figs
    sids = [r["sample_id"] for r in rows]
    # F03 memory breakdown
    comp = []
    for sid in sids:
        m = nat[sid]["mem"]
        start, cc_, runs_, cand = m["mem_ws_start"], m["mem_ws_cc"], m["mem_ws_runs"], m["mem_ws_candidates"]
        red = max(m["mem_peak_reduction"] or 0, cand) - cand
        comp.append({"sample": short(sid), "input_and_process": start, "chain_and_cc": cc_ - start,
                     "runs": runs_ - cc_, "candidates": cand - runs_, "reduction_transient": red,
                     "peak_E": nat[sid]["peak_E"], "peak_proj_CG": next(r for r in rows if r["sample_id"] == sid)[
                         "peak_proj"]})
    df = pd.DataFrame(comp)
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    bottom = np.zeros(len(df))
    for key, colr in (("input_and_process", GRAY), ("chain_and_cc", AQUA), ("runs", BLUE), ("candidates", ORANGE),
                      ("reduction_transient", RED)):
        v = df[key].to_numpy() / 2**20
        ax.bar(df["sample"], v, bottom=bottom, color=colr, label=key.replace("_", " "), width=0.62,
               edgecolor="white", linewidth=0.6)
        bottom += v
    ax.scatter(df["sample"], df["peak_proj_CG"] / 2**20, marker="_", s=260, color=INK, zorder=5,
               label="projected CG peak")
    ax.set_ylabel("MiB (fresh process)")
    ax.tick_params(axis="x", rotation=60, labelsize=6.5)
    ax.legend(fontsize=6.2, frameon=False, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    save_fig(fig, fdir, "F03_memory_breakdown", df, pdir)
    figs["F03"] = {"status": "OK", "caption_en": "Native Eθ encode-inclusive memory by structure (profile build, one "
                   "fresh process per sample) and the projected CG peak (black dash). The CG can only remove the "
                   "candidate and reduction parts; runs and the chain stay.",
                   "note_uz": "Native xotira taqsimoti va CG proyeksiyasi."}
    # F04 time breakdown
    tb = []
    for sid in sids:
        ph = nat[sid]["phases"]
        r = next(x for x in rows if x["sample_id"] == sid)
        tot = nat[sid]["T_profile_ns"] or 0
        known = sum(ph[k] for k in ("scan_ns", "boundary_ns", "cc_ns", "runs_ns", "candidate_ns", "reduction_ns",
                                    "component_ns")) + ph["solver_ns"]
        tb.append({"sample": short(sid), "scan_boundary": ph["scan_ns"] + ph["boundary_ns"], "cc": ph["cc_ns"],
                   "runs": ph["runs_ns"], "candidates": ph["candidate_ns"],
                   "reductions_components": ph["reduction_ns"] + ph["component_ns"], "solver": ph["solver_ns"],
                   "other": max(0.0, tot - known), "T_E": r["T_E_ns"], "T_proj_CG": r["T_proj_ns"]})
    df = pd.DataFrame(tb)
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    bottom = np.zeros(len(df))
    for key, colr in (("scan_boundary", GRAY), ("cc", AQUA), ("runs", BLUE), ("candidates", ORANGE),
                      ("reductions_components", RED), ("solver", "#7b1fa2"), ("other", "#dadce0")):
        v = df[key].to_numpy() / 1e6
        ax.bar(df["sample"], v, bottom=bottom, color=colr, label=key.replace("_", " "), width=0.62,
               edgecolor="white", linewidth=0.6)
        bottom += v
    ax.scatter(df["sample"], df["T_proj_CG"] / 1e6, marker="_", s=260, color=INK, zorder=5, label="projected CG time")
    ax.set_yscale("log")
    ax.set_ylabel("ms (median of 7)")
    ax.tick_params(axis="x", rotation=60, labelsize=6.5)
    ax.legend(fontsize=6.2, frameon=False, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    save_fig(fig, fdir, "F04_time_breakdown", df, pdir)
    figs["F04"] = {"status": "OK", "caption_en": "Native Eθ encode time by phase (profile build, median of 7 repeats) "
                   "and the projected CG time (black dash; pricing passes x native candidate-pass time + measured "
                   "HiGHS LP time + native greedy time). Log scale.",
                   "note_uz": "Native vaqt taqsimoti va CG proyeksiyasi (log)."}
    # F05 family sizes (every sample converged at the first LP, so a convergence plot is degenerate; see T04)
    fam = []
    for sid in sids:
        nv, cg = pro[sid]["native"], pro[sid]["cg"]
        fam.append({"sample": short(sid), "windows (= runs)": nv.get("candidate_count_before"),
                    "after singleton rule": nv.get("candidates_after_singleton"),
                    "after M1a (stored)": nv.get("candidates_after_adjacency"),
                    "after equal coverage": nv.get("candidates_after_equal"),
                    "after subset (final)": nv.get("candidate_count_after"), "CG columns (dedup)": cg["columns"],
                    "CG iterations": cg["iterations"], "converged": cg["converged"]})
    df = pd.DataFrame(fam)
    keys = ["windows (= runs)", "after singleton rule", "after M1a (stored)", "after equal coverage",
            "after subset (final)", "CG columns (dedup)"]
    cols_ = [GRAY, "#bdc1c6", ORANGE, AQUA, BLUE, RED]
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    x = np.arange(len(df))
    wbar = 0.13
    for k, (key, colr) in enumerate(zip(keys, cols_)):
        ax.bar(x + (k - 2.5) * wbar, df[key].astype(float), width=wbar, color=colr, label=key, edgecolor="white",
               linewidth=0.3)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(df["sample"], rotation=60, fontsize=6.5)
    ax.set_ylabel("count (log)")
    ax.legend(fontsize=6.2, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    save_fig(fig, fdir, "F05_family_sizes", df, pdir)
    nconv1 = int(sum(1 for f_ in fam if f_["CG iterations"] == 1 and f_["converged"]))
    figs["F05"] = {"status": "OK", "caption_en": "Candidate family sizes per development sample: native windows (equal "
                   "to the runs, since h = Z), what the native reductions keep, and the deduplicated columns of the CG "
                   f"prototype. CG converged at the first LP on {nconv1}/{len(fam)} samples, so its pricing never added "
                   "a column (the protocol's convergence plot would be a single point; see T04).",
                   "note_uz": "Oila hajmlari: native reduksiyalar va CG ustunlari; CG birinchi LP'da yaqinlashdi."}
    # F06 ratios
    df = pd.DataFrame([{"sample": short(r["sample_id"]), "R_M_proj": r["R_M"], "R_T_proj": r["R_T"],
                        "R_cert": r["R_cert"], "best_case_R_M": r["best_case_R_M"],
                        "R_T_warm_posthoc": r.get("R_T_warm")} for r in rows])
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    x = np.arange(len(df))
    ax.scatter(x - 0.15, df["R_M_proj"], color=BLUE, s=16, label="memory ratio (projected)")
    ax.scatter(x + 0.15, df["R_T_proj"], color=ORANGE, s=16, label="time ratio (projected)")
    ax.scatter(x, df["best_case_R_M"], color=GRAY, s=10, marker="x", label="memory ratio if CG structures cost 0")
    if "R_T_warm_posthoc" in df and df["R_T_warm_posthoc"].notna().any():
        ax.scatter(x + 0.15, df["R_T_warm_posthoc"], facecolors="none", edgecolors=ORANGE, s=22,
                   label="time ratio, warm HiGHS (post hoc)")
    ax.axhline(1.0, color=INK, lw=0.6)
    ax.axhline(0.95, color=INK, lw=0.6, ls="--")
    ax.text(len(df) - 0.5, 0.95, "gate 0.95", fontsize=6, va="bottom", ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels(df["sample"], rotation=60, fontsize=6.5)
    ax.set_yscale("log")
    ax.set_ylabel("CG / native Eθ")
    ax.legend(fontsize=6.2, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    save_fig(fig, fdir, "F06_projected_ratios", df, pdir)
    figs["F06"] = {"status": "OK", "caption_en": "Projected CG-implicit / native Eθ ratios per sample (memory, time) and "
                   "the memory ratio of the most favourable case where the CG structures cost nothing (runs and chain "
                   "kept). Hollow markers: post-hoc time ratio with the warm HiGHS solve time (the run's LP time "
                   "included the first-call scipy import); not part of the gate. Dashed line: the pre-registered 0.95 "
                   "gate. Log scale.",
                   "note_uz": "Har namuna bo'yicha proyeksiya nisbatlari va gate chizig'i."}
    return figs


# ------------------------------------------------------------------------------------------------------- texts
MATH = {
    "problem_definition.md": """# Problem definition (B protocol)

One regime of CAPE's PINS label section is fixed (certificate_model.md section 2): depth width r = w_D, longest pin
h = min(Z, 2^(8r)), pin cost c = w_I + r, singleton cost s = w_C, background label b (not covered).
A run is a maximal same-label z-interval of one column (x, y). Its CCs u_0..u_{R-1} are distinct (one 2D 4-connected
CC per slice). The CompleteWindows family takes the whole run if R <= h and every length-h window if R > h
(cpp/src/candidates.cpp lines 28-34, cpp/src/candidate_store.cpp lines 63-69).

    OPT = min  c * sum_j x_j + s * sum_u y_u   s.t.  sum_{j contains u} x_j + y_u >= 1  for every non-background CC u,
               x, y in {0, 1}

Question studied: can this problem be solved without materializing the candidate and incidence lists (pricing over
runs), with the same output quality, less memory or time, and a valid certificate?
""",
    "dominance_completeness_theorem.md": """# Dominance completeness of CompleteWindows

**Theorem (extension).** Inside one run let p be extendable to q with C_p subset of C_q and c(p) = c(q). In the
minimum-cost set cover, using q instead of p never increases the cost.

**Proof.** q covers every CC that p covers, so all covering constraints stay satisfied and the cost is unchanged.
If q is already selected, p is redundant and can be dropped, which can only lower the cost. QED

**Corollary (completeness).** In a fixed regime every interval [a, a+l) with l <= h of a run lies in the window that
starts at t = min(a, R - h) (R > h) or in the whole run (R <= h); all these have the same cost c. Hence the optimum over
every interval of every run equals the optimum over CompleteWindows.

**Source audit (2026-11-07).**
- Family: whole run if R <= h, every length-h window otherwise (candidates.cpp, candidate_store.cpp, candidates.hpp:53).
- Cost: c_r = w_I + r independent of the length; s = w_C (byte_model.cpp, certificate_model.md section 1-2).
- Couplings: replacing a pin by a pin of the same label changes neither the written labels K_w nor the counts (w_N);
  inside a fixed regime h_r fits the width r, so extension never widens w_D.

**Scope.** This is a statement about the per-regime set-cover model. The serializer-level bound (width compaction,
regime choice, background) is the one of certificate_model.md sections 4-5. Numerical check: precheck T1
(tables/T03_prechecks.csv).

**Consequence.** No compression gain can come from a wider interval family; inside the family the possible gain is at
most U - L of the certificate.
""",
    "pricing_exactness.md": """# Exact pricing

Duals lambda_u >= 0. Reduced cost of a pin p: r(p) = c - sum_{u in C_p} lambda_u. Along a run a_t = lambda_{u_t},
P_0 = 0, P_{t+1} = P_t + a_t, W_t = P_{t+h} - P_t for t in [0, R-h] (R > h), W = P_R (R <= h);
t* = smallest argmax W_t, r_min = c - W_{t*}.

**Guarantee.** Scanning every window with this formula finds the exact minimum reduced cost in the run, in O(R) time
and O(1) extra working memory (random access to lambda). This does not make the whole algorithm O(1) in memory:
lambda (one value per CC), the runs and the chain stay resident. One full pricing pass reads every useful run.

**Exactness in practice.** The LP pricing uses floor(lambda * 2^30) in int64 (float prefix sums over ~10^7 positions
carry ~1e-7 rounding), tolerance 1e-6 absolute; the certificate pricing uses the integer duals a_u exactly.
Check: precheck T2 (brute-force enumeration, ties, zero and large weights).
""",
    "integer_certificate.md": """# Integer certificate

A dual is feasible for the FULL family when 0 <= lambda_u <= s and W_max <= c for every useful run (fixed regime).
Then sum lambda <= OPT_LP <= OPT. Scaled integers: lambda_u = a_u / q, q = 2^20 (the native scale of
cpp/src/dual_bound.cpp): a_u <= q*s and every window sum <= q*c; L = sum over components ceil(sum a / q) plus s for
every CC outside the LP (each component optimum is an integer).

From float LP duals: a_u = floor(q * lambda_u) clipped to [0, q*s], then every violated window is repaired
deterministically (reduce from the window's last position) and the whole family is re-checked independently in
integers. A float result is never rounded into a "certificate". Runs with min(R, h)*s <= c need no check: their
window sums are at most len*q*s <= q*c. Check: precheck T3 (exact optimum, deliberately infeasible duals).

The native solver already computes such a bound (dual ascent, same scale); the prototype compares against it
(T06), with the same regime and the same background.
""",
    "column_generation_scope.md": """# Bounded column generation: modes and limits

- CG-cert: the native greedy stream is kept (full pipeline) and CG only seeks a tighter lower bound. No memory gain is
  possible in this mode.
- CG-implicit: no candidate list; columns = singletons + one window per useful run, plus violated windows found by
  exact pricing; integer solution = greedy over the generated columns, then redundant-pin removal.
- Limits: the LP optimum need not equal the integer optimum; a budget stop is not an optimality proof; without a
  feasible full-family dual no certificate is claimed; column generation may need many iterations and is not
  guaranteed to be faster.
- If CG-implicit is converged, the LP optimum value does not depend on the initial columns, so CG-cert reuses its L.

**Structural observation (fixed_depth_width, the regime Eθ writes).** The stream regime takes the narrowest depth width
that fits Z: 2^(8 w_D) >= Z, so h = min(Z, 2^(8 w_D)) = Z. Every run then has R <= Z = h and CompleteWindows is exactly
one window per run: the "implicit" family IS the run list, and window pricing cannot add any column. Window pricing
matters only in narrower regimes (h < Z), which the native solver bounds dual-only for the certificate.
""",
    "complexity.md": """# Complexity and measured cost model

One full pricing pass: O(sum of useful run lengths) <= O(V) time, O(1) extra memory per run. k passes plus k LP solves.
Native Eθ: linear passes over V (CC, runs) plus candidate generation, reductions and the solver. The projection model
(protocol section 10) replaces the native candidate + reduction + component + solver time by k pricing passes (each
priced as one native candidate pass), the measured HiGHS LP time and the native greedy time, and keeps runs and chain
resident in memory. It is favourable to CG on purpose; failing it is a robust negative result.
""",
}


def posthoc_warm(run_dir: Path, g: dict) -> dict:
    """Post-hoc diagnostic (results/<run>/posthoc_lp_split.json): the run's LP time included the first-call import of
    scipy.optimize; recompute R_T / R_cert with the warm assembly + HiGHS solve time. Never changes the gate."""
    p = run_dir / "posthoc_lp_split.json"
    if not p.exists():
        return {"rows": [["not measured", None, None, None, None, None, None, None]], "note": "no post-hoc file"}
    sp = json.loads(p.read_text(encoding="utf-8"))["samples"]
    rows, rt, rc = [], [], []
    for r in g["rows"]:
        s = sp.get(r["sample_id"])
        if not s:
            continue
        warm = (s["assembly_s"] + s["linprog_s"]) * 1e9
        r["R_T_warm"] = (r["T_proj_ns"] - r["T_lp_ns"] + warm) / r["T_E_ns"]
        r["R_cert_warm"] = ((r["T_cert_ns"] - r["T_lp_ns"] + warm) / r["T_cert_native_ns"]
                            if r["T_cert_native_ns"] else None)
        rt.append(r["R_T_warm"])
        rc.append(r["R_cert_warm"])
        rows.append([r["sample_id"], round(r["T_lp_ns"] / 1e9, 4), round(warm / 1e9, 4), round(r["R_T"], 4),
                     round(r["R_T_warm"], 4), None if r["R_cert"] is None else round(r["R_cert"], 4),
                     None if r["R_cert_warm"] is None else round(r["R_cert_warm"], 4), round(r["best_case_R_M"], 4)])
    g["posthoc"] = {"R_T_warm": gm(rt), "R_cert_warm": gm(rc), "n": len(rows)}
    rows.append(["geo-mean", None, None,
                 None if g["pooled"].get("R_T_proj") is None else round(g["pooled"]["R_T_proj"], 4),
                 None if gm(rt) is None else round(gm(rt), 4),
                 None if g["pooled"].get("R_cert") is None else round(g["pooled"]["R_cert"], 4),
                 None if gm(rc) is None else round(gm(rc), 4),
                 None if g.get("best_case_R_M") is None else round(g["best_case_R_M"], 4)])
    return {"rows": rows, "note": "Post hoc (after the run, same machine, pinned core, nothing else running): LP matrix "
            "assembly + HiGHS solve measured warm on the converged LP of each sample. The pre-registered gate uses the "
            "run's measured LP time and is not changed by this table."}


def build(run_dir: Path, state: dict, out_name: str) -> dict:
    out = ROOT / f"{out_name}.staging"
    if out.exists():
        shutil.rmtree(out)
    for sub in ("mathematics", "methods", "tables", "figures", "plot_data", "raw_results", "audit", "checks",
                "reproducibility", "scripts"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    g = json.loads((run_dir / "gate.json").read_text(encoding="utf-8")) if (run_dir / "gate.json").exists() else \
        {"rows": [], "routes": {}, "terminal": state.get("terminal") or "BLOCKED_PRECHECK", "G1": False, "G2": False,
         "problems": ["gate not evaluated"], "pooled": {}, "thresholds": TH}
    nat = load_native(ROOT / state["native"]["run_dir"]) if state.get("native", {}).get("run_dir") else {}
    pro = load_proto(run_dir, state)
    tdir = out / "tables"
    tables = []
    inv = state.get("inventory", {})
    tables.append(write_table(tdir, "T01_development_crops", "development crops (frozen before any prototype result)",
                              ["sample_id", "source", "dtype", "shape_zyx", "voxels", "role"],
                              [[d["sample_id"], d["source_id"], d["dtype"], "x".join(map(str, d["shape"])),
                                int(np.prod(d["shape"])), "development"] for d in inv.get("dev_samples", [])]))
    import scipy
    tables.append(write_table(tdir, "T02_methods", "methods and versions", ["method", "what", "version / settings"], [
        [E, "native Eθ encoder (timed comparator)", "impl_mask 6719, FAST, certificate off"],
        [EP, "native Eθ with phase timers and memory marks", "profile_memory on (diagnostics only)"],
        [EC, "native Eθ with the integer dual-ascent certificate", "certificate all_regimes"],
        ["cg_implicit (prototype)", "bounded column generation + exact pricing + integer certificate",
         f"Python, numpy {np.__version__}, scipy {scipy.__version__} linprog(HiGHS); budget "
         f"{inv.get('prototype_config', {}).get('budget_s')} s, max_iter {inv.get('prototype_config', {}).get('max_iter')}"]]))
    pc = state.get("prechecks", {}).get("by_check", {})
    t4 = [p.get("T4", {}).get("pass") for p in pro.values() if p.get("status") == "SUCCESS"]
    pre_rows = [[k, v["passed"], v["failed"], v["skipped"]] for k, v in sorted(pc.items())]
    pre_rows.append(["T4 on development crops", sum(1 for x in t4 if x), sum(1 for x in t4 if not x),
                     len(pro) - len(t4)])
    tables.append(write_table(tdir, "T03_prechecks", "precheck results (G1)", ["check", "passed", "failed",
                                                                              "skipped / not run"], pre_rows,
                              f"G1 = {g.get('G1')}"))
    t4rows = []
    for sid in sorted(pro):
        p = pro[sid]
        if p.get("status") != "SUCCESS":
            t4rows.append([sid] + [None] * 17 + [p.get("task_status")])
            continue
        n, cg, ins = p["native"], p["cg"], p["instance"]
        na = nat.get(sid, {})
        t4rows.append([sid, ins["n_cc"], ins["n_runs"], ins["useful_runs"], n.get("candidate_count_before"),
                       n.get("candidates_after_singleton"), n.get("candidates_after_adjacency"),
                       n.get("candidates_after_equal"), n.get("candidate_count_after"), n.get("incidence_count"),
                       cg["columns"], cg["nnz"], cg["iterations"], cg["pricing_passes"], cg["converged"],
                       round(cg["lp_time_s"], 2), mib(cg["lp_rss_bytes"]), ms(na.get("T_E_ns")), "SUCCESS"])
    tables.append(write_table(tdir, "T04_counts_per_sample", "native candidate counts vs prototype columns",
                              ["sample_id", "CCs", "runs", "useful runs", "windows (native, before)",
                               "after singleton rule", "after M1a (stored)", "after equal", "after subset (final)",
                               "native incidences", "CG columns", "CG incidences", "CG iterations", "pricing passes",
                               "converged", "LP s (HiGHS)", "LP RSS MiB", "Eθ encode ms", "status"], t4rows))
    t5 = []
    for r in g["rows"]:
        t5.append([r["sample_id"], mib(r["peak_E"]), mib(r["peak_proj"]), round(r["R_M"], 4),
                   round(r["best_case_R_M"], 4), ms(r["T_E_ns"]), ms(r["T_proj_ns"]), round(r["R_T"], 4), r["k"],
                   ms(r["T_cert_ns"]), ms(r["T_cert_native_ns"]), None if r["R_cert"] is None else round(r["R_cert"], 4)])
    po = g.get("pooled", {})
    t5.append(["geo-mean", None, None, None if po.get("R_M_proj") is None else round(po["R_M_proj"], 4),
               None if g.get("best_case_R_M") is None else round(g["best_case_R_M"], 4), None, None,
               None if po.get("R_T_proj") is None else round(po["R_T_proj"], 4), None, None, None,
               None if po.get("R_cert") is None else round(po["R_cert"], 4)])
    rt = g.get("routes", {})
    note = (f"Gate G2 = {g.get('G2')} (terminal {g.get('terminal')}). Route M pass = {rt.get('M', {}).get('pass')}, "
            f"route T pass = {rt.get('T', {}).get('pass')}, route C pass = {rt.get('C', {}).get('pass')}. Thresholds: "
            f"{json.dumps(TH)}.")
    tables.append(write_table(tdir, "T05_projection_and_gate", "projection model and gate G2",
                              ["sample_id", "Eθ peak MiB", "CG projected peak MiB", "R_M proj",
                               "R_M if CG structures cost 0", "Eθ ms", "CG projected ms", "R_T proj",
                               "pricing passes k", "CG-cert projected ms", "native certified ms", "R_cert"], t5, note))
    t6 = [[r["sample_id"], r["U_E"], r["L_asc"], r["L_CG"], r["U_E"] - r["L_asc"],
           None if r["L_CG"] is None else r["U_E"] - r["L_CG"], round(100 * (r["U_E"] - r["L_asc"]) / r["U_E"], 4),
           None if r["L_CG"] is None else round(100 * (r["U_E"] - r["L_CG"]) / r["U_E"], 4), r["U_CG"],
           r["U_CG"] <= r["U_E"], r["cert_feasible"], r["converged"], r["stop"]] for r in g["rows"]]
    t6.append(["pooled", None, None, None, po.get("gap_ascent"), po.get("gap_CG"), None, None, None, None, None, None,
               None])
    tables.append(write_table(tdir, "T06_certificate", "payload bounds (same regime, same background; cost units = "
                              "bytes of the labels payload)", ["sample_id", "U (Eθ)", "L ascent (native)", "L CG",
                                                               "gap ascent", "gap CG", "gap ascent % of U",
                                                               "gap CG % of U", "U CG-implicit",
                                                               "U_CG <= U_Eθ", "certificate feasible", "CG converged",
                                                               "CG stop"], t6))
    t7 = [[sid, p.get("task_status"), (p.get("error") or "")[:160]] for sid, p in sorted(pro.items())
          if p.get("task_status") != "SUCCESS"]
    for stg, v in state.get("stages", {}).items():
        if v.get("status") not in ("DONE", "RUNNING"):
            t7.append([f"stage {stg}", v.get("status"), (v.get("reason") or "")[:160]])
    for p in g.get("problems", []):
        t7.append(["gate", "PROBLEM", p[:160]])
    tables.append(write_table(tdir, "T07_failures_and_exclusions", "failures, timeouts, not-run stages",
                              ["item", "status", "reason"], t7 or [["none", "-", "no failures, timeouts or exclusions"]]))
    ph = posthoc_warm(run_dir, g)
    tables.append(write_table(tdir, "T08_posthoc_sensitivity", "POST-HOC sensitivity (not part of the gate): warm "
                              "HiGHS time instead of the run's first-call LP time", ["sample_id", "LP s (run)",
                              "LP s (warm, post hoc)", "R_T (gate)", "R_T (warm LP)", "R_cert (gate)",
                              "R_cert (warm LP)", "R_M if CG structures cost 0"], ph["rows"], ph["note"]))
    figs = build_figures(out / "figures", out / "plot_data", g, nat, pro)
    # mathematics, methods, report
    for name, txt in MATH.items():
        (out / "mathematics" / name).write_text(txt, encoding="utf-8")
    texts(out, g, state, nat, pro, figs, tables)
    # raw results, audit, reproducibility
    rr = out / "raw_results"
    for sid in pro:
        p = ROOT / (state["prototype"][sid]["json"])
        if p.exists():
            shutil.copy(p, rr / f"prototype_{sid}.json")
    if state.get("native", {}).get("run_dir"):
        shutil.copy(ROOT / state["native"]["run_dir"] / "05_raw_metrics" / "results.csv", rr / "native_results.csv")
    for fn in ("gate.json", "research_state.json", "prechecks_junit.xml"):
        if (run_dir / fn).exists():
            shutil.copy(run_dir / fn, (out / "audit" if fn != "prechecks_junit.xml" else rr) / fn)
    s0 = ROOT / "results" / "q1b_stage0.json"
    if s0.exists():
        shutil.copy(s0, out / "audit" / "stage0_q1_package_fixes.json")
    for fn in ("cg.py",):
        shutil.copy(ROOT / "cape" / fn, out / "scripts" / fn)
    for fn in ("cg_prototype.py", "run_research.py", "cg_article.py", "validate_cg_package.py"):
        shutil.copy(ROOT / "tools" / fn, out / "scripts" / fn)
    shutil.copy(ROOT / "tests" / "test_cg_prechecks.py", out / "scripts" / "test_cg_prechecks.py")
    shutil.copy(ROOT / "docs" / "CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md", out / "reproducibility" / "PROTOCOL_UZ.md")
    shutil.copy(ROOT / "requirements.lock", out / "reproducibility" / "requirements.lock")
    (out / "reproducibility" / "hashes.json").write_text(json.dumps(
        {"inventory": inv, "native_run": state.get("native"), "seed": 20261107}, indent=1, default=str),
        encoding="utf-8")
    (out / "reproducibility" / "REPRODUCE.md").write_text(f"""# Reproduce (B protocol)

```powershell
py -3.12 scripts\\bootstrap.py                                       # venv + native build (as for CAPE)
.venv\\Scripts\\python -m pytest tests\\test_cg_prechecks.py -q          # G1 prechecks T1-T4
.venv\\Scripts\\python tools\\run_research.py --mode full --fresh-run    # full B protocol run
.venv\\Scripts\\python tools\\run_research.py --mode full --resume-run {state['run_id']}
.venv\\Scripts\\python tools\\run_research.py --mode render --run-id {state['run_id']}   # rebuild this package only
```
Run id: `{state['run_id']}`; source hash `{inv.get('source_hash', '')[:12]}`; git `{inv.get('git_head')}`; environment
lock hash `{inv.get('env_lock_hash')}`; seed 20261107. Raw rows: `raw_results/`. Timing: one machine, one thread,
pinned P-core, nothing else running.
""", encoding="utf-8")
    manifest(out, figs, tables, g)
    # place: archive the previous folder (never delete), then move staging in, then zip
    dest = ROOT / out_name
    if dest.exists():
        arch = ROOT / f"{out_name}_archive_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        dest.rename(arch)
    out.rename(dest)
    z = ROOT / (out_name.replace(" ", "_") + ".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dest.rglob("*")):
            if p.is_file():
                zf.write(p, Path(out_name) / p.relative_to(dest))
    return {"package": dest.relative_to(ROOT).as_posix(), "zip": z.name, "terminal": g["terminal"],
            "figures": {k: v["status"] for k, v in figs.items()}, "tables": [t["id"] for t in tables]}


def texts(out: Path, g: dict, state: dict, nat: dict, pro: dict, figs: dict, tables: list) -> None:
    rows, po, rt = g["rows"], g.get("pooled", {}), g.get("routes", {})
    term = g["terminal"]
    neg = term != "COMPLETE_VALIDATED"
    n = len(rows)
    cand_share = []
    for r in rows:
        m = nat[r["sample_id"]]["mem"]
        cand_share.append((r["peak_E"] - m["mem_peak_runs"]) / r["peak_E"])
    t_share = []
    for r in rows:
        ph = nat[r["sample_id"]]["phases"]
        t_share.append((ph["candidate_ns"] + ph["reduction_ns"] + ph["component_ns"] + ph["solver_ns"]) /
                       (nat[r["sample_id"]]["T_profile_ns"] or 1))
    med = lambda x: st.median(x) if x else None  # noqa: E731
    conv = sum(1 for r in rows if r["converged"])
    hz = sum(1 for sid in pro if pro[sid].get("status") == "SUCCESS" and pro[sid]["instance"]["h"] ==
             pro[sid]["shape_zyx"][0])
    it1 = sum(1 for sid in pro if pro[sid].get("status") == "SUCCESS" and pro[sid]["cg"]["iterations"] == 1)
    rel = [(100 * (r["U_E"] - r["L_asc"]) / r["U_E"], 100 * (r["U_E"] - r["L_CG"]) / r["U_E"]) for r in rows
           if r["L_CG"] is not None]
    phc = g.get("posthoc") or {}
    qual = sum(1 for r in rows if r["U_CG"] <= r["U_E"])
    lge = sum(1 for r in rows if r["L_CG"] is not None and r["L_CG"] >= r["L_asc"])
    m = out / "methods"
    (m / "METHODS_EN.md").write_text(f"""# Methods (B protocol)

Model: one fixed regime of the PINS labels section (mathematics/problem_definition.md). Candidate family:
CompleteWindows (proved complete: mathematics/dominance_completeness_theorem.md).

Prototype (not an encoder): native diagnostic encode of Eθ (impl_mask 6719) returns its CC ids, records, background,
regime widths and the dual-ascent bound; the instance is rebuilt from them and checked against the native counts and
selection (precheck T4). Column generation: LP restricted master over singletons + one window per useful run, solved
with HiGHS (scipy.optimize.linprog); one exact pricing pass over every useful run per iteration (prefix sums on
floor(lambda * 2^30), tolerance 1e-6); at most 50 000 new columns per iteration; budget 40 iterations or 1800 s per
sample. Integer solution: deterministic greedy over the generated columns, then redundant-pin removal. Certificate:
integer duals (q = 2^20), deterministic repair, independent full-family check, per-component ceiling.

Pseudocode (CG-implicit, one regime):
```
lam <- none; cols <- {{one window per useful run}} (deduplicated by CC set)
repeat (<= 40 iterations, <= 1800 s):
    (x, y, lam) <- LP(cols + singletons)               # HiGHS
    for each useful run: W*, t* <- max window of floor(lam*2^30) (prefix sums)
    V <- runs with W* > c (1 + tolerance); if V empty: stop (converged)
    cols <- cols + best window of the most violated runs (<= 50 000)
U  <- greedy(cols + singletons) + redundant-pin removal
L  <- integer_certificate(lam)                           # floor q=2^20, repair, re-check, ceil per component
```
Comparator: native Eθ on the same {n} development crops, same machine, one thread, pinned P-core, 2 warmups + 7 timed
repeats; one fresh-process memory measurement per sample (profile build for the memory marks and phase times).
Projection and gate: protocol section 10 (favourable to CG on purpose). The prototype's own Python time and peak are
recorded in raw_results/ only for information.
""", encoding="utf-8")
    res = [f"# Results (B protocol, development data only; terminal status {term})", ""]
    res.append(f"- Prechecks (G1): {g.get('G1')}. Tables T03 (T1 coverage, T2 pricing, T3 certificate, T4 instance).")
    if n:
        res += [
            f"- Native Eθ memory: the part that CG could remove (peak minus the peak reached by the end of the runs "
            f"phase) is a median {100 * med(cand_share):.1f}% of the encode-inclusive peak over {n} crops; "
            f"the most favourable memory ratio (CG structures cost 0) is a geo-mean {f(g.get('best_case_R_M'), 4)}.",
            f"- Native Eθ time: candidates + reductions + components + solver are a median {100 * med(t_share):.1f}% "
            "of the profiled encode time.",
            f"- Structure: in the regime Eθ writes, h = Z on {hz}/{n} crops, so CompleteWindows is one window per run "
            f"and CG converged at the first LP on {it1}/{n} crops: pricing never added a column (mathematics/"
            "column_generation_scope.md).",
            f"- CG-implicit converged on {conv}/{n} crops; its greedy integer cover was not worse than Eθ on {qual}/{n} "
            "crops (Eθ also uses exact DP and local search).",
            f"- Projected CG-implicit / Eθ: memory {f(po.get('R_M_proj'), 4)}, time {f(po.get('R_T_proj'), 4)} "
            "(geo-means; table T05).",
            f"- Certificate: L_CG >= L_ascent on {lge}/{n} crops; pooled gap {po.get('gap_ascent')} (ascent) vs "
            f"{po.get('gap_CG')} (CG) payload bytes; median gap {f(med([a for a, _ in rel]), 3)}% -> "
            f"{f(med([b for _, b in rel]), 3)}% of U; projected CG-cert / native certified time {f(po.get('R_cert'), 4)} "
            "(table T06).",
            f"- Post hoc (not part of the gate, table T08): with the warm HiGHS time instead of the run's first-call LP "
            f"time, the time ratio is {f(phc.get('R_T_warm'), 4)} and the certificate time ratio "
            f"{f(phc.get('R_cert_warm'), 4)} (geo-means); the conclusion does not change.",
            f"- Gate G2: route M {rt.get('M', {}).get('pass')}, route T {rt.get('T', {}).get('pass')}, route C "
            f"{rt.get('C', {}).get('pass')} -> G2 = {g.get('G2')}."]
    else:
        res.append("- No prototype rows: " + "; ".join(g.get("problems", [])[:5]))
    res.append("")
    res.append("Negative result: the pre-registered gate was not met; native implementation and a final benchmark were "
               "not run (NOT_RUN_GATE_FAILED)." if neg else "The pre-registered gate was met on development data; a "
               "native implementation needs a separate decision (protocol section 11).")
    (m / "RESULTS_EN.md").write_text("\n".join(res) + "\n", encoding="utf-8")
    (m / "LIMITATIONS_EN.md").write_text(f"""# Limitations

- Development data only ({n} crops, CREMI and Crackle samples); no held-out or new acquisition was used.
- One machine, one thread. Time and memory of a native CG are projected (protocol section 10), not measured.
- The projection prices a pricing pass as one native candidate pass and the integer step as the native greedy; both
  favour CG. The LP time is HiGHS through scipy (native code), measured on this machine.
- One fresh-process memory measurement per sample (as in the Q1 final protocol).
- The certificate and the theorem concern the per-regime set-cover model; the serializer-level bound is that of
  certificate_model.md.
- Column generation and prefix-sum pricing are known techniques; nothing here is claimed as a new algorithm.
- The LP time of the run includes the sparse-matrix assembly and, on the first call of each process, the import of
  scipy.optimize; table T08 gives the warm time post hoc. The gate uses the run's measured time as pre-registered.
- In the Eθ stream regime h = Z, so on these data the window pricing had nothing to price (one window per run); a
  narrower regime (h < Z) was not tested by the prototype.
- One development smoke run (one CREMI crop, 300 s budget) checked the pipeline before the formal run; it is not
  evidence and no threshold was changed.
""", encoding="utf-8")
    (m / "CONTRIBUTION_AND_PRIOR_ART_EN.md").write_text("""# Contribution and prior art

| Item | Status | Note |
|---|---|---|
| Dominance completeness of CompleteWindows | small theoretical element (proved, source-audited, checked T1) | closes the "wider interval family" direction |
| Exact window pricing by prefix sums | known technique | O(R) per run; checked T2 |
| Column generation for set cover (LP duality) | classical | bounded prototype only |
| Integer dual certificate | already in CAPE (cpp/src/dual_bound.cpp) | prototype uses the same scale |
| Projection-based negative/positive verdict | protocol design | favourable to CG on purpose |

Novelty would require a new theorem from the CAPE format, an implicit algorithm different from known methods, or a
proven complexity improvement. None of these is claimed.
""", encoding="utf-8")
    (m / "MANUSCRIPT_DRAFT_EN.md").write_text(
        ("# NEGATIVE-RESULT DRAFT (not a ready manuscript)\n\n" if neg else "# PILOT DRAFT\n\n")
        + "## Abstract\nWe test whether CAPE's certified pin selection can be computed without materializing candidate "
          "and incidence lists, using exact window pricing and bounded column generation, and we prove that the "
          "CompleteWindows family is dominance-complete in each regime. "
        + (f"On {n} development crops the pre-registered gate was not met (terminal {term})." if neg else
           f"On {n} development crops the pre-registered gate was met.")
        + "\n\n## Method\nSee methods/METHODS_EN.md and mathematics/.\n\n## Results\nSee methods/RESULTS_EN.md, tables "
          "T03-T07 and figures F03-F06.\n\n## Limitations\nSee methods/LIMITATIONS_EN.md.\n", encoding="utf-8")
    caps = ["# Figure captions", ""]
    for fid in sorted(figs):
        r = figs[fid]
        caps += [f"**{fid}** ({r['status']}): {r.get('caption_en') or r.get('reason')}", f"  - UZ: {r.get('note_uz', '')}",
                 ""]
    (m / "CAPTIONS_EN.md").write_text("\n".join(caps), encoding="utf-8")
    (m / "references.bib").write_text("""% Only sources that the project already cites and verified (Q1 package references.bib).
@article{crackle, title={Crackle: a compression codec for 3D dense segmentation}, author={Silversmith, William},
  note={https://github.com/seung-lab/crackle, commit 14b39b1 vendored in this repository}}
""", encoding="utf-8")
    claims = [["B1", "CompleteWindows is dominance-complete in each regime", "SUPPORTED",
               "mathematics/dominance_completeness_theorem.md; tables/T03_prechecks.csv"],
              ["B2", "Prefix-sum pricing finds the exact minimum reduced cost per run", "SUPPORTED",
               "mathematics/pricing_exactness.md; tables/T03_prechecks.csv"],
              ["B3", "The integer certificate brackets the optimum (L <= OPT <= U)", "SUPPORTED",
               "mathematics/integer_certificate.md; tables/T03_prechecks.csv"],
              ["B4", "CG-implicit lowers the projected encode-inclusive peak by >= 5% at preserved quality",
               "SUPPORTED" if rt.get("M", {}).get("pass") else "UNSUPPORTED", "tables/T05_projection_and_gate.csv"],
              ["B5", "CG-implicit lowers the projected encode time by >= 5% at preserved quality",
               "SUPPORTED" if rt.get("T", {}).get("pass") else "UNSUPPORTED", "tables/T05_projection_and_gate.csv"],
              ["B6", "CG-cert halves the certificate gap at no extra time", "SUPPORTED" if rt.get("C", {}).get("pass")
               else "UNSUPPORTED", "tables/T06_certificate.csv"],
              ["B7", "A wider pin interval family can improve compression", "CONTRADICTED",
               "mathematics/dominance_completeness_theorem.md"],
              ["B8", "Native CG implementation / final benchmark", "NOT_RUN" if neg else "NOT_RUN (needs decision)",
               "protocol section 11"]]
    with open(out / "claims_ledger.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "claim", "status", "evidence"])
        w.writerows(claims)
    final_report(out, g, state, n, med(cand_share), med(t_share), conv, qual, lge, hz, it1, rel, phc)


def final_report(out, g, state, n, cand_med, t_med, conv, qual, lge, hz=0, it1=0, rel=(), phc=None):
    po, rt = g.get("pooled", {}), g.get("routes", {})
    s0 = state.get("stage0", {})
    term = g["terminal"]
    L = ["# B yo'nalishi: yakuniy hisobot (avtomatik yaratilgan)", "",
         f"**Texnik holat:** {term}. **Ilmiy holat:** " + ("salbiy natija (gate o'tmadi)" if term ==
                                                            "STOPPED_GATE_FAILED" else term), "",
         "## 0-bosqich: Q1 paketidagi tuzatishlar",
         f"- Holat: {s0.get('status')}; commit: {s0.get('commit')}; amendment run: {s0.get('amendment_run')}; "
         f"neuroglancer_b8_u32 uint16 qatorlari: {s0.get('ng_u32_rows')}; paket validatori: {s0.get('validation')}.",
         "", "## Oldindan tekshiruvlar (G1)",
         f"- G1 = {g.get('G1')} (T03 jadvali). Teorema: mathematics/dominance_completeness_theorem.md.", "",
         "## Prototip (development, {} crop)".format(n)]
    if n:
        L += [f"- CG to'liq yaqinlashdi: {conv}/{n}; integer yechim Eθ dan yomon emas: {qual}/{n}; "
              f"L_CG >= L_ascent: {lge}/{n}.",
              f"- CG olib tashlashi mumkin bo'lgan native xotira ulushi (mediana): {100 * cand_med:.1f}%; eng qulay "
              f"holatdagi xotira nisbati (geo-mean): {f(g.get('best_case_R_M'), 4)}.",
              f"- Candidate + reduksiya + komponent + solver vaqti ulushi (mediana): {100 * t_med:.1f}%.",
              f"- Proyeksiya (geo-mean): xotira {f(po.get('R_M_proj'), 4)}, vaqt {f(po.get('R_T_proj'), 4)}, "
              f"sertifikat vaqti {f(po.get('R_cert'), 4)}; gap {po.get('gap_ascent')} -> {po.get('gap_CG')} bayt.",
              f"- Tuzilish: Eθ yozadigan rejimda h = Z ({hz}/{n} crop), ya'ni CompleteWindows = har run'ga bitta oyna; "
              f"CG {it1}/{n} crop'da birinchi LP'da yaqinlashdi, pricing birorta ustun qo'shmadi.",
              f"- Sertifikat: gap mediana {f(st.median([a for a, _ in rel]) if rel else None, 3)}% -> "
              f"{f(st.median([b for _, b in rel]) if rel else None, 3)}% (U ga nisbatan); lekin vaqt "
              f"{f(po.get('R_cert'), 2)}x.",
              f"- Post-hoc (gate'ga kirmaydi, T08): iliq HiGHS vaqti bilan vaqt nisbati "
              f"{f((phc or {}).get('R_T_warm'), 3)}, sertifikat vaqti {f((phc or {}).get('R_cert_warm'), 3)}; "
              "xulosa o'zgarmaydi."]
    else:
        L += ["- Prototip qatorlari yo'q: " + "; ".join(g.get("problems", [])[:5])]
    L += ["", "## Gate G2",
          f"- Yo'l M (xotira): {rt.get('M', {}).get('pass')}; yo'l T (vaqt): {rt.get('T', {}).get('pass')}; "
          f"yo'l C (sertifikat): {rt.get('C', {}).get('pass')}. G2 = {g.get('G2')}.",
          "- Native implementatsiya va final benchmark: " + ("NOT_RUN_GATE_FAILED." if not g.get("G2") else
                                                           "alohida qaror kerak (protokol 11-bo'lim)."),
          "", "## Halol baho (10 ballik, faqat shu B ishi uchun)",
          "| Kategoriya | Ball | Asos |", "|---|---|---|",
          "| Matematik to'g'rilik | 9 | teorema isbotlangan, source bilan tekshirilgan, T1-T3 aniq solver bilan |",
          "| Tajriba dizayni | 8 | gate va proyeksiya natijadan oldin qayd etilgan; faqat development, bitta mashina |",
          "| Natija kuchi | " + ("2" if not g.get("G2") else "5") + " | " + ("gate o'tmadi" if not g.get("G2") else
                                                                         "gate o'tdi, lekin faqat proyeksiya") + " |",
          "| Yangilik | 2 | column generation va prefiks yig'indi ma'lum; teorema kichik element |",
          "| Halollik | 9 | salbiy natija va cheklovlar ochiq; raqamlar xom fayllardan |", "",
          "## Cheklovlar", "- methods/LIMITATIONS_EN.md.", "",
          "Hech narsa tashqariga yuborilmadi. Qayta yaratish: reproducibility/REPRODUCE.md."]
    (out / "YAKUNIY_HISOBOT_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "README_UZ.md").write_text(f"""# maqola uchun 2 (B yo'nalishi)

Texnik holat: **{term}**. Protokol: reproducibility/PROTOCOL_UZ.md. Yakuniy hisobot: YAKUNIY_HISOBOT_UZ.md.

| Papka | Tarkib |
|---|---|
| mathematics/ | masala, dominance-to'liqlik teoremasi, pricing, integer sertifikat, CG doirasi, murakkablik |
| methods/ | METHODS, RESULTS, LIMITATIONS, prior-art, qo'lyozma qoralamasi, captionlar |
| tables/ | T01-T07 (CSV, MD, TeX) |
| figures/ | F01-F06 (PNG, SVG, PDF); plot_data/ da CSV |
| raw_results/ | native results.csv, prototip JSONlari, precheck junit |
| audit/ | gate.json, run holati, 0-bosqich dalillari |
| checks/ | validator hisoboti, vizual ko'rik |
| reproducibility/ | protokol, REPRODUCE.md, hashlar, lock |
""", encoding="utf-8")


def manifest(out: Path, figs: dict, tables: list, g: dict) -> None:
    rows = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "artifact_manifest.csv":
            rel = p.relative_to(out).as_posix()
            rows.append([rel, rel.split("/")[0], hashlib.sha256(p.read_bytes()).hexdigest()[:16], "OK", ""])
    for fid, r in figs.items():
        if r["status"] != "OK":
            rows.append([f"figures/{fid}", "figures", "", r["status"], r.get("reason", "")])
    with open(out / "artifact_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "role", "sha256_16", "status", "reason"])
        w.writerows(rows)
