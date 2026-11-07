"""Shared helpers of the CAPE Q1 analysis (scripts/q1_develop.py, tools/q1_article.py, tools/q1_pipeline.py).

Everything comes from results/<run>/05_raw_metrics/run.sqlite (never from earlier reports).
Definitions (Q1 task v3, section 9), per paired cell i (same sample, both methods OK):
  T_i      median of encode_ns over the repeats;   s_i = T_base,i / T_new,i (> 1: new faster)
  S_T      exp(mean_i log s_i)                       time reduction = 100 (1 - 1/S_T) %
  M_i      encode-inclusive peak = peak_after_encode of the fresh-process memory row (Windows PeakWorkingSetSize read
           after encode and before decode; includes the Python process and the input array)
  R_M      exp(mean_i log(M_new,i / M_base,i))       (< 1: new uses less)
  G_B      100 (sum B_base - sum B_new) / sum B_base (pooled bytes; > 0: new smaller)
  bpv      8 B / V
Repeats describe timing only; sizes are deterministic (a cell whose bytes vary between repeats is flagged).
Bootstrap: paired cluster bootstrap over the given cluster key (percentile 95% CI).
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261107
N_BOOT = 10_000


def mkey(method: str, wrapper: str | None) -> str:
    return method if wrapper in (None, "none") else f"{method}+{wrapper}"


def run_path(run) -> Path:
    p = Path(run)
    return p if p.is_absolute() else ROOT / p


def load_cells(run) -> dict:
    """(sample_id, method_key) -> cell, with the encode-inclusive peak from the separate memory rows."""
    db = run_path(run) / "05_raw_metrics" / "run.sqlite"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cells: dict = {}
    mem = defaultdict(list)
    for r in con.execute("select * from measurements"):
        r = dict(r)
        if r["panel"] == "MEM":
            ex = json.loads(r["extra_json"]) if r["extra_json"] else {}
            mem[(r["sample_id"], r["method_id"])].append({
                "status": r["status"], "reason": r["reason"], "mode": r["rss_measurement_mode"],
                "peak_e2e": r["peak_rss_bytes"], "peak_enc": ex.get("peak_after_encode"),
                "peak_before": ex.get("peak_before_encode"), "measurement_id": r["measurement_id"]})
            continue
        k = (r["sample_id"], mkey(r["method_id"], r["wrapper"]))
        c = cells.get(k)
        if c is None:
            c = cells[k] = {"sample_id": r["sample_id"], "method": r["method_id"], "wrapper": r["wrapper"] or "none",
                            "key": k[1], "family_id": r["family_id"], "source_id": r["source_id"],
                            "macroblock_id": r["macroblock_id"], "input_bytes": r["input_bytes"],
                            "dtype": r["original_dtype"], "shape": r["canonical_shape"], "statuses": Counter(),
                            "bytes": set(), "sha": set(), "label_bytes": None, "enc": [], "dec": [], "ub": None,
                            "lb": None, "cert_valid": [], "cert_scope": None, "lossless": [], "extra": None,
                            "reasons": [], "row_ids": [], "label_format": None}
        c["statuses"][r["status"]] += 1
        c["row_ids"].append(r["measurement_id"])
        if r["status"] != "OK":
            if r["reason"]:
                c["reasons"].append(r["reason"])
            continue
        c["bytes"].add(r["total_bytes"])
        if r["bitstream_sha256"]:
            c["sha"].add(r["bitstream_sha256"])
        c["enc"].append(r["encode_ns"])
        c["dec"].append(r["decode_ns"])
        c["lossless"].append(r["lossless"])
        c["label_bytes"] = r["label_bytes"]
        c["label_format"] = r["label_format_actual"]
        c["ub"], c["lb"] = r["ub_bytes"], r["lb_bytes"]
        c["cert_scope"] = r["certificate_scope"] or c["cert_scope"]
        if r["certificate_valid"] is not None:
            c["cert_valid"].append(bool(r["certificate_valid"]))
        if c["extra"] is None and r["extra_json"]:
            c["extra"] = json.loads(r["extra_json"])
    con.close()
    for (s, m), c in cells.items():
        c["n_ok"] = len(c["enc"])
        c["bytes_vary"] = len(c["bytes"]) > 1
        c["total_bytes"] = next(iter(c["bytes"])) if len(c["bytes"]) == 1 else None
        c["sha256"] = next(iter(c["sha"])) if len(c["sha"]) == 1 else None
        c["enc_med"] = st.median(c["enc"]) if c["enc"] else None
        c["dec_med"] = st.median(c["dec"]) if c["dec"] else None
        mm = mem.get((s, c["method"])) if c["wrapper"] == "none" else None
        ok = [x for x in (mm or []) if x["status"] == "OK" and x["peak_enc"]]
        c["mem_rows"] = mm or []
        c["peak_enc"] = st.median(x["peak_enc"] for x in ok) if ok else None
        c["peak_before"] = st.median(x["peak_before"] for x in ok if x["peak_before"]) if ok else None
        c["peak_e2e"] = st.median(x["peak_e2e"] for x in ok if x["peak_e2e"]) if ok else None
        try:
            z, y, x = json.loads(c["shape"]) if isinstance(c["shape"], str) else c["shape"]
            c["voxels"], c["Z"] = int(z) * int(y) * int(x), int(z)
        except (TypeError, ValueError):
            c["voxels"], c["Z"] = None, None
        c["extra"] = c["extra"] or {}
    return cells


def merged(*dicts) -> dict:
    out = {}
    for d in dicts:
        for k, v in d.items():
            if k in out:
                raise ValueError(f"cell {k} appears in two runs")
            out[k] = v
    return out


def dev_cluster(c: dict) -> str:
    """Nested scaling crops overlap, so they cluster by source; every other crop clusters by its macroblock."""
    if str(c["sample_id"]).startswith("scale_"):
        return "scale:" + str(c["source_id"])
    return str(c["macroblock_id"] or c["sample_id"])


def macroblock_cluster(c: dict) -> str:
    return str(c["macroblock_id"] or c["sample_id"])


def _geo(x) -> float:
    x = np.asarray(x, float)
    return float(np.exp(np.mean(np.log(x)))) if len(x) else float("nan")


def paired(cells: dict, new: str, base: str, samples=None, cluster=macroblock_cluster, n_boot: int = N_BOOT,
           seed: int = SEED) -> dict:
    ss = sorted({s for (s, m) in cells if m == new} & {s for (s, m) in cells if m == base})
    if samples is not None:
        allowed = set(samples)
        ss = [s for s in ss if s in allowed]
    pairs, excluded = [], []
    for s in ss:
        a, b = cells[(s, new)], cells[(s, base)]
        if a["n_ok"] == 0 or b["n_ok"] == 0 or a["total_bytes"] is None or b["total_bytes"] is None:
            excluded.append({"sample_id": s, "new_status": dict(a["statuses"]), "base_status": dict(b["statuses"]),
                             "new_reason": (a["reasons"] or [None])[0], "base_reason": (b["reasons"] or [None])[0]})
            continue
        pairs.append((a, b))
    out = {"new": new, "base": base, "n": len(pairs), "n_excluded": len(excluded), "excluded": excluded}
    if not pairs:
        return out
    bn = np.array([a["total_bytes"] for a, _ in pairs], float)
    bb = np.array([b["total_bytes"] for _, b in pairs], float)
    tn = np.array([a["enc_med"] for a, _ in pairs], float)
    tb = np.array([b["enc_med"] for _, b in pairs], float)
    dn = np.array([a["dec_med"] for a, _ in pairs], float)
    db = np.array([b["dec_med"] for _, b in pairs], float)
    has_m = np.array([bool(a["peak_enc"] and b["peak_enc"]) for a, b in pairs])
    mn = np.array([a["peak_enc"] or np.nan for a, _ in pairs], float)
    mb = np.array([b["peak_enc"] or np.nan for _, b in pairs], float)
    cl = [cluster(a) for a, _ in pairs]
    uniq = sorted(set(cl))
    groups = [np.array([i for i, k in enumerate(cl) if k == u]) for u in uniq]

    def stat(ix):
        mi = ix[has_m[ix]]
        return (100 * (bb[ix].sum() - bn[ix].sum()) / bb[ix].sum(), _geo(tb[ix] / tn[ix]), _geo(db[ix] / dn[ix]),
                _geo(mn[mi] / mb[mi]) if len(mi) else float("nan"))

    g, s_t, s_d, r_m = stat(np.arange(len(pairs)))
    ci = dict.fromkeys(("G_B", "S_T", "S_D", "R_M"))
    if len(uniq) >= 2 and n_boot > 0:
        rng = np.random.default_rng(seed)
        bs = np.empty((n_boot, 4))
        for i in range(n_boot):
            bs[i] = stat(np.concatenate([groups[k] for k in rng.integers(0, len(uniq), size=len(uniq))]))
        for j, key in enumerate(("G_B", "S_T", "S_D", "R_M")):
            col = bs[:, j][~np.isnan(bs[:, j])]
            ci[key] = [float(np.percentile(col, 2.5)), float(np.percentile(col, 97.5))] if len(col) else None
    per = []
    for i, (a, b) in enumerate(pairs):
        per.append({"sample_id": a["sample_id"], "source_id": a["source_id"], "cluster": cl[i], "voxels": a["voxels"],
                    "new_bytes": int(bn[i]), "base_bytes": int(bb[i]), "same_sha256": a["sha256"] == b["sha256"]
                    if a["sha256"] and b["sha256"] else None, "gain_pct": 100 * (bb[i] - bn[i]) / bb[i],
                    "new_enc_ms": tn[i] / 1e6, "base_enc_ms": tb[i] / 1e6, "speedup": tb[i] / tn[i],
                    "new_dec_ms": dn[i] / 1e6, "base_dec_ms": db[i] / 1e6,
                    "new_peak_enc_mib": mn[i] / 2**20 if has_m[i] else None,
                    "base_peak_enc_mib": mb[i] / 2**20 if has_m[i] else None,
                    "mem_ratio": mn[i] / mb[i] if has_m[i] else None,
                    "new_rows": ";".join(map(str, a["row_ids"])), "base_rows": ";".join(map(str, b["row_ids"]))})
    worst_t = min(per, key=lambda p: p["speedup"])
    mper = [p for p in per if p["mem_ratio"]]
    worst_m = max(mper, key=lambda p: p["mem_ratio"]) if mper else None
    out.update({
        "n_clusters": len(uniq), "n_mem": int(has_m.sum()), "bytes_new": int(bn.sum()), "bytes_base": int(bb.sum()),
        "G_B_pct": float(g), "G_B_ci": ci["G_B"], "S_T": float(s_t), "S_T_ci": ci["S_T"],
        "time_reduction_pct": 100 * (1 - 1 / s_t), "S_D": float(s_d), "S_D_ci": ci["S_D"],
        "R_M": float(r_m), "R_M_ci": ci["R_M"], "time_ratio_of_totals": float(tn.sum() / tb.sum()),
        "smaller": int((bn < bb).sum()), "equal": int((bn == bb).sum()), "larger": int((bn > bb).sum()),
        "bytes_identical": bool((bn == bb).all()),
        "sha_identical": all(p["same_sha256"] for p in per) if all(p["same_sha256"] is not None for p in per) else None,
        "slower_gt10pct": [p["sample_id"] for p in per if p["speedup"] < 1 / 1.10],
        "peak_gt10pct": [p["sample_id"] for p in mper if p["mem_ratio"] > 1.10],
        "worst_speedup": {"sample_id": worst_t["sample_id"], "speedup": worst_t["speedup"]},
        "worst_mem_ratio": {"sample_id": worst_m["sample_id"], "mem_ratio": worst_m["mem_ratio"]} if worst_m else None,
        "per_sample": per,
    })
    return out


def bootstrap_p(cells: dict, new: str, base: str, metric: str, null: float = 1.0, samples=None,
                cluster=macroblock_cluster, n_boot: int = N_BOOT, seed: int = SEED) -> float | None:
    """Two-sided percentile-bootstrap p-value of H0: metric == null, metric in {S_T, R_M}, by test inversion:
    p = 2 min(P*(stat <= null), P*(stat >= null)), floored at 1/(n_boot + 1)."""
    ss = sorted({s for (s, m) in cells if m == new} & {s for (s, m) in cells if m == base})
    if samples is not None:
        ss = [s for s in ss if s in set(samples)]
    pairs = []
    for s in ss:
        a, b = cells[(s, new)], cells[(s, base)]
        if not (a["n_ok"] and b["n_ok"]):
            continue
        if metric == "S_T":
            pairs.append((a, math.log(b["enc_med"] / a["enc_med"])))
        elif a["peak_enc"] and b["peak_enc"]:
            pairs.append((a, math.log(a["peak_enc"] / b["peak_enc"])))
    if not pairs:
        return None
    cl = [cluster(a) for a, _ in pairs]
    uniq = sorted(set(cl))
    if len(uniq) < 2:
        return None
    x = np.array([v for _, v in pairs])
    groups = [np.array([i for i, k in enumerate(cl) if k == u]) for u in uniq]
    rng = np.random.default_rng(seed)
    vals = np.array([float(np.exp(x[np.concatenate([groups[k] for k in rng.integers(0, len(uniq), len(uniq))])].mean()))
                     for _ in range(n_boot)])
    lo, hi = (vals <= null).mean(), (vals >= null).mean()
    return float(max(min(1.0, 2 * min(lo, hi)), 1.0 / (n_boot + 1)))


def holm(pvalues: dict) -> dict:
    items = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m, adj, running = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def fmt(x, nd=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "NA"
    return f"{x:.{nd}f}"


def ci_fmt(ci, nd=3):
    return "NA" if not ci else f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


def write_csv(path: Path, rows: list[dict]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys or ["empty"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()})


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
