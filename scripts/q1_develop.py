"""CAPE Q1 development: run the pre-registered panels and apply the acceptance rule (configs/q1_development.yaml).

    python scripts/q1_develop.py --panels     # core + scale panels (run_all.py --stage development, resumable)
    python scripts/q1_develop.py --select     # acceptance rule -> analysis/q1_select/{selected.json, SELECT_Q1_UZ.md}

Development data only (CREMI + Crackle samples + scaling_v21). State: analysis/q1_state.json; logs: analysis/q1_logs/.
Exit codes: 0 done, 1 a panel/selection failed, 3 correctness failure (a variant changed bytes vs E0).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from q1_common import (atomic_json, ci_fmt, dev_cluster, fmt, load_cells, merged, paired,  # noqa: E402
                       write_csv)

PY = ROOT / ".venv" / "Scripts" / "python.exe"
STATE = ROOT / "analysis" / "q1_state.json"
LOGS = ROOT / "analysis" / "q1_logs"
OUT = ROOT / "analysis" / "q1_select"
PROTOCOL = ROOT / "configs" / "q1_development.yaml"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"created_at": now(), "panels": {}}


def run_panel(name: str, spec: dict, st: dict) -> dict:
    prev = st["panels"].get(name, {})
    if prev.get("status") == "DONE":
        return prev
    LOGS.mkdir(parents=True, exist_ok=True)
    st["panels"][name] = dict(prev, status="RUNNING", started_at=now())
    atomic_json(STATE, st)
    cmd = [PY, ROOT / "run_all.py", "--stage", "development", "--config", spec["config"], "--manifest",
           spec["manifest"], "--resume"]
    with open(LOGS / f"dev_{name}.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {now()} {' '.join(map(str, cmd))}\n")
        fh.flush()
        code = subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    latest = (ROOT / "results" / "LATEST_RUN.txt").read_text(encoding="utf-8").strip()
    rd = Path(latest) if Path(latest).is_absolute() else ROOT / latest
    status = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")).get("status")
    res = {"status": "DONE" if code == 0 and status == "COMPLETE" else "FAILED", "exit_code": code,
           "run_dir": rd.relative_to(ROOT).as_posix(), "run_status": status,
           "started_at": st["panels"][name]["started_at"], "ended_at": now()}
    st["panels"][name] = res
    atomic_json(STATE, st)
    return res


def panels() -> int:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    st = load_state()
    rc = 0
    for name, spec in proto["panels"].items():
        res = run_panel(name, spec, st)
        print(f"panel {name}: {res['status']} {res.get('run_dir')}")
        rc |= res["status"] != "DONE"
    return rc


def select() -> int:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    st = load_state()
    if any(st["panels"].get(p, {}).get("status") != "DONE" for p in proto["panels"]):
        print("BLOCKED: development panels not DONE")
        return 1
    runs = {p: st["panels"][p]["run_dir"] for p in proto["panels"]}
    cells = merged(*(load_cells(r) for r in runs.values()))
    e0 = proto["reference_E0"]["method"]
    g = proto["gates"]
    variants = sorted({m for (_, m) in cells} - {e0})
    # ---- correctness: every variant equals E0 byte for byte on every sample (size and sha256)
    corr, mismatches = [], 0
    for m in variants:
        p = paired(cells, m, e0, n_boot=0)
        bad = [x["sample_id"] for x in p.get("per_sample", []) if x["new_bytes"] != x["base_bytes"]
               or x["same_sha256"] is False]
        non_ok = {s: dict(c["statuses"]) for (s, k), c in cells.items() if k == m and c["n_ok"] < sum(c["statuses"].values())}
        lossless_bad = [s for (s, k), c in cells.items() if k == m and any(v is not None and not v for v in c["lossless"])]
        mismatches += len(bad) + len(p["excluded"]) + len(lossless_bad)
        corr.append({"method": m, "n": p["n"], "byte_or_sha_mismatch": len(bad), "excluded": len(p["excluded"]),
                     "non_ok_cells": len(non_ok), "lossless_false": len(lossless_bad),
                     "mismatch_samples": bad[:20]})
    # ---- module decisions on the leave-one-out contrast (all bits vs all bits minus the module)
    allm = proto["all_bits"]
    tol = float(g["module"]["and_other_axis_not_worse_than"])
    decisions, rows = {}, []
    for mod, spec in proto["modules"].items():
        loo = paired(cells, allm, spec["leave_one_out"], cluster=dev_cluster)
        single = paired(cells, spec["single"], "cape_q1_base_m0", cluster=dev_cluster)
        speed_ok = bool(loo["S_T_ci"] and loo["S_T_ci"][0] > 1.0)
        mem_ok = bool(loo["R_M_ci"] and loo["R_M_ci"][1] < 1.0)
        other_ok = loo["S_T"] >= 1 - tol and loo["R_M"] <= 1 + tol
        accepted = (speed_ok or mem_ok) and other_ok and mismatches == 0
        reason = []
        reason.append(f"speed CI lower {fmt(loo['S_T_ci'][0] if loo['S_T_ci'] else None)} > 1: {speed_ok}")
        reason.append(f"memory CI upper {fmt(loo['R_M_ci'][1] if loo['R_M_ci'] else None)} < 1: {mem_ok}")
        reason.append(f"other axis within {tol:.0%} (S_T {fmt(loo['S_T'])} >= {1 - tol:.2f}, R_M {fmt(loo['R_M'])} <= "
                      f"{1 + tol:.2f}): {other_ok}")
        decisions[mod] = {"bit": spec["bit"], "accepted": accepted, "reason": reason,
                          "loo": {k: loo.get(k) for k in ("n", "n_clusters", "n_mem", "S_T", "S_T_ci", "R_M", "R_M_ci",
                                                          "time_reduction_pct", "slower_gt10pct", "peak_gt10pct",
                                                          "worst_speedup", "worst_mem_ratio", "bytes_identical")},
                          "single": {k: single.get(k) for k in ("n", "S_T", "S_T_ci", "R_M", "R_M_ci")}}
        rows.append({"module": mod, "name": spec["name"], "decision": "ACCEPT" if accepted else "REJECT",
                     "loo_S_T": loo["S_T"], "loo_S_T_ci": loo["S_T_ci"], "loo_R_M": loo["R_M"],
                     "loo_R_M_ci": loo["R_M_ci"], "single_S_T": single.get("S_T"), "single_R_M": single.get("R_M"),
                     "slower_gt10pct": len(loo["slower_gt10pct"]), "peak_gt10pct": len(loo["peak_gt10pct"])})
    mask = 575 + sum(d["bit"] for d in decisions.values() if d["accepted"])
    summary = {}
    for new, base in (("cape_q1_all_m0", e0), ("cape_q1_base_m0", e0), ("cape_q1_all_m0", "cape_q1_base_m0")):
        p = paired(cells, new, base, cluster=dev_cluster)
        summary[f"{new}__vs__{base}"] = {k: p.get(k) for k in ("n", "n_clusters", "S_T", "S_T_ci", "R_M", "R_M_ci",
                                                               "time_reduction_pct", "bytes_identical", "slower_gt10pct",
                                                               "peak_gt10pct", "worst_speedup", "worst_mem_ratio")}
    sel = {"written_at": now(), "protocol": "configs/q1_development.yaml", "runs": runs,
           "correctness": {"mismatches": mismatches, "by_method": corr},
           "modules": decisions, "selected_impl_mask": mask if mismatches == 0 else 575,
           "selected_bits": [m for m, d in decisions.items() if d["accepted"]],
           "summary": summary, "note": "development data only (seen); the final experiment re-measures everything"}
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT / "selected.json", sel)
    write_csv(OUT / "modules.csv", rows)
    write_csv(OUT / "correctness.csv", corr)
    L = ["# CAPE Q1: development selection (avtomatik, `scripts/q1_develop.py`)", "",
         f"Yaratilgan: {sel['written_at']}. Faqat development ma'lumoti (CREMI + Crackle namunalari + scaling_v21).",
         f"Run'lar: {', '.join(f'{k} `{v}`' for k, v in runs.items())}.", "",
         "## To'g'rilik (E0 = muzlatilgan v3 bilan bayt va sha256)", "",
         "| method | n | bayt/sha farqi | chiqarilgan | OK emas | lossless=False |", "|---|---|---|---|---|---|"]
    for c in corr:
        L.append(f"| {c['method']} | {c['n']} | {c['byte_or_sha_mismatch']} | {c['excluded']} | {c['non_ok_cells']} | "
                 f"{c['lossless_false']} |")
    L += ["", "## Modul qarorlari (leave-one-out: barcha bitlar vs bitta modulsiz)", "",
          "| modul | qaror | S_T | 95% CI | R_M | 95% CI | yakka bit S_T | yakka bit R_M |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['module']} | **{r['decision']}** | {fmt(r['loo_S_T'])} | {ci_fmt(r['loo_S_T_ci'])} | "
                 f"{fmt(r['loo_R_M'])} | {ci_fmt(r['loo_R_M_ci'])} | {fmt(r['single_S_T'])} | {fmt(r['single_R_M'])} |")
    L += ["", f"Tanlangan impl_mask: **{sel['selected_impl_mask']}** ({', '.join(sel['selected_bits']) or 'hech biri'}).",
          "", "## Umumiy (development)", ""]
    for k, v in summary.items():
        L.append(f"- `{k}`: n={v['n']}, S_T {fmt(v['S_T'])} {ci_fmt(v['S_T_ci'])} (vaqt kamayishi "
                 f"{fmt(v['time_reduction_pct'], 2)}%), R_M {fmt(v['R_M'])} {ci_fmt(v['R_M_ci'])}, baytlar bir xil: "
                 f"{v['bytes_identical']}; >10% sekin: {len(v['slower_gt10pct'] or [])}; >10% peak: "
                 f"{len(v['peak_gt10pct'] or [])}")
    (OUT / "SELECT_Q1_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 3 if mismatches else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panels", action="store_true")
    ap.add_argument("--select", action="store_true")
    a = ap.parse_args(argv)
    if not (a.panels or a.select):
        ap.error("choose --panels and/or --select")
    rc = 0
    if a.panels:
        rc = panels()
        if rc:
            return rc
    if a.select:
        rc = select()
    return rc


if __name__ == "__main__":
    sys.exit(main())
