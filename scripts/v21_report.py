"""CAPE-Pins v2.1 report (plan v2.1). Every number is recomputed from raw run files
(`05_raw_metrics/results.csv`, `07_component_stats/component_stats.csv`, `12_tables/memory.csv`) and
from analysis/v21_speedup/*.csv; nothing is typed in by hand. Missing inputs are reported as BLOCKED.

    python scripts/v21_report.py --state analysis/v21_state.json

Output (analysis/v21_final/): V21_HISOBOT_UZ.md, v21_summary.json, figures/*.png, plot_data/*.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from v2_report import GRID, INK, INK2, SURFACE, Run, f, geo, method_table, pair, table  # noqa: E402

OUT = ROOT / "analysis" / "v21_final"
SPEED = ROOT / "analysis" / "v21_speedup"
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # validated categorical slots 1-4 (dataviz palette)
NEUTRAL = "#8a8984"
CORE, SAFE, REFINE = "cape_fast_m0", "safe_archive_m0_zstd9", "safe_refine_e24_m0_zstd9"
STOCK_C = "crackle_pins_opt_corrected_m0"


def rcsv(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fam(sid: str) -> str:
    for k, v in (("crackle_connectomics", "Crackle connectomics"), ("crackle_ws", "Crackle ws"),
                 ("cremi_A", "CREMI A")):
        if k in sid:
            return v
    return "other"


def loglog_fit(xs, ys):
    pts = [(math.log(x), math.log(y)) for x, y in zip(xs, ys) if x and y and x > 0 and y > 0]
    if len({p[0] for p in pts}) < 3:
        return None
    a = np.array(pts)
    b, c = np.polyfit(a[:, 0], a[:, 1], 1)
    pred = b * a[:, 0] + c
    ss = float(((a[:, 1] - pred) ** 2).sum())
    tot = float(((a[:, 1] - a[:, 1].mean()) ** 2).sum())
    return {"slope": float(b), "r2": 1 - ss / tot if tot else None, "n": len(pts)}


# ------------------------------------------------------------------------------------------- sections
def z512_section(width: Run) -> tuple[str, dict]:
    if not width.ok:
        return "**BLOCKED:** width run (Z=512) not available.\n", {}
    keys_raw = [CORE, "cape_certified_m0", "cape_m0", "cape_m0_legacy", STOCK_C, "crackle_pins_opt_m0",
                "crackle_flat_m0", "cape_core", "cape_fixed_depth_width", "stock_cover"]
    keys_arc = [CORE + "+zstd9", "crackle_flat_m0+zstd9", STOCK_C + "+zstd9", SAFE, REFINE]
    raw = method_table(width, [k for k in keys_raw if any(k in v for v in width.S.values())], STOCK_C)
    arc = method_table(width, [k for k in keys_arc if any(k in v for v in width.S.values())], "crackle_flat_m0+zstd9")
    pairs = [p for p in (pair(width, CORE, STOCK_C), pair(width, CORE, "cape_m0"), pair(width, "cape_m0", "cape_m0_legacy"),
                         pair(width, "cape_certified_m0", CORE), pair(width, SAFE, "crackle_flat_m0+zstd9"),
                         pair(width, REFINE, SAFE)) if p]
    per = []
    for s in sorted(width.S):
        S = width.S[s]
        row = {"sample": s.replace("crackle_", "")}
        for k, lab in ((CORE, "FAST"), ("cape_m0", "regimes"), ("cape_m0_legacy", "v1"), (STOCK_C, "stock_c")):
            if k in S:
                row[f"{lab}_B"] = S[k]["total_bytes"]
                row[f"{lab}_s"] = S[k]["enc_med"] / 1e9
        per.append(row)
    md = [f"Run: `{width.rel}` - holat **{width.status}**, OK bo'lmagan qatorlar: {width.n_fail} / {width.n_rows}. "
          "Ma'lumot: 4 ta ko'rilgan Crackle crop (2 ta Z=512), 2 manba fayl - **tadqiqot (exploratory)**, CI yo'q.\n",
          "### Raw stream (nisbat = tuzatilgan stock'ga nisbatan)\n", table(raw, [
              ("method", "Usul", 0), ("n", "n", 0), ("total_bytes", "jami bayt", 0), ("ratio_vs_ref", "nisbat", 5),
              ("encode_ms_median", "encode ms", 1), ("encode_speedup_vs_ref_geo", "stock'dan tez x", 2),
              ("decode_ms_median", "decode ms", 1), ("peak_rss_mib_median", "peak RSS MiB", 1)]),
          "\n### Arxiv (nisbat = flat + zstd9 ga nisbatan)\n", table(arc, [
              ("method", "Usul", 0), ("n", "n", 0), ("total_bytes", "jami bayt", 0), ("ratio_vs_ref", "nisbat", 5),
              ("encode_ms_median", "encode ms", 1), ("decode_ms_median", "decode ms", 1),
              ("peak_rss_mib_median", "peak RSS MiB", 1)]),
          "\n### Juft taqqoslashlar\n", table(pairs, [
              ("new", "Yangi", 0), ("base", "Baza", 0), ("n", "n", 0), ("better", "kichik", 0), ("equal", "teng", 0),
              ("worse", "katta", 0), ("saved_bytes", "tejalgan B", 0), ("saved_percent", "tejash %", 4),
              ("encode_time_ratio_geo", "encode vaqti x", 3), ("encode_extra_ms_median", "+ms", 1)]),
          "\n### Namunalar bo'yicha (bayt va encode soniya)\n",
          table(per, [(k, k, 3 if k.endswith("_s") else 0) for k in (per[0].keys() if per else [])])]
    return "".join(md), {"raw": raw, "archive": arc, "pairs": pairs, "per_sample": per}


def attribution_section() -> tuple[str, dict]:
    summ = SPEED / "summary.json"
    if not summ.exists():
        return "**BLOCKED:** `analysis/v21_speedup/summary.json` yo'q (attribution qadami bajarilmagan).\n", {}
    s = json.loads(summ.read_text(encoding="utf-8"))
    shap = rcsv(SPEED / "shapley_summary.csv")
    contr = rcsv(SPEED / "contrasts.csv")
    stages = rcsv(SPEED / "stage_effects.csv")
    mem = rcsv(SPEED / "memory.csv")
    per = rcsv(SPEED / "per_sample.csv")
    md = [f"Namunalar: {s['n_samples']} (development: CREMI A pilot + Crackle width). Har kombinatsiya baytlari "
          f"mos: **{s['bytes_identical_all']}** (nomuvofiq: {s['bytes_mismatches']}); decode voksel bo'yicha aniq: "
          f"**{s['decode_voxel_identical_all']}**. Shapley qoldig'i max |{s['max_abs_shapley_residual']:.2e}|.\n\n"]
    rows = []
    for r in shap:
        rows.append({"group": r["group"], "factor": r["factor"], "label": r["label"], "class": r["class"],
                     "x": num(r["factor_x"]), "share": 100 * num(r["share_of_total"]) if num(r["share_of_total"]) is not None else None,
                     "ci": f"[{f(num(r['ci_lo_x']), 3)}, {f(num(r['ci_hi_x']), 3)}]" if r.get("ci_lo_x") else "-",
                     "n": r["n_samples"], "k": r["n_clusters"]})
    md.append("### Shapley: v1 legacy → v2 FAST tezlashuvining omillarga bo'linishi (geo-o'rtacha)\n")
    md.append(table(rows, [("group", "Guruh", 0), ("factor", "Omil", 0), ("label", "O'zgarish", 0), ("class", "Sinf", 0),
                           ("x", "tezlashuv x", 3), ("share", "ulush %", 1), ("ci", "95% CI (x)", 0), ("n", "n", 0),
                           ("k", "klaster", 0)]))
    cls = []
    for g, d in s.get("classes", {}).items():
        tot = sum(d.values())
        for c, v in d.items():
            cls.append({"group": g, "class": c, "x": math.exp(v), "share": 100 * v / tot if tot else None})
    md.append("\n### Sinflar bo'yicha: kod optimallashtirish / algoritmik / qidiruv fazosi (FAST qarori)\n")
    md.append(table(cls, [("group", "Guruh", 0), ("class", "Sinf", 0), ("x", "tezlashuv x", 3), ("share", "ulush %", 1)]))
    agg = defaultdict(lambda: defaultdict(list))
    for r in contr:
        for k in ("add_one_to_legacy", "drop_one_from_fast", "shapley"):
            agg[(r["group"], r["factor"])][k].append(num(r[k]))
    crow = [{"group": g, "factor": fa, **{k: math.exp(st.median(v)) for k, v in d.items()}} for (g, fa), d in sorted(agg.items())]
    md.append("\n### Kontrastlar (median tezlashuv x): legacy'ga bittasini qo'shish / FAST'dan bittasini olish / Shapley\n")
    md.append(table(crow, [("group", "Guruh", 0), ("factor", "Omil", 0), ("add_one_to_legacy", "legacy + omil", 3),
                           ("drop_one_from_fast", "FAST − omil", 3), ("shapley", "Shapley", 3)]))
    top = []
    for g in sorted({r["group"] for r in stages}):
        for fa in ("L", "H", "T", "S", "D"):
            rs = sorted((r for r in stages if r["group"] == g and r["factor"] == fa), key=lambda r: -abs(num(r["median_saved_ms"]) or 0))[:3]
            top.append({"group": g, "factor": fa, "stages": "; ".join(f"{r['stage'].replace('_ns', '')} {num(r['median_saved_ms']):+.2f} ms" for r in rs)})
    md.append("\n### Har omil qaysi bosqichni o'zgartirdi (median tejalgan ms, eng katta 3 ta; + = tezroq)\n")
    md.append(table(top, [("group", "Guruh", 0), ("factor", "Omil", 0), ("stages", "Bosqichlar", 0)]))
    if per:
        pr = [{"sample": p["sample_id"].replace("crackle_", ""), "v1_exact_ms": num(p["t_v1_exact_ms"]),
               "legacy_ms": num(p["t_legacy_ms"]), "v2_regimes_ms": num(p["t_v2_impl_regimes_ms"]),
               "fast_noR_ms": num(p["t_fast_noR_ms"]), "fast_ms": num(p["t_fast_ms"]),
               "x": math.exp(num(p["log_speedup_total"]))} for p in per]
        md.append("\n### Namunalar bo'yicha encode vaqti (median, ms)\n")
        md.append(table(pr, [("sample", "Namuna", 0), ("v1_exact_ms", "v1 aniq", 1), ("legacy_ms", "legacy", 1),
                             ("v2_regimes_ms", "v2 impl + regimes", 1), ("fast_noR_ms", "FAST, R'siz", 1),
                             ("fast_ms", "v2 FAST", 1), ("x", "jami x", 2)]))
    if mem:
        mr = [{"sample": m["sample_id"].replace("crackle_", ""), "cell": m["cell"],
               "peak_mib": (num(m.get("peak_after")) or 0) / 2**20,
               "extra_mib": (num(m.get("encode_extra_peak_bytes")) or 0) / 2**20 if m.get("encode_extra_peak_bytes") else None,
               "input_mib": (num(m.get("input_bytes")) or 0) / 2**20} for m in mem if m.get("status") == "OK"]
        md.append("\n### Xotira (yangi jarayon, OS peak working set; extra = encode paytidagi o'sish)\n")
        md.append(table(mr, [("sample", "Namuna", 0), ("cell", "Kombinatsiya", 0), ("input_mib", "kirish MiB", 0),
                             ("peak_mib", "peak MiB", 0), ("extra_mib", "encode extra MiB", 0)]))
    md.append("\nGrafiklar: `analysis/v21_speedup/figures/V21_S1_shapley.png`, `V21_S2_stage_profile.png` "
              "(plot data `analysis/v21_speedup/plot_data/`).\n")
    return "".join(md), {"summary": s, "contrasts_median": crow}


def measured_stats(run: Run, key: str) -> dict:
    """Per-sample problem-size statistics of one method straight from run.sqlite (first OK timed row).

    07_component_stats only lists methods that produce certificates; CAPE-FAST runs without one, so its
    candidate / incidence / component counts are read from the measurement rows (deterministic per sample).
    """
    db = run.dir / "05_raw_metrics" / "run.sqlite"
    out: dict = {}
    if not run.ok or not db.exists():
        return out
    c = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        q = ("select sample_id, candidate_count_before, candidate_count_after, incidence_count, component_count, "
             "max_component_cc, extra_json from measurements where method_id=? and (wrapper is null or wrapper='none') "
             "and status='OK' and encode_ns is not null order by sample_id, repeat")
        for sid, cb, ca, inc, ncomp, mx, ex in c.execute(q, (key,)):
            if sid in out:
                continue
            e = json.loads(ex) if ex else {}
            out[sid] = {"cc_count": e.get("cc_count"), "runs": e.get("run_count"), "candidates_before": cb,
                        "after_subset": ca, "incidence_before": e.get("incidence_count_before"),
                        "incidence_after": inc, "components": ncomp, "max_component_cc": mx,
                        "reduction_ns": e.get("reduction_ns"), "pass1_ns": e.get("pass1_ns"), "pass2_ns": e.get("pass2_ns")}
    finally:
        c.close()
    return out


def scaling_data(run: Run, stock: Run) -> list[dict]:
    comp = defaultdict(dict)
    if run.ok:
        for r in rcsv(run.dir / "07_component_stats" / "component_stats.csv"):
            if r.get("panel") in ("B", None, ""):
                comp[r["sample_id"]][r["method"]] = r
        for key in (CORE, "cape_m0_legacy"):
            for sid, d in measured_stats(run, key).items():
                comp[sid].setdefault(key, d)
    memo = defaultdict(dict)
    for rr in (run, stock):
        if rr.ok:
            for r in rcsv(rr.dir / "12_tables" / "memory.csv"):
                if r.get("status") in ("OK", "", None) and num(r.get("peak_rss_mib")):
                    memo[r["sample_id"]][r["method"]] = (num(r["peak_rss_mib"]), num(r.get("input_mib")))
    man = {json.loads(l)["sample_id"]: json.loads(l) for l in open(ROOT / "data" / "manifests" / "scaling_v21.jsonl",
                                                                       encoding="utf-8")} if (ROOT / "data" / "manifests" / "scaling_v21.jsonl").exists() else {}
    out = []
    for sid, m in man.items():
        Z, Y, X = m["shape"]
        c = comp.get(sid, {}).get(CORE, {})
        row = {"sample_id": sid, "family": fam(sid), "X": X, "Y": Y, "Z": Z, "voxels": X * Y * Z,
               "cc_count": num(c.get("cc_count")), "runs": num(c.get("runs")), "candidates_before": num(c.get("candidates_before")),
               "candidates_after": num(c.get("after_subset")), "incidence_before": num(c.get("incidence_before")),
               "incidence_after": num(c.get("incidence_after")),
               "components": num(c.get("components")), "max_component_cc": num(c.get("max_component_cc")),
               "reduction_ms": (num(c.get("reduction_ns")) or 0) / 1e6 if c else None,
               "solve_ms": ((num(c.get("pass1_ns")) or 0) + (num(c.get("pass2_ns")) or 0)) / 1e6 if c else None}
        for k, lab in ((CORE, "fast"), ("cape_m0", "regimes"), ("cape_m0_legacy", "legacy"), (SAFE, "safe"),
                       (REFINE, "refine"), ("crackle_flat_m0", "flat")):
            cell = run.S.get(sid, {}).get(k) if run.ok else None
            row[f"{lab}_enc_ms"] = cell["enc_med"] / 1e6 if cell and cell["enc_med"] else None
            row[f"{lab}_dec_ms"] = cell["dec_med"] / 1e6 if cell and cell["dec_med"] else None
            row[f"{lab}_bytes"] = cell["total_bytes"] if cell else None
            pk = memo.get(sid, {}).get(k)
            row[f"{lab}_peak_mib"] = pk[0] if pk else None
            row["input_mib"] = pk[1] if pk else row.get("input_mib")
        cell = stock.S.get(sid, {}).get(STOCK_C) if stock.ok else None
        row["stock_enc_ms"] = cell["enc_med"] / 1e6 if cell and cell["enc_med"] else None
        row["stock_bytes"] = cell["total_bytes"] if cell else None
        pk = memo.get(sid, {}).get(STOCK_C)
        row["stock_peak_mib"] = pk[0] if pk else None
        out.append(row)
    return sorted(out, key=lambda r: (r["family"], r["voxels"]))


def scaling_section(rows: list[dict], run: Run, stock: Run) -> tuple[str, dict]:
    if not rows or not run.ok:
        return "**BLOCKED:** scaling run yo'q yoki tugamagan.\n", {}
    md = [f"Runlar: `{run.rel}` (holat {run.status}, OK bo'lmagan {run.n_fail}/{run.n_rows}); stock: "
          f"`{stock.rel if stock.ok else 'yo`q'}` (holat {stock.status if stock.ok else '-'}). Crop'lar ko'rilgan "
          "development manbalardan, origin'dan nested - qiyaliklar **tavsifiy**, mustaqil dalil emas.\n\n"]
    md.append("Muammo o'lchami CAPE-FAST o'lchov qatorlaridan (`run.sqlite`; v1 legacy bilan bir xil, chunki baytlar "
              "va qisqartirish qoidalari bir xil): `nomzod` = qisqartirishdan oldingi nomzodlar (runs), `qolgan` = "
              "singleton/equal/subset dan keyingi nomzodlar, `incidence` = qolgan nomzod-CC bog'lanishlari, "
              "`komp.` = mustaqil komponentlar, `max komp.` = eng yirik komponentdagi CC soni; `reduksiya`/`yechish` "
              "= FAST ichidagi qisqartirish va pass1+pass2 vaqti (bitta o'lchov).\n\n")
    cols = [("sample_id", "Namuna", 0), ("voxels", "V", 0), ("candidates_before", "nomzod", 0),
            ("candidates_after", "qolgan", 0), ("incidence_after", "incidence", 0), ("components", "komp.", 0),
            ("max_component_cc", "max komp. CC", 0), ("reduction_ms", "reduksiya ms", 1), ("solve_ms", "yechish ms", 2),
            ("fast_enc_ms", "FAST ms", 1), ("legacy_enc_ms", "v1 ms", 1), ("regimes_enc_ms", "regimes ms", 1),
            ("safe_enc_ms", "SAFE ms", 1), ("refine_enc_ms", "refine ms", 1), ("flat_enc_ms", "flat ms", 1),
            ("stock_enc_ms", "stock ms", 1), ("fast_peak_mib", "FAST peak MiB", 0), ("legacy_peak_mib", "v1 peak", 0),
            ("stock_peak_mib", "stock peak", 0), ("input_mib", "kirish MiB", 0)]
    md.append(table([dict(r, sample_id=r["sample_id"].replace("scale_", "")) for r in rows], cols))
    fits = []
    for fam_ in sorted({r["family"] for r in rows}):
        rs = [r for r in rows if r["family"] == fam_]
        for lab in ("fast", "legacy", "regimes", "safe", "refine", "flat", "stock"):
            for x, xl in (("voxels", "V"), ("candidates_before", "nomzod"), ("candidates_after", "qolgan nomzod")):
                fit = loglog_fit([r[x] for r in rs], [r[f"{lab}_enc_ms"] for r in rs])
                if fit:
                    fits.append({"family": fam_, "method": lab, "y": "encode ms", "x": xl, **fit})
            fit = loglog_fit([r["voxels"] for r in rs], [r.get(f"{lab}_peak_mib") for r in rs])
            if fit:
                fits.append({"family": fam_, "method": lab, "y": "peak RSS", "x": "V", **fit})
        fit = loglog_fit([r["max_component_cc"] for r in rs], [(r["solve_ms"] or 0) or None for r in rs])
        if fit:
            fits.append({"family": fam_, "method": "fast", "y": "pass1+pass2 ms", "x": "max komp. CC", **fit})
        fit = loglog_fit([r["candidates_before"] for r in rs], [(r["reduction_ms"] or 0) or None for r in rs])
        if fit:
            fits.append({"family": fam_, "method": "fast", "y": "reduksiya ms", "x": "nomzod", **fit})
        fit = loglog_fit([r["voxels"] for r in rs], [r["candidates_before"] for r in rs])
        if fit:
            fits.append({"family": fam_, "method": "-", "y": "nomzod", "x": "V", **fit})
        fit = loglog_fit([r["voxels"] for r in rs], [r["max_component_cc"] for r in rs])
        if fit:
            fits.append({"family": fam_, "method": "-", "y": "max komp. CC", "x": "V", **fit})
    md.append("\n### Log-log qiyaliklar (y ∝ x^qiyalik; 1 = chiziqli)\n")
    md.append(table(fits, [("family", "Manba", 0), ("method", "Usul", 0), ("y", "y", 0), ("x", "x", 0),
                           ("slope", "qiyalik", 2), ("r2", "R²", 3), ("n", "n", 0)]))
    sep = []
    con = [r for r in rows if r["family"] == "Crackle connectomics"]
    for lab in ("fast", "legacy"):
        pts = [(math.log(r["X"] * r["Y"]), math.log(r["Z"]), math.log(r[f"{lab}_enc_ms"])) for r in con if r.get(f"{lab}_enc_ms")]
        if len(pts) >= 6:
            A = np.array([[1, p[0], p[1]] for p in pts])
            y = np.array([p[2] for p in pts])
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            sep.append({"method": lab, "exp_XY": float(coef[1]), "exp_Z": float(coef[2]), "n": len(pts)})
    if sep:
        md.append("\n### Crackle connectomics 4×4 grid: vaqt ∝ (XY)^a · Z^b\n")
        md.append(table(sep, [("method", "Usul", 0), ("exp_XY", "a (XY)", 2), ("exp_Z", "b (Z)", 2), ("n", "n", 0)]))
    skipped = ROOT / "data" / "manifests" / "scaling_v21_skipped.json"
    if skipped.exists():
        sk = json.loads(skipped.read_text(encoding="utf-8"))
        md.append(f"\nO'tkazib yuborilgan: {len(sk)} ta (stock uchun >2^25 voksel `SKIPPED_BUDGET`, manbaga sig'maydiganlar "
                  "`NOT_APPLICABLE`) - `data/manifests/scaling_v21_skipped.json`.\n")
    return "".join(md), {"rows": rows, "fits": fits, "xy_z_exponents": sep}


def times_section(test: Run, width: Run, scale: Run, rows: list[dict]) -> tuple[str, dict]:
    out = []
    for name, run in (("v2 test (24 ko'rilmagan CREMI B/C crop)", test), ("Z=512 width (4 Crackle crop)", width),
                      ("scaling (barcha crop'lar)", scale)):
        if not run.ok:
            continue
        for k, lab in ((CORE, "CAPE yadrosi (FAST, raw)"), (CORE + "+zstd9", "CAPE yadrosi + zstd9"),
                       (SAFE, "SAFE-ARCHIVE"), (REFINE, "SAFE + refine [EXPERIMENTAL]"),
                       ("crackle_flat_m0", "flat (pastki chegara)"), ("crackle_flat_m0+zstd9", "flat + zstd9"),
                       (STOCK_C, "tuzatilgan stock")):
            ids = [s for s in run.S if k in run.S[s] and run.S[s][k]["enc_med"]]
            if not ids:
                continue
            ex = run.extra.get(k, {})
            enc = [run.S[s][k]["enc_med"] for s in ids]

            def g(e, *keys):
                return next((num(e[x]) for x in keys if e.get(x) is not None), None)

            # native: the C++ encode call(s); SAFE/refine: wall time around cn.encode (both streams) when the
            # v2.1 timers exist, else the native encode_core_ns. zstd: every zstd call (SAFE: both streams;
            # refine: flat + J0 + every evaluation). glue = encode - native - zstd - refine Python work.
            def native(e):
                return g(e, "safe_native_ns", "refine_native_ns", "encode_core_ns")

            def zstd(e):
                if e.get("safe_zstd_ns") is not None:
                    return num(e["safe_zstd_ns"])
                parts = [e.get(x) for x in ("refine_flat_zstd_ns", "refine_J0_zstd_ns", "refine_eval_zstd_ns")]
                return sum(num(x) for x in parts) if all(x is not None for x in parts) else None

            def refine_loop(e):
                return num(e["refine_ns"]) if e.get("refine_ns") is not None else None

            def refine_py(e):  # refine loop without its zstd calls (serialize, moves, bookkeeping)
                if e.get("refine_ns") is None or e.get("refine_eval_zstd_ns") is None:
                    return None
                return num(e["refine_ns"]) - num(e.get("refine_J0_zstd_ns") or 0) - num(e["refine_eval_zstd_ns"])

            def glue(e, s):
                n = native(e)
                if n is None:
                    return None
                z = zstd(e)
                rp = refine_py(e) if z is not None else refine_loop(e)
                return run.S[s][k]["enc_med"] - n - (z or 0) - (rp or 0)

            def med(vals):
                vals = [v for v in vals if v is not None]
                return st.median(vals) / 1e6 if vals else None

            exs = [(s, ex[s]) for s in ids if s in ex]
            evals = [num(e["refine_evals"]) for _, e in exs if e.get("refine_evals") is not None]
            mem = run.mem.get(k, [])
            out.append({"data": name, "method": lab, "n": len(ids), "enc_ms_median": st.median(enc) / 1e6,
                        "enc_ms_total": sum(enc) / 1e6,
                        "native_ms_median": med(native(e) for _, e in exs),
                        "zstd_ms_median": med(zstd(e) for _, e in exs),
                        "refine_loop_ms_median": med(refine_loop(e) for _, e in exs),
                        "refine_py_ms_median": med(refine_py(e) for _, e in exs),
                        "refine_evals_median": st.median(evals) if evals else None,
                        "zstd_glue_ms_median": med(glue(e, s) for s, e in exs),
                        "dec_ms_median": st.median(run.S[s][k]["dec_med"] for s in ids) / 1e6,
                        "peak_mib_median": st.median(mem) if mem else None})
    if not out:
        return "**BLOCKED:** vaqt manbalari yo'q.\n", {}
    md = ["Encode = worker o'lchagan to'liq vaqt (bitta yadro, median). `native` = C++ encode chaqiruvi "
          "(SAFE/refine'da ikkala stream: CAPE + flat; v2.1 taymeri bo'lmasa `encode_core_ns`). `zstd` = barcha zstd "
          "chaqiruvlari (SAFE: ikkala stream; refine: flat + J0 + har bir baholash); faqat v2.1 taymerlari bor "
          "run'larda (scaling). `refine sikli` = `refine_ns` (ichida zstd ham bor), `refine Python` = refine sikli "
          "minus uning zstd'si. `glue` = encode − native − zstd − refine Python (nusxalash, Python; taymer yo'q "
          "run'larda zstd ham shu ustunda). Har ustun alohida median, shuning uchun qismlar yig'indisi encode "
          "medianiga aniq teng bo'lishi shart emas. Decode yo'li SAFE va refine'da bir xil: unzstd + stock Crackle.\n\n",
          table(out, [("data", "Ma'lumot", 0), ("method", "Usul", 0), ("n", "n", 0), ("enc_ms_median", "encode ms (med)", 2),
                      ("native_ms_median", "native ms", 2), ("zstd_ms_median", "zstd ms", 2),
                      ("refine_loop_ms_median", "refine sikli ms", 2), ("refine_py_ms_median", "refine Python ms", 2),
                      ("refine_evals_median", "baholashlar", 0), ("zstd_glue_ms_median", "glue ms", 2),
                      ("enc_ms_total", "encode jami ms", 0), ("dec_ms_median", "decode ms", 2),
                      ("peak_mib_median", "peak MiB", 1)])]
    return "".join(md), {"rows": out}


def snemi_section() -> tuple[str, dict]:
    log = ROOT / "data" / "downloads" / "snemi3d" / "download_log.json"
    man = ROOT / "data" / "manifests" / "confirm_snemi3d.jsonl"
    if not (log.exists() and man.exists()):
        return "**BLOCKED:** SNEMI3D tayyorlanmagan (`scripts/fetch_snemi3d.py`, `freeze_data.py --snemi3d-confirm`).\n", {}
    d = json.loads(log.read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in open(man, encoding="utf-8")]
    used = []
    for rm in (ROOT / "results").glob("*/run_manifest.json"):
        try:
            j = json.loads(rm.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "confirm_snemi3d" in json.dumps(j):
            used.append(rm.parent.name)
    info = {"doi": d.get("doi"), "license": d.get("license"), "md5": d.get("md5"), "sha256": d.get("sha256"),
            "n_crops": len(rows), "clusters": len({r["macroblock_id"] for r in rows}),
            "prepared_at": min(r["prepared_at"] for r in rows), "runs_using_it": used}
    md = (f"- Manba: DOI {info['doi']}, litsenziya {info['license']}, md5 `{info['md5']}` (Zenodo bilan mos), "
          f"SHA-256 `{info['sha256'][:16]}…`.\n- Muzlatilgan: {info['n_crops']} crop, {info['clusters']} klaster, "
          f"`prepared_at` {info['prepared_at']}.\n- Oldindan ro'yxatdan o'tgan konfiguratsiya: `configs/confirm_snemi3d.yaml` "
          "(primary: CAPE-FAST va tuzatilgan stock; secondary: SAFE va flat+zstd9; refine yo'q).\n"
          f"- Bu ma'lumotdan foydalangan run'lar: **{', '.join(used) if used else 'yo`q (siqish o`lchovi hali qilinmagan)'}**.\n"
          "- Batafsil: `docs/MUSTAQIL_DATA_SNEMI3D_UZ.md`.\n")
    return md, info


def figures(rows: list[dict], times: list[dict]) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    (OUT / "plot_data").mkdir(parents=True, exist_ok=True)
    made = []
    markers = {"Crackle connectomics": "o", "Crackle ws": "s", "CREMI A": "^"}

    def style(ax, title, xl, yl):
        ax.set_facecolor(SURFACE)
        ax.set_title(title, color=INK, fontsize=10, loc="left")
        ax.set_xlabel(xl, color=INK2, fontsize=9)
        ax.set_ylabel(yl, color=INK2, fontsize=9)
        ax.tick_params(colors=INK2, labelsize=8)
        ax.grid(True, color=GRID, linewidth=0.6)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)

    def save(fig, name, data):
        fig.patch.set_facecolor(SURFACE)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"{name}.png", dpi=150)
        plt.close(fig)
        if data:
            with open(OUT / "plot_data" / f"{name}.csv", "w", encoding="utf-8", newline="") as fh:
                fields = list(dict.fromkeys(k for r in data for k in r))  # union, first-seen order
                w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(data)
        made.append(name)

    def scatter(name, title, xkey, xl, series, yl):
        fig, ax = plt.subplots(figsize=(7.2, 4.4))
        data = []
        for i, (ykey, lab) in enumerate(series):
            color = PAL[i] if i < len(PAL) else NEUTRAL
            for fam_, mk in markers.items():
                pts = sorted((r[xkey], r[ykey]) for r in rows if r["family"] == fam_ and r.get(xkey) and r.get(ykey))
                if not pts:
                    continue
                # markers only: several crop shapes share one V, a connecting line would zig-zag
                ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=mk, ms=6, ls="none", color=color,
                        markeredgecolor=SURFACE, markeredgewidth=0.8, label=f"{lab} - {fam_}")
                data += [{"series": lab, "family": fam_, "x_field": xkey, "x": p[0], "y_field": ykey, "y": p[1]}
                         for p in pts]
        ax.set_xscale("log")
        ax.set_yscale("log")
        style(ax, title, xl, yl)
        ax.legend(fontsize=6.5, ncol=2, frameon=False)
        save(fig, name, data)

    if rows:
        scatter("V21_S3_time_vs_voxels", "Encode vaqti va hajm (log-log)", "voxels", "voksellar soni V",
                [("fast_enc_ms", "CAPE-FAST"), ("legacy_enc_ms", "v1 legacy"), ("stock_enc_ms", "tuzatilgan stock")],
                "encode ms (median)")
        scatter("V21_S4_memory_vs_voxels", "Peak xotira va hajm (yangi jarayon)", "voxels", "voksellar soni V",
                [("fast_peak_mib", "CAPE-FAST"), ("legacy_peak_mib", "v1 legacy"), ("stock_peak_mib", "tuzatilgan stock")],
                "peak working set MiB")
        scatter("V21_S5_time_vs_candidates", "Encode vaqti va nomzodlar soni", "candidates_before",
                "nomzodlar soni (reduksiyadan oldin)", [("fast_enc_ms", "CAPE-FAST"), ("legacy_enc_ms", "v1 legacy")],
                "encode ms (median)")
        scatter("V21_S6_solve_vs_maxcomp", "Yechish (pass1+pass2) vaqti va eng yirik komponent", "max_component_cc",
                "eng yirik komponentdagi CC soni", [("solve_ms", "CAPE-FAST pass1+pass2")], "ms")
    tr = [t for t in times if t["native_ms_median"] is not None]
    if tr:
        # one panel per data set with its own LINEAR axis: stacked parts on a log axis would hide the small ones
        groups = list(dict.fromkeys(t["data"] for t in tr))
        fig, axes = plt.subplots(len(groups), 1, figsize=(9.2, 0.42 * len(tr) + 1.1 * len(groups) + 0.6), squeeze=False)
        data = []
        for ax, gname in zip(axes[:, 0], groups):
            gt = [t for t in tr if t["data"] == gname]
            timed = any(t.get("zstd_ms_median") is not None for t in gt)  # v2.1 timers: zstd separated from glue
            for y, t in enumerate(gt):
                refine = t.get("refine_py_ms_median") if timed else t.get("refine_loop_ms_median")
                parts = [("native", t["native_ms_median"] or 0, PAL[0])]
                if timed:
                    parts.append(("zstd", t.get("zstd_ms_median") or 0, PAL[2]))
                parts += [("refine (Python)" if timed else "refine sikli (zstd bilan)", refine or 0, PAL[1]),
                          ("glue" if timed else "zstd + glue", max(0.0, t["zstd_glue_ms_median"] or 0), NEUTRAL)]
                left = 0.0
                for lab, v, c in parts:
                    ax.barh(y, v, left=left, color=c, height=0.62, label=lab if y == 0 else None,
                            edgecolor=SURFACE, linewidth=1.0)
                    left += v
                data.append({"data": gname, "method": t["method"], **{p[0]: p[1] for p in parts}})
            ax.set_yticks(range(len(gt)), [t["method"] for t in gt], fontsize=7.5)
            ax.invert_yaxis()
            style(ax, gname, "ms (median)", "")
            ax.legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
        fig.suptitle("Encode vaqtining tarkibi", fontsize=10, x=0.02, ha="left", color=INK)
        save(fig, "V21_S7_time_breakdown", data)
    return made


# ------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="analysis/v21_state.json")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    s21 = json.loads((ROOT / args.state).read_text(encoding="utf-8")) if (ROOT / args.state).exists() else {"steps": {}}
    s2 = json.loads((ROOT / "analysis" / "v2_state.json").read_text(encoding="utf-8"))["steps"]
    test, width = Run(s2.get("test", {}).get("run_dir")), Run(s2.get("width", {}).get("run_dir"))
    scale = Run(s21["steps"].get("scaling", {}).get("run_dir"))
    stock = Run(s21["steps"].get("scaling_stock", {}).get("run_dir"))
    z_md, z_js = z512_section(width)
    a_md, a_js = attribution_section()
    rows = scaling_data(scale, stock) if scale.ok else []
    s_md, s_js = scaling_section(rows, scale, stock)
    t_md, t_js = times_section(test, width, scale, rows)
    n_md, n_js = snemi_section()
    figs = figures(rows, t_js.get("rows", []))
    steps = [{"step": k, "status": "DONE (shu fayl)" if k == "report" else v.get("status"),
              "detail": v.get("run_dir") or v.get("detail")} for k, v in s21["steps"].items()]
    md = [
        "# CAPE-Pins v2.1 hisobot: Z=512, tezlashuv sabablari, masshtab, to'liq vaqtlar, SNEMI3D\n\n",
        "Bu hisobot avtomatik yaratilgan (`scripts/v21_report.py`). Har bir raqam xom run fayllaridan qayta hisoblangan. "
        "v2.1 da **yangi mexanizm qo'shilmagan**: faqat o'lchovlar va tayyorgarlik. Refinement **EKSPERIMENTAL** "
        "rejimda (standart pipeline'da yo'q).\n\n",
        "## 0. Qadamlar holati\n\n", table(steps, [("step", "Qadam", 0), ("status", "Holat", 0), ("detail", "Izoh", 0)]),
        "\n## 1. Z=512 (width) sinovi\n\n", z_md,
        "\n## 2. v1 → v2 tezlashuvi: bosqichlar va alohida o'zgarishlar\n\n",
        "v2 da **yangi qisqartirish qoidasi yo'q** (singleton / equal / subset v1 bilan bir xil). O'zgarishlar: "
        "L = column-major joylashuv + bir pass'li runs, H = arzon hash (ikkalasi **kod optimallashtirish**); "
        "T = hash-jadval guruhlash, S = erishiladigan holatli DP (ikkalasi **algoritmik**, natija bir xil); "
        "D = depth regime'larni o'chirish (**qidiruv fazosi / FAST qarori**, bayt o'zgarishi mumkin).\n\n", a_md,
        "\n## 3. Katta hajmlarda bog'liqlik: vaqt, xotira, nomzodlar, eng yirik komponent\n\n", s_md,
        "\n## 4. CAPE yadrosi, SAFE va refine: to'liq vaqtlar alohida\n\n", t_md,
        "\n## 5. Refinement holati: EKSPERIMENTAL\n\n",
        "Refine `configs/methods.yaml` da `experimental: true`; faqat config'da nomi aniq yozilganda ishlaydi, "
        "hisobotlarda g'olib sifatida ko'rsatilmaydi va tasdiqlovchi `confirm_snemi3d.yaml` ga kiritilmagan. "
        "Sabab (v2 test): SAFE'ga nisbatan +0.013% (42 B / 24 crop), encode 2.73× sekin.\n",
        "\n## 6. CREMI'dan mustaqil manba: SNEMI3D (tayyor, hali o'lchanmagan)\n\n", n_md,
        "\n## 7. Grafiklar\n\n", "".join(f"- `analysis/v21_final/figures/{x}.png` (plot data `plot_data/{x}.csv`)\n" for x in figs),
        "- `analysis/v21_speedup/figures/V21_S1_shapley.png`, `V21_S2_stage_profile.png`\n",
    ]
    (OUT / "V21_HISOBOT_UZ.md").write_text("".join(md), encoding="utf-8")
    (OUT / "v21_summary.json").write_text(json.dumps({
        "z512": z_js, "attribution": a_js, "scaling": s_js, "times": t_js, "snemi3d": n_js, "steps": steps,
        "figures": figs}, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT / 'V21_HISOBOT_UZ.md'} ({len(figs)} figures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
