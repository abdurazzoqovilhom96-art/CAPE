"""Independent audit of finished runs (plan v2, P0): every headline number is recomputed from the
raw `05_raw_metrics/results.csv` (and `07_component_stats`) with code that does NOT reuse
cape.statistics/cape.metrics, then compared with the run's own `09_statistics/summary.json`.

Run directories are only read. Outputs go to analysis/<out>/ (csv + AUDIT_UZ.md + audit.json).

    python scripts/audit_report.py --runs results/<v1_heldout> results/<v1_pilot> --out v1_audit
    python scripts/audit_report.py --runs results/<v2_dev> --compare-to results/<v1_heldout> --out v2_audit
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REL_TOL = 1e-9


def key_of(r: dict) -> str:
    w = r.get("wrapper") or "none"
    return r["method_id"] + ("" if w == "none" else "+" + w)


def load_cells(run: Path) -> tuple[dict, list[dict]]:
    """(sample, key, panel) -> aggregated cell; raw OK rows are returned too."""
    rows = [r for r in csv.DictReader(open(run / "05_raw_metrics" / "results.csv", encoding="utf-8"))
            if r["status"] == "OK"]
    groups: dict = defaultdict(list)
    for r in rows:
        groups[(r["sample_id"], key_of(r), r["panel"])].append(r)
    cells = {}
    for k, rs in groups.items():
        timed = [r for r in rs if r.get("encode_ns")]
        shas = {r["bitstream_sha256"] for r in rs if r.get("bitstream_sha256")}
        sizes = {int(float(r["total_bytes"])) for r in rs if r.get("total_bytes")}
        r0 = rs[0]
        cells[k] = {
            "sample_id": k[0], "key": k[1], "panel": k[2], "n_rows": len(rs),
            "total_bytes": min(sizes) if sizes else None, "deterministic_bytes": len(sizes) <= 1,
            "deterministic_sha": len(shas) <= 1, "sha": next(iter(shas)) if len(shas) == 1 else None,
            "label_bytes": int(float(r0["label_bytes"])) if r0.get("label_bytes") else None,
            "ub": float(r0["ub_bytes"]) if r0.get("ub_bytes") else None,
            "lb": float(r0["lb_bytes"]) if r0.get("lb_bytes") else None,
            "enc_med": st.median(float(r["encode_ns"]) for r in timed) if timed else None,
            "dec_med": st.median(float(r["decode_ns"]) for r in timed if r.get("decode_ns")) if timed else None,
            "macroblock_id": r0.get("macroblock_id"), "source_id": r0.get("source_id"),
            "is_synthetic": r0.get("is_synthetic") in ("True", "true", "1"),
        }
    return cells, rows


def by_sample(cells: dict, panel: str = "B") -> dict:
    out: dict = defaultdict(dict)
    for (sid, key, p), c in cells.items():
        if p == panel and not c["is_synthetic"] and c["total_bytes"] is not None:
            out[sid][key] = c
    return out


def primary(S: dict, new: str, base: str) -> dict:
    ids = sorted(s for s in S if new in S[s] and base in S[s])
    bn = sum(S[s][new]["total_bytes"] for s in ids)
    bb = sum(S[s][base]["total_bytes"] for s in ids)
    gains = [100 * (1 - S[s][new]["total_bytes"] / S[s][base]["total_bytes"]) for s in ids]
    sp = [S[s][base]["enc_med"] / S[s][new]["enc_med"] for s in ids if S[s][new]["enc_med"] and S[s][base]["enc_med"]]
    dp = [S[s][base]["dec_med"] / S[s][new]["dec_med"] for s in ids if S[s][new]["dec_med"] and S[s][base]["dec_med"]]
    return {
        "new": new, "base": base, "n_samples": len(ids),
        "n_clusters": len({S[s][new]["macroblock_id"] for s in ids}),
        "n_source_volumes": len({S[s][new]["source_id"] for s in ids}),
        "total_bytes_new": bn, "total_bytes_base": bb, "saved_bytes": bb - bn,
        "total_ratio": bn / bb if bb else None,
        "n_smaller": sum(S[s][new]["total_bytes"] < S[s][base]["total_bytes"] for s in ids),
        "n_ties": sum(S[s][new]["total_bytes"] == S[s][base]["total_bytes"] for s in ids),
        "n_regressions": sum(S[s][new]["total_bytes"] > S[s][base]["total_bytes"] for s in ids),
        "median_sample_gain_percent": st.median(gains) if gains else None,
        "geo_speedup_encode": math.exp(sum(map(math.log, sp)) / len(sp)) if sp else None,
        "geo_speedup_decode": math.exp(sum(map(math.log, dp)) / len(dp)) if dp else None,
    }


def counterpart(key: str, prefix: str = "cape") -> str:
    w = "+" + key.split("+", 1)[1] if "+" in key else ""
    lvl = "m5" if "_m5" in key else "m0"
    return f"{prefix}_{lvl}{w}"


def head_to_head(S: dict, new_prefix: str = "cape") -> list[dict]:
    keys = sorted({k for s in S.values() for k in s})
    out = []
    for k in keys:
        if k.startswith(new_prefix) or k.startswith("safe_archive"):
            continue
        c = counterpart(k, new_prefix)
        ids = [s for s in S if k in S[s] and c in S[s]]
        if not ids:
            continue
        sc = sum(S[s][c]["total_bytes"] for s in ids)
        so = sum(S[s][k]["total_bytes"] for s in ids)
        out.append({"competitor": k, "cape_counterpart": c, "n": len(ids),
                    "cape_smaller": sum(S[s][c]["total_bytes"] < S[s][k]["total_bytes"] for s in ids),
                    "equal": sum(S[s][c]["total_bytes"] == S[s][k]["total_bytes"] for s in ids),
                    "cape_larger": sum(S[s][c]["total_bytes"] > S[s][k]["total_bytes"] for s in ids),
                    "sum_cape": sc, "sum_competitor": so, "cape_vs_competitor_percent": 100 * (sc / so - 1)})
    return out


def safe_posthoc(S: dict) -> list[dict]:
    """Post-hoc min(flat, X) per sample with the SAME wrapper and Markov order (engineering bound)."""
    out = []
    for m in ("m0", "m5"):
        for w in ("", "+zstd3", "+zstd9"):
            f, c, p = f"crackle_flat_{m}{w}", f"cape_{m}{w}", f"crackle_pins_opt_{m}{w}"
            ids = [s for s in S if f in S[s] and c in S[s]]
            if not ids:
                continue
            sf = sum(S[s][f]["total_bytes"] for s in ids)
            row = {"track": f"{m}{w or '+none'}", "n": len(ids), "flat": sf,
                   "cape": sum(S[s][c]["total_bytes"] for s in ids),
                   "safe_cape": sum(min(S[s][f]["total_bytes"], S[s][c]["total_bytes"]) for s in ids)}
            if all(p in S[s] for s in ids):
                row["safe_stock_pins"] = sum(min(S[s][f]["total_bytes"], S[s][p]["total_bytes"]) for s in ids)
            row["safe_cape_vs_flat_percent"] = 100 * (row["safe_cape"] / sf - 1)
            if "safe_stock_pins" in row:
                row["safe_stock_vs_flat_percent"] = 100 * (row["safe_stock_pins"] / sf - 1)
            out.append(row)
    return out


def label_share(S: dict, keys=("cape_m0", "crackle_pins_opt_m0")) -> list[dict]:
    out = []
    for k in keys:
        v = [(S[s][k]["label_bytes"], S[s][k]["total_bytes"]) for s in S if k in S[s] and S[s][k]["label_bytes"]]
        if v:
            sh = [100 * a / b for a, b in v]
            out.append({"method": k, "n": len(v), "label_bytes": sum(a for a, _ in v), "total_bytes": sum(b for _, b in v),
                        "share_median_percent": st.median(sh), "share_min_percent": min(sh), "share_max_percent": max(sh)})
    return out


def gaps(S: dict, key: str = "cape_m0") -> dict | None:
    """UB/LB gap of the certified restricted model. `ub_bytes` == the whole stream length and
    `lb_bytes` == label LB + the rest of the stream, so UB - LB is the room left INSIDE the model;
    it is reported against the whole file (both conventions) and against the label section."""
    v = [(S[s][key]["ub"], S[s][key]["lb"], S[s][key]["label_bytes"]) for s in S
         if key in S[s] and S[s][key]["ub"] and S[s][key]["lb"] is not None]
    if not v:
        return None
    g_ub = [100 * (u - l) / u for u, l, _ in v]
    g_lb = [100 * (u - l) / l for u, l, _ in v if l > 0]
    g_lab = [100 * (u - l) / lb for u, l, lb in v if lb]
    return {"method": key, "n": len(v), "note": "ub/lb are whole-stream bytes; model = restricted certified pin model",
            "room_bytes_total": sum(u - l for u, l, _ in v),
            "room_percent_of_files": 100 * sum(u - l for u, l, _ in v) / sum(u for u, _, _ in v),
            "file_gap_over_ub_median_percent": st.median(g_ub), "file_gap_over_ub_max_percent": max(g_ub),
            "file_gap_over_lb_median_percent": st.median(g_lb) if g_lb else None,
            "label_section_gap_median_percent": st.median(g_lab) if g_lab else None,
            "label_section_gap_max_percent": max(g_lab) if g_lab else None}


STAGE_FIELDS = ["scan_ns", "boundary_ns", "cc_ns", "transpose_ns", "runs_ns", "candidate_ns", "reduction_ns",
                "reduction_singleton_ns", "reduction_equal_hash_ns", "reduction_equal_sort_ns",
                "reduction_subset_incidence_ns", "reduction_subset_scan_ns", "component_ns", "pass1_ns", "dp_ns",
                "local_ns", "pass2_ns", "serialize_ns"]


def stage_shares(run: Path, method: str = "cape_core") -> list[dict]:
    p = run / "07_component_stats" / "component_stats.csv"
    if not p.exists():
        return []
    rows = [r for r in csv.DictReader(open(p, encoding="utf-8")) if r["method"] == method and r["is_synthetic"] == "False"]
    out = []
    for f in STAGE_FIELDS:
        v = [100 * float(r[f]) / float(r["encode_ns_median"]) for r in rows
             if r.get(f) not in (None, "") and r.get("encode_ns_median") not in (None, "", "0")]
        if v:
            out.append({"method": method, "stage": f, "n": len(v), "median_share_percent": st.median(v),
                        "max_share_percent": max(v)})
    return out


def determinism(cells: dict) -> dict:
    multi = [c for c in cells.values() if c["n_rows"] > 1]
    return {"cells_with_repeats": len(multi),
            "nondeterministic_bytes": sum(not c["deterministic_bytes"] for c in multi),
            "nondeterministic_sha": sum(not c["deterministic_sha"] for c in multi)}


def check_against_summary(run: Path, mine: dict) -> dict:
    p = run / "09_statistics" / "summary.json"
    if not p.exists():
        return {"verified": False, "problems": ["summary.json missing"]}
    pr = json.loads(p.read_text(encoding="utf-8")).get("primary") or {}
    problems = []
    for k in ("total_bytes_new", "total_bytes_base", "total_ratio", "n_regressions", "n_ties", "n_samples",
              "n_clusters", "median_sample_gain_percent", "geo_speedup_encode", "geo_speedup_decode"):
        a, b = mine.get(k), pr.get(k)
        if a is None or b is None:
            problems.append(f"{k}: missing (audit={a}, report={b})")
        elif not math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=1e-12):
            problems.append(f"{k}: audit={a} report={b}")
    return {"verified": not problems, "problems": problems}


def compare_runs(S_new: dict, S_old: dict, keys: list[str]) -> list[dict]:
    """Same method key in two runs: bitstream identity and encode-time ratio on shared samples."""
    out = []
    for k in keys:
        ids = [s for s in S_new if k in S_new[s] and s in S_old and k in S_old[s]]
        if not ids:
            continue
        same = sum(S_new[s][k]["sha"] is not None and S_new[s][k]["sha"] == S_old[s][k]["sha"] for s in ids)
        sp = [S_old[s][k]["enc_med"] / S_new[s][k]["enc_med"] for s in ids if S_new[s][k]["enc_med"] and S_old[s][k]["enc_med"]]
        out.append({"key": k, "n": len(ids), "identical_bitstreams": same,
                    "geo_speedup_vs_old_run": math.exp(sum(map(math.log, sp)) / len(sp)) if sp else None,
                    "note": "cross-run timing: same machine and protocol, different session"})
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def md_table(rows: list[dict], fmt: dict | None = None) -> str:
    if not rows:
        return "_yo'q_\n"
    fmt = fmt or {}
    cols = list(dict.fromkeys(k for r in rows for k in r))

    def cell(c, v):
        if v is None:
            return "-"
        if isinstance(v, float):
            return format(v, fmt.get(c, ".4f"))
        return str(v)

    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(cell(c, r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def run_primary_pair(run: Path, new: str, base: str) -> tuple[str, str]:
    """The run's own pre-registered primary pair (summary.json); the CLI pair is only a fallback."""
    p = run / "09_statistics" / "summary.json"
    if p.exists():
        pr = json.loads(p.read_text(encoding="utf-8")).get("primary") or {}
        if pr.get("new") and pr.get("base"):
            return pr["new"], pr["base"]
    return new, base


def audit_run(run: Path, new: str, base: str) -> dict:
    cells, _ = load_cells(run)
    S = by_sample(cells)
    # the summary check must recompute the SAME pair the run reported; the CLI --new/--base pair is added
    # as an extra pair by main() when it differs
    pr = primary(S, *run_primary_pair(run, new, base))
    return {"run": run.name, "cells": cells, "S": S, "primary": pr, "summary_check": check_against_summary(run, pr),
            "head_to_head": head_to_head(S), "safe_posthoc": safe_posthoc(S), "label_share": label_share(S),
            "gaps": gaps(S), "stage_shares": stage_shares(run), "determinism": determinism(cells)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default="v1_audit")
    ap.add_argument("--new", default="cape_m0")
    ap.add_argument("--base", default="crackle_pins_opt_m0")
    ap.add_argument("--compare-to", default=None, help="older run: bitstream identity + cross-run timing")
    ap.add_argument("--compare-keys", nargs="*", default=["cape_m0", "cape_m5", "cape_core", "crackle_pins_opt_m0"])
    ap.add_argument("--pairs", nargs="*", default=[], help="extra within-run pairs new:base")
    args = ap.parse_args(argv)
    from cape.result_store import atomic_write_text, now_iso

    out_dir = ROOT / "analysis" / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": now_iso(), "runs": {}, "rel_tol": REL_TOL}
    md = [f"# Mustaqil audit — `{args.out}`", "",
          "Raqamlar `05_raw_metrics/results.csv` dan `cape.statistics` dan foydalanmasdan qayta hisoblangan va "
          "run'ning `09_statistics/summary.json` bilan solishtirilgan. Run papkalari faqat o'qildi.", ""]
    all_ok = True
    for rp in args.runs:
        run = (ROOT / rp) if not Path(rp).is_absolute() else Path(rp)
        a = audit_run(run, args.new, args.base)
        tag = run.name
        for name in ("head_to_head", "safe_posthoc", "label_share", "stage_shares"):
            write_csv(out_dir / f"{tag}_{name}.csv", a[name])
        extra = []
        if (a["primary"]["new"], a["primary"]["base"]) != (args.new, args.base):
            extra.append(primary(a["S"], args.new, args.base))
        for pair in args.pairs:
            n, b = pair.split(":", 1)
            extra.append(primary(a["S"], n, b))
        cmp_rows = []
        if args.compare_to:
            old = (ROOT / args.compare_to) if not Path(args.compare_to).is_absolute() else Path(args.compare_to)
            S_old = by_sample(load_cells(old)[0])
            cmp_rows = compare_runs(a["S"], S_old, args.compare_keys)
            write_csv(out_dir / f"{tag}_vs_{old.name}.csv", cmp_rows)
        has_summary = (run / "09_statistics" / "summary.json").exists()
        all_ok &= a["summary_check"]["verified"] or not has_summary
        report["runs"][tag] = {k: a[k] for k in ("primary", "summary_check", "gaps", "determinism")} | {
            "extra_pairs": extra, "compare": cmp_rows}
        pr = a["primary"]
        md += [f"## `{tag}`", "",
               f"- **Mustaqillik:** {pr['n_samples']} namuna, {pr['n_clusters']} klaster (macroblock), "
               f"{pr['n_source_volumes']} ta original volume. CI shu volume'lar ichida shartli.",
               f"- **Hisobot bilan moslik:** {'✅ verified' if a['summary_check']['verified'] else '❌ ' + '; '.join(a['summary_check']['problems'])}",
               f"- **Determinizm:** {a['determinism']}", "", "### Asosiy juftlik", "", md_table([pr]),
               "### Head-to-head (panel B, bir xil wrapper va Markov tartibi)", "", md_table(a["head_to_head"]),
               "### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)", "",
               md_table(a["safe_posthoc"]), "### Label bo'limi ulushi", "", md_table(a["label_share"]),
               "### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)", "",
               md_table([a["gaps"]] if a["gaps"] else []),
               "### Encode bosqichlari ulushi (`cape_core`, panel A)", "", md_table(a["stage_shares"])]
        if extra:
            md += ["### Qo'shimcha juftliklar", "", md_table(extra)]
        if cmp_rows:
            md += [f"### Run'lararo taqqoslash (`{args.compare_to}`)", "", md_table(cmp_rows)]
    report["verified"] = all_ok
    atomic_write_text(out_dir / "audit.json", json.dumps(report, indent=2, default=str))
    atomic_write_text(out_dir / "AUDIT_UZ.md", "\n".join(md) + "\n")
    print(f"audit verified={all_ok} -> {out_dir}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
