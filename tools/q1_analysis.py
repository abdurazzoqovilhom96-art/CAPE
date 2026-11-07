"""CAPE Q1 analysis layer: every number of the article package, computed once from the raw run databases of ONE
Q1 run (results/<run_id>/q1_state.json). Figures, tables and texts read only the returned dict / plot_data.

Status mapping (task v3, section 8.2): OK -> SUCCESS; UNSUPPORTED_DTYPE / UNSUPPORTED* / UNAVAILABLE* -> UNSUPPORTED;
TIMEOUT -> TIMEOUT; OOM* / MEMORY* -> OOM; SKIPPED_BUDGET -> SKIPPED (pre-registered budget rule); anything else ->
ERROR. Missing data is never zero.
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("CAPE_ROOT") or Path(__file__).resolve().parents[1])  # CAPE_ROOT: run a copy against the repo data
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from q1_common import (bootstrap_p, holm, load_cells, macroblock_cluster, paired)  # noqa: E402

E_NEW, E0, BASE, V21 = "cape_q1_fast_m0", "cape_v3frozen_fast_m0", "cape_q1_base_m0", "cape_v21_fast_m0"
DATASETS = {"j0126": "j0126 zebra finch (new external, primary)", "snemi": "SNEMI3D 32 crops (previously seen)",
            "hemibrain": "hemibrain v1.2 cutouts (new external, descriptive)",
            "scale": "SNEMI3D full volume + 4 subvolumes (seen, one acquisition)",
            "scale_stock": "SNEMI3D 4 subvolumes, stock track"}
COMPARISONS = [
    # (id, group, new, base)
    ("C1", "C1 primary", E_NEW, E0), ("BUILD", "build drift", BASE, E0), ("C1_live", "Q1 bits only", E_NEW, BASE),
    ("C2", "C2 historical", E_NEW, V21),
    ("C3_wgreedy", "C3 matched", E_NEW, "q1_fast_weighted_greedy_m0"),
    ("C3_glocal", "C3 matched", E_NEW, "q1_fast_greedy_local_m0"),
    ("C3_stock_corr", "C3 pin encoder", E_NEW, "crackle_pins_opt_corrected_m0"),
    ("C3_stock", "C3 pin encoder", E_NEW, "crackle_pins_opt_m0"),
    ("C3_stock_vendor", "C3 pin encoder", E_NEW, "crackle_vendor_pins_opt_m0"),
    ("C3_pins_fast", "C3 pin encoder", E_NEW, "crackle_pins_fast_m0"),
    ("C3_flat", "C3 simple", E_NEW, "crackle_flat_m0"),
    ("C3_compresso", "C3 other codec", E_NEW, "compresso_native"),
    ("C3_ng_u32", "C3 other codec (amended)", E_NEW, "neuroglancer_b8_u32"),
    ("C3_ng", "C3 other codec", E_NEW, "neuroglancer_b8"),
    ("C3_zstd9", "C3 generic", E_NEW, "zstd9"),
    ("A_z9_flat", "archive zstd9", f"{E_NEW}+zstd9", "crackle_flat_m0+zstd9"),
    ("A_z9_stock", "archive zstd9", f"{E_NEW}+zstd9", "crackle_pins_opt_corrected_m0+zstd9"),
    ("A_z3_flat", "archive zstd3", f"{E_NEW}+zstd3", "crackle_flat_m0+zstd3"),
    ("A_z3_stock", "archive zstd3", f"{E_NEW}+zstd3", "crackle_pins_opt_corrected_m0+zstd3"),
    ("SAFE9_stock", "SAFE zstd9", "safe_q1_fast_m0_zstd9", "safe_stock_m0_zstd9"),
    ("SAFE9_flat", "SAFE zstd9", "safe_q1_fast_m0_zstd9", "crackle_flat_m0+zstd9"),
    ("SAFE3_stock", "SAFE zstd3", "safe_q1_fast_m0_zstd3", "safe_stock_m0_zstd3"),
    ("M5_stock", "m5", "cape_q1_fast_m5", "crackle_pins_opt_corrected_m5"),
    ("M5_flat", "m5", "cape_q1_fast_m5", "crackle_flat_m5"),
    ("CERT_cost", "CERTIFIED", "cape_q1_certified_m0", E_NEW),
]


def map_status(s: str) -> str:
    if s == "OK":
        return "SUCCESS"
    u = (s or "").upper()
    if u.startswith(("UNSUPPORTED", "UNAVAILABLE")):
        return "UNSUPPORTED"
    if "TIMEOUT" in u:
        return "TIMEOUT"
    if u.startswith(("OOM", "MEMORY")) or "OOM" in u:
        return "OOM"
    if u.startswith("SKIPPED"):
        return "SKIPPED"
    return "ERROR"


def load_state(run_id: str) -> dict:
    return json.loads((ROOT / "results" / run_id / "q1_state.json").read_text(encoding="utf-8"))


def method_versions(run_dir: str) -> dict:
    con = sqlite3.connect(f"file:{ROOT / run_dir / '05_raw_metrics' / 'run.sqlite'}?mode=ro", uri=True)
    out = {}
    for m, w, v, n in con.execute("select method_id, wrapper, method_version, count(*) from measurements "
                                  "where panel!='MEM' group by method_id, wrapper, method_version"):
        out.setdefault(m, {})[w or "none"] = {"version": v, "rows": n}
    con.close()
    return out


def status_rows(run_dir: str, key: str) -> list[dict]:
    con = sqlite3.connect(f"file:{ROOT / run_dir / '05_raw_metrics' / 'run.sqlite'}?mode=ro", uri=True)
    rows = []
    for m, w, panel, s, reason, n in con.execute(
            "select method_id, wrapper, panel, status, max(reason), count(*) from measurements "
            "group by method_id, wrapper, panel, status order by method_id, wrapper"):
        rows.append({"dataset": key, "method": m, "wrapper": w or "none", "row_kind": "memory" if panel == "MEM"
                     else "timing", "raw_status": s, "status": map_status(s), "rows": n, "reason": reason})
    con.close()
    return rows


def oracle_summary(run_dir: str) -> dict | None:
    p = ROOT / run_dir / "06_solver_certificates" / "oracle_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def totals(cells: dict) -> list[dict]:
    """Per method key: totals over samples measured OK (sum of per-sample medians; never fills missing cells)."""
    by = defaultdict(list)
    for (s, k), c in cells.items():
        by[k].append(c)
    out = []
    for k, cs in sorted(by.items()):
        ok = [c for c in cs if c["n_ok"] and c["total_bytes"] is not None]
        vox = sum(c["voxels"] or 0 for c in ok)
        pk = [c["peak_enc"] for c in ok if c["peak_enc"]]
        out.append({"method": k, "n_samples": len(cs), "n_ok": len(ok),
                    "statuses": dict(sum((c["statuses"] for c in cs), Counter())),
                    "status_mapped": dict(Counter(map_status(s) for c in cs for s, n in c["statuses"].items()
                                                  for _ in range(n))),
                    "total_bytes": sum(c["total_bytes"] for c in ok) if ok else None,
                    "bpv": 8 * sum(c["total_bytes"] for c in ok) / vox if ok and vox else None,
                    "enc_ms_sum_of_medians": sum(c["enc_med"] for c in ok) / 1e6 if ok else None,
                    "dec_ms_sum_of_medians": sum(c["dec_med"] for c in ok) / 1e6 if ok else None,
                    "peak_enc_mib_median": st.median(pk) / 2**20 if pk else None,
                    "reasons": sorted({r for c in cs for r in c["reasons"]})[:3]})
    return out


def comp(cells: dict, new: str, base: str, n_boot: int) -> dict | None:
    if not any(k == new for (_, k) in cells) or not any(k == base for (_, k) in cells):
        return None
    p = paired(cells, new, base, cluster=macroblock_cluster, n_boot=n_boot)
    return p if p["n"] else dict(p, empty=True)


def phase_shares(cells: dict, method: str) -> dict:
    keys = ["scan_ns", "boundary_ns", "cc_ns", "runs_ns", "candidate_ns", "reduction_ns", "component_ns", "csr_ns",
            "pass1_ns", "pass2_ns", "serialize_ns"]
    tot = defaultdict(float)
    n = 0
    for (s, k), c in cells.items():
        if k != method or not c["extra"]:
            continue
        n += 1
        for key in keys:
            tot[key] += float(c["extra"].get(key) or 0)
        tot["encode_core_ns"] += float(c["extra"].get("encode_core_ns") or 0)
    if not n or not tot["encode_core_ns"]:
        return {}
    return {"n": n, **{k: tot[k] / tot["encode_core_ns"] for k in keys}}


def profile_phases(cells: dict) -> list[dict]:
    rows = []
    phases = ["start", "scan", "boundary", "cc", "runs", "candidates", "reduction", "components", "solve",
              "serialize"]
    for (s, k), c in sorted(cells.items()):
        ex = c.get("mem_extra")  # fresh worker process: the stage peaks are not inflated by earlier encodes
        if not k.endswith("_profile_m0") or not ex:
            continue
        r = {"sample_id": s, "method": k, "voxels": c["voxels"], "input_mib": (c["input_bytes"] or 0) / 2**20,
             "source": "fresh-process memory run"}
        for p in phases:
            v = ex.get(f"mem_peak_{p}")
            r[f"peak_{p}_mib"] = v / 2**20 if v else None
            w = ex.get(f"mem_ws_{p}")
            r[f"ws_{p}_mib"] = w / 2**20 if w else None
        rows.append(r)
    return rows


def counters(cells: dict, method: str) -> list[dict]:
    rows = []
    for (s, k), c in sorted(cells.items()):
        if k != method or not c["extra"]:
            continue
        e = c["extra"]
        rows.append({"sample_id": s, "voxels": c["voxels"], "cc_count": e.get("cc_count"),
                     "label_count": e.get("label_count"), "run_count": e.get("run_count"),
                     "runs_expected": e.get("runs_expected"), "compact_chain": e.get("compact_chain"),
                     "candidates_total": e.get("candidate_count_before"),
                     "after_adjacency": e.get("candidates_after_adjacency"),
                     "adjacent_dropped": e.get("candidates_adjacent_dropped"),
                     "after_equal": e.get("candidates_after_equal"), "after_subset": e.get("candidate_count_after"),
                     "label_format": c["label_format"]})
    return rows


def certificates(cells: dict, method: str = "cape_q1_certified_m0") -> list[dict]:
    rows = []
    for (s, k), c in sorted(cells.items()):
        if k != method or not c["n_ok"]:
            continue
        rows.append({"sample_id": s, "ub_bytes": c["ub"], "lb_bytes": c["lb"],
                     "gap_bytes": (c["ub"] - c["lb"]) if c["ub"] is not None and c["lb"] is not None else None,
                     "gap_pct": 100 * (c["ub"] - c["lb"]) / c["ub"] if c["ub"] else None,
                     "valid": all(c["cert_valid"]) if c["cert_valid"] else None, "scope": c["cert_scope"],
                     "lb_le_ub": (c["lb"] <= c["ub"]) if c["ub"] is not None and c["lb"] is not None else None})
    return rows


def byte_equality(cells: dict, new: str, base: str = E0) -> dict:
    ss = sorted({s for (s, k) in cells if k == new} & {s for (s, k) in cells if k == base})
    eq = neq = miss = 0
    bad = []
    for s in ss:
        a, b = cells[(s, new)], cells[(s, base)]
        if not (a["n_ok"] and b["n_ok"]) or a["sha256"] is None or b["sha256"] is None:
            miss += 1
            continue
        if a["sha256"] == b["sha256"] and a["total_bytes"] == b["total_bytes"]:
            eq += 1
        else:
            neq += 1
            bad.append(s)
    return {"new": new, "base": base, "samples": len(ss), "equal": eq, "different": neq, "not_comparable": miss,
            "different_samples": bad, "pct_equal": 100 * eq / max(1, eq + neq)}


def lossless(cells: dict) -> dict:
    bad = []
    n = 0
    for (s, k), c in cells.items():
        for v in c["lossless"]:
            n += 1
            if v is not None and not v:
                bad.append(f"{s}|{k}")
    return {"rows_checked": n, "failed": len(bad), "failed_cells": sorted(set(bad))[:50]}


def analyze(run_id: str, n_boot: int = 10_000) -> dict:
    state = load_state(run_id)
    runs = {k: v for k, v in state["runs"].items() if v.get("run_dir")}
    res = {"run_id": run_id, "state": {"status": state.get("status"), "created_at": state.get("created_at"),
                                       "runs": runs}, "datasets": {}, "profile": [], "status_rows": [],
           "n_boot": n_boot, "smoke": bool(state.get("smoke"))}
    cells_by = {}
    for key, info in runs.items():
        cells = load_cells(info["run_dir"])
        cells_by[key] = cells
        res["status_rows"] += status_rows(info["run_dir"], key)
        if key.startswith("profile_"):
            res["profile"] += [dict(r, dataset=key[len("profile_"):]) for r in profile_phases(cells)]
            continue
        d = {"label": DATASETS.get(key, key), "run_dir": info["run_dir"], "run_status": info.get("status"),
             "totals": totals(cells), "comparisons": {}, "versions": method_versions(info["run_dir"]),
             "oracle": oracle_summary(info["run_dir"]), "lossless": lossless(cells),
             "byte_equality": {m: byte_equality(cells, m) for m in
                               sorted({k for (_, k) in cells if k.startswith("cape_q1_") and not k.endswith(
                                   ("_m5", "_profile_m0")) and k != "cape_q1_certified_m0"})},
             "certificates": certificates(cells), "phase_shares": {m: phase_shares(cells, m) for m in (E_NEW, E0)},
             "counters": counters(cells, E_NEW), "ablation": {}}
        for cid, group, new, base in COMPARISONS:
            p = comp(cells, new, base, n_boot)
            if p is not None:
                d["comparisons"][cid] = dict(p, group=group)
        for k in sorted({k for (_, k) in cells if k.startswith("cape_q1_no")}):
            p = comp(cells, E_NEW, k, n_boot)
            if p is not None:
                d["ablation"][k] = p
        res["datasets"][key] = d
    # primary family (pre-registered): C1 speed and memory on j0126
    fam = {}
    if "j0126" in cells_by:
        c = cells_by["j0126"]
        fam["H1_C1_speed_j0126"] = bootstrap_p(c, E_NEW, E0, "S_T", 1.0, n_boot=n_boot)
        fam["H2_C1_memory_j0126"] = bootstrap_p(c, E_NEW, E0, "R_M", 1.0, n_boot=n_boot)
    res["primary_family"] = {"p": fam, "p_holm": holm(fam)}
    crit = json.loads((ROOT / "analysis" / "q1_freeze" / "success_criteria.json").read_text(encoding="utf-8"))
    res["criteria"] = crit
    tg = crit["C1"]["practical_targets"]
    verdicts = {}
    for key in ("j0126", "snemi", "hemibrain"):
        c1 = res["datasets"].get(key, {}).get("comparisons", {}).get("C1")
        if not c1 or c1.get("empty"):
            verdicts[key] = {"status": "BLOCKED", "reason": "no C1 pairs"}
            continue
        be = res["datasets"][key]["byte_equality"].get(E_NEW, {})
        verdicts[key] = {
            "n": c1["n"], "S_T": c1["S_T"], "S_T_ci": c1["S_T_ci"], "R_M": c1["R_M"], "R_M_ci": c1["R_M_ci"],
            "speed_target_reached": c1["S_T"] >= tg["speed_S_T_geomean_min"],
            "memory_target_reached": c1["R_M"] <= tg["memory_R_M_geomean_max"],
            "speed_ci_excludes_1": bool(c1["S_T_ci"] and c1["S_T_ci"][0] > 1),
            "memory_ci_excludes_1": bool(c1["R_M_ci"] and c1["R_M_ci"][1] < 1),
            "byte_equal_pct": be.get("pct_equal"), "byte_equal_all": be.get("different") == 0 and be.get("equal", 0) > 0,
            "worst_speedup": c1["worst_speedup"], "worst_mem_ratio": c1["worst_mem_ratio"]}
    res["c1_verdicts"] = verdicts
    return res


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, Counter):
        return dict(o)
    return o
