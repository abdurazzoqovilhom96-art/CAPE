"""Paired statistics (spec section 21): total-bytes ratio and dataset-wise ratios for size,
geometric-mean and median per-sample speedups for time, cluster bootstrap over macroblocks
(or sources), Wilcoxon only as a secondary test with Holm adjustment, coverage tables and
dense/sparse strata. Repeats are timing replicates, never biological samples."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

MIN_CLUSTERS_CONFIRMATORY = 5


def paired_cells(cells: dict, new: str, base: str, panel: str, real_only: bool = True) -> list[tuple[dict, dict]]:
    pairs = []
    for (sid, key, p), c in cells.items():
        if key != new or p != panel:
            continue
        b = cells.get((sid, base, panel))
        if b is None:
            continue
        if real_only and c["is_synthetic"]:
            continue
        if c.get("total_bytes") and b.get("total_bytes"):
            pairs.append((c, b))
    return sorted(pairs, key=lambda t: t[0]["sample_id"])


def _ratio_stats(pairs, cluster_key: str, n_boot: int, seed: int) -> dict:
    new_b = np.array([c["total_bytes"] for c, _ in pairs], dtype=float)
    base_b = np.array([b["total_bytes"] for _, b in pairs], dtype=float)
    t_new = np.array([c["encode_ns_median"] for c, _ in pairs], dtype=float)
    t_base = np.array([b["encode_ns_median"] for _, b in pairs], dtype=float)
    d_new = np.array([c["decode_ns_median"] for c, _ in pairs], dtype=float)
    d_base = np.array([b["decode_ns_median"] for _, b in pairs], dtype=float)
    clusters = [c.get(cluster_key) or c["sample_id"] for c, _ in pairs]
    uniq = sorted(set(clusters))
    idx_by_cluster = [np.array([i for i, k in enumerate(clusters) if k == u]) for u in uniq]

    def point(ix):
        return {"total_ratio": new_b[ix].sum() / base_b[ix].sum(),
                "geo_speedup_encode": float(np.exp(np.mean(np.log(t_base[ix] / t_new[ix])))),
                "geo_speedup_decode": float(np.exp(np.mean(np.log(d_base[ix] / d_new[ix]))))}

    all_ix = np.arange(len(pairs))
    est = point(all_ix)
    rng = np.random.default_rng(seed)
    boots = {k: [] for k in est}
    if len(uniq) >= 2:
        for _ in range(n_boot):
            pick = rng.integers(0, len(uniq), size=len(uniq))
            ix = np.concatenate([idx_by_cluster[k] for k in pick])
            p = point(ix)
            for k, v in p.items():
                boots[k].append(v)
    ci = {k: ([float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None) for k, v in boots.items()}
    log_ratio = np.log(new_b / base_b)
    out = {
        "n_samples": len(pairs), "n_clusters": len(uniq), "cluster_key": cluster_key,
        "interval_kind": ("confirmatory" if len(uniq) >= MIN_CLUSTERS_CONFIRMATORY else "exploratory (few independent clusters)"),
        "total_bytes_new": float(new_b.sum()), "total_bytes_base": float(base_b.sum()),
        "total_ratio": float(est["total_ratio"]), "total_ratio_ci95": ci["total_ratio"],
        "total_gain_percent": 100.0 * (1 - float(est["total_ratio"])),
        "median_sample_gain_percent": float(np.median(100.0 * (1 - new_b / base_b))),
        "min_sample_gain_percent": float(np.min(100.0 * (1 - new_b / base_b))),
        "max_sample_gain_percent": float(np.max(100.0 * (1 - new_b / base_b))),
        "n_regressions": int(np.sum(new_b > base_b)), "n_ties": int(np.sum(new_b == base_b)),
        "median_log_ratio": float(np.median(log_ratio)),
        "geo_speedup_encode": est["geo_speedup_encode"], "geo_speedup_encode_ci95": ci["geo_speedup_encode"],
        "median_speedup_encode": float(np.median(t_base / t_new)),
        "geo_speedup_decode": est["geo_speedup_decode"], "geo_speedup_decode_ci95": ci["geo_speedup_decode"],
        "median_speedup_decode": float(np.median(d_base / d_new)),
        "bootstrap_resamples": n_boot if len(uniq) >= 2 else 0, "bootstrap_seed": seed,
    }
    if len(pairs) >= 6 and np.any(log_ratio != 0):
        from scipy.stats import wilcoxon

        try:
            out["wilcoxon_size_p"] = float(wilcoxon(log_ratio).pvalue)
        except ValueError:
            out["wilcoxon_size_p"] = None
    else:
        out["wilcoxon_size_p"] = None
    return out


def compare(cells: dict, new: str, base: str, panel: str, cluster_key: str, n_boot: int, seed: int,
            real_only: bool = True) -> dict | None:
    pairs = paired_cells(cells, new, base, panel, real_only)
    if not pairs:
        return None
    res = _ratio_stats(pairs, cluster_key, n_boot, seed)
    res.update(new=new, base=base, panel=panel, real_only=real_only)
    by_family = defaultdict(list)
    for c, b in pairs:
        by_family[c.get("family_id") or "unknown"].append((c, b))
    res["by_family"] = {f: {"n": len(ps), "total_ratio": sum(c["total_bytes"] for c, _ in ps) /
                            sum(b["total_bytes"] for _, b in ps)} for f, ps in sorted(by_family.items())}
    res["per_sample"] = [{"sample_id": c["sample_id"], "family_id": c.get("family_id"),
                          "macroblock_id": c.get("macroblock_id"), "new_bytes": c["total_bytes"],
                          "base_bytes": b["total_bytes"], "gain_percent": 100.0 * (1 - c["total_bytes"] / b["total_bytes"]),
                          "label_new": c.get("label_bytes"), "label_base": b.get("label_bytes"),
                          "encode_speedup": b["encode_ns_median"] / c["encode_ns_median"],
                          "decode_speedup": b["decode_ns_median"] / c["decode_ns_median"],
                          "label_format_new": c.get("label_format_actual"),
                          "label_format_base": b.get("label_format_actual")} for c, b in pairs]
    return res


def holm(pvalues: dict) -> dict:
    items = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m = len(items)
    adj, running = {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def coverage(rows: list[dict], tasks: list[dict]) -> list[dict]:
    from cape.metrics import mkey

    planned = defaultdict(int)
    for t in tasks:
        planned[(t["method_id"] if t["wrapper"] == "none" else f"{t['method_id']}+{t['wrapper']}", t["panel"])] += 1
    by = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by[(mkey(r), r["panel"])][r["status"]] += 1
    out = []
    for key in sorted(set(planned) | set(by)):
        st = by.get(key, {})
        committed = sum(st.values())
        out.append({"method": key[0], "panel": key[1], "planned": planned.get(key, 0), "committed": committed,
                    "ok": st.get("OK", 0), "pending": planned.get(key, 0) - committed,
                    **{f"n_{s}": st.get(s, 0) for s in ("FAILED_LOSSLESS", "FAILED_BUILD", "UNAVAILABLE",
                                                        "UNSUPPORTED_DTYPE", "OOM", "TIMEOUT", "NOT_APPLICABLE",
                                                        "INTERRUPTED", "BLOCKED_DATA")}})
    return out


def stratum(sample_stats: dict) -> str:
    """dense: no label covers half of the voxels; sparse: one dominant (background-like) label."""
    return "sparse" if sample_stats.get("max_label_fraction", 0.0) >= 0.5 else "dense"


def safe_float(v):
    return None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
