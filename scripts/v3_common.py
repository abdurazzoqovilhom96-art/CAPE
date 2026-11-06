"""Shared helpers of the CAPE v3 analysis scripts (pilot_select_v3.py, report_v3.py, package_v3.py).

Everything is computed from results/<run>/05_raw_metrics/run.sqlite. Sizes are deterministic per (sample, method):
repeats only describe timing (a sample whose bytes differ between repeats is flagged, never averaged).
T_i = median encode time over the repeats of sample i; G_B = 1 - sum B_new / sum B_base;
S_T = exp(mean_i log(T_base / T_new)); bpv = 8 B / V. Paired cluster bootstrap over the given cluster key.
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
SEED = 20261106
N_BOOT = 10_000


def mkey(method: str, wrapper: str) -> str:
    return method if wrapper in (None, "none") else f"{method}+{wrapper}"


def run_path(run: str | Path) -> Path:
    p = Path(run)
    return p if p.is_absolute() else ROOT / p


def load_cells(run: str | Path) -> dict:
    """(sample_id, method_key) -> cell. method_key = method or method+wrapper."""
    rd = run_path(run)
    db = rd / "05_raw_metrics" / "run.sqlite"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cells: dict = {}
    peaks = defaultdict(list)
    for r in con.execute("select * from measurements"):
        r = dict(r)
        if r["panel"] == "MEM":
            if r["status"] == "OK" and r["peak_rss_bytes"]:
                peaks[(r["sample_id"], r["method_id"])].append(r["peak_rss_bytes"])
            continue
        k = (r["sample_id"], mkey(r["method_id"], r["wrapper"]))
        c = cells.get(k)
        if c is None:
            c = cells[k] = {"sample_id": r["sample_id"], "method": r["method_id"], "wrapper": r["wrapper"],
                            "family_id": r["family_id"], "source_id": r["source_id"],
                            "macroblock_id": r["macroblock_id"], "input_bytes": r["input_bytes"],
                            "shape": r["canonical_shape"], "statuses": Counter(), "bytes": set(), "enc": [],
                            "dec": [], "label_bytes": None, "ub": None, "lb": None, "cert_valid": [],
                            "extra": None, "reasons": []}
        c["statuses"][r["status"]] += 1
        if r["status"] != "OK":
            c["reasons"].append(r["reason"])
            continue
        c["bytes"].add(r["total_bytes"])
        c["enc"].append(r["encode_ns"])
        c["dec"].append(r["decode_ns"])
        c["label_bytes"] = r["label_bytes"]
        c["ub"], c["lb"] = r["ub_bytes"], r["lb_bytes"]
        if r["certificate_valid"] is not None:
            c["cert_valid"].append(bool(r["certificate_valid"]))
        if c["extra"] is None and r["extra_json"]:
            c["extra"] = json.loads(r["extra_json"])
    con.close()
    for (s, m), c in cells.items():
        c["n_ok"] = len(c["enc"])
        c["bytes_vary"] = len(c["bytes"]) > 1
        c["total_bytes"] = next(iter(c["bytes"])) if len(c["bytes"]) == 1 else None
        c["enc_med"] = st.median(c["enc"]) if c["enc"] else None
        c["dec_med"] = st.median(c["dec"]) if c["dec"] else None
        pk = peaks.get((s, c["method"])) if c["wrapper"] in (None, "none") else None
        c["peak"] = st.median(pk) if pk else None
        try:
            z, y, x = json.loads(c["shape"]) if isinstance(c["shape"], str) else c["shape"]
            c["voxels"] = int(z) * int(y) * int(x)
            c["Z"] = int(z)
        except (TypeError, ValueError):
            c["voxels"], c["Z"] = None, None
        c["extra"] = c["extra"] or {}
    return cells


def status_table(cells: dict) -> list[dict]:
    by = defaultdict(Counter)
    for (_, m), c in cells.items():
        by[m].update(c["statuses"])
    return [{"method": m, **dict(v)} for m, v in sorted(by.items())]


def _geo(x: np.ndarray) -> float:
    return float(np.exp(np.mean(np.log(x)))) if len(x) else float("nan")


def paired(cells: dict, new: str, base: str, samples=None, cluster=None, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Paired effect of `new` against `base` over the samples both measured (status OK, deterministic bytes)."""
    cluster = cluster or (lambda c: c["macroblock_id"] or c["sample_id"])
    ss = sorted({s for (s, m) in cells if m == new} & {s for (s, m) in cells if m == base})
    if samples is not None:
        allowed = set(samples)
        ss = [s for s in ss if s in allowed]
    pairs, excluded = [], []
    for s in ss:
        a, b = cells[(s, new)], cells[(s, base)]
        if a["n_ok"] == 0 or b["n_ok"] == 0 or a["total_bytes"] is None or b["total_bytes"] is None:
            excluded.append({"sample_id": s, "new_status": dict(a["statuses"]), "base_status": dict(b["statuses"]),
                             "bytes_vary": a["bytes_vary"] or b["bytes_vary"]})
            continue
        pairs.append((a, b))
    out = {"new": new, "base": base, "n": len(pairs), "excluded": excluded}
    if not pairs:
        return out
    bn = np.array([a["total_bytes"] for a, _ in pairs], float)
    bb = np.array([b["total_bytes"] for _, b in pairs], float)
    tn = np.array([a["enc_med"] for a, _ in pairs], float)
    tb = np.array([b["enc_med"] for _, b in pairs], float)
    dn = np.array([a["dec_med"] for a, _ in pairs], float)
    db = np.array([b["dec_med"] for _, b in pairs], float)
    cl = [cluster(a) for a, _ in pairs]
    uniq = sorted(set(cl))
    groups = [np.array([i for i, k in enumerate(cl) if k == u]) for u in uniq]

    def pt(ix):
        return (1 - bn[ix].sum() / bb[ix].sum(), _geo(tb[ix] / tn[ix]), _geo(db[ix] / dn[ix]))

    g, s_t, s_d = pt(np.arange(len(pairs)))
    ci = {"G_B": None, "S_T": None, "S_D": None}
    if len(uniq) >= 2 and n_boot > 0:
        rng = np.random.default_rng(seed)
        bs = np.empty((n_boot, 3))
        for i in range(n_boot):
            pick = rng.integers(0, len(uniq), size=len(uniq))
            bs[i] = pt(np.concatenate([groups[k] for k in pick]))
        for j, key in enumerate(("G_B", "S_T", "S_D")):
            ci[key] = [float(np.percentile(bs[:, j], 2.5)), float(np.percentile(bs[:, j], 97.5))]
    # source-weighted: every source counts once
    by_src = defaultdict(list)
    for i, (a, _) in enumerate(pairs):
        by_src[a["source_id"] or "unknown"].append(i)
    src = {k: {"n": len(v), "G_B": float(1 - bn[v].sum() / bb[v].sum()), "S_T": _geo(tb[v] / tn[v])}
           for k, v in sorted(by_src.items())}
    pk = [(a["peak"], b["peak"]) for a, b in pairs if a["peak"] and b["peak"]]
    per = []
    for a, b in pairs:
        per.append({"sample_id": a["sample_id"], "source_id": a["source_id"], "macroblock_id": a["macroblock_id"],
                    "voxels": a["voxels"], "new_bytes": a["total_bytes"], "base_bytes": b["total_bytes"],
                    "gain_pct": 100 * (1 - a["total_bytes"] / b["total_bytes"]),
                    "new_enc_ms": a["enc_med"] / 1e6, "base_enc_ms": b["enc_med"] / 1e6,
                    "speedup": b["enc_med"] / a["enc_med"], "new_dec_ms": a["dec_med"] / 1e6,
                    "base_dec_ms": b["dec_med"] / 1e6, "new_peak_mib": (a["peak"] or 0) / 2**20 or None,
                    "base_peak_mib": (b["peak"] or 0) / 2**20 or None, "repeats_new": a["n_ok"],
                    "repeats_base": b["n_ok"]})
    out.update({
        "n_clusters": len(uniq), "bytes_new": float(bn.sum()), "bytes_base": float(bb.sum()),
        "G_B": float(g), "G_B_pct": 100 * float(g), "G_B_ci": ci["G_B"], "S_T": s_t, "S_T_ci": ci["S_T"],
        "S_D": s_d, "S_D_ci": ci["S_D"], "smaller": int((bn < bb).sum()), "equal": int((bn == bb).sum()),
        "larger": int((bn > bb).sum()), "bytes_identical": bool((bn == bb).all()),
        "time_ratio_total": float(tn.sum() / tb.sum()),
        "slowdowns_gt10pct": [p["sample_id"] for p in per if p["speedup"] < 1 / 1.10],
        "source_weighted": {"S_T": _geo(np.array([v["S_T"] for v in src.values()])),
                            "G_B": float(np.mean([v["G_B"] for v in src.values()])), "sources": src},
        "peak_ratio_median": float(st.median(a / b for a, b in pk)) if pk else None, "n_peak": len(pk),
        "per_sample": per, "bpv_new": float(8 * bn.sum() / sum(a["voxels"] or 0 for a, _ in pairs))
        if all(a["voxels"] for a, _ in pairs) else None,
    })
    return out


def bootstrap_p(cells: dict, new: str, base: str, metric: str, null: float, samples=None, cluster=None,
                n_boot: int = N_BOOT, seed: int = SEED) -> float | None:
    """Two-sided percentile-bootstrap p-value of H0: metric == null (metric 'S_T' or 'G_B'), by test inversion:
    p = 2 * min(share of resamples <= null, share >= null), floored at 1/(n_boot+1)."""
    cluster = cluster or (lambda c: c["macroblock_id"] or c["sample_id"])
    ss = sorted({s for (s, m) in cells if m == new} & {s for (s, m) in cells if m == base})
    if samples is not None:
        ss = [s for s in ss if s in set(samples)]
    pairs = [(cells[(s, new)], cells[(s, base)]) for s in ss
             if cells[(s, new)]["n_ok"] and cells[(s, base)]["n_ok"] and cells[(s, new)]["total_bytes"] is not None
             and cells[(s, base)]["total_bytes"] is not None]
    if not pairs:
        return None
    cl = [cluster(a) for a, _ in pairs]
    uniq = sorted(set(cl))
    if len(uniq) < 2:
        return None
    groups = [np.array([i for i, k in enumerate(cl) if k == u]) for u in uniq]
    if metric == "S_T":
        x = np.log(np.array([b["enc_med"] / a["enc_med"] for a, b in pairs]))
        stat = lambda ix: float(np.exp(x[ix].mean()))  # noqa: E731
    else:
        bn = np.array([a["total_bytes"] for a, _ in pairs], float)
        bb = np.array([b["total_bytes"] for _, b in pairs], float)
        stat = lambda ix: float(1 - bn[ix].sum() / bb[ix].sum())  # noqa: E731
    rng = np.random.default_rng(seed)
    vals = np.array([stat(np.concatenate([groups[k] for k in rng.integers(0, len(uniq), size=len(uniq))]))
                     for _ in range(n_boot)])
    lo = (vals <= null).mean()
    hi = (vals >= null).mean()
    return float(max(min(1.0, 2 * min(lo, hi)), 1.0 / (n_boot + 1)))


def holm(pvalues: dict) -> dict:
    items = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m = len(items)
    adj, running = {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def fmt(x, nd=3, pct=False):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "NA"
    return f"{x:.{nd}f}{'%' if pct else ''}"


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
