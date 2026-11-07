"""CAPE Q1 article package validator (task v3, section 11). Checks the staging package of one run and writes
checks/validation_report.json + checks/VALIDATION_UZ.md; appends the verdict to the final report. Exit 1 on FAIL.

    python tools/validate_article_package.py --run-id q1_<stamp> [--package <dir>]

Independent recomputation: the headline ratios are recomputed from raw_results/*_results.csv with pandas (a code path
separate from tools/q1_analysis.py, which reads run.sqlite) and compared with tables/T03.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("CAPE_ROOT") or Path(__file__).resolve().parents[1])  # CAPE_ROOT: run a copy against the repo data


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check(name, ok, detail, severity="FAIL"):
    return {"check": name, "result": "PASS" if ok else severity, "detail": detail}


def recompute(raw_csv: Path, new: str, base: str) -> dict | None:
    d = pd.read_csv(raw_csv, usecols=["sample_id", "method_id", "wrapper", "status", "total_bytes", "encode_ns",
                                      "rss_measurement_mode", "bitstream_sha256"], low_memory=False)
    d = d[(d.status == "OK") & (d.wrapper.fillna("none") == "none") & d.encode_ns.notna()]
    d = d[~d.rss_measurement_mode.astype(str).str.contains("fresh_process", na=False)]
    g = d.groupby(["method_id", "sample_id"]).agg(t=("encode_ns", "median"), b=("total_bytes", "first"),
                                                  bmin=("total_bytes", "min"), bmax=("total_bytes", "max"),
                                                  sha=("bitstream_sha256", "first")).reset_index()
    a, b = g[g.method_id == new].set_index("sample_id"), g[g.method_id == base].set_index("sample_id")
    j = a.join(b, how="inner", lsuffix="_n", rsuffix="_b")
    j = j[(j.bmin_n == j.bmax_n) & (j.bmin_b == j.bmax_b)]
    if j.empty:
        return None
    return {"n": len(j), "S_T": float(np.exp(np.mean(np.log(j.t_b / j.t_n)))),
            "G_B_pct": float(100 * (j.b_b.sum() - j.b_n.sum()) / j.b_b.sum()),
            "sha_equal": int((j.sha_n == j.sha_b).sum())}


def numbers_digest(pkg: Path) -> dict:
    out = {}
    for p in sorted(list((pkg / "tables").glob("*.csv")) + list((pkg / "plot_data").glob("*.csv"))):
        out[p.relative_to(pkg).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--package")
    a = ap.parse_args(argv)
    pkg = Path(a.package) if a.package else ROOT / "results" / a.run_id / "article_staging"
    res = []
    # 1. manifest: every OK artifact exists and is non-empty; BLOCKED carries a reason
    man = list(csv.DictReader(open(pkg / "artifact_manifest.csv", encoding="utf-8")))
    bad = [r["artifact"] for r in man if r["status"] == "OK" and not ((pkg / r["artifact"]).exists() and
                                                                       (pkg / r["artifact"]).stat().st_size > 0)]
    if any(r["artifact"] == "artifact_manifest.csv" and r["status"] != "OK" for r in man):
        bad.append("artifact_manifest.csv (self entry)")
    noreason = [r["artifact"] for r in man if r["status"] == "BLOCKED" and not r["reason"]]
    empty_dirs = [d.name for d in pkg.iterdir() if d.is_dir() and not any(d.iterdir())]
    res.append(check("1 manifest files exist, non-empty; BLOCKED has a reason; no empty folder",
                     not bad and not noreason and not empty_dirs,
                     {"missing_or_empty": bad[:20], "blocked_without_reason": noreason[:20], "empty_dirs": empty_dirs,
                      "blocked": [r["artifact"] for r in man if r["status"] == "BLOCKED"][:30]}))
    analysis = json.loads((pkg / "supplementary" / "analysis.json").read_text(encoding="utf-8"))
    # 2. claims trace to evidence that exists
    claims = list(csv.DictReader(open(pkg / "claims_ledger.csv", encoding="utf-8")))
    untraced = []
    for c in claims:
        ev = [e.strip() for e in re.split(r"[,;]", c["evidence"]) if e.strip() and e.strip() != "-"]
        for e in ev:
            tok = e.split()[0]
            hits = list(pkg.glob(f"**/{tok}*")) or list(pkg.glob(f"**/*{tok}*"))
            if not hits:
                untraced.append(f"{c['id']}:{tok}")
    res.append(check("2 every claim traces to an artifact in the package", not untraced, {"untraced": untraced}))
    # 3. independent recomputation of headline ratios vs T03
    t03 = list(csv.DictReader(open(pkg / "tables" / "T03_primary_matched.csv", encoding="utf-8")))
    mism, done = [], []
    for row in t03:
        if row["comparison"] not in ("C1", "C2", "C3_wgreedy", "C3_stock_corr", "C3_flat", "BUILD"):
            continue
        raw = pkg / "raw_results" / f"{row['dataset']}_results.csv"
        if not raw.exists():
            mism.append(f"{row['dataset']}: raw csv missing")
            continue
        r = recompute(raw, row["new"], row["base"])
        if r is None:
            mism.append(f"{row['dataset']}/{row['comparison']}: no pairs in raw")
            continue
        st, gb = float(row["S_T"]), float(row["G_B_pct"])
        ok = int(row["n"]) == r["n"] and abs(st - r["S_T"]) <= 1e-9 * max(1, st) and abs(gb - r["G_B_pct"]) <= 1e-7
        done.append({"dataset": row["dataset"], "comparison": row["comparison"], "table_S_T": st, "raw_S_T": r["S_T"],
                     "table_G_B": gb, "raw_G_B": r["G_B_pct"], "n": r["n"], "ok": ok})
        if not ok:
            mism.append(f"{row['dataset']}/{row['comparison']}")
    res.append(check("3 formulas recomputed independently from raw CSV (S_T, G_B, n)", not mism and done,
                     {"mismatch": mism, "recomputed": done}))
    # 4. CSV / Markdown / LaTeX agree (same numbers, display rounding only)
    incons = []
    for p in (pkg / "tables").glob("*.csv"):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        md = p.with_suffix(".md").read_text(encoding="utf-8")
        tex = p.with_suffix(".tex").read_text(encoding="utf-8")
        for r in rows[:200]:
            for k, v in r.items():
                if v is None or not re.fullmatch(r"-?\d+(\.\d*)?([eE][-+]?\d+)?", v.strip()):
                    continue
                if re.fullmatch(r"-?\d+", v.strip()):  # integers are written as integers by the generator
                    s = v.strip()
                else:
                    x = float(v)
                    s = f"{x:.4g}" if abs(x) < 1e6 else f"{x:.0f}"
                if s not in md or s not in tex.replace(r"\%", "%"):
                    incons.append(f"{p.name}:{k}={s}")
    res.append(check("4 CSV, Markdown and LaTeX tables carry the same numbers", not incons, {"inconsistent": incons[:30]}))
    # 5. missing is never zero
    zero_missing = []
    for ds, d in analysis["datasets"].items():
        for t in d["totals"]:
            if t["n_ok"] == 0 and t["total_bytes"] not in (None, "None"):
                zero_missing.append(f"{ds}:{t['method']}")
    t04 = pkg / "tables" / "T04_scale.csv"
    if t04.exists():
        for r in csv.DictReader(open(t04, encoding="utf-8")):
            if "SKIPPED" in r["status"] and r["bytes"] not in ("", None):
                zero_missing.append(f"T04:{r['sample_id']}")
    res.append(check("5 missing / skipped / unsupported cells carry no value (never 0)", not zero_missing,
                     {"violations": zero_missing}))
    # 6. lossless and byte equality with E0
    raw = json.loads((pkg / "raw_results" / "raw_audit.json").read_text(encoding="utf-8"))
    loss = {k: v["lossless_false_rows"] for k, v in raw["runs"].items()}
    be = {ds: x.get("byte_equal_pct") for ds, x in analysis["c1_verdicts"].items() if x.get("n")}
    res.append(check("6 original/decoded mismatch = 0 on every SUCCESS row; Eθ bytes == E0 bytes",
                     all(v == 0 for v in loss.values()) and all(v == 100.0 for v in be.values()),
                     {"lossless_false_rows": loss, "byte_equal_pct": be}))
    # 7. captions and texts: scope words
    bad_words = []
    for p in list((pkg / "methods").glob("*.md")) + [pkg / "YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md"]:
        t = p.read_text(encoding="utf-8").lower()
        for w in ("5 independent volumes", "five independent volumes", "5 independent acquisitions",
                  "10/10 achieved", "q1 accepted", "new stronger compression"):
            if w in t:
                bad_words.append(f"{p.name}: '{w}'")
    res.append(check("7 captions/texts: no wrong scope ('5 independent volumes', acceptance claims)", not bad_words,
                     {"found": bad_words}))
    # 8. figures rendered (programmatic part; the visual review is recorded in checks/visual_review.json)
    figs = json.loads((pkg / "supplementary" / "figures_index.json").read_text(encoding="utf-8"))
    blank = []
    import matplotlib.image as mpimg

    for fid, r in figs.items():
        if r["status"] != "OK":
            continue
        png = pkg / f"{r['file']}.png"
        img = mpimg.imread(png)
        if img.shape[0] < 300 or img.shape[1] < 300 or float(np.std(img)) < 0.01:
            blank.append(fid)
    # the agent's visual review of the rendered PNGs is kept next to the run (staging is rebuilt on every render)
    vis = ROOT / "results" / a.run_id / "visual_review.json"
    vis_state = json.loads(vis.read_text(encoding="utf-8")) if vis.exists() else {"status": "PENDING"}
    (pkg / "checks").mkdir(exist_ok=True)
    (pkg / "checks" / "visual_review.json").write_text(json.dumps(vis_state, indent=2), encoding="utf-8")
    res.append(check("8 figures rendered, non-blank, >= 300 px; visual review recorded", not blank and
                     vis_state.get("status") == "PASS", {"blank_or_small": blank, "visual_review": vis_state},
                     severity="FAIL" if blank else "WARN"))
    # 9. render reproducibility (numbers identical across renders; timestamps ignored)
    dig = numbers_digest(pkg)
    prevp = ROOT / "results" / a.run_id / "numbers_digest.json"
    prev = json.loads(prevp.read_text(encoding="utf-8")) if prevp.exists() else None
    diff = [k for k in dig if prev and prev.get(k) not in (None, dig[k])]
    prevp.write_text(json.dumps(dig, indent=1), encoding="utf-8")
    res.append(check("9 --mode render reproduces the numbers (table/plot-data digests)", prev is None or not diff,
                     {"first_render": prev is None, "changed": diff[:20]}))
    # 10. complete vs partial status separated
    st = json.loads((ROOT / "results" / a.run_id / "q1_state.json").read_text(encoding="utf-8"))
    runs_ok = all(r.get("status") == "DONE" for r in st["runs"].values())
    readme = (pkg / "README_UZ.md").read_text(encoding="utf-8")
    status_ok = ("COMPLETE" in readme) == runs_ok or ("PARTIAL" in readme and not runs_ok)
    res.append(check("10 technical status (COMPLETE/PARTIAL) matches the runs", status_ok,
                     {"runs_all_done": runs_ok, "readme_says_complete": "COMPLETE" in readme}))
    fails = [r for r in res if r["result"] == "FAIL"]
    warns = [r for r in res if r["result"] == "WARN"]
    verdict = "FAIL" if fails else ("PASS_WITH_WARNINGS" if warns else "PASS")
    (pkg / "checks").mkdir(exist_ok=True)
    (pkg / "checks" / "validation_report.json").write_text(json.dumps({"run_id": a.run_id, "at": now(),
                                                                        "verdict": verdict, "checks": res}, indent=2,
                                                                       default=str), encoding="utf-8")
    L = [f"# Validator: {verdict}", "", f"Run `{a.run_id}`, {now()}.", "", "| tekshiruv | natija |", "|---|---|"]
    L += [f"| {r['check']} | {r['result']} |" for r in res]
    L += ["", "Tafsilot: `checks/validation_report.json`."]
    (pkg / "checks" / "VALIDATION_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    rep = pkg / "YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md"
    txt = rep.read_text(encoding="utf-8").split("\n## 10. Validator")[0]
    rep.write_text(txt.rstrip("\n") + f"\n\n## 10. Validator\n\nNatija: **{verdict}** (`checks/VALIDATION_UZ.md`).\n",
                   encoding="utf-8")
    print("\n".join(L))
    return 1 if fails else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # console/redirect encodings on Windows (cp1252)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
