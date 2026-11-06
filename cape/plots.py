"""Figures F01-F11 (spec section 28): every empirical figure is drawn from validated records,
its data is written to 10_plot_data/<id>.csv first, and a provenance sidecar records the
measurement ids, data hash and the number of plotted series/points (checked by the verifier).
F01 is a diagram drawn from DIAGRAM_SPEC (not empirical). A figure that cannot be drawn
honestly is NOT_ENOUGH_DATA / NOT_APPLICABLE; a render error is REPORT_FAILED."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from cape import metrics  # noqa: E402
from cape.result_store import atomic_write_text, now_iso  # noqa: E402

DIAGRAM_SPEC = [
    ("Canonical\nZYX labels", False), ("Upstream CC labeling\n+ crack codes\n(bridge)", False),
    ("Column runs ->\ndepth-bounded\nwindows", True), ("Safe reductions\n(equal / subset /\nsingleton)", True),
    ("Independent\ncomponents\n(CC-pin graph)", True), ("Greedy UB +\ninteger dual LB", True),
    ("Exact bitmask DP\n(n <= 20) or\nlocal search", True), ("Background (8)\n+ width\ncompaction", True),
    ("Explicit-record\nserializer ->\nCrackle v1 stream", True), ("Original decoder\nlossless check", False),
]
PALETTE = plt.get_cmap("tab10").colors
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "<", ">", "*"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "figure.dpi": 100})
_STYLE: dict = {}


def set_methods(names) -> None:
    """Deterministic, unique (colour, marker) per method key for every figure of a run."""
    _STYLE.clear()
    for i, n in enumerate(sorted(set(names))):
        _STYLE[n] = (PALETTE[i % len(PALETTE)], MARKERS[(i // len(PALETTE)) % len(MARKERS)])


def _color(name: str):
    return _STYLE.get(name, (PALETTE[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(PALETTE)], "o"))[0]


def _marker(name: str) -> str:
    return _STYLE.get(name, (None, "o"))[1]


def _write_data(ctx, fid: str, rows: list[dict]) -> tuple[Path, str]:
    p = ctx.run_dir / "10_plot_data" / f"{fid}.csv"
    buf = io.StringIO()
    fields = list(rows[0]) if rows else ["empty"]
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r[k]) for k in fields})
    atomic_write_text(p, buf.getvalue())
    return p, hashlib.sha256(buf.getvalue().encode()).hexdigest()


def _save(ctx, fig, fid: str, prov: dict, preliminary: bool) -> list[str]:
    out_dir = ctx.run_dir / "11_figures" / ("preliminary" if preliminary else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{fid}_PRELIMINARY" if preliminary else fid
    files = []
    for ext, kw in (("pdf", {}), ("png", {"dpi": 300})):
        p = out_dir / f"{stem}.{ext}"
        tmp = out_dir / f"{stem}.tmp.{ext}"
        fig.savefig(tmp, bbox_inches="tight", metadata={"Title": stem} if ext == "pdf" else None, **kw)
        tmp.replace(p)
        files.append(str(p))
    plt.close(fig)
    prov = dict(prov, figure=fid, preliminary=preliminary, created_at=now_iso(), files=[Path(f).name for f in files],
                source_hash=ctx.hashes.get("source"))
    atomic_write_text(out_dir / f"{stem}.provenance.json", json.dumps(prov, indent=2, default=str))
    return files


def _real_cells(cells: dict, panel: str = "B") -> list[dict]:
    return [c for (s, k, p), c in cells.items() if p == panel and not c["is_synthetic"] and c.get("total_bytes")]


# ----------------------------------------------------------------------- figures
def f01(ctx, cells, prelim):
    """Snake layout: row 1 left->right, row 2 right->left, one short vertical hand-over arrow."""
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    ax.axis("off")
    cols, w, h, gx, gy = 5, 1.62, 1.0, 0.42, 0.75
    pos = []
    for i in range(len(DIAGRAM_SPEC)):
        r, c = divmod(i, cols)
        c = c if r == 0 else cols - 1 - c
        pos.append((c * (w + gx), -r * (h + gy)))
    for (label, contrib), (x, y) in zip(DIAGRAM_SPEC, pos):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    facecolor="#dbe9f6" if contrib else "#eeeeee",
                                    edgecolor="#1f4e79" if contrib else "#777777", lw=1.3 if contrib else 0.8))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=6.4, wrap=True)
    for i in range(len(pos) - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            start = (x1 + w, y1 + h / 2) if x2 > x1 else (x1, y1 + h / 2)
            end = (x2, y2 + h / 2) if x2 > x1 else (x2 + w, y2 + h / 2)
        else:
            start, end = (x1 + w / 2, y1), (x2 + w / 2, y2 + h)
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "-|>", "lw": 0.9, "color": "#333333"})
    ax.set_xlim(-0.15, cols * (w + gx))
    ax.set_ylim(-(h + gy) - 0.15, h + 0.35)
    ax.set_title("CAPE-Pins pipeline (blue: algorithmic contribution; grey: reused upstream code / verification)",
                 fontsize=9)
    spec_hash = hashlib.sha256(json.dumps(DIAGRAM_SPEC).encode()).hexdigest()
    rows = [{"step": i + 1, "label": lab.replace("\n", " "), "cape_contribution": contrib} for i, (lab, contrib)
            in enumerate(DIAGRAM_SPEC)]
    p, h = _write_data(ctx, "F01_algorithm", rows)
    return _save(ctx, fig, "F01_algorithm", {"empirical": False, "diagram_spec_sha256": spec_hash, "data_csv": p.name,
                                              "data_sha256": h, "n_series": 1, "n_points": len(rows),
                                              "measurement_ids": []}, prelim), len(rows)


def _bpv_vs_time(ctx, cells, prelim, fid, tkey, label):
    data = _real_cells(cells)
    if len(data) < 2:
        return None, "NOT_ENOUGH_DATA: fewer than two real OK cells"
    rows = [{"sample_id": c["sample_id"], "method": c["method"], "wrapper": c["wrapper"], "bpv": c["bpv"],
             "time_ms": c[tkey] / 1e6, "measurement_ids": json.dumps(c["measurement_ids"])} for c in data]
    p, h = _write_data(ctx, fid, rows)
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.6), sharey=False)
    series = 0
    handles: dict = {}
    for ax, wrapped in zip(axes, (False, True)):
        sub = [r for r in rows if (r["wrapper"] != "none") == wrapped]
        for m in sorted({r["method"] for r in sub}):
            pts = [r for r in sub if r["method"] == m]
            handles[m] = ax.scatter([r["time_ms"] for r in pts], [r["bpv"] for r in pts], s=18, color=_color(m),
                                    marker=_marker(m), label=m, edgecolors="black", linewidths=0.3)
            series += 1
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(f"{label} time per volume (ms, median, log)")
        ax.set_ylabel("bits per voxel (all bytes, log)")
        ax.set_title("external zstd-wrapped" if wrapped else "native streams")
        ax.grid(alpha=0.3)
    fig.subplots_adjust(wspace=0.32, bottom=0.36)
    fig.legend([handles[k] for k in sorted(handles)], sorted(handles), loc="lower center", ncol=4, fontsize=6,
               frameon=False)
    return _save(ctx, fig, fid, {"empirical": True, "data_csv": p.name, "data_sha256": h, "n_series": series,
                                 "n_points": len(rows),
                                 "measurement_ids": sorted({i for c in data for i in c["measurement_ids"]})}, prelim), len(rows)


def f02(ctx, cells, prelim):
    return _bpv_vs_time(ctx, cells, prelim, "F02_bpv_vs_encode", "encode_ns_median", "encode")


def f03(ctx, cells, prelim):
    return _bpv_vs_time(ctx, cells, prelim, "F03_bpv_vs_decode", "decode_ns_median", "CPU decode")


def f04(ctx, cells, prelim):
    new, base = ctx.cfg["primary"]["new"], ctx.cfg["primary"]["baseline"]
    rows = []
    for c in _real_cells(cells):
        if c["method"] != new:
            continue
        b = cells.get((c["sample_id"], base, "B"))
        if b and b.get("total_bytes"):
            rows.append({"sample_id": c["sample_id"], "gain_percent": 100 * (1 - c["total_bytes"] / b["total_bytes"]),
                         "new_bytes": c["total_bytes"], "base_bytes": b["total_bytes"],
                         "measurement_ids": json.dumps(c["measurement_ids"] + b["measurement_ids"])})
    if not rows:
        return None, "NOT_ENOUGH_DATA: primary pair not measured on real samples"
    p, h = _write_data(ctx, "F04_per_dataset_gain", rows)
    fig, ax = plt.subplots(figsize=(max(4.0, 0.5 * len(rows) + 2), 3.4))
    g = [r["gain_percent"] for r in rows]
    ax.bar(range(len(rows)), g, color=["#2e7d32" if v > 0 else "#c62828" if v < 0 else "#9e9e9e" for v in g])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(rows)), [r["sample_id"][-28:] for r in rows], rotation=60, ha="right", fontsize=6)
    ax.set_ylabel(f"size gain of {new} vs {base} (%)")
    ax.set_title("Per-sample gain (negative = larger; every sample shown)")
    ax.grid(axis="y", alpha=0.3)
    return _save(ctx, fig, "F04_per_dataset_gain", {"empirical": True, "data_csv": p.name, "data_sha256": h,
                                                     "n_series": 1, "n_points": len(rows),
                                                     "measurement_ids": []}, prelim), len(rows)


def _cape_cells(cells):
    return [c for (s, k, p), c in cells.items() if k == "cape_m0" and p == "B" and not c["is_synthetic"]
            and c.get("n_ok") and c.get("extra", {}).get("component_size_hist_cc")]


def f05(ctx, cells, prelim):
    data = _cape_cells(cells)
    if not data:
        return None, "NOT_ENOUGH_DATA: no real cape_m0 pins-format diagnostics"
    agg_cc = np.zeros(33)
    agg_n = np.zeros(33)
    for c in data:
        agg_cc += np.array(c["extra"]["component_size_hist_cc"], dtype=float)
        agg_n += np.array(c["extra"]["component_size_hist_count"], dtype=float)
    rows = [{"size_bucket_log2": b, "size_min": 2 ** b, "components": int(agg_n[b]), "cc_weight": int(agg_cc[b]),
             "cc_fraction": float(agg_cc[b] / agg_cc.sum())} for b in range(33) if agg_n[b]]
    p, h = _write_data(ctx, "F05_component_distribution", rows)
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.bar([r["size_bucket_log2"] for r in rows], [r["cc_fraction"] for r in rows], color="#1f77b4")
    ax.axvline(np.log2(20) + 0.5, color="#c62828", ls="--", lw=1, label="exact DP limit (20 CCs)")
    ax.set_xlabel("component size bucket (log2 #CCs)")
    ax.set_ylabel("fraction of CCs (CC-weighted)")
    ax.set_title(f"Component sizes after reductions ({len(data)} real samples)")
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)
    return _save(ctx, fig, "F05_component_distribution", {"empirical": True, "data_csv": p.name, "data_sha256": h,
                                                           "n_series": 1, "n_points": len(rows),
                                                           "measurement_ids": sorted({i for c in data for i in c["measurement_ids"]})},
                 prelim), len(rows)


def f06(ctx, cells, prelim):
    data = _cape_cells(cells)
    if not data:
        return None, "NOT_ENOUGH_DATA: no real cape_m0 pins-format diagnostics"
    rows = [{"sample_id": c["sample_id"], "before": c.get("candidate_count_before"),
             "after_singleton": c["extra"].get("candidates_after_singleton"),
             "after_equal": c["extra"].get("candidates_after_equal"), "after_subset": c.get("candidate_count_after"),
             "reduction_ms": (c["extra"].get("reduction_ns") or 0) / 1e6} for c in data]
    p, h = _write_data(ctx, "F06_reduction_time_memory", rows)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.2))
    stages = ["before", "after_singleton", "after_equal", "after_subset"]
    for r in rows:
        a1.plot(range(4), [r[s] for s in stages], marker="o", lw=1, label=r["sample_id"][-24:])
    a1.set_xticks(range(4), ["all", "-singleton", "-equal", "-subset"])
    a1.set_yscale("log")
    a1.set_ylabel("candidate pins")
    a1.set_title("Candidates after each safe reduction")
    a1.legend(fontsize=5)
    a2.bar(range(len(rows)), [r["reduction_ms"] for r in rows], color="#6a3d9a")
    a2.set_xticks(range(len(rows)), [r["sample_id"][-16:] for r in rows], rotation=60, ha="right", fontsize=6)
    a2.set_ylabel("reduction time (ms)")
    a2.set_title("Reduction cost")
    return _save(ctx, fig, "F06_reduction_time_memory", {"empirical": True, "data_csv": p.name, "data_sha256": h,
                                                          "n_series": len(rows) + 1, "n_points": 5 * len(rows),
                                                          "measurement_ids": []}, prelim), 5 * len(rows)


def f07(ctx, cells, prelim):
    data = [c for c in _cape_cells(cells) if c.get("ub_bytes") is not None]
    if not data:
        return None, "NOT_ENOUGH_DATA: no certificates on real samples"
    rows = [{"sample_id": c["sample_id"], "encode_ms": c["encode_ns_median"] / 1e6,
             "label_gap_bytes": c["extra"].get("label_bytes", 0) - c["extra"].get("label_lb_bytes", 0),
             "label_ub": c["extra"].get("label_bytes"), "label_lb": c["extra"].get("label_lb_bytes"),
             "exact_cc_fraction": c.get("exact_cc_fraction")} for c in data]
    p, h = _write_data(ctx, "F07_gap_vs_cost", rows)
    fig, ax = plt.subplots(figsize=(5, 3.2))
    sc = ax.scatter([r["encode_ms"] for r in rows], [r["label_gap_bytes"] for r in rows],
                    c=[r["exact_cc_fraction"] or 0 for r in rows], cmap="viridis", vmin=0, vmax=1, edgecolors="black",
                    linewidths=0.3)
    fig.colorbar(sc, ax=ax, label="exactly solved CC fraction")
    ax.set_xlabel("CAPE encode time (ms)")
    ax.set_ylabel("certified label gap UB-LB (bytes)")
    ax.set_title("Certificate gap vs cost (restricted model scope)")
    ax.grid(alpha=0.3)
    return _save(ctx, fig, "F07_gap_vs_cost", {"empirical": True, "data_csv": p.name, "data_sha256": h, "n_series": 1,
                                                "n_points": len(rows),
                                                "measurement_ids": sorted({i for c in data for i in c["measurement_ids"]})},
                 prelim), len(rows)


def f08(ctx, cells, prelim):
    from cape.reporting import ABLATIONS

    rows = []
    for (s, k, p), c in cells.items():
        if p != "A" or k not in ABLATIONS or c["is_synthetic"] or not c.get("total_bytes"):
            continue
        core = cells.get((s, "cape_core", "A"))
        if core and core.get("total_bytes"):
            rows.append({"sample_id": s, "variant": k, "relative_bytes": c["total_bytes"] / core["total_bytes"],
                         "relative_encode_time": c["encode_ns_median"] / core["encode_ns_median"]})
    if not rows:
        return None, "NOT_ENOUGH_DATA: no ablation measurements on real samples"
    p, h = _write_data(ctx, "F08_ablation", rows)
    variants = sorted({r["variant"] for r in rows})
    means = [np.mean([r["relative_bytes"] for r in rows if r["variant"] == v]) for v in variants]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.bar(range(len(variants)), [100 * (m - 1) for m in means], color=[_color(v) for v in variants])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(variants)), variants, rotation=50, ha="right", fontsize=6.5)
    ax.set_ylabel("bytes vs full CAPE (% , + = worse)")
    ax.set_title("Panel A ablations (forced pins format)")
    ax.grid(axis="y", alpha=0.3)
    return _save(ctx, fig, "F08_ablation", {"empirical": True, "data_csv": p.name, "data_sha256": h, "n_series": 1,
                                             "n_points": len(variants), "measurement_ids": []}, prelim), len(variants)


def f09(ctx, cells, prelim):
    data = _real_cells(cells)
    sizes = {c["voxels"] for c in data}
    if len(sizes) < 2:
        return None, "NOT_ENOUGH_DATA: scaling needs at least two distinct real volume sizes"
    keep = {ctx.cfg["primary"]["new"], ctx.cfg["primary"]["baseline"], "crackle_flat_m0", "zstd3"}
    rows = [{"method": c["method"], "voxels": c["voxels"], "encode_ms": c["encode_ns_median"] / 1e6,
             "sample_id": c["sample_id"]} for c in data if c["method"] in keep]
    p, h = _write_data(ctx, "F09_scaling", rows)
    fig, ax = plt.subplots(figsize=(5, 3.2))
    series = 0
    for m in sorted({r["method"] for r in rows}):
        pts = sorted((r["voxels"], r["encode_ms"]) for r in rows if r["method"] == m)
        ax.plot([a for a, _ in pts], [b for _, b in pts], marker="o", lw=1, label=m, color=_color(m))
        series += 1
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("voxels")
    ax.set_ylabel("encode ms")
    ax.legend(fontsize=6)
    ax.grid(alpha=0.3)
    return _save(ctx, fig, "F09_scaling", {"empirical": True, "data_csv": p.name, "data_sha256": h, "n_series": series,
                                            "n_points": len(rows), "measurement_ids": []}, prelim), len(rows)


def f10(ctx, cells, prelim):
    data = [c for c in _real_cells(cells) if c.get("label_bytes") is not None and c["wrapper"] == "none"]
    if not data:
        return None, "NOT_ENOUGH_DATA: no real Crackle-family streams"
    rows = [{"sample_id": c["sample_id"], "method": c["method"], "label_bytes": c["label_bytes"],
             "other_bytes": c["total_bytes"] - c["label_bytes"], "total_bytes": c["total_bytes"]} for c in data]
    p, h = _write_data(ctx, "F10_byte_breakdown", rows)
    methods = sorted({r["method"] for r in rows})
    lab = [np.mean([r["label_bytes"] / r["total_bytes"] for r in rows if r["method"] == m]) for m in methods]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.bar(range(len(methods)), lab, color="#1f77b4", label="label section")
    ax.bar(range(len(methods)), [1 - v for v in lab], bottom=lab, color="#bbbbbb", label="crack codes + headers + CRC")
    ax.set_xticks(range(len(methods)), methods, rotation=50, ha="right", fontsize=6.5)
    ax.set_ylabel("fraction of stream bytes (mean over samples)")
    ax.legend(fontsize=7)
    return _save(ctx, fig, "F10_byte_breakdown", {"empirical": True, "data_csv": p.name, "data_sha256": h,
                                                   "n_series": 2, "n_points": 2 * len(methods),
                                                   "measurement_ids": []}, prelim), 2 * len(methods)


FIGURES = {"F01_algorithm": f01, "F02_bpv_vs_encode": f02, "F03_bpv_vs_decode": f03, "F04_per_dataset_gain": f04,
           "F05_component_distribution": f05, "F06_reduction_time_memory": f06, "F07_gap_vs_cost": f07,
           "F08_ablation": f08, "F09_scaling": f09, "F10_byte_breakdown": f10}


def render_all(ctx, preliminary: bool = False, only: list[str] | None = None) -> dict:
    rows = ctx.store.measurements()
    cells = metrics.aggregate_cells(rows)
    set_methods(k for (_s, k, _p) in cells)
    out = {}
    fail_hook = os.environ.get("CAPE_TEST_FAIL_FIGURE")  # acceptance test T10 hook
    for fid, fn in FIGURES.items():
        if only and fid not in only:
            continue
        try:
            if fail_hook == fid:
                raise RuntimeError(f"injected renderer failure (CAPE_TEST_FAIL_FIGURE={fid})")
            files, info = fn(ctx, cells, preliminary)
            if files is None:
                out[fid] = {"status": "NOT_ENOUGH_DATA", "reason": info, "files": []}
                _write_data(ctx, fid, [])  # explicit empty data table, never a fake figure
            else:
                out[fid] = {"status": "COMPLETE", "reason": None, "files": files, "points": info}
        except Exception as exc:  # noqa: BLE001 - one figure failing must not stop the others
            plt.close("all")
            out[fid] = {"status": "REPORT_FAILED", "reason": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc()[-1500:], "files": []}
    if not only:
        out["F11_roi_latency"] = {"status": "NOT_APPLICABLE", "files": [],
                                  "reason": "ROI panel C disabled (second stage, configs/roi.yaml)"
                                  if not ctx.cfg["roi"]["enabled"] else "ROI measurements not implemented in this run"}
    if not preliminary:
        atomic_write_text(ctx.run_dir / "11_figures" / "figures_status.json", json.dumps(out, indent=2, default=str))
    return out
