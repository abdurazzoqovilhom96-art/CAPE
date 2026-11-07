"""Validator of the B protocol package (docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md, section 14).

    python tools/validate_cg_package.py --package "maqola uchun 2" --run-dir results/<run_id>

Writes <package>/checks/validation_report.json. Recomputes the projection ratios from the raw files with its own code
(not by importing tools/cg_article.py)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

MATH = ["problem_definition.md", "dominance_completeness_theorem.md", "pricing_exactness.md", "integer_certificate.md",
        "column_generation_scope.md", "complexity.md"]
METH = ["METHODS_EN.md", "RESULTS_EN.md", "LIMITATIONS_EN.md", "CONTRIBUTION_AND_PRIOR_ART_EN.md",
        "MANUSCRIPT_DRAFT_EN.md", "CAPTIONS_EN.md", "references.bib"]
TABLES = ["T01_development_crops", "T02_methods", "T03_prechecks", "T04_counts_per_sample", "T05_projection_and_gate",
          "T06_certificate", "T07_failures_and_exclusions"]
FIGS = ["F01_dominance_example", "F02_algorithm_flow", "F03_memory_breakdown", "F04_time_breakdown",
        "F05_cg_convergence", "F06_projected_ratios"]
SOLVER = ("greedy_ns", "dual_ns", "pass1_ns", "dp_ns", "local_ns", "pass2_ns", "rc_ns", "repair_ns", "regime_gate_ns")


def chk(name, ok, detail, sev="FAIL"):
    return {"check": name, "result": "PASS" if ok else sev, "detail": detail}


def nonempty(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 0


def recompute(pkg: Path) -> dict:
    """Independent projection: per sample R_M = max(peak_runs, ws_runs + S)/peak, R_T = T_proj/T."""
    nat = pd.read_csv(pkg / "raw_results" / "native_results.csv", low_memory=False)
    nat = nat[nat.status == "OK"]
    out = {}
    for p in sorted((pkg / "raw_results").glob("prototype_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("status") != "SUCCESS":
            continue
        sid = r["sample_id"]
        g = nat[nat.sample_id == sid]
        eb = g[(g.method_id == "cape_q1_fast_m0") & (g.panel == "B")]
        em = g[(g.method_id == "cape_q1_fast_m0") & (g.panel == "MEM")]
        pb = g[(g.method_id == "cape_q1_fast_profile_m0") & (g.panel == "B")]
        pm = g[(g.method_id == "cape_q1_fast_profile_m0") & (g.panel == "MEM")]
        if not (len(eb) and len(em) and len(pb) and len(pm)):
            continue
        xs = [json.loads(s) for s in pb.extra_json]
        med = lambda k: float(st.median([x.get(k, 0.0) or 0.0 for x in xs]))  # noqa: E731
        mm = json.loads(pm.extra_json.iloc[0])
        peak = float(json.loads(em.extra_json.iloc[0])["peak_after_encode"])
        S = 12 * r["cg"]["columns"] + 4 * r["cg"]["nnz"] + 8 * r["instance"]["n_cc"] + r["cg"]["lp_rss_bytes"]
        pp = max(mm["mem_peak_runs"], mm["mem_ws_runs"] + S)
        T = float(eb.encode_ns.median())
        Tcr = med("candidate_ns") + med("reduction_ns") + med("component_ns") + sum(med(k) for k in SOLVER)
        Tp = T - Tcr + r["cg"]["pricing_passes"] * med("candidate_ns") + r["cg"]["lp_time_s"] * 1e9 + med("greedy_ns")
        out[sid] = {"R_M": pp / peak, "R_T": Tp / T}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args(argv)
    pkg, rd = Path(a.package), Path(a.run_dir)
    res = []
    gate = json.loads((pkg / "audit" / "gate.json").read_text(encoding="utf-8")) if (pkg / "audit" / "gate.json").exists() \
        else {}
    term = gate.get("terminal")
    man = list(csv.DictReader(open(pkg / "artifact_manifest.csv", encoding="utf-8"))) if (
        pkg / "artifact_manifest.csv").exists() else []
    notrun = {r["path"].split("/")[-1] for r in man if r["status"] != "OK" and r["reason"]}
    # 1 files
    miss = [f"mathematics/{x}" for x in MATH if not nonempty(pkg / "mathematics" / x)]
    miss += [f"methods/{x}" for x in METH if not nonempty(pkg / "methods" / x)]
    miss += [f"tables/{t}.{e}" for t in TABLES for e in ("csv", "md", "tex") if not nonempty(pkg / "tables" / f"{t}.{e}")]
    for fg in FIGS:
        if not all(nonempty(pkg / "figures" / f"{fg}.{e}") for e in ("png", "svg", "pdf")) and fg.split("_")[0] not in \
                notrun:
            miss.append(f"figures/{fg}")
    miss += [x for x in ("README_UZ.md", "YAKUNIY_HISOBOT_UZ.md", "claims_ledger.csv", "artifact_manifest.csv",
                         "reproducibility/REPRODUCE.md", "reproducibility/PROTOCOL_UZ.md") if not nonempty(pkg / x)]
    res.append(chk("1 required files exist and are non-empty (NOT_RUN figures carry a reason)", not miss,
                   {"missing": miss}))
    # 2 claims trace
    bad = []
    for r in csv.DictReader(open(pkg / "claims_ledger.csv", encoding="utf-8")):
        for ev in r["evidence"].split(";"):
            ev = ev.strip()
            if "/" in ev and not (pkg / ev).exists():
                bad.append(f"{r['id']}: {ev}")
    res.append(chk("2 every claim traces to a file in the package", not bad, {"untraced": bad}))
    # 3 recompute
    mism = []
    try:
        rc = recompute(pkg)
        t5 = list(csv.DictReader(open(pkg / "tables" / "T05_projection_and_gate.csv", encoding="utf-8")))
        for row in t5:
            sid = row["sample_id"]
            if sid in rc:
                for k, col in (("R_M", "R_M proj"), ("R_T", "R_T proj")):
                    if abs(float(row[col]) - rc[sid][k]) > 1e-3 * max(1.0, abs(rc[sid][k])):
                        mism.append(f"{sid} {k}: table {row[col]} vs recomputed {rc[sid][k]:.5f}")
            if sid == "geo-mean" and rc and row["R_M proj"]:
                g_m = float(np.exp(np.mean(np.log([v["R_M"] for v in rc.values()]))))
                if abs(float(row["R_M proj"]) - g_m) > 1e-3:
                    mism.append(f"geo-mean R_M: {row['R_M proj']} vs {g_m:.5f}")
        done = len(rc)
    except Exception as exc:  # noqa: BLE001
        mism.append(f"recompute failed: {exc}")
        done = 0
    res.append(chk("3 projection ratios recomputed independently from raw_results", not mism,
                   {"recomputed_samples": done, "mismatch": mism[:20]}))
    # 4 CSV / MD / TeX
    incons = []
    for t in TABLES:
        try:
            rows = list(csv.reader(open(pkg / "tables" / f"{t}.csv", encoding="utf-8")))[1:]
            md = (pkg / "tables" / f"{t}.md").read_text(encoding="utf-8")
            tex = (pkg / "tables" / f"{t}.tex").read_text(encoding="utf-8")
            n_md = sum(1 for ln in md.splitlines() if ln.startswith("| ") and not ln.startswith("| " + "sample_id")) - 1
            if tex.count(r"\\") - 1 != len(rows):
                incons.append(f"{t}: tex rows {tex.count(chr(92) * 2) - 1} vs csv {len(rows)}")
            for r in rows:
                if "| " + " | ".join(r) + " |" not in md:
                    incons.append(f"{t}: csv row not in md: {r[:3]}")
                    break
            _ = n_md
        except Exception as exc:  # noqa: BLE001
            incons.append(f"{t}: {exc}")
    res.append(chk("4 CSV, Markdown and LaTeX tables carry the same rows", not incons, {"inconsistent": incons}))
    # 5 missing is never 0
    zero = []
    t4 = list(csv.DictReader(open(pkg / "tables" / "T04_counts_per_sample.csv", encoding="utf-8")))
    for r in t4:
        if r["status"] != "SUCCESS" and any(v.strip() == "0" for k, v in r.items() if k not in ("sample_id", "status")):
            zero.append(r["sample_id"])
    res.append(chk("5 non-success samples carry no numbers (never 0)", not zero, {"zero_filled": zero}))
    # 6 lossless + certificates
    nat = pd.read_csv(pkg / "raw_results" / "native_results.csv", low_memory=False)
    e = nat[(nat.method_id == "cape_q1_fast_m0") & (nat.status == "OK")]
    loss_ok = bool(len(e)) and e.lossless.astype(str).str.lower().eq("true").all()
    t6 = [r for r in csv.DictReader(open(pkg / "tables" / "T06_certificate.csv", encoding="utf-8"))
          if r["sample_id"] != "pooled"]
    cert_ok = all(r["certificate feasible"] == "True" for r in t6)
    res.append(chk("6 every Eθ stream decoded voxel-equal; every prototype certificate integer-feasible",
                   loss_ok and cert_ok, {"eθ_rows": int(len(e)), "lossless_all": loss_ok, "certificates": len(t6),
                                         "all_feasible": cert_ok}))
    # 7 scope words / negative draft label
    words = []
    for p in list((pkg / "methods").glob("*.md")) + [pkg / "YAKUNIY_HISOBOT_UZ.md"]:
        t = p.read_text(encoding="utf-8").lower()
        for w in ("native cg implemented", "q1 accepted", "new algorithm is proposed", "10/10 achieved",
                  "guaranteed faster"):
            if w in t:
                words.append(f"{p.name}: {w}")
    draft = (pkg / "methods" / "MANUSCRIPT_DRAFT_EN.md").read_text(encoding="utf-8")
    if term in ("STOPPED_GATE_FAILED", "STOPPED_GATE_INCONCLUSIVE", "BLOCKED_PRECHECK") and \
            not draft.startswith("# NEGATIVE-RESULT DRAFT"):
        words.append("manuscript not labelled as a negative-result draft")
    res.append(chk("7 no over-claiming; negative results labelled", not words, {"found": words}))
    # 8 figures + visual review
    from PIL import Image
    blank = []
    for fg in FIGS:
        p = pkg / "figures" / f"{fg}.png"
        if p.exists():
            im = Image.open(p).convert("L")
            arr = np.asarray(im)
            if min(im.size) < 300 or arr.std() < 2:
                blank.append(fg)
    vr = rd / "visual_review.json"
    rev = json.loads(vr.read_text(encoding="utf-8")) if vr.exists() else None
    if rev:
        (pkg / "checks").mkdir(exist_ok=True)
        shutil.copy(vr, pkg / "checks" / "visual_review.json")
    ok8 = not blank and rev is not None and rev.get("status") == "PASS"
    res.append(chk("8 figures rendered, non-blank, >= 300 px; visual review recorded", ok8,
                   {"blank": blank, "visual_review": None if rev is None else rev.get("status")},
                   "WARN" if rev is None and not blank else "FAIL"))
    # 9 render reproducibility
    dg = {}
    for p in sorted(list((pkg / "tables").glob("*.csv")) + list((pkg / "plot_data").glob("*.csv"))):
        dg[p.relative_to(pkg).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    prev_p = rd / "numbers_digest.json"
    prev = json.loads(prev_p.read_text(encoding="utf-8")) if prev_p.exists() else None
    diff = sorted(k for k in set(dg) | set(prev or {}) if (prev or {}).get(k) != dg.get(k)) if prev else []
    prev_p.write_text(json.dumps(dg, indent=1), encoding="utf-8")
    res.append(chk("9 --mode render reproduces the numbers (table / plot-data digests)", prev is None or not diff,
                   {"previous": prev is not None, "changed": diff}))
    # 10 status consistency
    readme = (pkg / "README_UZ.md").read_text(encoding="utf-8")
    state = json.loads((pkg / "audit" / "research_state.json").read_text(encoding="utf-8")) if (
        pkg / "audit" / "research_state.json").exists() else {}
    ok10 = term is not None and f"**{term}**" in readme and state.get("terminal") in (term, None)
    res.append(chk("10 terminal status consistent (gate.json, README, run state)", ok10,
                   {"gate": term, "state": state.get("terminal")}))
    verdict = "FAIL" if any(r["result"] == "FAIL" for r in res) else ("WARN" if any(r["result"] == "WARN" for r in res)
                                                                       else "PASS")
    rep = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "verdict": verdict,
           "summary": f"{sum(r['result'] == 'PASS' for r in res)}/{len(res)} PASS", "checks": res}
    (pkg / "checks").mkdir(exist_ok=True)
    (pkg / "checks" / "validation_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for r in res:
        print(r["result"], r["check"])
    print("verdict:", verdict)
    return 0 if verdict != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
