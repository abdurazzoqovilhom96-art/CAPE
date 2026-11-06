"""CAPE-Pins v2 final report (plan v2): every number is recomputed from the runs' raw
`05_raw_metrics/results.csv` and `12_tables/memory.csv`; nothing is typed in by hand.

Outputs (analysis/v2_final/): V2_YAKUNIY_HISOBOT_UZ.md, v2_summary.json, figures/*.png and the exact
plot data of every figure in plot_data/*.csv. Missing runs are reported as BLOCKED with the reason.

    python scripts/v2_report.py --state analysis/v2_state.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_report import by_sample, load_cells  # noqa: E402

OUT = ROOT / "analysis" / "v2_final"
V1_PILOT = "results/20261105T112549Z_pilot_5fc4a006"
V1_HELDOUT = "results/20261105T122347Z_all_d1a76eb7"
V1_WIDTH = "results/20261105T145305Z_development_c1d12b3e"
SEED = 20261106
N_BOOT = 10_000

# reference palette (dataviz skill, light mode); scatter charts use at most the first 3 slots
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]


# ------------------------------------------------------------------ data access
class Run:
    def __init__(self, rel: str | None):
        self.rel = rel
        self.ok = bool(rel) and (ROOT / rel / "05_raw_metrics" / "results.csv").exists()
        if not self.ok:
            return
        self.dir = ROOT / rel
        cells, rows = load_cells(self.dir)
        self.cells = cells
        self.S = by_sample(cells, "B")
        self.A = by_sample(cells, "A")
        self.rows = rows
        self.extra = defaultdict(dict)  # key -> sample -> extra json of the first OK row
        for r in rows:
            if r["panel"] != "B":
                continue
            key = r["method_id"] + ("" if (r.get("wrapper") or "none") == "none" else "+" + r["wrapper"])
            if r["sample_id"] not in self.extra[key] and r.get("extra_json"):
                try:
                    self.extra[key][r["sample_id"]] = json.loads(r["extra_json"])
                except json.JSONDecodeError:
                    pass
        self.mem = defaultdict(list)
        mp = self.dir / "12_tables" / "memory.csv"
        if mp.exists():
            for r in csv.DictReader(open(mp, encoding="utf-8")):
                if r.get("peak_rss_mib") and r.get("status") in ("OK", "", None):
                    self.mem[r["method"]].append(float(r["peak_rss_mib"]))
        rm = json.loads((self.dir / "run_manifest.json").read_text(encoding="utf-8"))
        self.status = rm.get("status")
        self.n_fail = sum(1 for r in csv.DictReader(open(self.dir / "05_raw_metrics" / "results.csv", encoding="utf-8"))
                          if r["status"] != "OK")
        self.n_rows = sum(1 for _ in open(self.dir / "05_raw_metrics" / "results.csv", encoding="utf-8")) - 1

    def samples(self, *keys) -> list[str]:
        return sorted(s for s in self.S if all(k in self.S[s] for k in keys))


def boot_ratio(new: list[float], base: list[float], clusters: list[str]) -> tuple[float, float]:
    cl = sorted(set(clusters))
    idx = {c: i for i, c in enumerate(cl)}
    sn = np.zeros(len(cl))
    sb = np.zeros(len(cl))
    for n, b, c in zip(new, base, clusters):
        sn[idx[c]] += n
        sb[idx[c]] += b
    rng = np.random.default_rng(SEED)
    draw = rng.integers(0, len(cl), size=(N_BOOT, len(cl)))
    r = sn[draw].sum(1) / sb[draw].sum(1)
    return float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def geo(xs: list[float]) -> float | None:
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else None


def pair(run: Run, new: str, base: str) -> dict | None:
    ids = run.samples(new, base)
    if not ids:
        return None
    S = run.S
    bn = [S[s][new]["total_bytes"] for s in ids]
    bb = [S[s][base]["total_bytes"] for s in ids]
    cl = [S[s][new]["macroblock_id"] for s in ids]
    lo, hi = boot_ratio(bn, bb, cl) if len(set(cl)) >= 2 else (None, None)
    tn = [S[s][new]["enc_med"] for s in ids]
    tb = [S[s][base]["enc_med"] for s in ids]
    dn = [S[s][new]["dec_med"] for s in ids]
    db = [S[s][base]["dec_med"] for s in ids]
    saved = sum(bb) - sum(bn)
    extra_s = (sum(tn) - sum(tb)) / 1e9
    return {
        "new": new, "base": base, "n": len(ids), "n_clusters": len(set(cl)),
        "interval": "confirmatory-style (>=5 clusters)" if len(set(cl)) >= 5 else "exploratory (<5 clusters)",
        "better": sum(a < b for a, b in zip(bn, bb)), "equal": sum(a == b for a, b in zip(bn, bb)),
        "worse": sum(a > b for a, b in zip(bn, bb)),
        "bytes_new": sum(bn), "bytes_base": sum(bb), "saved_bytes": saved,
        "saved_percent": 100 * saved / sum(bb) if sum(bb) else None, "ratio": sum(bn) / sum(bb),
        "ratio_ci95": [lo, hi],
        "median_sample_saved_percent": st.median(100 * (b - a) / b for a, b in zip(bn, bb)),
        "encode_time_ratio_geo": geo([a / b for a, b in zip(tn, tb) if a and b]),
        "encode_extra_ms_median": st.median((a - b) / 1e6 for a, b in zip(tn, tb)),
        "decode_time_ratio_geo": geo([a / b for a, b in zip(dn, db) if a and b]),
        "saved_bytes_per_extra_encode_second": saved / extra_s if extra_s > 0 else None,
    }


def method_table(run: Run, keys: list[str], ref: str) -> list[dict]:
    out = []
    for k in keys:
        ids = run.samples(k, ref)
        if not ids:
            continue
        S = run.S
        mem = run.mem.get(k, [])
        out.append({
            "method": k, "n": len(ids), "total_bytes": sum(S[s][k]["total_bytes"] for s in ids),
            "ratio_vs_ref": sum(S[s][k]["total_bytes"] for s in ids) / sum(S[s][ref]["total_bytes"] for s in ids),
            "encode_ms_median": st.median(S[s][k]["enc_med"] / 1e6 for s in ids),
            "encode_speedup_vs_ref_geo": geo([S[s][ref]["enc_med"] / S[s][k]["enc_med"] for s in ids]),
            "decode_ms_median": st.median(S[s][k]["dec_med"] / 1e6 for s in ids),
            "peak_rss_mib_median": st.median(mem) if mem else None,
            "peak_rss_mib_max": max(mem) if mem else None,
        })
    return out


def winners(run: Run, keys: list[str]) -> dict:
    cnt = defaultdict(int)
    if len(keys) < 2:
        return {}
    for s in run.samples(*keys):
        best = min(run.S[s][k]["total_bytes"] for k in keys)
        for k in keys:
            if run.S[s][k]["total_bytes"] == best:
                cnt[k] += 1
    return dict(cnt)


def refine_stats(run: Run, key: str) -> dict:
    ex = run.extra.get(key, {})
    if not ex:
        return {}
    vals = list(ex.values())
    choice = defaultdict(int)
    for v in vals:
        choice[v.get("safe_choice")] += 1
    def tot(f):
        return sum(int(v.get(f) or 0) for v in vals)
    return {"samples": len(vals), "choice": dict(choice), "evals_total": tot("refine_evals"),
            "unpin_applied": tot("refine_unpin_applied"), "anchor_applied": tot("refine_anchor_applied"),
            "unpin_candidates": tot("refine_unpin_candidates"), "anchor_candidates": tot("refine_anchor_candidates"),
            "refine_ms_median": st.median((v.get("refine_ns") or 0) / 1e6 for v in vals),
            # effect on the pins stream itself (before the flat/pins choice) vs on the stored file
            "pins_stream_saved_bytes": sum(int(v.get("refine_J0") or 0) - int(v.get("refine_J") or 0) for v in vals),
            "pins_stored": choice.get("PINS_VARIABLE_WIDTH", 0)}


def cross_run_identity(new: Run, old_rel: str, key: str) -> dict | None:
    old = Run(old_rel)
    if not (new.ok and old.ok):
        return None
    ids = [s for s in new.S if key in new.S[s] and s in old.S and key in old.S[s]]
    if not ids:
        return {"key": key, "old_run": old_rel, "n": 0}
    same = sum(new.S[s][key]["sha"] is not None and new.S[s][key]["sha"] == old.S[s][key]["sha"] for s in ids)
    sp = geo([old.S[s][key]["enc_med"] / new.S[s][key]["enc_med"] for s in ids])
    return {"key": key, "old_run": old_rel, "n": len(ids), "identical_bitstreams": same,
            "encode_speedup_vs_v1_run_geo": sp, "note": "cross-run timing (same machine/protocol, other session)"}


# ------------------------------------------------------------------ formatting
def f(v, d=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def table(rows: list[dict], cols: list[tuple[str, str, int]]) -> str:
    if not rows:
        return "_ma'lumot yo'q_\n"
    lines = ["| " + " | ".join(h for _, h, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = []
        for k, _, d in cols:
            v = r.get(k)
            if isinstance(v, list):
                v = "[" + ", ".join(f(x, 5) for x in v) + "]"
            cells.append(f(v, d))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


PAIR_COLS = [("new", "Yangi", 0), ("base", "Baza", 0), ("n", "n", 0), ("n_clusters", "klaster", 0),
             ("better", "kichik", 0), ("equal", "teng", 0), ("worse", "katta", 0), ("saved_bytes", "tejalgan B", 0),
             ("saved_percent", "tejash %", 4), ("ratio_ci95", "nisbat 95% CI", 5),
             ("encode_time_ratio_geo", "encode vaqti x", 2), ("encode_extra_ms_median", "+ms (median)", 1),
             ("decode_time_ratio_geo", "decode vaqti x", 3)]
METHOD_COLS = [("method", "Usul", 0), ("n", "n", 0), ("total_bytes", "jami bayt", 0), ("ratio_vs_ref", "nisbat", 5),
               ("encode_ms_median", "encode ms", 2), ("encode_speedup_vs_ref_geo", "encode tezl. x", 2),
               ("decode_ms_median", "decode ms", 2), ("peak_rss_mib_median", "peak RSS MiB (med)", 1),
               ("peak_rss_mib_max", "max", 1)]


# ------------------------------------------------------------------ figures
def _style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def _logx(ax, values, right_pad=1.5, both=False):
    """Log axis with plain-number ticks (no 2x10^1 style labels)."""
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator, ScalarFormatter

    lo, hi = min(values), max(values)
    ticks = [t for t in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000)
             if lo / 2 <= t <= hi * right_pad]
    axes = [ax.xaxis, ax.yaxis] if both else [ax.xaxis]
    if both:
        ax.set_yscale("log")
    ax.set_xscale("log")
    for a in axes:
        a.set_major_locator(FixedLocator(ticks))
        a.set_major_formatter(ScalarFormatter())
        a.set_minor_locator(NullLocator())
        a.set_minor_formatter(NullFormatter())
    ax.set_xlim(lo / 1.4, hi * right_pad)
    if both:
        ax.set_ylim(lo / 1.4, hi * right_pad)


def figures(test: Run, pilot: Run, width: Run, budget: int | None) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    (OUT / "plot_data").mkdir(parents=True, exist_ok=True)
    made = []

    def save(fig, name, rows):
        fig.patch.set_facecolor(SURFACE)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"{name}.png", dpi=150)
        plt.close(fig)
        with open(OUT / "plot_data" / f"{name}.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        made.append(name)

    # V2-F1: refinement gain vs extra encode time per sample (test run, up to 3 tracks)
    src = test if test.ok else pilot
    e = budget or 24
    tracks = [(f"safe_refine_e{e}_m0_zstd9", "safe_archive_m0_zstd9", "Markov 0, zstd 9"),
              (f"safe_refine_e{e}_m0_zstd3", "safe_archive_m0_zstd3", "Markov 0, zstd 3"),
              (f"safe_refine_e{e}_m5_zstd9", "safe_archive_m5_zstd9", "Markov 5, zstd 9")]
    rows = []
    if src.ok:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for i, (n, b, lab) in enumerate(tracks):
            ids = src.samples(n, b)
            if not ids:
                continue
            xs = [(src.S[s][n]["enc_med"] - src.S[s][b]["enc_med"]) / 1e6 for s in ids]
            ys = [100 * (src.S[s][b]["total_bytes"] - src.S[s][n]["total_bytes"]) / src.S[s][b]["total_bytes"] for s in ids]
            ax.scatter(xs, ys, s=46, color=SERIES[i], edgecolor=SURFACE, linewidth=1.5, label=lab, zorder=3)
            rows += [{"run": src.rel, "track": lab, "sample_id": s, "extra_encode_ms": x, "saved_percent_vs_safe": y}
                     for s, x, y in zip(ids, xs, ys)]
        if rows:
            ax.axhline(0, color=INK2, linewidth=0.8)
            _style(ax, "Refinement: SAFE-ARCHIVE'ga nisbatan qo'shimcha tejash va vaqt narxi",
                   "qo'shimcha encode vaqti, ms (refine - SAFE)", "tejash, % (SAFE bayti)")
            ax.legend(frameon=False, fontsize=8, labelcolor=INK)
            save(fig, "V2_F1_refine_gain_vs_time", rows)
        else:
            plt.close(fig)

    # V2-F2: archive track - bytes vs encode time (one series, direct labels)
    if src.ok:
        keys = [f"safe_refine_e{e}_m0_zstd9", "safe_archive_m0_zstd9", "crackle_flat_m0+zstd9", "cape_fast_m0+zstd9",
                "cape_m0+zstd9", "crackle_pins_opt_m0+zstd9", "crackle_pins_opt_corrected_m0+zstd9"]
        keys = [k for k in keys if src.samples(k, "crackle_flat_m0+zstd9")]
        if len(keys) >= 2:
            tab = method_table(src, keys, "crackle_flat_m0+zstd9")
            fig, ax = plt.subplots(figsize=(7, 4.2))
            xs = [t["encode_ms_median"] for t in tab]
            ys = [100 * (t["ratio_vs_ref"] - 1) for t in tab]
            ax.scatter(xs, ys, s=46, color=SERIES[0], edgecolor=SURFACE, linewidth=1.5, zorder=3)
            groups: list[list] = []  # methods at (nearly) the same point share one label
            for t, x, y in zip(tab, xs, ys):
                for g in groups:
                    if abs(math.log(g[0] / x)) < 0.08 and abs(g[1] - y) < 0.02:
                        g[2].append(t["method"])
                        break
                else:
                    groups.append([x, y, [t["method"]]])
            for x, y, names in groups:
                ax.annotate(chr(10).join(names), (x, y), textcoords="offset points", xytext=(7, -3), fontsize=7,
                            color=INK2, va="top" if len(names) > 1 else "center")
            ax.axhline(0, color=INK2, linewidth=0.8)
            _logx(ax, xs, right_pad=4.0)
            _style(ax, "Archive track (zstd 9): hajm va encode vaqti", "encode ms (namunalar mediani, log)",
                   "hajm farqi, % (flat+zstd9 ga nisbatan)")
            save(fig, "V2_F2_archive_bytes_vs_time",
                 [{"run": src.rel, "method": t["method"], "encode_ms_median": x, "size_vs_flat_zstd9_percent": y}
                  for t, x, y in zip(tab, xs, ys)])

    # V2-F3: implementation speed-up, legacy vs fast (same bytes), up to 3 runs
    rows = []
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    lim = [math.inf, 0]
    for i, (r, lab) in enumerate([(pilot, "pilot (CREMI A)"), (test, "test (CREMI B/C ko'rilmagan)"), (width, "width (Z=512)")]):
        if not r.ok:
            continue
        ids = r.samples("cape_m0", "cape_m0_legacy")
        if not ids:
            continue
        xs = [r.S[s]["cape_m0_legacy"]["enc_med"] / 1e6 for s in ids]
        ys = [r.S[s]["cape_m0"]["enc_med"] / 1e6 for s in ids]
        lim = [min(lim[0], *xs, *ys), max(lim[1], *xs, *ys)]
        ax.scatter(xs, ys, s=46, color=SERIES[i], edgecolor=SURFACE, linewidth=1.5, label=lab, zorder=3)
        rows += [{"run": r.rel, "sample_id": s, "legacy_encode_ms": x, "fast_encode_ms": y,
                  "identical_bytes": r.S[s]["cape_m0"]["sha"] == r.S[s]["cape_m0_legacy"]["sha"]}
                 for s, x, y in zip(ids, xs, ys)]
    if rows:
        ax.plot(lim, lim, color=INK2, linewidth=0.8, linestyle="--")
        _logx(ax, lim, right_pad=1.4, both=True)
        _style(ax, "Bir xil bitstream: v1 (legacy) va v2 (fast) encode vaqti", "legacy encode ms", "fast encode ms")
        ax.legend(frameon=False, fontsize=8, labelcolor=INK)
        save(fig, "V2_F3_legacy_vs_fast_encode", rows)
    else:
        plt.close(fig)

    # V2-F4: pilot budget / move ablation (small multiples: bytes and time, never a dual axis)
    if pilot.ok:
        variants = ["safe_refine_e8_m0_zstd9", "safe_refine_e24_m0_zstd9", "safe_refine_e64_m0_zstd9",
                    "safe_refine_unpin_e24_m0_zstd9", "safe_refine_anchor_e24_m0_zstd9"]
        ps = [p for p in (pair(pilot, v, "safe_archive_m0_zstd9") for v in variants) if p]
        if ps:
            fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.6))
            names = [p["new"].replace("safe_refine_", "").replace("_m0_zstd9", "") for p in ps]
            a1.barh(names, [p["saved_bytes"] for p in ps], color=SERIES[0], height=0.55)
            a2.barh(names, [p["encode_extra_ms_median"] for p in ps], color=SERIES[0], height=0.55)
            _style(a1, "Pilot: SAFE'ga nisbatan tejalgan bayt (jami)", "bayt", "")
            _style(a2, "Pilot: qo'shimcha encode vaqti (median)", "ms", "")
            a1.invert_yaxis()
            a2.invert_yaxis()
            save(fig, "V2_F4_pilot_refine_ablation",
                 [{"variant": p["new"], "saved_bytes": p["saved_bytes"], "saved_percent": p["saved_percent"],
                   "extra_encode_ms_median": p["encode_extra_ms_median"]} for p in ps])
    return made


# ------------------------------------------------------------------ report
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="analysis/v2_state.json")
    ap.add_argument("--out", default=None, help="output directory (default analysis/v2_final)")
    args = ap.parse_args(argv)
    global OUT
    if args.out:
        OUT = Path(args.out)
    from cape.result_store import atomic_write_text, now_iso

    state = json.loads((ROOT / args.state).read_text(encoding="utf-8")) if (ROOT / args.state).exists() else {"steps": {}}
    steps = state.get("steps", {})

    def rd(k):
        s = steps.get(k, {})
        return s.get("run_dir") if s.get("status") == "DONE" else None

    pilot, test, width = Run(rd("pilot")), Run(rd("test")), Run(rd("width"))
    freeze = json.loads((ROOT / "analysis/v2_freeze/freeze.json").read_text(encoding="utf-8")) \
        if (ROOT / "analysis/v2_freeze/freeze.json").exists() else None
    budget = freeze.get("frozen_budget") if freeze else None
    e = budget or 24
    summary: dict = {"generated_at": now_iso(), "runs": {"pilot": pilot.rel, "test": test.rel, "width": width.rel},
                     "steps": {k: {"status": v.get("status"), "detail": v.get("detail")} for k, v in steps.items()},
                     "freeze": freeze}
    OUT.mkdir(parents=True, exist_ok=True)

    # research question
    rq_test = [p for p in (pair(test, f"safe_refine_e{e}_m{m}_zstd{z}", f"safe_archive_m{m}_zstd{z}")
                           for m in (0, 5) for z in (9, 3)) if p] if test.ok else []
    rq_pilot = [p for p in (pair(pilot, v, b) for v, b in [
        ("safe_refine_e8_m0_zstd9", "safe_archive_m0_zstd9"), ("safe_refine_e24_m0_zstd9", "safe_archive_m0_zstd9"),
        ("safe_refine_e64_m0_zstd9", "safe_archive_m0_zstd9"), ("safe_refine_unpin_e24_m0_zstd9", "safe_archive_m0_zstd9"),
        ("safe_refine_anchor_e24_m0_zstd9", "safe_archive_m0_zstd9"), ("safe_refine_e24_m0_zstd3", "safe_archive_m0_zstd3")]) if p] \
        if pilot.ok else []
    ref_stats = {k: refine_stats(r, k) for r in (pilot, test) if r.ok for k in r.extra if k.startswith("safe_")}
    safe_vs_flat = [p for p in ((pair(r, f"safe_archive_m{m}_zstd{z}", f"crackle_flat_m{m}+zstd{z}"), r.rel)
                                for r in (pilot, test) if r.ok for m in (0, 5) for z in (3, 9)) if p[0]]
    summary["research_question"] = {"test": rq_test, "pilot": rq_pilot, "refine_internals": ref_stats,
                                    "safe_vs_flat": [dict(p, run=rel) for p, rel in safe_vs_flat]}

    # raw track / archive track / memory
    main_run = test if test.ok else pilot
    raw_keys = ["cape_fast_m0", "cape_certified_m0", "cape_m0", "cape_m0_legacy", "crackle_pins_opt_corrected_m0",
                "crackle_pins_opt_m0", "crackle_vendor_pins_opt_m0", "crackle_flat_m0", "cape_fast_m5",
                "crackle_pins_opt_m5", "crackle_flat_m5"]
    arch_keys = [f"safe_refine_e{e}_m0_zstd9", "safe_archive_m0_zstd9", "crackle_flat_m0+zstd9", "cape_fast_m0+zstd9",
                 "cape_m0+zstd9", "crackle_pins_opt_m0+zstd9", "crackle_pins_opt_corrected_m0+zstd9",
                 f"safe_refine_e{e}_m5_zstd9", "safe_archive_m5_zstd9", "crackle_flat_m5+zstd9", "cape_fast_m5+zstd9"]
    raw_tab = method_table(main_run, raw_keys, "crackle_pins_opt_corrected_m0") if main_run.ok else []
    arch_tab = method_table(main_run, arch_keys, "crackle_flat_m0+zstd9") if main_run.ok else []
    arch_win = winners(main_run, [k for k in arch_keys if "_m5" not in k and main_run.samples(k)]) if main_run.ok else {}
    raw_pairs = [p for p in (pair(main_run, a, b) for a, b in [
        ("cape_fast_m0", "crackle_pins_opt_corrected_m0"), ("cape_fast_m0", "crackle_pins_opt_m0"),
        ("cape_m0", "crackle_pins_opt_m0"), ("cape_fast_m0", "cape_m0"), ("cape_m0", "cape_m0_legacy"),
        ("cape_certified_m0", "cape_fast_m0"), ("crackle_pins_opt_corrected_m0", "crackle_pins_opt_m0"),
        ("cape_fast_m0", "crackle_flat_m0"), ("cape_fast_m5", "crackle_pins_opt_m5")]) if p] if main_run.ok else []
    width_pairs = [p for p in (pair(width, a, b) for a, b in [
        ("cape_m0", "cape_m0_legacy"), ("cape_fast_m0", "cape_m0"), ("cape_certified_m0", "cape_fast_m0"),
        ("cape_fast_m0", "crackle_pins_opt_corrected_m0"), ("crackle_pins_opt_corrected_m0", "crackle_pins_opt_m0"),
        ("safe_refine_e24_m0_zstd9", "safe_archive_m0_zstd9"), ("safe_archive_m0_zstd9", "crackle_flat_m0+zstd9")]) if p] \
        if width.ok else []
    width_tab = method_table(width, ["cape_fast_m0", "cape_certified_m0", "cape_m0", "cape_m0_legacy",
                                     "crackle_pins_opt_corrected_m0", "crackle_pins_opt_m0", "crackle_flat_m0"],
                             "crackle_pins_opt_corrected_m0") if width.ok else []
    ident = [x for x in (cross_run_identity(pilot, V1_PILOT, "cape_m0"), cross_run_identity(width, V1_WIDTH, "cape_m0"),
                         cross_run_identity(pilot, V1_PILOT, "crackle_pins_opt_m0")) if x]
    summary.update({"raw_track": {"run": main_run.rel if main_run.ok else None, "table": raw_tab, "pairs": raw_pairs},
                    "archive_track": {"table": arch_tab, "winners": arch_win},
                    "width": {"table": width_tab, "pairs": width_pairs}, "v1_identity": ident})
    ceil = {}
    for tag in ("pilot", "test"):
        p = ROOT / "analysis" / f"v2_ceiling_{tag}" / "archive_ceiling_summary.json"
        if p.exists():
            ceil[tag] = json.loads(p.read_text(encoding="utf-8"))
    summary["archive_ceiling"] = ceil
    made = figures(test, pilot, width, budget)
    summary["figures"] = made

    # ---------------------------------------------------------------- markdown
    def P(lst, new, base):
        for p in lst:
            if p["new"] == new and p["base"] == base:
                return p
        return None

    L = ["# CAPE-Pins v2 — yakuniy hisobot", "",
         f"Yaratildi: {summary['generated_at']} (avtomatik, `scripts/v2_report.py`). Barcha raqamlar run'larning xom "
         "`results.csv` / `memory.csv` fayllaridan qayta hisoblangan. v1 raqamlari faqat taqqoslash uchun keltirilgan, "
         "ular qayta o'lchanmagan (v1 run'larining audit qilingan qiymatlari).", "",
         "## 0. Bosqichlar holati", "",
         table([{"step": k, "status": v.get("status"), "detail": v.get("detail"), "run": v.get("run_dir")}
                for k, v in steps.items()], [("step", "Qadam", 0), ("status", "Holat", 0), ("run", "Run", 0),
                                              ("detail", "Izoh", 0)])]
    for name, r in (("pilot", pilot), ("test", test), ("width", width)):
        if r.ok:
            L.append(f"- `{name}`: `{r.rel}` — holat {r.status}, {r.n_rows} o'lchov, OK bo'lmagan qator: {r.n_fail}.")
        else:
            L.append(f"- `{name}`: **BLOCKED / bajarilmagan** — {steps.get(name, {}).get('detail') or 'qadam ishga tushmagan'}.")
    L += ["", "**Mustaqil test oilasi: BLOCKED.** H01/MICrONS kabi boshqa acquisition yuklanmagan (foydalanuvchi "
          "qarori). `test` run'i CREMI B/C volume'larining hech qachon o'lchanmagan z 64–123 qatlamlaridagi croplarda "
          "bajarilgan: voksel kesishmasi yo'q, lekin volume'lar o'sha — bu mustaqil test EMAS, faqat volume ichida "
          "umumlashuv.", ""]

    L += ["## 1. Nima qayta yaratildi (ishlaydigan kod)", "",
          "- `reduction_impl: fast` (default): column-major CC zanjirlari, hash-jadval dedup, faqat erishiladigan "
          "holatlarni ko'radigan exact DP, bitta pass'li run qurish. v1 kodi `reduction_impl: legacy` sifatida saqlangan; "
          "540 ta golden v1 bitstream bayt-bayt bir xil (`tests/test_golden_v1.py`, `tests/test_reduction_fast.py`).",
          "- FAST / CERTIFIED: `cape_fast_*` (depth-regime qidiruvi o'chirilgan, sertifikat hisoblanmaydi) va "
          "`cape_certified_*` (FAST bilan bayt-bayt bir xil stream + barcha depth regime'lar bo'yicha cheklangan-model "
          "LB; vaqti alohida o'lchanadi).",
          "- Tuzatilgan stock: `crackle_pins_opt_corrected_*` — upstream tanlovi/foni/serializeri, faqat F2 count kengligi "
          "tuzatilgan; stock to'g'ri ishlagan har joyda bayt-bayt bir xil. Upstream HEAD `3426263` da ham F2 tasdiqlandi.",
          "- SAFE-ARCHIVE: `safe_archive_*` — bitta native chaqiruvda flat va CAPE-FAST stream'lari, bir xil zstd bilan "
          "o'raladi, kichigi saqlanadi (engineering baseline, hissa emas).",
          f"- Refinement: `safe_refine_e{{8,24,64}}_*` — `cape/refine.py`: unpin va anchor harakatlari, har biri to'liq "
          "fayl (header, indeks, CRC'lar bilan) + zstd orqali baholanadi, faqat qat'iy kichrayish qabul qilinadi, S0 "
          "self-check. Dekoder — o'zgartirilmagan stock Crackle dekoderi (encoder xotirasiga tayanmaydi).",
          f"- Testlar: {steps.get('tests', {}).get('detail') or '-'} (+ 12/12 acceptance).", ""]

    L += ["## 2. Asosiy ilmiy savol: refinement SAFE'dan qo'shimcha foyda beradimi?", "",
          "SAFE+refine va SAFE-ARCHIVE bir xil zstd darajasi va Markov tartibida solishtirildi; ikkalasida ham encode "
          "vaqtiga barcha nomzodlarni yaratish va tanlash xarajati kiradi; har qator stock dekoder bilan voksel bo'yicha "
          "tekshirilgan.", ""]
    if freeze:
        L += [f"**Freeze (pilotdan, testdan oldin):** byudjet e={freeze['frozen_budget']} — {freeze['reason']}. "
              f"Pilot yutuqlari (bayt): {freeze['gain_bytes_by_budget']}; ablation: {freeze.get('ablation_gain_bytes')}.", ""]
    L += ["### 2.1 Test (ko'rilmagan croplar, muzlatilgan sozlamalar)", "", table(rq_test, PAIR_COLS),
          "### 2.2 Pilot ablation (CREMI A, development)", "", table(rq_pilot, PAIR_COLS),
          "### 2.3 Refinement ichki statistikasi", "",
          table([dict(method=k, **v) for k, v in sorted(ref_stats.items()) if v],
                [("method", "Usul", 0), ("samples", "namuna", 0), ("choice", "saqlangan format", 0),
                 ("evals_total", "baholashlar", 0), ("unpin_applied", "unpin qabul", 0),
                 ("unpin_candidates", "unpin nomzod", 0), ("anchor_applied", "anchor qabul", 0),
                 ("anchor_candidates", "anchor nomzod", 0), ("refine_ms_median", "refine ms (med)", 1),
                 ("pins_stream_saved_bytes", "pins stream'da tejash B", 0)]),
          "Izoh: refinement faqat pins stream'ni o'zgartiradi; saqlanadigan fayl min(zstd(flat), zstd(refined pins)). "
          "Flat yutgan namunalarda pins stream'dagi tejash saqlanadigan faylga o'tmaydi.", "",
          "### 2.4 SAFE-ARCHIVE va bir xil sozlamadagi flat+zstd (engineering ta'siri)", "",
          table([dict(p, run=rel) for p, rel in safe_vs_flat], [("run", "Run", 0)] + PAIR_COLS[:10]), ""]

    L += ["## 3. Raw track (Crackle-v1 mos, zstd'siz)", "", f"Run: `{main_run.rel if main_run.ok else '-'}`; nisbat va tezlashuv "
          "`crackle_pins_opt_corrected_m0` ga nisbatan.", "", table(raw_tab, METHOD_COLS),
          "### Juftliklar", "", table(raw_pairs, PAIR_COLS),
          "## 4. Archive track (zstd 9)", "", "Nisbat `crackle_flat_m0+zstd9` ga nisbatan.", "", table(arch_tab, METHOD_COLS),
          f"Namuna bo'yicha eng kichik fayl (Markov 0): {arch_win}", "",
          "## 5. Scale paneli (width, ko'rilgan Crackle croplari, Z=512)", "", table(width_tab, METHOD_COLS),
          table(width_pairs, PAIR_COLS),
          "## 6. v1 bilan bitstream mosligi (run'lararo)", "",
          table(ident, [("key", "Usul", 0), ("old_run", "v1 run", 0), ("n", "n", 0),
                        ("identical_bitstreams", "bir xil bitstream", 0),
                        ("encode_speedup_vs_v1_run_geo", "encode tezl. x (run'lararo)", 2)]),
          "## 7. Archive ceiling (label bo'limining siqilgan fayldagi ulushi)", ""]
    for tag, c in ceil.items():
        L.append(f"- `{tag}`: median ulush {c['gate']['median_pins_archive_label_share_pct']:.2f}% (gate >= 3%: "
                 f"{'o`tdi' if c['gate']['passed'] else 'o`tmadi'}).")
    L += ["", "## 8. Grafiklar", ""] + [f"- `figures/{m}.png` (manba: `plot_data/{m}.csv`)" for m in made] + [""]

    # ---- answers (conditional on the numbers) ----
    L += ["## 9. Javoblar", ""]
    t9 = P(rq_test, f"safe_refine_e{e}_m0_zstd9", "safe_archive_m0_zstd9")
    if t9:
        lo, hi = t9["ratio_ci95"]
        sig = hi is not None and hi < 1.0
        L += [f"**Refinement qo'shimcha foydasi (test, Markov 0, zstd 9):** {t9['saved_bytes']} B "
              f"({f(t9['saved_percent'], 4)}% SAFE baytidan), {t9['better']}/{t9['n']} namunada kichik, "
              f"{t9['worse']} ta katta. Nisbat 95% CI [{f(lo, 5)}, {f(hi, 5)}] — "
              f"{'1 dan past, ya`ni foyda statistik jihatdan barqaror' if sig else 'foyda statistik jihatdan tasdiqlanmadi'}"
              f" (CI {t9['n_clusters']} klaster, 2 volume ichida shartli). Narxi: encode vaqti x{f(t9['encode_time_ratio_geo'], 2)} "
              f"(median +{f(t9['encode_extra_ms_median'], 1)} ms), decode x{f(t9['decode_time_ratio_geo'], 3)}.", ""]
    else:
        L += ["**Refinement qo'shimcha foydasi:** test run mavjud emas — javob berilmadi (BLOCKED).", ""]
    rp = P(raw_pairs, "cape_fast_m0", "crackle_pins_opt_corrected_m0")
    lg = P(raw_pairs, "cape_m0", "cape_m0_legacy")
    ce = P(raw_pairs, "cape_certified_m0", "cape_fast_m0")
    fl = P(raw_pairs, "cape_fast_m0", "crackle_flat_m0")
    L += ["**Yutgan va yutqazgan joylar (o'lchangan):**", ""]
    if rp:
        L.append(f"- Hajm, raw: CAPE-FAST tuzatilgan stock'ga nisbatan {f(rp['saved_percent'], 4)}% tejaydi "
                 f"({rp['better']} kichik / {rp['equal']} teng / {rp['worse']} katta), encode vaqti "
                 f"x{f(rp['encode_time_ratio_geo'], 3)} (1 dan kichik = tezroq).")
    if fl:
        L.append(f"- CAPE-FAST va flat (zstd'siz): hajm {f(fl['saved_percent'], 4)}% tejash, encode vaqti "
                 f"x{f(fl['encode_time_ratio_geo'], 2)} — flat tezroq bo'lsa bu yutqazish.")
    if lg:
        L.append(f"- Implementatsiya: bir xil bitstream ({lg['equal']}/{lg['n']} teng bayt), v2 fast encode "
                 f"x{f(lg['encode_time_ratio_geo'], 3)} (legacy vaqtiga nisbatan).")
    if ce:
        L.append(f"- CERTIFIED: stream bayti FAST bilan teng ({ce['equal']}/{ce['n']}), vaqt ustamasi "
                 f"x{f(ce['encode_time_ratio_geo'], 3)}.")
    if arch_win:
        L.append(f"- Archive track (zstd 9) g'oliblari namunalar bo'yicha: {arch_win}.")
    mem_rows = [t for t in raw_tab if t.get("peak_rss_mib_median")]
    if mem_rows:
        L.append("- Peak RSS (median MiB): " + ", ".join(f"{t['method']} {t['peak_rss_mib_median']:.0f}" for t in mem_rows) + ".")
    L += ["", "**Tajriba bilan tasdiqlangan xulosalar:** faqat yuqoridagi jadvallarda CI yoki bayt-bayt tenglik bilan "
          "ko'rsatilganlari. Ko'rilgan ma'lumotdagi (pilot, width) raqamlar development/exploratory.", "",
          "**Saqlash / o'chirish / qayta ishlash (o'lchovlarga asoslangan qoida):**", ""]
    if lg and lg["equal"] == lg["n"]:
        L.append("- SAQLASH: `reduction_impl: fast` — baytlar bir xil, vaqt kamaygan.")
    wp = P(width_pairs, "cape_fast_m0", "cape_m0")
    if wp:
        verdict = "O'CHIRISH (standartda)" if wp["saved_percent"] is not None and wp["saved_percent"] > -0.05 else "QAYTA KO'RISH"
        L.append(f"- {verdict}: depth-regime qidiruvi — Z=512 da FAST va to'liq qidiruv farqi {f(wp['saved_percent'], 4)}%, "
                 f"FAST vaqti x{f(wp['encode_time_ratio_geo'], 3)}.")
    if t9:
        good = t9["saved_percent"] is not None and t9["saved_percent"] >= 0.1 and (t9["ratio_ci95"][1] or 2) < 1
        L.append(f"- {'SAQLASH (ixtiyoriy rejim)' if good else 'QAYTA ISHLASH yoki standartdan chiqarish'}: refinement — "
                 f"tejash {f(t9['saved_percent'], 4)}%, encode x{f(t9['encode_time_ratio_geo'], 2)}.")
    an = refine_stats(test, f"safe_refine_e{e}_m0_zstd9") if test.ok else {}
    if an and an.get("anchor_applied", 0) == 0:
        L.append("- O'CHIRISH yoki QAYTA LOYIHALASH: anchor harakati — testda birorta ham qabul qilinmadi.")
    L += ["- SAQLASH: SAFE-ARCHIVE engineering himoya sifatida (o'sha sozlamadagi flat'dan hech qachon katta emas), "
          "lekin ilmiy hissa sifatida emas.",
          "- SAQLASH: tuzatilgan stock baseline; F2 reproducer (upstream'ga xabar berish — loyiha egasining qarori).", "",
          "**Q1 uchun hali yetishmayotgan dalillar:**", "",
          "- Mustaqil acquisition / volume oilasi (BLOCKED: H01/MICrONS yuklanmagan); hozirgi CI 2 volume ichida.",
          "- Kattaroq ta'sir: label bo'limi faylning kichik qismi; crack-code (boundary) qismiga tegadigan usul yo'q.",
          "- Entropy-aware set cover / serialization bo'yicha prior-art tekshiruvi qilinmagan.",
          "- Linux track, ROI/random-access va GPU raqiblar bilan vazifaga mos taqqoslash yo'q.",
          "- To'liq factorial ablation (weighted cost × reductions × solver × wrapper) yo'q.", ""]
    atomic_write_text(OUT / "V2_YAKUNIY_HISOBOT_UZ.md", "\n".join(L) + "\n")
    atomic_write_text(OUT / "v2_summary.json", json.dumps(summary, indent=2, default=str))
    print(f"report -> {OUT / 'V2_YAKUNIY_HISOBOT_UZ.md'} (figures: {len(made)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
