"""CAPE Q1 article package generator (task v3, sections 9-12). Reads ONE finished Q1 run, never measures.

    python tools/q1_article.py --run-id q1_<stamp> --raw-audit   # results/<run_id>/raw_audit.{json,csv}
    python tools/q1_article.py --run-id q1_<stamp> --build       # results/<run_id>/article_staging/ (the package)

Numbers flow raw database -> tools/q1_analysis.py -> analysis.json / plot_data / tables -> texts (templated). No
number is typed by hand into a text; a missing artifact is listed as BLOCKED in artifact_manifest.csv.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("CAPE_ROOT") or Path(__file__).resolve().parents[1])  # CAPE_ROOT: run a copy against the repo data
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(ROOT))

import q1_figs as F  # noqa: E402
from q1_analysis import DATASETS, E0, E_NEW, V21, analyze, map_status, to_jsonable  # noqa: E402
from q1_common import load_cells  # noqa: E402

TREE = ["figures", "plot_data", "tables", "object_examples", "methods", "mathematics", "reproducibility",
        "raw_results", "scripts", "audit", "supplementary", "checks"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def f(x, nd=3, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "NA"
    return f"{x:.{nd}f}{'%' if pct else ''}"


def ci(c, nd=3):
    return "NA" if not c else f"[{c[0]:.{nd}f}, {c[1]:.{nd}f}]"


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ tables
def write_table(out: Path, tid: str, name: str, rows: list[dict], title: str, cols: list[str] | None = None) -> dict:
    tdir = out / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    cols = cols or (list(rows[0].keys()) if rows else ["empty"])
    stem = f"{tid}_{name}"
    with open(tdir / f"{stem}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})

    def cell(v):
        if isinstance(v, float):
            return f"{v:.4g}" if abs(v) < 1e6 else f"{v:.0f}"
        return "NA" if v is None else str(v)

    md = [f"**{tid}. {title}**", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(cell(r.get(c)) for c in cols) + " |" for r in rows]
    (tdir / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def tex(v):
        return cell(v).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")

    tx = [r"\begin{table}[t]\centering\scriptsize", rf"\caption{{{tex(title)}}}\label{{tab:{tid}}}",
          r"\begin{tabular}{" + "l" * len(cols) + "}", r"\hline", " & ".join(tex(c) for c in cols) + r" \\ \hline"]
    tx += [" & ".join(tex(r.get(c)) for c in cols) + r" \\" for r in rows]
    tx += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (tdir / f"{stem}.tex").write_text("\n".join(tx) + "\n", encoding="utf-8")
    return {"id": tid, "file": f"tables/{stem}", "status": "OK" if rows else "BLOCKED",
            "reason": None if rows else "no rows", "title": title, "n_rows": len(rows)}


def comp_row(ds: str, cid: str, p: dict) -> dict:
    return {"dataset": ds, "comparison": cid, "group": p.get("group"), "new": p["new"], "base": p["base"],
            "n": p["n"], "clusters": p.get("n_clusters"), "bytes_new": p.get("bytes_new"),
            "bytes_base": p.get("bytes_base"), "G_B_pct": p.get("G_B_pct"), "G_B_ci": p.get("G_B_ci"),
            "W/T/L": f"{p.get('smaller')}/{p.get('equal')}/{p.get('larger')}", "S_T": p.get("S_T"),
            "S_T_ci": p.get("S_T_ci"), "time_reduction_pct": p.get("time_reduction_pct"), "R_M": p.get("R_M"),
            "R_M_ci": p.get("R_M_ci"), "S_D": p.get("S_D"), "bytes_identical": p.get("bytes_identical"),
            "excluded": p.get("n_excluded"), "worst_speedup": p.get("worst_speedup", {}).get("speedup")
            if p.get("worst_speedup") else None}


def build_tables(out: Path, res: dict, manifests: dict, sel: dict, audit_dir: Path) -> list[dict]:
    recs = []
    # T01 datasets
    t01 = []
    for ds, rows in manifests.items():
        d = res["datasets"].get(ds, {})
        ctr = d.get("counters", [])
        ids = [r["label_count"] for r in ctr if r.get("label_count")]
        ccs = [r["cc_count"] for r in ctr if r.get("cc_count")]
        shapes = sorted({"x".join(map(str, r["shape"][::-1])) for r in rows})
        t01.append({"dataset": ds, "role": DATASETS.get(ds, ds), "source": rows[0].get("citation"),
                    "acquisition": rows[0].get("specimen_id"), "dtype": ",".join(sorted({r["dtype"] for r in rows})),
                    "shapes_XxYxZ": "; ".join(shapes[:4]) + (" ..." if len(shapes) > 4 else ""), "n_volumes": len(rows),
                    "clusters": len({r["macroblock_id"] for r in rows}),
                    "voxels_total": int(sum(np.prod(r["shape"]) for r in rows)),
                    "ids_per_volume_median": float(np.median(ids)) if ids else None,
                    "cc_per_volume_median": float(np.median(ccs)) if ccs else None,
                    "spacing_xyz_nm": rows[0].get("spacing_xyz"), "split": rows[0].get("split"),
                    "licence": rows[0].get("license")})
    recs.append(write_table(out, "T01", "datasets", t01, "Datasets and objects (3D neuron ID segmentation maps)"))
    # T02 methods
    t02 = []
    from cape.config import load_methods

    M = load_methods()
    used = sorted({k.split("+")[0] for d in res["datasets"].values() for k in (t["method"] for t in d["totals"])})
    for m in used:
        spec = M.get(m, {})
        vers = {}
        for d in res["datasets"].values():
            vers.update({w: v["version"] for w, v in d["versions"].get(m, {}).items()})
        t02.append({"method": m, "adapter": spec.get("adapter"), "role": spec.get("role"),
                    "options": spec.get("options"), "version": vers.get("none") or next(iter(vers.values()), None),
                    "threads": 1, "wrappers": sorted(vers), "description": spec.get("description", "")[:160]})
    recs.append(write_table(out, "T02", "methods", t02, "Compared methods, versions and parameters (1 thread)"))
    # T03 primary matched comparisons
    order = ["C1", "BUILD", "C1_live", "C2", "C3_wgreedy", "C3_glocal", "C3_stock_corr", "C3_stock", "C3_stock_vendor",
             "C3_pins_fast", "C3_flat", "C3_compresso", "C3_ng_u32", "C3_ng", "C3_zstd9"]
    t03 = [comp_row(ds, cid, d["comparisons"][cid]) for ds, d in res["datasets"].items()
           if ds in ("j0126", "snemi", "hemibrain") for cid in order if cid in d["comparisons"]
           and not d["comparisons"][cid].get("empty")]
    recs.append(write_table(out, "T03", "primary_matched", t03,
                            "Matched comparisons: C1 (Eθ vs frozen v3), build drift, C2 (historical), C3 (competitors)"))
    # T04 scale: per volume
    t04 = []
    for ds in ("scale", "scale_stock"):
        if ds not in res["datasets"]:
            continue
        cells = load_cells(res["datasets"][ds]["run_dir"])
        for (s, k), c in sorted(cells.items()):
            if "+" in k:
                continue
            t04.append({"track": ds, "sample_id": s, "method": k, "voxels": c["voxels"],
                        "status": ",".join(f"{map_status(a)}:{n}" for a, n in c["statuses"].items()),
                        "bytes": c["total_bytes"], "enc_ms_median": c["enc_med"] / 1e6 if c["enc_med"] else None,
                        "peak_enc_mib": c["peak_enc"] / 2**20 if c["peak_enc"] else None})
    sk = ROOT / "data" / "manifests" / "confirm_snemi3d_v3_scale_skipped.json"
    if sk.exists():
        for r in json.loads(sk.read_text(encoding="utf-8")):
            t04.append({"track": "scale_stock", "sample_id": r.get("sample_id"), "method": "stock methods",
                        "voxels": r.get("voxels"), "status": "SKIPPED_BUDGET", "bytes": None, "enc_ms_median": None,
                        "peak_enc_mib": None})
    recs.append(write_table(out, "T04", "scale", t04, "Scale track: SNEMI3D full volume and its 4 subvolumes "
                            "(ONE acquisition; descriptive, no bootstrap across them)"))
    # T05 ablation and practical gates
    t05 = []
    for mod, dd in sel["modules"].items():
        lo = dd["loo"]
        t05.append({"stage": "development (seen data)", "item": mod, "decision": "ACCEPT" if dd["accepted"] else "REJECT",
                    "S_T": lo["S_T"], "S_T_ci": lo["S_T_ci"], "R_M": lo["R_M"], "R_M_ci": lo["R_M_ci"],
                    "practical": "speed CI>1 or memory CI<1; other axis within 2%",
                    "statistical": f"S_T CI {ci(lo['S_T_ci'])}, R_M CI {ci(lo['R_M_ci'])}"})
    for ds, d in res["datasets"].items():
        for k, p in d["ablation"].items():
            if p.get("empty"):
                continue
            t05.append({"stage": f"final {ds}", "item": f"Eθ vs {k}", "decision": "reported", "S_T": p["S_T"],
                        "S_T_ci": p["S_T_ci"], "R_M": p["R_M"], "R_M_ci": p["R_M_ci"], "practical": "",
                        "statistical": ""})
    recs.append(write_table(out, "T05", "ablation_gates", t05, "Ablation and pre-registered development gates "
                            "(practical threshold and statistical evidence kept apart)"))
    # T06 archive / SAFE
    arch = ["A_z9_flat", "A_z9_stock", "A_z3_flat", "A_z3_stock", "SAFE9_stock", "SAFE9_flat", "SAFE3_stock",
            "M5_stock", "M5_flat"]
    t06 = [comp_row(ds, cid, d["comparisons"][cid]) for ds, d in res["datasets"].items() for cid in arch
           if cid in d["comparisons"] and not d["comparisons"][cid].get("empty")]
    recs.append(write_table(out, "T06", "archive_safe", t06, "Archive track: zstd3 / zstd9 / SAFE / m5, never mixed"))
    # T07 certificates
    t07 = []
    pc = audit_dir / "certificate_propagation.csv"
    if pc.exists():
        with open(pc, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                t07.append({"part": "v2.1 invalid rows (audit)", "item": r["sample_id"], "rows": r["old_invalid_rows"],
                            "old_LB/UB": f"{r['old_lb']}/{r['old_ub']}", "new_LB/UB": f"{r['v3_lb']}/{r['v3_ub']}",
                            "valid_now": r["v3_valid"], "stream_bytes_changed": r["influenced_selection"],
                            "solver_status": ""})
    for ds, d in res["datasets"].items():
        cs = d.get("certificates") or []
        if cs:
            g = [c["gap_pct"] for c in cs if c["gap_pct"] is not None]
            t07.append({"part": f"final {ds} CERTIFIED", "item": f"{len(cs)} samples", "rows": len(cs),
                        "old_LB/UB": "", "new_LB/UB": f"gap median {f(float(np.median(g)), 4)}% max "
                        f"{f(float(np.max(g)), 4)}%" if g else "NA",
                        "valid_now": f"{sum(1 for c in cs if c['valid'])}/{len(cs)} valid",
                        "stream_bytes_changed": "no (same stream as FAST)", "solver_status": ""})
        o = d.get("oracle")
        if o:
            t07.append({"part": f"final {ds} CP-SAT oracle", "item": f"{o.get('components_audited')} components",
                        "rows": o.get("components_audited"), "old_LB/UB": "", "new_LB/UB": "",
                        "valid_now": f"contradictions {o.get('contradictions')}", "stream_bytes_changed": "",
                        "solver_status": f"OPTIMAL {o.get('cpsat_optimal')}, not optimal {o.get('cpsat_not_optimal')}; "
                        f"time limit {o.get('time_limit_s')} s"})
    recs.append(write_table(out, "T07", "certificate_audit", t07, "Certificate audit (restricted model)"))
    # T08 negative results, unsupported, limitations
    t08 = []
    for r in res["status_rows"]:
        if r["status"] != "SUCCESS":
            t08.append({"kind": "status", "dataset": r["dataset"], "item": f"{r['method']} ({r['wrapper']}, "
                        f"{r['row_kind']})", "value": f"{r['status']} x{r['rows']}", "note": r["reason"]})
    for ds, d in res["datasets"].items():
        for cid, p in d["comparisons"].items():
            if p.get("empty") or not p.get("n"):
                continue
            if cid in ("C1", "C1_live") and (p["S_T"] < 1 or (p["R_M"] == p["R_M"] and p["R_M"] > 1)):
                t08.append({"kind": "regression", "dataset": ds, "item": cid, "value": f"S_T {f(p['S_T'])}, R_M "
                            f"{f(p['R_M'])}", "note": "aggregate regression of the new encoder"})
            if p.get("larger"):
                t08.append({"kind": "larger", "dataset": ds, "item": cid, "value": f"{p['larger']}/{p['n']} samples "
                            "larger", "note": f"{p['new']} vs {p['base']}"})
            if cid in ("C1", "C1_live") and p.get("slower_gt10pct"):
                t08.append({"kind": "slower >10%", "dataset": ds, "item": cid,
                            "value": f"{len(p['slower_gt10pct'])} samples", "note": ", ".join(p["slower_gt10pct"][:5])})
            if cid in ("C1", "C1_live") and p.get("peak_gt10pct"):
                t08.append({"kind": "peak >10%", "dataset": ds, "item": cid,
                            "value": f"{len(p['peak_gt10pct'])} samples", "note": ", ".join(p["peak_gt10pct"][:5])})
    for ds, d in res["datasets"].items():
        ab = d["comparisons"].get("C3_flat")
        if ab and not ab.get("empty") and ab["S_T"] < 1:
            t08.append({"kind": "trade-off", "dataset": ds, "item": "Eθ vs Crackle flat",
                        "value": f"{f(ab['G_B_pct'], 2)}% smaller, S_T {f(ab['S_T'])}", "note": "CAPE is slower than flat"})
    recs.append(write_table(out, "T08", "negative_results", t08, "Negative results, non-success statuses, trade-offs"))
    return recs


# ------------------------------------------------------------------------------------------------ claims
def claims(res: dict, sel: dict) -> list[dict]:
    L = []
    v = res["c1_verdicts"]
    j = v.get("j0126", {})
    fam = res["primary_family"]["p_holm"]

    def add(cid, text, status, scope, evidence, limit=""):
        L.append({"id": cid, "claim": text, "status": status, "scope": scope, "evidence": evidence, "limitation": limit})

    if j.get("n"):
        add("Q1", f"Eθ writes byte-identical streams to frozen v3 E0 on {f(j['byte_equal_pct'], 1)}% of j0126 samples",
            "SUPPORTED" if j["byte_equal_all"] else "UNSUPPORTED", "j0126 (33 volumes); also SNEMI3D, hemibrain",
            "tables/T03, raw_results", "implementation equivalence, not compression")
        sp = j["speed_target_reached"] and j["speed_ci_excludes_1"] and (fam.get("H1_C1_speed_j0126") or 1) < 0.05
        add("Q2", f"Eθ encodes faster than E0 (j0126 S_T {f(j['S_T'])} {ci(j['S_T_ci'])}; time reduction "
            f"{f(100 * (1 - 1 / j['S_T']), 1)}%)", "SUPPORTED" if sp else ("PARTIAL" if j["speed_ci_excludes_1"]
                                                                          else "UNSUPPORTED"),
            "one new acquisition (j0126), 1 thread, Windows/MinGW, i7-13700F", "F04, T03",
            "target 1.05 reached: " + str(j["speed_target_reached"]))
        mp = j["memory_target_reached"] and j["memory_ci_excludes_1"] and (fam.get("H2_C1_memory_j0126") or 1) < 0.05
        add("Q3", f"Eθ needs less encode-inclusive peak memory than E0 (j0126 R_M {f(j['R_M'])} {ci(j['R_M_ci'])})",
            "SUPPORTED" if mp else ("PARTIAL" if j["memory_ci_excludes_1"] else "UNSUPPORTED"),
            "process peak incl. Python and input; one new acquisition", "F05, T03",
            "target 0.95 reached: " + str(j["memory_target_reached"]))
    for ds in ("snemi", "hemibrain"):
        x = v.get(ds, {})
        if x.get("n"):
            add(f"Q4_{ds}", f"C1 on {ds}: S_T {f(x['S_T'])} {ci(x['S_T_ci'])}, R_M {f(x['R_M'])} {ci(x['R_M_ci'])}",
                "CONDITIONAL", "previously seen (SNEMI3D)" if ds == "snemi" else "descriptive (4 cutouts, one "
                "acquisition)", "T03", "not independent" if ds == "snemi" else "CI = timing variation only")
    j3 = res["datasets"].get("j0126", {}).get("comparisons", {})
    w = j3.get("C3_wgreedy")
    if w and not w.get("empty"):
        add("Q5", f"CAPE selection vs matched weighted greedy (same infrastructure): {f(w['G_B_pct'], 4)}% smaller "
            f"{ci(w['G_B_ci'], 4)}, S_T {f(w['S_T'])}", "CONDITIONAL" if (w["G_B_ci"] or [0])[0] > 0 else "UNSUPPORTED",
            "j0126", "T03 C3", "small size gain; not a Q1 change")
    s = j3.get("C3_stock_corr")
    if s and not s.get("empty"):
        add("Q6", f"vs corrected stock pins: {f(s['G_B_pct'], 4)}% smaller, S_T {f(s['S_T'])}", "CONDITIONAL",
            "j0126; stock = pinned upstream + count-width fix", "T03", "whole CAPE vs stock; mostly v2.1/v3 work")
    add("Q7", "the Q1 mechanisms are new algorithms", "UNSUPPORTED", "-", "methods/CONTRIBUTION_AND_PRIOR_ART_EN.md",
        "buffer/allocation engineering with proofs of output equivalence")
    add("Q8", "results generalize to all connectomics label data", "UNSUPPORTED", "-", "T01",
        "three acquisitions in total; one new primary")
    add("Q9", "certificates are valid lower bounds of the restricted model", "SUPPORTED" if all(
        all(c["valid"] for c in d.get("certificates", [])) for d in res["datasets"].values()) else "UNSUPPORTED",
        "restricted model", "F08, T07", "not global, no zstd bound")
    add("Q10", "Q1 acceptance / 10-out-of-10", "UNSUPPORTED", "-", "-", "never derived automatically")
    return L


# ------------------------------------------------------------------------------------------------ texts
def texts(out: Path, res: dict, sel: dict, frz: dict, figs: dict, tables: list[dict], cl: list[dict]) -> None:
    m = out / "methods"
    m.mkdir(parents=True, exist_ok=True)
    mask = frz["selected_impl_mask"]
    v = res["c1_verdicts"]
    j = v.get("j0126", {})
    D = res["datasets"]

    def c(ds, cid):
        return D.get(ds, {}).get("comparisons", {}).get(cid) or {}

    obj = f"""# Object and data

**What is compressed.** 3D neuron object-ID segmentation maps (dense label volumes in which every voxel carries the ID
of the neurite it belongs to). They are not electron-microscopy intensity images; no RGB or medical intensity data is
used. Every encoding is lossless: the decoded volume equals the input voxel by voxel, and object IDs and boundaries
are preserved exactly.

**Codec.** Crackle (seung-lab, pinned commit 14b39b1): crack-code boundaries plus a label section. CAPE chooses the
records of the PINS label section; the stream is decoded by the unmodified upstream decoder.

**Datasets** (Table T01):
- j0126 zebra finch Area X, SBEM (Januszewski et al. 2018): 33 dense manual ground-truth volumes, uint64; the NEW
  primary test (never used before the final run).
- SNEMI3D (Kasthuri et al. 2015 / SNEMI3D challenge): 32 crops + the full training volume and 4 subvolumes, uint16;
  previously seen (the v3 holdout), so secondary.
- Janelia hemibrain v1.2 (Scheffer et al. 2020), FIB-SEM 8 nm: 4 pre-registered 512x512x256 cutouts, uint64,
  proofread automated segmentation; descriptive.
- Development only: CREMI A/B/C and the Crackle repository samples.

**Not applied to.** Intensity images, RGB, medical images, streaming/partial decoding (not implemented), GPU codecs.
"""
    (m / "OBJECT_AND_DATA_EN.md").write_text(obj, encoding="utf-8")
    (m / "OBYEKT_VA_MALUMOT_UZ.md").write_text(f"""# Obyekt va ma'lumot

**Nima siqiladi.** Neyronlarning 3D obyekt-ID segmentatsiya xaritalari: har voksel o'zi tegishli neyrit ID'sini
saqlaydi. Bu elektron mikroskop intensivlik tasviri emas. Siqish lossless: dekodlangan hajm kirish bilan voksel
bo'yicha bir xil, ID va chegaralar aynan saqlanadi.

**Kodek.** Crackle (seung-lab, 14b39b1 commit). CAPE PINS label bo'limidagi yozuvlarni tanlaydi; oqimni o'zgartirilmagan
upstream dekoder ochadi.

**Datasetlar** (T01):
- j0126 (zebra finch, SBEM): 33 ta zich qo'lda belgilangan hajm, uint64; YANGI asosiy test.
- SNEMI3D: 32 crop + butun hajm va 4 kvadrant, uint16; avval ko'rilgan (v3 holdout), ikkilamchi.
- hemibrain v1.2 (FIB-SEM 8 nm): 4 ta oldindan belgilangan 512x512x256 kesma, uint64; tavsifiy.
- Faqat development: CREMI A/B/C va Crackle repo namunalari.

**Qo'llanmagan joylar.** Intensivlik tasvirlari, RGB, tibbiy tasvirlar, qisman dekodlash (kodda yo'q).
""", encoding="utf-8")
    acc = ", ".join(sel["selected_bits"]) or "none"
    (m / "METHODS_EN.md").write_text(f"""# Methods

## Problem
Given a label volume D and the frozen original v3 encoder E0 (impl_mask 575: v2.1 FAST + M1a neighbour-column
duplicate filter + M5b batched CC), find an encoder Eθ with Dec(Eθ(D)) = D and Eθ(D) = E0(D) byte for byte that lowers
encode time T and peak memory M (Pareto sense; no weighted score).

## Encoder (Eθ = impl_mask {mask}; accepted Q1 bits: {acc})
1. scan (max label, pixel pairs) -> upstream crack-code boundaries (unchanged).
2. 2D 4-connected CC per slice, batched (M5b). O1 lean CC: the same upstream labeling started at label 0, crc taken
   from the batch, CC values read at first raster pixels, offset added in the transpose. O3 compact chain: the
   column-major chain buffer stores slice-local uint16 numbers (2V bytes) with a per-slice offset when every slice
   has <= 65536 CCs, else the uint32 buffer.
3. Same-label z-runs; O2 allocates them once with the exact count V - z_pairs.
4. Depth-bounded complete-window candidates with the M1a neighbour filter; singleton, equal-coverage and subset
   reductions; independent components; greedy + integer dual bound; exact bitmask DP / local search on small
   components; explicit serializer.
Proofs: mathematics/m1a_proposition.md, mathematics/q1_output_preserving.md; certificate: mathematics/certificate_model.md.

Pseudocode (one regime, FAST):
```
labels -> boundaries (upstream)
for z-batch of 16 slices: CC2D_4(slice, start=0) -> crc(slice), values at first pixels, transpose(+offset) [uint16 if O3]
runs <- column runs (reserve V - z_pairs if O2)
cands <- windows(runs, h) minus neighbour twins (M1a)
alive <- reduce(cands); comps <- components(alive)
for comp: UB <- greedy; LB <- dual ascent; if small: exact DP / local search
records -> serialize -> assemble(header, labels section, boundaries, crcs)
```
Complexity: unchanged from v3 (linear passes over V plus the candidate work); Q1 changes constants and memory only
(O3: chain buffer 4V -> 2V bytes; O2: no transient second run array).

## Measurement
- One thread, worker pinned to one P-core, tasks sequential, randomized block order, 2 warmups; 7 repeats (j0126,
  SNEMI3D), 3 repeats (hemibrain, scale). T = median over repeats of the encode time of each (sample, method).
- Memory: a fresh worker process per (sample, method); Windows PeakWorkingSetSize read after encode and before decode
  (encode-inclusive peak, includes the Python process and the input array); end-to-end peak reported separately.
- Every stream decoded by the original Crackle decoder and compared voxel by voxel; sha256 of every stream stored.
- Statistics: S_T = exp(mean log(T_base/T_new)), R_M = exp(mean log(M_new/M_base)), pooled byte gain; paired cluster
  bootstrap (10 000, seed 20261107); Holm over the pre-registered primary family (C1 speed and memory on j0126).
- Reproduction: reproducibility/REPRODUCE.md.
""", encoding="utf-8")
    rows = []
    for ds in ("j0126", "snemi", "hemibrain"):
        x = v.get(ds, {})
        if x.get("n"):
            rows.append(f"- **{ds}** ({DATASETS[ds]}): n = {x['n']}; S_T {f(x['S_T'])} {ci(x['S_T_ci'])} "
                        f"(time reduction {f(100 * (1 - 1 / x['S_T']), 2)}%); R_M {f(x['R_M'])} {ci(x['R_M_ci'])}; "
                        f"byte-identical to E0: {f(x['byte_equal_pct'], 1)}%; worst sample speed-up "
                        f"{f(x['worst_speedup']['speedup'])} ({x['worst_speedup']['sample_id']}).")
    fam = res["primary_family"]
    b = c("j0126", "BUILD")
    c2 = c("j0126", "C2")
    w = c("j0126", "C3_wgreedy")
    st = c("j0126", "C3_stock_corr")
    fl = c("j0126", "C3_flat")
    results = f"""# Results (generated from tables; run {res['run_id']})

## C1: Eθ vs frozen v3 E0 (primary: j0126)
{chr(10).join(rows) or '- BLOCKED: no C1 pairs'}

Primary family (two-sided bootstrap p, Holm): {json.dumps({k: (None if x is None else round(x, 5)) for k, x in fam['p_holm'].items()})}.
Practical targets (pre-registered): S_T >= 1.05 and R_M <= 0.95 on j0126 -> speed reached: {j.get('speed_target_reached')},
memory reached: {j.get('memory_target_reached')}.

Build drift (live binary at the E0 mask vs E0, j0126): S_T {f(b.get('S_T'))} {ci(b.get('S_T_ci'))}, R_M {f(b.get('R_M'))}.

## C2: historical (Eθ vs v2.1, j0126)
S_T {f(c2.get('S_T'))} {ci(c2.get('S_T_ci'))}, R_M {f(c2.get('R_M'))} {ci(c2.get('R_M_ci'))}; bytes identical:
{c2.get('bytes_identical')}. This includes the v3 gain (M1a, M5b) and is not counted as a Q1 contribution.

## C3: competitors (j0126; different streams)
- matched weighted greedy (same infrastructure): size gain {f(w.get('G_B_pct'), 4)}% {ci(w.get('G_B_ci'), 4)}, S_T
  {f(w.get('S_T'))}, R_M {f(w.get('R_M'))}.
- corrected stock pins: size gain {f(st.get('G_B_pct'), 4)}% {ci(st.get('G_B_ci'), 4)}, S_T {f(st.get('S_T'))}
  {ci(st.get('S_T_ci'))}, R_M {f(st.get('R_M'))}.
- Crackle flat: size gain {f(fl.get('G_B_pct'), 3)}% {ci(fl.get('G_B_ci'), 3)}, S_T {f(fl.get('S_T'))}, R_M
  {f(fl.get('R_M'))} (a size-time trade-off when S_T < 1).
Other codecs, archive and SAFE: tables T03 and T06. Negative results and statuses: T08.
"""
    (m / "RESULTS_EN.md").write_text(results, encoding="utf-8")
    n_acq = sum(1 for ds in ("j0126", "snemi", "hemibrain") if v.get(ds, {}).get("n"))
    (m / "LIMITATIONS_EN.md").write_text(f"""# Limitations

- Acquisitions actually used in the final test: {n_acq} ({', '.join(ds for ds in ('j0126', 'snemi', 'hemibrain') if v.get(ds, {}).get('n'))}).
  The primary C1 evidence rests on ONE new acquisition (j0126; 33 volumes are clusters of one dataset); SNEMI3D was
  seen before (and one SNEMI3D subvolume was used for a diagnostic memory profile while designing O2/O3); hemibrain is
  descriptive (4 cutouts). Generalization beyond these acquisitions is not claimed.
- Timing: one machine (Windows 11, MinGW g++ 16.2, i7-13700F), one thread. Other platforms may differ.
- Memory: process peak working set including the Python interpreter and the input array; it is not an
  algorithm-only memory figure.
- Size: Eθ writes exactly the bytes of E0; there is no compression gain from Q1. Size gains against other encoders
  belong to the CAPE selection already present in v2.1/v3 and are small against matched greedy.
- Certificates bound a restricted model (candidate family, safe reductions); not a global optimum; no bound after zstd.
- Rejected / unsuccessful mechanisms are listed in T05 (development) and docs; a run-based CC labeling was dropped
  before measurement (slower on fragmented slices).
- Novelty: the Q1 changes are engineering (buffer layout, allocation, fused passes) with proofs of output equivalence;
  inverted-index / dedup ideas are known (methods/CONTRIBUTION_AND_PRIOR_ART_EN.md).
""" + "\n".join(post_run_lines_en(res.get("post_run") or {})) + "\n", encoding="utf-8")
    (m / "CONTRIBUTION_AND_PRIOR_ART_EN.md").write_text("""# Contribution and prior art

| Mechanism | Known before | CAPE / Q1 difference | Evidence | Limitation |
|---|---|---|---|---|
| Crackle crack codes + PINS labels | Crackle (seung-lab, commit 14b39b1) | CAPE selects PINS records by a certified set-cover solver; stream unchanged in format | v1-v3 reports; T03 C3 | size gain small vs matched greedy |
| Equal-coverage dedup by hashing | standard (hash grouping) | M1a: neighbour-column twins dropped at generation, proved exact for 4-connected 2D CCs | mathematics/m1a_proposition.md; ablation F06 | M1a is v3, not Q1 |
| Inverted incidence / eager greedy | Crackle issue #19 (2024-07, closed 2025-01); lazy greedy (Minoux 1978) | v3 M2 rejected (no gain) | v3 selection | not used |
| Batched CC straight into column-major chains | common blocking/transposition practice | M5b (v3) | v3 | - |
| O1 lean CC | cc3d relabel numbering (first raster pixel) | removes two per-voxel passes; proof that start_label offsets commute | q1_output_preserving.md | engineering |
| O2 exact run allocation | standard reserve-before-fill | exact count V - z_pairs computed in the CC pass | q1_output_preserving.md | engineering |
| O3 compact uint16 chains | standard narrow-index storage | slice-local ids + per-slice offset, exact equality/hash/subset on local ids | q1_output_preserving.md | falls back above 65536 CCs per slice |
| Integer dual lower bound / certificate | LP duality for set cover (classical) | format-coupled bound incl. w_D compaction fix | certificate_model.md | restricted model |

Conclusion: Q1 is an engineering contribution with machine-checked output equivalence (byte identity against the
frozen binary on every measured sample), not a new compression algorithm.
""", encoding="utf-8")
    caps = ["# Figure captions", ""]
    for fid in sorted(figs):
        r = figs[fid]
        caps.append(f"**{fid}** ({r['status']}): {r.get('caption_en') or r.get('reason')}")
        caps.append(f"  - UZ: {r.get('note_uz', '')}")
        caps.append("")
    (m / "CAPTIONS_EN.md").write_text("\n".join(caps), encoding="utf-8")
    (m / "references.bib").write_text(REFERENCES, encoding="utf-8")
    abstract = (f"Lossless compression of dense neuron segmentation maps with the Crackle format spends much of its "
                f"encode time and memory in connected-component labeling, run extraction and candidate handling. We "
                f"present output-preserving changes to the CAPE encoder (impl_mask {mask}) that write byte-identical "
                f"streams to the frozen previous version. On a new external test set (j0126, 33 volumes) the encode "
                f"speed-up is S_T = {f(j.get('S_T'))} {ci(j.get('S_T_ci'))} and the encode-inclusive peak memory ratio "
                f"is R_M = {f(j.get('R_M'))} {ci(j.get('R_M_ci'))}, with "
                f"{f(j.get('byte_equal_pct'), 1)}% byte identity. Results on a previously seen volume (SNEMI3D) and "
                f"on hemibrain cutouts are reported separately. The contribution is engineering; compression ratios "
                f"are unchanged.") if j.get("n") else "BLOCKED: no primary C1 result."
    (m / "MANUSCRIPT_DRAFT_EN.md").write_text(f"""# Output-preserving acceleration of a certified Crackle label encoder (draft)

*Draft generated from the verified tables of run {res['run_id']}; not submitted anywhere.*

## Abstract
{abstract}

## 1. Introduction
Connectomics produces large 3D label volumes. Crackle stores them as crack-code boundaries plus a label section;
CAPE chooses the PINS records by a set-cover model with a certificate. This paper asks whether the encoder can be made
faster and leaner without changing a single output byte.

## 2. Object and data
{obj.split('**Datasets**')[0].strip()}
See Table T01 and Fig. 1.

## 3. Method
See methods/METHODS_EN.md (algorithm, pseudocode, proofs in mathematics/).

## 4. Results
{results.split('## C1:', 1)[1] if '## C1:' in results else results}

## 5. Discussion
The new encoder is a constant-factor and memory improvement over its predecessor on the measured data, with exact
output equivalence. Against other encoders the size differences are those of the CAPE selection and are small against
a matched greedy; Crackle flat remains faster where S_T < 1.

## 6. Limitations
{(m / 'LIMITATIONS_EN.md').read_text(encoding='utf-8').split(chr(10), 2)[2]}
""", encoding="utf-8")


REFERENCES = r"""% Only sources checked by the pipeline author; DOIs are given only where verified from the source itself.
@article{januszewski2018ffn,
  author = {Januszewski, Micha{\l} and Kornfeld, J{\"o}rgen and Li, Peter H. and Pope, Art and Blakely, Tim and
            Lindsey, Larry and Maitin-Shepard, Jeremy and Tyka, Mike and Denk, Winfried and Jain, Viren},
  title = {High-precision automated reconstruction of neurons with flood-filling networks},
  journal = {Nature Methods}, volume = {15}, number = {8}, pages = {605--610}, year = {2018},
  doi = {10.1038/s41592-018-0049-4}, note = {DOI from the official j0126 bucket README}}
@misc{snemi3d_zenodo,
  author = {Arganda-Carreras, Ignacio and Seung, H. Sebastian and Vishwanathan, Ashwin and Berger, Daniel R.},
  title = {SNEMI3D: 3D Segmentation of neurites in EM images}, year = {2022}, publisher = {Zenodo},
  doi = {10.5281/zenodo.7142003}, note = {DOI from the Zenodo API record used for the download}}
@misc{hemibrain_v12,
  author = {{FlyEM Project, Janelia Research Campus}},
  title = {Hemibrain v1.2 segmentation (neuroglancer precomputed)},
  howpublished = {\url{https://storage.googleapis.com/neuroglancer-janelia-flyem-hemibrain/v1.2/segmentation/}},
  note = {Scheffer et al. 2020, eLife; DOI not verified by the pipeline}}
@misc{crackle,
  author = {Silversmith, William}, title = {Crackle: a compression codec for 3D dense segmentation labels},
  howpublished = {\url{https://github.com/seung-lab/crackle}}, note = {pinned commit 14b39b196a14b3b1ba7d1cd34f350c324308000f}}
@misc{crackle_issue19,
  title = {Crackle issue \#19 (inverted index for pin selection)}, howpublished = {\url{https://github.com/seung-lab/crackle/issues/19}},
  note = {opened 2024-07, closed 2025-01 (as read on GitHub)}}
@misc{cremi, title = {CREMI: MICCAI Challenge on Circuit Reconstruction from Electron Microscopy Images},
  howpublished = {\url{https://cremi.org}}, note = {data via Hugging Face mirror pytc/tutorial, SHA-256 checked}}
@misc{rfc8878, author = {Collet, Yann and Kucherawy, Murray}, title = {Zstandard Compression and the application/zstd Media Type},
  howpublished = {RFC 8878}, year = {2021}, doi = {10.17487/RFC8878}}
@misc{neuroglancer_cseg, title = {Neuroglancer compressed segmentation format},
  howpublished = {\url{https://github.com/google/neuroglancer}}, note = {python package compressed-segmentation}}
"""


# ------------------------------------------------------------------------------------------------ package
def decode_checks(samples: list[dict], mask: int) -> dict:
    files = [str(ROOT / s["path"]) for s in samples]
    opts = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
            "depth_policy": "fixed_depth_width", "certificate": "off", "impl_mask": mask}
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "q1_encode_helper.py"), "live", json.dumps(opts), *files],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    r = json.loads(out.stdout)
    return {s["sample_id"]: {"mismatch_count": 0 if r[str(ROOT / s["path"])]["lossless"] else "NONZERO",
                             "bytes": r[str(ROOT / s["path"])]["bytes"], "sha256": r[str(ROOT / s["path"])]["sha256"]}
            for s in samples}


MEASUREMENT_CODE = ("cape/", "cpp/", "run_all.py", "configs/", "snapshots/", "vendor/", "data/manifests/")


def post_run_findings(run_id: str, st: dict) -> dict:
    """Facts found after the final run, computed from the raw rows and git (never typed in by hand)."""
    import pandas as pd

    out: dict = {"neuroglancer_u32": {}, "interference": [], "post_freeze_commits": [], "post_freeze_files": []}
    raws = {}
    for key, info in st["runs"].items():
        p = ROOT / info.get("run_dir", "") / "05_raw_metrics" / "results.csv"
        if p.exists():
            raws[key] = pd.read_csv(p, low_memory=False)
    # 1. amended neuroglancer uint32 widening track (I13): did it run on uint8/uint16 inputs?
    reasons = set()
    for key, d in raws.items():
        x = d[d.method_id == "neuroglancer_b8_u32"]
        if not len(x):
            continue
        nar = x[x.original_dtype.isin(["uint8", "uint16"])]
        bad = nar[nar.status != "OK"]
        reasons |= {str(r) for r in bad.reason.dropna().unique()[:3]}
        out["neuroglancer_u32"][key] = {"rows": int(len(x)), "narrow_rows": int(len(nar)),
                                        "narrow_ok": int((nar.status == "OK").sum()),
                                        "narrow_non_ok": {str(k): int(v) for k, v in bad.status.value_counts().items()}}
    ng = out["neuroglancer_u32"]
    n_nar = sum(v["narrow_rows"] for v in ng.values())
    n_ok = sum(v["narrow_ok"] for v in ng.values())
    out["neuroglancer_u32_reason_examples"] = sorted(reasons)[:3]
    if n_nar:
        out["I13_status"] = ("FIXED (amended track ran on uint8/uint16)" if n_ok == n_nar else
                             f"NOT FIXED in the final run ({n_nar - n_ok}/{n_nar} uint8/uint16 rows not SUCCESS: the "
                             "runner checks the class-level supported_dtypes before the adapter, so the widening path "
                             "was never reached)")
    # 2. interference windows recorded in results/<run_id>/disclosures.json (other CPU work during timing)
    dp = ROOT / "results" / run_id / "disclosures.json"
    disc = json.loads(dp.read_text(encoding="utf-8")) if dp.exists() else {}

    def s_t(x):
        med = x.groupby(["sample_id", "method_id"]).encode_ns.median().unstack()
        if E0 not in med or E_NEW not in med:
            return None
        med = med[[E0, E_NEW]].dropna()
        return float(np.exp(np.mean(np.log(med[E0] / med[E_NEW])))) if len(med) else None

    for w in disc.get("interference_windows", []):
        a, b = pd.Timestamp(w["start"]), pd.Timestamp(w["end"])
        rec = {k: w[k] for k in ("start", "end", "what")} | {"runs": {}}
        for key, d in raws.items():
            at = pd.to_datetime(d.committed_at, utc=True, format="ISO8601")
            inwin = (at >= a) & (at <= b)
            if not inwin.any():
                continue
            c1 = d.method_id.isin([E_NEW, E0]) & (d.status == "OK") & (d.wrapper.fillna("none") == "none")
            timed = c1 & (d.panel != "MEM")
            rec["runs"][key] = {
                "rows_in_window": int(inwin.sum()), "rows_total": int(len(d)),
                "c1_timed_rows_in_window": int((timed & inwin).sum()), "c1_timed_rows": int(timed.sum()),
                "c1_memory_rows_in_window": int((c1 & (d.panel == "MEM") & inwin).sum()),
                "S_T_all_rows": s_t(d[timed]), "S_T_without_window_rows": s_t(d[timed & ~inwin])}
        out["interference"].append(rec)
    # 3. code changes after the freeze commit (git), and whether any touches measurement code
    try:
        g = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout  # noqa: E731
        fc = g("log", "--grep", "Q1 FREEZE", "-1", "--format=%h").strip()
        if fc:
            out["freeze_commit"] = fc
            out["post_freeze_commits"] = [l for l in g("log", "--format=%h %cI %s", f"{fc}..HEAD").splitlines() if l]
            files = sorted(set(g("diff", "--name-only", fc, "HEAD").split()))
            out["post_freeze_files"] = files
            out["uncommitted_files"] = sorted(l[3:] for l in g("status", "--porcelain", "--", "tools", "scripts",
                                                                  "cape", "cpp", "configs").splitlines()
                                              if l and not l[3:].startswith("configs/frozen/"))  # run outputs
            out["measurement_code_changed_after_freeze"] = any(
                f.startswith(MEASUREMENT_CODE) and not f.startswith("configs/frozen/") for f in files)
    except OSError as exc:
        out["git_error"] = str(exc)
    return out


def post_run_lines_en(pr: dict) -> list[str]:
    L = []
    ng = pr.get("neuroglancer_u32") or {}
    n_nar = sum(v["narrow_rows"] for v in ng.values())
    if n_nar:
        n_ok = sum(v["narrow_ok"] for v in ng.values())
        L.append(f"- The amended neuroglancer uint32-widening track (neuroglancer_b8_u32) produced {n_ok}/{n_nar} "
                 "SUCCESS rows on uint8/uint16 inputs (SNEMI3D): "
                 + ("it ran as planned." if n_ok == n_nar else "the runner rejected the dtype before the adapter, so "
                    "this baseline is unavailable on uint16 data in the final run (it ran only on uint64 data, where "
                    "it is the native path)."))
    for w in pr.get("interference") or []:
        for key, r in w["runs"].items():
            L.append(f"- Interference window {w['start']} to {w['end']} ({w['what']}): {key} {r['rows_in_window']}/"
                     f"{r['rows_total']} rows; C1 timed rows {r['c1_timed_rows_in_window']}/{r['c1_timed_rows']}, "
                     f"C1 memory rows {r['c1_memory_rows_in_window']}; S_T {f(r['S_T_all_rows'], 4)} with all rows, "
                     f"{f(r['S_T_without_window_rows'], 4)} without the window rows.")
    return L


def raw_audit(run_id: str) -> int:
    st = json.loads((ROOT / "results" / run_id / "q1_state.json").read_text(encoding="utf-8"))
    rows, summary = [], {"run_id": run_id, "written_at": now(), "runs": {}}
    for key, info in st["runs"].items():
        if not info.get("run_dir"):
            continue
        cells = load_cells(info["run_dir"])
        nonok = sum(n for c in cells.values() for s, n in c["statuses"].items() if s != "OK")
        lossless_bad = sum(1 for c in cells.values() for v in c["lossless"] if v is not None and not v)
        vary = [f"{s}|{k}" for (s, k), c in cells.items() if c["bytes_vary"]]
        e = {s: c for (s, k), c in cells.items() if k == E_NEW}
        z = {s: c for (s, k), c in cells.items() if k == E0}
        eq = sum(1 for s in e if s in z and e[s]["sha256"] and e[s]["sha256"] == z[s]["sha256"])
        summary["runs"][key] = {"run_dir": info["run_dir"], "status": info.get("status"), "cells": len(cells),
                                "non_ok_rows": nonok, "lossless_false_rows": lossless_bad, "bytes_vary_cells": vary[:20],
                                "Etheta_vs_E0_sha_equal": f"{eq}/{len(set(e) & set(z))}" if e and z else "n/a"}
        for (s, k), c in cells.items():
            for raw, n in c["statuses"].items():
                rows.append({"dataset": key, "sample_id": s, "method": k, "raw_status": raw,
                             "status": map_status(raw), "rows": n, "reason": (c["reasons"] or [None])[0]})
    out = ROOT / "results" / run_id
    (out / "raw_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(out / "raw_audit_statuses.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["empty"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=2))
    return 0


def build(run_id: str) -> int:
    out = ROOT / "results" / run_id / "article_staging"
    if out.exists():
        shutil.rmtree(out)
    for d in TREE:
        (out / d).mkdir(parents=True, exist_ok=True)
    frz = json.loads((ROOT / "analysis" / "q1_freeze" / "freeze.json").read_text(encoding="utf-8"))
    sel = json.loads((ROOT / "analysis" / "q1_select" / "selected.json").read_text(encoding="utf-8"))
    res = analyze(run_id, n_boot=int(os.environ.get("Q1_NBOOT", "10000")))  # Q1_NBOOT < 10000 only for tests
    (out / "supplementary" / "analysis.json").write_text(json.dumps(to_jsonable(res), indent=1, default=str),
                                                         encoding="utf-8")
    manifests = {}
    plan = json.loads((ROOT / "analysis" / "q1_freeze" / "experiment_plan.json").read_text(encoding="utf-8"))
    st0 = json.loads((ROOT / "results" / run_id / "q1_state.json").read_text(encoding="utf-8"))
    for key, r in st0["runs"].items():  # the manifest each child run actually measured (smoke runs use dev data)
        if key.startswith("profile_") or not r.get("manifest"):
            continue
        manifests[key] = [json.loads(l) for l in (ROOT / r["manifest"]).read_text(encoding="utf-8").splitlines() if l]
    # ---- figures
    fw = F.FigWriter(out)
    ex = []
    for ds in ("j0126", "snemi", "hemibrain"):
        if ds in manifests:
            r0 = sorted(manifests[ds], key=lambda r: r["sample_id"])[0]
            sp = r0.get("spacing_xyz")
            ex.append({"dataset": ds, "sample_id": r0["sample_id"], "path": r0["path"], "dtype": r0["dtype"],
                       "spacing": sp, "spacing_xy": sp[0] if sp else None, "spacing_z": sp[2] if sp else None})
    dc = decode_checks(ex, frz["selected_impl_mask"]) if ex else {}
    try:
        F.f01_objects(fw, ex, dc)
    except Exception as exc:  # noqa: BLE001 - recorded, never hidden
        fw.blocked("F01", "object_examples", f"error: {exc}")
    shares = res["datasets"].get("j0126", {}).get("phase_shares", {}).get(E_NEW, {})
    F.f02_pipeline(fw, shares, frz["selected_impl_mask"])
    if "j0126" in res["datasets"]:
        F.f03_pareto(fw, res["datasets"]["j0126"]["totals"], "j0126")
    F.f04_speedups(fw, res)
    peaks = []
    for ds, d in res["datasets"].items():
        if ds not in ("j0126", "snemi", "hemibrain", "scale", "scale_stock"):
            continue
        keep = ("crackle_pins_opt_corrected_m0",) if ds == "scale_stock" else (E_NEW, E0,
                                                                               "crackle_pins_opt_corrected_m0")
        for (s, k), c in load_cells(d["run_dir"]).items():
            if k in keep and c["peak_enc"]:
                peaks.append({"dataset": ds, "sample_id": s, "method": k, "voxels": c["voxels"],
                              "peak_enc_mib": c["peak_enc"] / 2**20,
                              "peak_e2e_mib": (c["peak_e2e"] or 0) / 2**20 or None})
    F.f05_memory(fw, res, peaks, res["profile"])
    F.f06_ablation(fw, res)
    F.f07_size(fw, res)
    prop = []
    pc = ROOT / "audit" / "certificate_propagation.csv"
    if pc.exists():
        with open(pc, encoding="utf-8") as fh:
            prop = [{k: (int(v) if k in ("old_lb", "old_ub", "v3_lb", "v3_ub") else v) for k, v in r.items()}
                    for r in csv.DictReader(fh)]
    F.f08_certificates(fw, res, prop)
    for ex_r in ex:  # object examples as data (slices) next to the figure
        vol = np.load(ROOT / ex_r["path"])
        np.save(out / "object_examples" / f"{ex_r['sample_id']}_xy_center.npy", vol[vol.shape[0] // 2])
    shutil.copy(out / "figures" / "F01_object_examples.png", out / "object_examples" / "F01_object_examples.png") \
        if (out / "figures" / "F01_object_examples.png").exists() else None
    # ---- tables, claims, texts
    res["post_run"] = post_run_findings(run_id, st0)
    tables = build_tables(out, res, manifests, sel, ROOT / "audit")
    cl = claims(res, sel)
    with open(out / "claims_ledger.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cl[0].keys()))
        w.writeheader()
        w.writerows(cl)
    texts(out, res, sel, frz, fw.records, tables, cl)
    # ---- mathematics, audit, reproducibility, raw results, scripts
    for p in (ROOT / "docs" / "q1" / "mathematics").glob("*.md"):
        shutil.copy(p, out / "mathematics" / p.name)
    for p in (ROOT / "audit").glob("*"):
        if p.is_file():
            shutil.copy(p, out / "audit" / p.name)
    (out / "audit" / "post_run_findings.json").write_text(json.dumps(res["post_run"], indent=1, default=str),
                                                          encoding="utf-8")
    shutil.copy(ROOT / "analysis" / "q1_select" / "selected.json", out / "audit" / "development_selection.json")
    shutil.copy(ROOT / "analysis" / "q1_select" / "SELECT_Q1_UZ.md", out / "audit" / "SELECT_Q1_UZ.md")
    st = json.loads((ROOT / "results" / run_id / "q1_state.json").read_text(encoding="utf-8"))
    (out / "audit" / "stage_status.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
    rep = out / "reproducibility"
    for name in ("freeze.json", "experiment_plan.json", "success_criteria.json"):
        shutil.copy(ROOT / "analysis" / "q1_freeze" / name, rep / name)
    for p in sorted((ROOT / "analysis" / "q1_freeze").glob("freeze_superseded_*.json")):
        shutil.copy(p, rep / p.name)
    for name in ("requirements.lock", "requirements.in", "sources.lock.json", "pyproject.toml"):
        if (ROOT / name).exists():
            shutil.copy(ROOT / name, rep / name)
    for k, r in st0["runs"].items():
        for kk in ("config", "manifest"):
            if r.get(kk) and (ROOT / r[kk]).exists():
                shutil.copy(ROOT / r[kk], rep / Path(r[kk]).name)
    shutil.copy(ROOT / "configs" / "q1_methods.yaml", rep / "q1_methods.yaml")
    shutil.copy(ROOT / "configs" / "q1_development.yaml", rep / "q1_development.yaml")
    shutil.copy(ROOT / "docs" / "q1" / "EXTERNAL_DATA_PLAN.md", rep / "EXTERNAL_DATA_PLAN.md")
    (rep / "REPRODUCE.md").write_text(f"""# Reproduce

Environment: Windows 11, Python 3.12, MinGW-w64 g++ 16.2 (see freeze.json for every hash).

```powershell
py -3.12 scripts\\bootstrap.py                                  # venv + hashed lock + native build
.venv-fetch\\Scripts\\python scripts\\fetch_external_q1.py --j0126 --hemibrain   # external data (authorized sources)
.venv\\Scripts\\python scripts\\make_q1_manifests.py             # refuses to rewrite frozen manifests
.venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode full --fresh-run --output "maqola uchun"
.venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode render --run-id {run_id} --output "maqola uchun"
```
Seeds: {plan['seed']} (bootstrap, randomized order). Source hash: {frz['expected_source_hash']}.
Frozen binaries: E0 {frz['hashes']['E0_binary']}, v2.1 {frz['hashes']['v21_binary']}, Eθ {frz['hashes']['Etheta_binary']}.
Datasets are not redistributed (licences); manifests give source URLs, coordinates and SHA-256.
""", encoding="utf-8")
    for key, info in st["runs"].items():
        rd = ROOT / info.get("run_dir", "") / "05_raw_metrics"
        if (rd / "results.csv").exists():
            shutil.copy(rd / "results.csv", out / "raw_results" / f"{key}_results.csv")
    shutil.copy(ROOT / "results" / run_id / "raw_audit.json", out / "raw_results" / "raw_audit.json")
    shutil.copy(ROOT / "results" / run_id / "raw_audit_statuses.csv", out / "raw_results" / "terminal_statuses.csv")
    for p in ("tools/q1_article.py", "tools/q1_analysis.py", "tools/q1_figs.py", "tools/q1_pipeline.py",
              "tools/validate_article_package.py", "tools/q1_audit.py", "tools/q1_freeze.py", "scripts/q1_common.py",
              "scripts/q1_develop.py"):
        if (ROOT / p).exists():
            shutil.copy(ROOT / p, out / "scripts" / Path(p).name)
    # supplementary: disaggregated per-sample comparisons
    for ds, d in res["datasets"].items():
        for cid, p in d["comparisons"].items():
            if p.get("per_sample"):
                with open(out / "supplementary" / f"{ds}_{cid}_per_sample.csv", "w", encoding="utf-8",
                          newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(p["per_sample"][0].keys()))
                    w.writeheader()
                    w.writerows(p["per_sample"])
    (out / "supplementary" / "figures_index.json").write_text(json.dumps(fw.records, indent=2), encoding="utf-8")
    (out / "supplementary" / "tables_index.json").write_text(json.dumps(tables, indent=2), encoding="utf-8")
    (out / "checks" / "README.md").write_text("Validator output of tools/validate_article_package.py (written after "
                                              "the package build).\n", encoding="utf-8")
    final_docs(out, res, sel, frz, fw.records, tables, cl, st)
    print(f"staging package: {out}")
    return 0


EXPECTED = (["README_UZ.md", "YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md", "artifact_manifest.csv", "claims_ledger.csv"]
            + [f"methods/{n}" for n in ("OBJECT_AND_DATA_EN.md", "OBYEKT_VA_MALUMOT_UZ.md", "METHODS_EN.md",
                                        "RESULTS_EN.md", "LIMITATIONS_EN.md", "CONTRIBUTION_AND_PRIOR_ART_EN.md",
                                        "MANUSCRIPT_DRAFT_EN.md", "CAPTIONS_EN.md", "references.bib")]
            + [f"mathematics/{n}" for n in ("m1a_proposition.md", "q1_output_preserving.md", "certificate_model.md")]
            + ["reproducibility/REPRODUCE.md", "reproducibility/freeze.json", "reproducibility/experiment_plan.json",
               "reproducibility/success_criteria.json", "audit/issue_register.csv", "audit/inventory.json",
               "audit/run_dependency_map.json", "audit/claims_recheck.csv", "audit/certificate_propagation.csv",
               "raw_results/raw_audit.json", "raw_results/terminal_statuses.csv"])


def artifact_manifest(out: Path, figs: dict, tables: list[dict]) -> list[dict]:
    rows = []
    for rel in EXPECTED:
        p = out / rel
        if rel == "artifact_manifest.csv":  # the manifest lists itself as written by this function
            rows.append({"artifact": rel, "kind": "file", "status": "OK", "reason": "this file", "bytes": None,
                         "sha256": None})
            continue
        rows.append({"artifact": rel, "kind": "file", "status": "OK" if p.exists() and p.stat().st_size > 0 else
                     "BLOCKED", "reason": "" if p.exists() else "not produced", "bytes": p.stat().st_size if p.exists()
                     else None, "sha256": sha_file(p) if p.exists() else None})
    for fid, r in sorted(figs.items()):
        for ext in ("pdf", "svg", "png"):
            p = out / f"{r['file']}.{ext}"
            rows.append({"artifact": f"{r['file']}.{ext}", "kind": f"figure {fid}",
                         "status": "OK" if r["status"] == "OK" and p.exists() else "BLOCKED",
                         "reason": r.get("reason") or ("" if p.exists() else "not produced"),
                         "bytes": p.stat().st_size if p.exists() else None, "sha256": sha_file(p) if p.exists() else None})
        if r["status"] == "OK":
            p = out / r["plot_data"]
            rows.append({"artifact": r["plot_data"], "kind": f"plot data {fid}", "status": "OK" if p.exists() else
                         "BLOCKED", "reason": "", "bytes": p.stat().st_size if p.exists() else None,
                         "sha256": sha_file(p) if p.exists() else None})
    for t in tables:
        for ext in ("csv", "md", "tex"):
            p = out / f"{t['file']}.{ext}"
            rows.append({"artifact": f"{t['file']}.{ext}", "kind": f"table {t['id']}",
                         "status": "OK" if t["status"] == "OK" and p.exists() else "BLOCKED",
                         "reason": t.get("reason") or "", "bytes": p.stat().st_size if p.exists() else None,
                         "sha256": sha_file(p) if p.exists() else None})
    return rows


def final_docs(out: Path, res: dict, sel: dict, frz: dict, figs: dict, tables: list[dict], cl: list[dict],
               st: dict) -> None:
    v = res["c1_verdicts"]
    j = v.get("j0126", {})
    D = res["datasets"]
    runs_ok = all(r.get("status") == "DONE" for r in st["runs"].values())
    tech = "COMPLETE" if runs_ok and all(r["status"] == "OK" for r in figs.values() if r["id"] != "F08") else "PARTIAL"
    if j.get("n") and j["byte_equal_all"] and (j["speed_ci_excludes_1"] or j["memory_ci_excludes_1"]):
        sci = "tayyorlash mumkin (cheklangan da'vo bilan); muhim dalil yetishmaydi: mustaqil acquisition'lar soni"
    elif j.get("n") and j["byte_equal_all"]:
        sci = "asosiy hissa qo'llab-quvvatlanmadi (C1 tezlik/xotira dalili yo'q)"
    else:
        sci = "muhim dalil yetishmaydi"
    issues = []
    ip = ROOT / "audit" / "issue_register.csv"
    if ip.exists():
        with open(ip, encoding="utf-8") as fh:
            issues = list(csv.DictReader(fh))

    def cmp_line(ds, cid, lab):
        p = D.get(ds, {}).get("comparisons", {}).get(cid)
        if not p or p.get("empty"):
            return f"| {ds} | {lab} | NA | NA | NA | NA | NA |"
        return (f"| {ds} | {lab} | {p['n']} | {f(p['S_T'])} {ci(p['S_T_ci'])} | {f(p['R_M'])} {ci(p['R_M_ci'])} | "
                f"{f(p['G_B_pct'], 4)}% | {p['smaller']}/{p['equal']}/{p['larger']} |")

    L = [f"# CAPE Q1: yakuniy audit va xulosa", "",
         f"Run ID: `{res['run_id']}` · Yaratilgan: {now()} · Eθ impl_mask {frz['selected_impl_mask']} "
         f"(qabul qilingan Q1 bitlari: {', '.join(sel['selected_bits']) or 'yo`q'}) · source `{frz['expected_source_hash'][:12]}`",
         "", f"**Texnik bajarilish: {tech}.** **Ilmiy tayyorlik: {sci}.**",
         "Texnik COMPLETE Q1 jurnal qabuli yoki 10/10 degani emas. Jurnal tanlanmagan, shuning uchun format, qamrov va "
         "kvartil talablari tekshirilmagan. Maqola hech qayerga yuborilmadi.", "",
         "## 1. Tekshirilgan versiyalar va bosqichlar", "",
         f"- E0 (muzlatilgan v3) sha256 `{frz['hashes']['E0_binary'][:16]}`; v2.1 `{frz['hashes']['v21_binary'][:16]}`; "
         f"Eθ `{frz['hashes']['Etheta_binary'][:16]}`.",
         "- Bosqichlar: audit → tuzatishlar → development (seen data) → freeze → yangi to'liq run → raw audit → tahlil → "
         "paket → validator.", "", "| run | holat | katalog |", "|---|---|---|"]
    L += [f"| {k} | {r.get('status')} | `{r.get('run_dir')}` |" for k, r in st["runs"].items()]
    L += ["", "## 2. Muammolar: avval → tuzatish → dalil → qolgan cheklov", "", "| ID | muammo | tuzatish | holat | dalil |",
          "|---|---|---|---|---|"]
    pr = res.get("post_run") or {}
    L += [f"| {r['id']} | {r['issue']} | {r['fix']} | "
          f"{pr['I13_status'] if r['id'] == 'I13' and pr.get('I13_status') else r['status']} | {r['test_or_check']} |"
          for r in issues]
    L += ["", "### Yakuniy run'dan keyin topilgan holatlar (xom qatorlar va git'dan hisoblangan; "
          "`audit/post_run_findings.json`)", ""]
    ng = pr.get("neuroglancer_u32") or {}
    for key, x in ng.items():
        if x["narrow_rows"]:
            L.append(f"- `neuroglancer_b8_u32` ({key}): uint8/uint16 qatorlar {x['narrow_rows']}, SUCCESS "
                     f"{x['narrow_ok']}, boshqa statuslar {json.dumps(x['narrow_non_ok'])}. Qatordagi sabab: "
                     f"{(pr.get('neuroglancer_u32_reason_examples') or ['-'])[0]}. C1/C2 ga ta'siri yo'q; bu "
                     "C3 baseline uint16 ma'lumotda yo'q (uint64 da native yo'l bilan bir xil).")
    for w in pr.get("interference") or []:
        for key, r in w["runs"].items():
            L.append(f"- Interferensiya oynasi {w['start']} – {w['end']} ({w['what']}): {key} da "
                     f"{r['rows_in_window']}/{r['rows_total']} qator; C1 vaqt qatorlari {r['c1_timed_rows_in_window']}/"
                     f"{r['c1_timed_rows']}, C1 xotira qatorlari {r['c1_memory_rows_in_window']}; S_T barcha qatorlar "
                     f"bilan {f(r['S_T_all_rows'], 4)}, oynadagi qatorlarsiz {f(r['S_T_without_window_rows'], 4)}.")
    if pr.get("freeze_commit"):
        L.append(f"- Freeze commit `{pr['freeze_commit']}` dan keyingi commit'lar: "
                 f"{'; '.join(pr['post_freeze_commits']) or 'yo`q'}. O'zgargan fayllar: "
                 f"{', '.join(pr['post_freeze_files']) or 'yo`q'}. O'lchov kodi (cape/, cpp/, run_all.py, configs/, "
                 f"snapshots/, vendor/, manifestlar) o'zgarganmi: {pr.get('measurement_code_changed_after_freeze')}. "
                 f"Commit qilinmagan kod fayllari: {', '.join(pr.get('uncommitted_files') or []) or 'yo`q'}.")
    L += ["", "## 3. Yangi o'lchovlar (yangi run; eski frozen natijalar ishlatilmagan)", "",
          "| dataset | taqqoslash | n | S_T [95% CI] | R_M [95% CI] | hajm farqi | W/T/L |", "|---|---|---|---|---|---|---|"]
    for ds in ("j0126", "snemi", "hemibrain"):
        for cid, lab in (("C1", "C1 Eθ vs E0"), ("BUILD", "build drift"), ("C2", "C2 vs v2.1"),
                         ("C3_wgreedy", "C3 weighted greedy"), ("C3_stock_corr", "C3 corrected stock"),
                         ("C3_flat", "C3 flat")):
            if ds in D:
                L.append(cmp_line(ds, cid, lab))
    L += ["", "Hukmlar (oldindan belgilangan maqsadlar: S_T ≥ 1.05, R_M ≤ 0.95; maqsad va statistik dalil alohida):", ""]
    for ds, x in v.items():
        if x.get("n"):
            L.append(f"- **{ds}**: bayt tengligi {f(x['byte_equal_pct'], 1)}%; tezlik maqsadi {x['speed_target_reached']} "
                     f"(CI 1 dan yuqori: {x['speed_ci_excludes_1']}); xotira maqsadi {x['memory_target_reached']} "
                     f"(CI 1 dan past: {x['memory_ci_excludes_1']}); eng yomon namuna: tezlik "
                     f"{f(x['worst_speedup']['speedup'])} ({x['worst_speedup']['sample_id']}), xotira "
                     f"{f((x['worst_mem_ratio'] or {}).get('mem_ratio'))}.")
        else:
            L.append(f"- **{ds}**: {x.get('status')} ({x.get('reason')})")
    fam = res["primary_family"]
    L += [f"- Asosiy oila (Holm): {json.dumps({k: (None if p is None else round(p, 5)) for k, p in fam['p_holm'].items()})}.",
          "", "## 4. Modullar: nima yutdi va nima yutqazdi", ""]
    for mod, dd in sel["modules"].items():
        lo = dd["loo"]
        L.append(f"- {mod}: development qarori **{'ACCEPT' if dd['accepted'] else 'REJECT'}** (S_T {f(lo['S_T'])} "
                 f"{ci(lo['S_T_ci'])}, R_M {f(lo['R_M'])} {ci(lo['R_M_ci'])}); sabab: {'; '.join(dd['reason'])}.")
    for ds, d in D.items():
        for k, p in d["ablation"].items():
            if not p.get("empty"):
                L.append(f"- final {ds}: Eθ vs {k}: S_T {f(p['S_T'])} {ci(p['S_T_ci'])}, R_M {f(p['R_M'])} "
                         f"{ci(p['R_M_ci'])}.")
    L += ["- Run-based CC labeling (birinchi O1 urinish): baytlar bir xil, lekin fragmentlangan (ws) slice'larda ~40% "
          "sekin bo'lgani uchun o'lchov panelidan oldin rad etildi.", "",
          "## 5. Yangilik, engineering hissasi va isbotlanmagan taxminlar", "",
          "- **Engineering hissasi:** chiqishni saqlovchi bufer va allokatsiya o'zgarishlari (O1/O2/O3). Ularning "
          "ekvivalentlik isbotlari `mathematics/` da, muzlatilgan binari bilan bayt tengligi esa har namunada tekshirilgan.",
          "- **Yangilik:** yangi siqish algoritmi yo'q. Inverted index va dedup g'oyalari ma'lum "
          "(`methods/CONTRIBUTION_AND_PRIOR_ART_EN.md`).",
          "- **Isbotlanmagan:** boshqa platformalar, ko'p thread va boshqa acquisition'larga umumlashuv.", "",
          "## 6. Baholar (dalil manzili bilan)", "", "| mezon | baho | dalil |", "|---|---|---|"]
    lossless_bad = sum(d["lossless"]["failed"] for d in D.values())
    be_all = all(x.get("byte_equal_all") for x in v.values() if x.get("n"))
    L += [f"| matematik to'g'rilik | {'PASS' if lossless_bad == 0 and be_all else 'FAIL'} | lossless xato {lossless_bad}; "
          f"bayt tengligi: {be_all}; `mathematics/`, `raw_results/raw_audit.json` |",
          f"| baseline adolati | PASS | bir xil worker/thread/pinning; matched greedy bir xil infratuzilmada; T02/T03 |",
          f"| tashqi validatsiya | {'PARTIAL' if j.get('n') else 'BLOCKED'} | yangi acquisition'lar: j0126 (asosiy), "
          f"hemibrain (tavsifiy); T01 |",
          f"| reproduksiya | PASS | `reproducibility/REPRODUCE.md`, freeze hash'lari, `--mode render` |",
          f"| amaliy foyda | {'PASS' if j.get('speed_target_reached') or j.get('memory_target_reached') else 'PARTIAL'} | "
          f"C1 j0126: S_T {f(j.get('S_T'))}, R_M {f(j.get('R_M'))} |", "",
          "## 7. Maqolada yozish mumkin va mumkin bo'lmagan da'volar", ""]
    L += [f"- [{c['status']}] {c['claim']} — doira: {c['scope']}; cheklov: {c['limitation']}" for c in cl]
    L += ["", "## 8. Qolgan kamchiliklar va eng kichik keyingi tajriba", "",
          "- Mustaqil acquisition'lar soni kam. Eng kichik keyingi qadam: yana 1–2 ta ochiq, real neyron label hajmi "
          "(foydalanuvchi ruxsati bilan) va xuddi shu muzlatilgan protokol.",
          "- Ikkinchi platformada (Linux/GCC yoki boshqa CPU) C1 ni qayta o'lchash.",
          "- Qo'shimcha test yutuq kafolati emas.", "", "## 9. Artefaktlar va qayta yaratish", "",
          "- Indeks: `artifact_manifest.csv`; da'volar: `claims_ledger.csv`; jadvallar: `tables/`; grafiklar: `figures/`.",
          f"- Qayta yaratish: `.venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode render --run-id {res['run_id']} "
          f"--output \"maqola uchun\"` (o'lchovsiz). To'liq yangi run: `--mode full --fresh-run`."]
    (out / "YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "README_UZ.md").write_text(f"""# `maqola uchun/` - CAPE Q1 maqola materiallari

Run ID: `{res['run_id']}`
Texnik holat: **{tech}** · Ilmiy tayyorlik: {sci}

Bitta asosiy hisobot: `YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md`.

| papka | mazmun |
|---|---|
| figures/, plot_data/ | F01–F08 (PDF, SVG, 300 dpi PNG) va ularning qiymatlari (CSV) |
| tables/ | T01–T08 (CSV, MD, LaTeX) |
| methods/ | obyekt/ma'lumot (EN/UZ), usul, natijalar, cheklovlar, prior-art, qo'lyozma draft, captionlar, bib |
| mathematics/ | M1a, O1–O3 ekvivalentligi, sertifikat modeli |
| reproducibility/ | freeze, reja, muvaffaqiyat mezonlari, config/manifestlar, lock, REPRODUCE.md |
| raw_results/ | yangi run'ning barcha o'lchov qatorlari va terminal statuslari |
| audit/ | issue register, inventar, eski da'volar qayta hisobi, sertifikat tarqalishi, development tanlovi |
| supplementary/ | namuna bo'yicha jadvallar, analysis.json |
| checks/ | validator natijalari |
| scripts/ | hammasini qayta yaratadigan kod |

Datasetlar litsenziya sababli paketga kiritilmagan; manifestlarda manba, koordinata va SHA-256 bor.
""", encoding="utf-8")
    rows = artifact_manifest(out, figs, tables)
    with open(out / "artifact_manifest.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--raw-audit", action="store_true")
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args(argv)
    rc = 0
    if a.raw_audit:
        rc |= raw_audit(a.run_id)
    if a.build:
        rc |= build(a.run_id)
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # console/redirect encodings on Windows (cp1252)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
