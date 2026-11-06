"""AGGREGATED and report writing (spec sections 21, 28, 31, 35-37).

Everything is regenerated from the committed SQLite records: missing numbers are reported as
missing with a reason, failures and regressions stay visible, synthetic rows are kept apart
from real results, and every table/figure lists the measurement ids it was built from."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cape import metrics, statistics
from cape.provenance import ROOT
from cape.result_store import atomic_write_text, now_iso
from cape.tables import write_table

CONFIRMATORY_PAIRS = [
    ("cape_m5", "crackle_pins_opt_m5", "B"),
    ("cape_m0+zstd3", "crackle_pins_opt_m0+zstd3", "B"),
    ("cape_m0+zstd9", "crackle_pins_opt_m0+zstd9", "B"),
    ("cape_m0", "crackle_vendor_pins_opt_m0", "B"),
    ("cape_core", "stock_cover", "A"),
    ("cape_core", "weighted_greedy", "A"),
    ("cape_core", "greedy_local", "A"),
]
STAGE_PROFILE_FIELDS = [
    "encode_core_ns", "scan_ns", "boundary_ns", "cc_ns", "transpose_ns", "runs_ns", "candidate_ns",
    "reduction_singleton_ns", "reduction_equal_hash_ns", "reduction_equal_sort_ns", "reduction_subset_incidence_ns",
    "reduction_subset_scan_ns", "component_ns", "greedy_ns", "dual_ns", "dp_ns", "local_ns", "serialize_ns",
    "stock_selection_ns", "flat_ns",
    # v2.1 timing of the SAFE / refine wrappers (Python side, behaviour unchanged)
    "safe_native_ns", "safe_zstd_ns", "refine_native_ns", "refine_flat_zstd_ns", "refine_ns", "refine_setup_ns",
    "refine_J0_zstd_ns", "refine_eval_serialize_ns", "refine_eval_zstd_ns", "refine_evals",
]
ABLATIONS = ["cape_no_dedup", "cape_no_dominance", "cape_no_exact", "cape_no_local", "cape_no_dual_gate",
             "cape_stock_background", "cape_fixed_depth_width", "cape_maximal_runs_only", "weighted_greedy",
             "greedy_local", "stock_cover"]


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else (json.dumps(r[k]) if isinstance(r.get(k), (list, dict)) else r[k]))
                    for k in fields})
    atomic_write_text(path, buf.getvalue())


def _sample_stats(ctx) -> dict:
    from cape.dataset_manifest import resolve_path
    from cape.io import load_canonical

    out = {}
    for r in ctx.rows:
        arr = load_canonical(resolve_path(r["path"]))
        _vals, counts = np.unique(arr, return_counts=True)
        frac = float(counts.max() / arr.size) if arr.size else 0.0
        out[r["sample_id"]] = {"sample_id": r["sample_id"], "n_labels": int(len(counts)), "max_label_fraction": frac,
                               "voxels": int(arr.size), "dtype": str(arr.dtype), "shape_zyx": list(arr.shape),
                               "is_synthetic": r["is_synthetic"], "family_id": r["family_id"], "split": r["split"],
                               "stratum": statistics.stratum({"max_label_fraction": frac})}
    return out


def outcome(primary: dict | None) -> str:
    if primary is None or primary["n_samples"] == 0:
        return "NO_REAL_DATA"
    gains = [p["gain_percent"] for p in primary["per_sample"]]
    if all(g == 0 for g in gains):
        return "INCONCLUSIVE"
    if all(g >= 0 for g in gains) and primary["total_ratio"] < 1:
        return "IMPROVED"
    if all(g <= 0 for g in gains) and primary["total_ratio"] > 1:
        return "REGRESSED"
    return "MIXED"


def aggregate(ctx) -> dict:
    from cape import gates

    store = ctx.store
    rows = store.measurements()
    tasks = store.tasks()
    cfg = ctx.cfg
    rd = ctx.run_dir

    # ---- exports ------------------------------------------------------------------------------
    store.export_jsonl(rd / "05_raw_metrics" / "measurements.jsonl")
    store.export_csv(rd / "05_raw_metrics" / "results.csv", rows)
    failures = [r for r in rows if r["status"] != "OK"]
    store.export_csv(rd / "05_raw_metrics" / "failures.csv", failures)
    store.export_csv(rd / "12_tables" / "failures.csv", failures)
    avail_path = rd / "05_raw_metrics" / "availability.json"
    avail = json.loads(avail_path.read_text(encoding="utf-8")) if avail_path.exists() else {}
    av_rows = [{"method": k, **{f: v.get(f) for f in ("status", "version", "reason", "adapter", "role", "citation")},
                "experimental": bool(v.get("experimental", False)),
                "panels": v.get("panels"), "supported_dtypes": v.get("supported_dtypes")} for k, v in sorted(avail.items())]
    for p in (rd / "05_raw_metrics" / "availability.csv", rd / "12_tables" / "availability.csv"):
        _csv(p, av_rows, ["method", "status", "version", "reason", "adapter", "role", "experimental", "citation",
                          "panels", "supported_dtypes"])
    lossless_rows = []
    for r in rows:
        extra = json.loads(r["extra_json"]) if r.get("extra_json") else {}
        lossless_rows.append({"measurement_id": r["measurement_id"], "sample_id": r["sample_id"],
                              "method": metrics.mkey(r), "panel": r["panel"], "repeat": r["repeat"],
                              "status": r["status"], "lossless": r["lossless"], "input_voxel_sha256": r["input_hash"],
                              "bitstream_sha256": r["bitstream_sha256"],
                              "secondary_checks": extra.get("secondary_checks"), "reason": r["reason"]})
    _csv(rd / "04_roundtrip" / "lossless_checks.csv", lossless_rows, list(lossless_rows[0]) if lossless_rows else
         ["measurement_id", "sample_id", "method", "status", "lossless"])

    # ---- cells and statistics -----------------------------------------------------------------
    cells = metrics.aggregate_cells(rows)
    mem = metrics.memory_cells(rows)
    sstats = _sample_stats(ctx)
    _csv(rd / "09_statistics" / "sample_stats.csv", list(sstats.values()),
         ["sample_id", "family_id", "split", "is_synthetic", "dtype", "shape_zyx", "voxels", "n_labels",
          "max_label_fraction", "stratum"])
    st = cfg["stats"]
    new, base = cfg["primary"]["new"], cfg["primary"]["baseline"]
    primary = statistics.compare(cells, new, base, "B", st["cluster_by"], st["bootstrap_resamples"], st["seed"], True)
    primary_synth = statistics.compare(cells, new, base, "B", st["cluster_by"], 1000, st["seed"], False)
    comparisons = {"primary": primary}
    for n, b, p in CONFIRMATORY_PAIRS:
        comparisons[f"{n} vs {b} [{p}]"] = statistics.compare(cells, n, b, p, st["cluster_by"],
                                                               st["bootstrap_resamples"], st["seed"], True)
    pvals = {k: v.get("wilcoxon_size_p") for k, v in comparisons.items() if v}
    adj = statistics.holm(pvals)
    eff_rows = []
    for k, v in comparisons.items():
        if not v:
            eff_rows.append({"comparison": k, "n_samples": 0, "note": "not measured on real samples"})
            continue
        eff_rows.append({"comparison": k, "new": v["new"], "base": v["base"], "panel": v["panel"],
                         "n_samples": v["n_samples"], "n_clusters": v["n_clusters"], "interval_kind": v["interval_kind"],
                         "total_ratio": v["total_ratio"], "total_ratio_ci95": v["total_ratio_ci95"],
                         "total_gain_percent": v["total_gain_percent"],
                         "median_sample_gain_percent": v["median_sample_gain_percent"],
                         "n_regressions": v["n_regressions"], "geo_speedup_encode": v["geo_speedup_encode"],
                         "geo_speedup_encode_ci95": v["geo_speedup_encode_ci95"],
                         "geo_speedup_decode": v["geo_speedup_decode"], "wilcoxon_size_p": v["wilcoxon_size_p"],
                         "wilcoxon_size_p_holm": adj.get(k), "note": ""})
    _csv(rd / "09_statistics" / "effect_sizes.csv", eff_rows,
         ["comparison", "new", "base", "panel", "n_samples", "n_clusters", "interval_kind", "total_ratio",
          "total_ratio_ci95", "total_gain_percent", "median_sample_gain_percent", "n_regressions",
          "geo_speedup_encode", "geo_speedup_encode_ci95", "geo_speedup_decode", "wilcoxon_size_p",
          "wilcoxon_size_p_holm", "note"])
    cov = statistics.coverage(rows, tasks)
    _csv(rd / "09_statistics" / "coverage.csv", cov, list(cov[0]) if cov else ["method"])

    # ---- certificates, components, ablations --------------------------------------------------
    certs, comp_rows, hist_rows = [], [], []
    for (sid, key, panel), c in sorted(cells.items()):
        if not c.get("n_ok") or not c["method_id"].startswith("cape") and c["method_id"] not in ("weighted_greedy", "greedy_local"):
            continue
        e = c.get("extra", {})
        if c.get("ub_bytes") is None:
            continue
        certs.append({"sample_id": sid, "method_id": key, "panel": panel,
                      "candidate_policy": cfg["algorithm"]["candidate_policy"],
                      "full_family_complete": cfg["algorithm"]["candidate_policy"] == "depth_bounded_complete_windows",
                      "reductions": cfg["algorithm"]["reductions"],
                      # labels are uint64; older diagnostics carried them as int64 (two's complement)
                      "background": int(e.get("background_label", 0)) & 0xFFFFFFFFFFFFFFFF,
                      "widths": {w: e.get(w) for w in ("w_L", "w_I", "w_G", "w_N", "w_D", "w_C")},
                      "regime_id": f"wD{e.get('regime_w_D')}-h{e.get('regime_h')}", "ub_bytes": int(c["ub_bytes"]),
                      "lb_bytes": int(c["lb_bytes"]), "label_ub_bytes": int(e.get("label_bytes", 0)),
                      "label_lb_bytes": int(e.get("label_lb_bytes", 0)), "certificate_scope": c.get("certificate_scope"),
                      "constraints_active": ["coverage", "pin validity (same ID run)"],
                      "global_or_restricted": "restricted",
                      "verifier_result": "VALID" if c.get("certificate_valid") else "INVALID",
                      "gap_bytes": int(c["ub_bytes"]) - int(c["lb_bytes"]),
                      "relative_label_gap": ((e.get("label_bytes", 0) - e.get("label_lb_bytes", 0)) /
                                             e["label_lb_bytes"]) if e.get("label_lb_bytes") else None,
                      "is_synthetic": c["is_synthetic"], "measurement_ids": c["measurement_ids"]})
        comp_rows.append({"sample_id": sid, "method": key, "panel": panel, "is_synthetic": c["is_synthetic"],
                          "cc_count": e.get("cc_count"), "label_count": e.get("label_count"), "runs": e.get("run_count"),
                          "candidates_before": c.get("candidate_count_before"),
                          "after_singleton": e.get("candidates_after_singleton"),
                          "after_equal": e.get("candidates_after_equal"), "after_subset": c.get("candidate_count_after"),
                          "incidence_before": e.get("incidence_count_before"), "incidence_after": c.get("incidence_count"),
                          "components": c.get("component_count"), "max_component_cc": c.get("max_component_cc"),
                          "exact_cc_fraction": c.get("exact_cc_fraction"),
                          "exact_cost_fraction": e.get("exact_cost_fraction"),
                          "status_counts": e.get("component_status_counts"),
                          "dp_transitions": e.get("dp_transitions"), "local_checks": e.get("local_checks"),
                          "reduction_ns": e.get("reduction_ns"), "candidate_ns": e.get("candidate_ns"),
                          "pass1_ns": e.get("pass1_ns"), "pass2_ns": e.get("pass2_ns"),
                          "encode_ns_median": c.get("encode_ns_median"),
                          # v2 stage profile (one untimed-protocol encode's own clocks; see
                          # encode_core_ns for their total). Depth regimes: values of the best regime.
                          "reduction_impl": e.get("reduction_impl"),
                          **{f: e.get(f) for f in STAGE_PROFILE_FIELDS}})
        for b, (n, w) in enumerate(zip(e.get("component_size_hist_count") or [], e.get("component_size_hist_cc") or [])):
            if n:
                hist_rows.append({"sample_id": sid, "method": key, "size_bucket_log2": b, "size_min": 2 ** b,
                                  "components": n, "cc_weight": w, "is_synthetic": c["is_synthetic"]})
    import jsonschema

    cschema = json.loads((ROOT / "schemas" / "certificate.schema.json").read_text(encoding="utf-8"))
    for cert in certs:
        jsonschema.validate(cert, cschema)
    atomic_write_text(rd / "06_solver_certificates" / "certificates.jsonl",
                      "".join(json.dumps(c) + "\n" for c in certs))
    _csv(rd / "06_solver_certificates" / "certificate_summary.csv", certs,
         ["sample_id", "method_id", "panel", "is_synthetic", "ub_bytes", "lb_bytes", "gap_bytes", "label_ub_bytes",
          "label_lb_bytes", "relative_label_gap", "regime_id", "verifier_result", "certificate_scope"])
    _csv(rd / "07_component_stats" / "component_stats.csv", comp_rows,
         list(comp_rows[0]) if comp_rows else ["sample_id", "method"])
    _csv(rd / "07_component_stats" / "component_size_histogram.csv", hist_rows,
         ["sample_id", "method", "size_bucket_log2", "size_min", "components", "cc_weight", "is_synthetic"])

    abl_rows = []
    for (sid, key, panel), c in sorted(cells.items()):
        if panel != "A" or key == "cape_core" or key not in ABLATIONS:
            continue
        core = cells.get((sid, "cape_core", "A"))
        if not core:
            continue
        abl_rows.append({"sample_id": sid, "variant": key, "is_synthetic": c["is_synthetic"],
                         "variant_bytes": c.get("total_bytes"), "cape_core_bytes": core.get("total_bytes"),
                         "variant_label_bytes": c.get("label_bytes"), "cape_core_label_bytes": core.get("label_bytes"),
                         "delta_bytes_vs_core": (c["total_bytes"] - core["total_bytes"])
                         if c.get("total_bytes") and core.get("total_bytes") else None,
                         "variant_encode_ms": c["encode_ns_median"] / 1e6 if c.get("encode_ns_median") else None,
                         "cape_core_encode_ms": core["encode_ns_median"] / 1e6 if core.get("encode_ns_median") else None,
                         "status": ",".join(c["statuses"])})
    _csv(rd / "08_ablations" / "ablation_comparison.csv", abl_rows,
         list(abl_rows[0]) if abl_rows else ["sample_id", "variant"])

    # ---- tables --------------------------------------------------------------------------------
    tables = write_tables(ctx, cells, mem, primary, sstats, av_rows)

    # ---- gates and summary ---------------------------------------------------------------------
    real_samples = sorted(r["sample_id"] for r in ctx.rows if not r["is_synthetic"])
    oracle = ctx.store.get_meta("oracle_summary")
    freeze = ctx.store.get_meta("stage_result:FROZEN")
    flags = gates.claim_gates(rows=rows, cells=cells, primary=primary, coverage=cov, cfg=cfg, tasks=tasks,
                              oracle=oracle, freeze=freeze, real_samples=real_samples)
    for p in (rd / "15_reports" / "claim_gate.json", rd / "09_statistics" / "claim_gate.json"):
        atomic_write_text(p, json.dumps(flags, indent=2))
    summary = {
        "run_id": ctx.run_id, "generated_at": now_iso(), "mode": cfg["mode"], "config_hash": ctx.hashes.get("config"),
        "source_hash": ctx.hashes.get("source"), "n_measurements": len(rows),
        "n_ok": sum(r["status"] == "OK" for r in rows), "task_counts": ctx.store.task_counts(),
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
        "n_real_samples": len(real_samples), "n_synthetic_samples": len(ctx.rows) - len(real_samples),
        "scientific_outcome": outcome(primary), "primary": _strip(primary), "primary_synthetic": _strip(primary_synth),
        "comparisons": {k: _strip(v) for k, v in comparisons.items() if k != "primary"},
        "claim_gate": {k: v["value"] for k, v in flags.items()}, "oracle": oracle, "tables": tables,
    }
    for p in (rd / "09_statistics" / "summary.json",):
        atomic_write_text(p, json.dumps(summary, indent=2, default=str))
    ctx.store.set_meta("summary", {k: summary[k] for k in ("scientific_outcome", "n_measurements", "n_ok")})
    return {k: summary[k] for k in ("scientific_outcome", "n_measurements", "n_ok", "status_counts")}


def _strip(cmp: dict | None):
    if not cmp:
        return None
    return {k: v for k, v in cmp.items() if k != "per_sample"} | {"n_per_sample": len(cmp.get("per_sample", []))}


def write_tables(ctx, cells, mem, primary, sstats, av_rows) -> list[str]:
    rd = ctx.run_dir / "12_tables"
    cfg = ctx.cfg
    base = cfg["primary"]["baseline"]
    out = []
    # overall native / wrapped (panel B), real samples only; synthetic in its own table
    for real in (True, False):
        by = defaultdict(list)
        for (sid, key, panel), c in cells.items():
            if panel == "B" and c["is_synthetic"] != real:
                by[key].append(c)
        trows = []
        for key, cs in sorted(by.items()):
            ok = [c for c in cs if c.get("total_bytes")]
            pairs = [(c, cells.get((c["sample_id"], base if "+" not in key else f"{base}+{key.split('+')[1]}", "B")))
                     for c in ok]
            pairs = [(c, b) for c, b in pairs if b and b.get("total_bytes")]
            trows.append({
                "method": key, "samples": len(cs), "ok_samples": len(ok),
                "total_bytes": sum(c["total_bytes"] for c in ok) if ok else None,
                "mean_bpv": float(np.mean([c["bpv"] for c in ok])) if ok else None,
                "ratio_vs_baseline": (sum(c["total_bytes"] for c, _ in pairs) / sum(b["total_bytes"] for _, b in pairs))
                if pairs else None,
                "geo_encode_speedup_vs_baseline": float(np.exp(np.mean([np.log(b["encode_ns_median"] / c["encode_ns_median"])
                                                                        for c, b in pairs]))) if pairs else None,
                "median_encode_ms": float(np.median([c["encode_ns_median"] for c in ok]) / 1e6) if ok else None,
                "median_decode_ms": float(np.median([c["decode_ns_median"] for c in ok]) / 1e6) if ok else None,
                "regressions_vs_baseline": sum(c["total_bytes"] > b["total_bytes"] for c, b in pairs) if pairs else None,
                "statuses": ",".join(sorted({s for c in cs for s in c["statuses"]})),
            })
        name = "results_overall" if real else "results_synthetic"
        out += write_table(rd / name, trows, [
            ("method", "Method", None), ("ok_samples", "OK samples", "d"), ("total_bytes", "Total bytes", ",d"),
            ("mean_bpv", "Mean bpv", ".4f"), ("ratio_vs_baseline", "Ratio vs stock pins", ".4f"),
            ("geo_encode_speedup_vs_baseline", "Geo enc. speedup", ".3f"),
            ("median_encode_ms", "Enc. ms (median)", ".2f"), ("median_decode_ms", "Dec. ms (median)", ".2f"),
            ("regressions_vs_baseline", "Regressions", "d"), ("statuses", "Statuses", None)],
            f"Panel B, {'real' if real else 'synthetic'} samples: totals include every header/metadata byte. "
            "Wrapped rows are compared with the equally wrapped baseline.",
            best={"total_bytes": "min", "mean_bpv": "min"})
    # per-dataset wins/losses for the primary pair
    prows = (primary or {}).get("per_sample", [])
    out += write_table(rd / "per_sample_primary", prows, [
        ("sample_id", "Sample", None), ("family_id", "Family", None), ("new_bytes", "CAPE bytes", ",d"),
        ("base_bytes", "Stock bytes", ",d"), ("gain_percent", "Gain %", ".3f"), ("label_new", "CAPE label B", ",d"),
        ("label_base", "Stock label B", ",d"), ("encode_speedup", "Enc. speedup", ".3f"),
        ("decode_speedup", "Dec. speedup", ".3f"), ("label_format_base", "Stock format", None)],
        "Primary pair per real sample (negative gain = CAPE larger; nothing is clipped or dropped)")
    # timing / memory
    mrows = [{"method": v["method"], "sample_id": v["sample_id"], "status": v["status"],
              "peak_rss_mib": (v["peak_rss_bytes"] / 2 ** 20) if v.get("peak_rss_bytes") else None,
              "input_mib": (v["input_bytes"] / 2 ** 20) if v.get("input_bytes") else None,
              "normalized_peak": v.get("input_normalized_peak"), "mode": v.get("rss_measurement_mode"),
              "attribution": v.get("peak_attribution")} for v in sorted(mem.values(), key=lambda x: (x["sample_id"], x["method"]))]
    out += write_table(rd / "memory", mrows, [
        ("sample_id", "Sample", None), ("method", "Method", None), ("status", "Status", None),
        ("peak_rss_mib", "Peak RSS MiB", ".1f"), ("input_mib", "Input MiB", ".1f"),
        ("normalized_peak", "Peak/input", ".2f"), ("attribution", "Attribution", None)],
        "Peak working set of a fresh profiling process (separate from timing runs)")
    # dataset provenance
    drows = [{"sample_id": r["sample_id"], "split": r["split"], "family": r["family_id"], "source": r["source_id"],
              "dtype": r["dtype"], "shape_zyx": "x".join(map(str, r["shape"])), "license": r["license"],
              "synthetic": r["is_synthetic"], "stratum": sstats.get(r["sample_id"], {}).get("stratum")}
             for r in sorted(ctx.rows, key=lambda r: r["sample_id"])]
    out += write_table(rd / "dataset_provenance", drows, [
        ("sample_id", "Sample", None), ("split", "Split", None), ("family", "Family", None), ("source", "Source", None),
        ("dtype", "dtype", None), ("shape_zyx", "Shape ZYX", None), ("stratum", "Stratum", None),
        ("synthetic", "Synthetic", None), ("license", "License", None)], "Samples used in this run")
    # software versions
    out += write_table(rd / "software_versions", av_rows, [
        ("method", "Method", None), ("status", "Status", None), ("version", "Version", None),
        ("experimental", "Experimental", None), ("reason", "Reason", None)],
        "Method availability and versions (unavailable comparators stay listed)")
    return out


# ================================================================ written reports
REFERENCES_BIB = r"""@misc{crackle, title={Crackle: 3D dense segmentation compression}, author={Silversmith, William}, howpublished={\url{https://github.com/seung-lab/crackle}}, note={commit 14b39b196a14b3b1ba7d1cd34f350c324308000f; PyPI crackle-codec 0.53.0}}
@inproceedings{compresso, title={Compresso: Efficient Compression of Segmentation Data for Connectomics}, author={Matejek, Brian and Haehn, Daniel and Lekschas, Fritz and Mitzenmacher, Michael and Pfister, Hanspeter}, booktitle={MICCAI}, year={2017}}
@article{csgv, title={Fast Compressed Segmentation Volumes for Scientific Visualization}, author={Piochowiak, Max and Dachsbacher, Carsten}, journal={IEEE TVCG}, volume={30}, number={1}, pages={12--22}, year={2024}, doi={10.1109/TVCG.2023.3326573}}
@article{csgvr, title={Random Access Segmentation Volume Compression for Interactive Volume Rendering}, author={Piochowiak, Max and Kurpicz, Florian and Dachsbacher, Carsten}, journal={Computer Graphics Forum}, volume={44}, number={3}, year={2025}, doi={10.1111/cgf.70116}}
@misc{volcanite, title={Volcanite}, author={Piochowiak, Max}, howpublished={\url{https://github.com/max-pio/volcanite}}}
@article{chvatal1979, title={A Greedy Heuristic for the Set-Covering Problem}, author={Chv{\'a}tal, Va{\v{s}}ek}, journal={Mathematics of Operations Research}, volume={4}, number={3}, pages={233--235}, year={1979}, doi={10.1287/moor.4.3.233}}
@article{yagiura2006, title={A 3-flip neighborhood local search for the set covering problem}, author={Yagiura, Mutsunori and Kishida, Masahiro and Ibaraki, Toshihide}, journal={European Journal of Operational Research}, volume={172}, number={2}, pages={472--499}, year={2006}}
@misc{ortools, title={OR-Tools CP-SAT}, author={{Google}}, howpublished={\url{https://developers.google.com/optimization/cp/cp_solver}}}
@misc{neuroglancer, title={Neuroglancer compressed segmentation format}, author={{Google}}, howpublished={\url{https://github.com/google/neuroglancer}}}
@misc{cremi, title={CREMI: MICCAI Challenge on Circuit Reconstruction from Electron Microscopy Images}, howpublished={\url{https://cremi.org/data/}}}
@misc{zstd, title={Zstandard}, howpublished={\url{https://github.com/facebook/zstd}}}
@misc{blosc2, title={C-Blosc2}, howpublished={\url{https://github.com/Blosc/c-blosc2}}}
"""


def _stage_rows(stages: list[dict]) -> list[dict]:
    from cape.runner import STAGES

    by = {s["name"]: s for s in stages}
    rows = []
    for name in STAGES[2:]:
        s = by.get(name, {})
        status = s.get("status") or "PENDING"
        detail = (s.get("detail") or "").replace("\n", " ")[:160]
        if status == "RUNNING" and name == "RENDERED":
            detail = "bu hisobot shu bosqichda yozilmoqda"
        elif status == "PENDING" and name in ("VERIFIED", "PACKAGED"):
            detail = "hisobotdan keyin bajariladi"
        rows.append({"stage": name, "status": status, "started": s.get("started_at"), "finished": s.get("finished_at"),
                     "detail": detail})
    return rows


def _failure_summary(ctx) -> list[dict]:
    by = defaultdict(list)
    for r in ctx.store.measurements("status <> 'OK'"):
        by[r["status"]].append(r)
    out = []
    for status, rs in sorted(by.items()):
        out.append({"status": status, "count": len(rs),
                    "methods": ", ".join(sorted({metrics.mkey(r) for r in rs}))[:300],
                    "example_reason": (rs[0]["reason"] or "")[:200].replace("|", "/").replace("\n", " ")})
    return out


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _md_table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    if not rows:
        return "_Ma'lumot yo'q._\n"
    lines = ["| " + " | ".join(h for _, h in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        cells = []
        for k, _ in cols:
            v = r.get(k)
            if isinstance(v, float):
                v = f"{v:.4g}"
            cells.append("-" if v is None or v == "" else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


DEPTH_WINDOW = 256  # w_D = 1 windows; regimes only differ when some real sample has Z > 256


def _depth_regime_note(ctx) -> str:
    """Limitation text derived from the samples actually used (never a fixed claim)."""
    zs = [int(r["shape"][0]) for r in getattr(ctx, "rows", None) or []
          if not r.get("is_synthetic") and r.get("shape")]
    if not zs:
        return "- Real namuna yo'q: depth-regime mexanizmi `NOT_EXERCISED`."
    if max(zs) > DEPTH_WINDOW:
        n = sum(z > DEPTH_WINDOW for z in zs)
        return (f"- Depth-regime mexanizmi real namunalarda sinaldi: {n}/{len(zs)} namunada Z > {DEPTH_WINDOW} "
                f"(eng katta Z={max(zs)}); ta'siri `08_ablations/ablation_comparison.csv` dagi "
                "`cape_fixed_depth_width` qatorlarida.")
    return (f"- Real namunalarda eng katta Z={max(zs)} <= {DEPTH_WINDOW}: depth-regime mexanizmi "
            "`NOT_EXERCISED`.")


def _independence_notes(ctx) -> list[str]:
    """Manifest-level independence statements (e.g. v2 test crops of already-seen volumes)."""
    rows = [r for r in getattr(ctx, "rows", None) or [] if not r.get("is_synthetic")]
    notes = sorted({r["v2_independence"] for r in rows if r.get("v2_independence")})
    vols = sorted({r.get("source_id") for r in rows if r.get("source_id")})
    out = [f"- Mustaqillik: {n}" for n in notes]
    if rows:
        out.append(f"- Real namunalar {len(vols)} ta original volume'dan: {', '.join(vols)}. Klaster CI shu "
                   "volume'lar ichida shartli; boshqa acquisition'larga umumlashmaydi.")
    return out


def _csgv_note(avail: list[dict]) -> str:
    st = {r.get("method"): r.get("status") for r in avail}
    csgv = {m: s for m, s in st.items() if m and m.startswith("csgv")}
    if not csgv:
        return "- CSGV/CSGV-R bu run'ning usullar ro'yxatida yo'q."
    if all(s == "AVAILABLE" for s in csgv.values()):
        return ("- CSGV/CSGV-R Volcanite CLI orqali o'lchangan (`cli_process_file_to_file`): vaqtga jarayon "
                "ishga tushishi va fayl I/O kiradi, shuning uchun tezligi in-process usullar bilan teng "
                "solishtirilmaydi; hajm solishtirmasi to'g'ri.")
    return (f"- CSGV/CSGV-R holati {csgv}: mavjud bo'lmagan usul bo'yicha zamonaviy raqib da'vosi "
            "bloklanadi.")


def write_reports(ctx, figures: dict | None = None, status: str | None = None, message: str | None = None) -> list[str]:
    rd = ctx.run_dir
    summary_path = rd / "09_statistics" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    gate_path = rd / "15_reports" / "claim_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}
    stages = ctx.store.stages()
    counts = ctx.store.task_counts()
    cov = _read_csv(rd / "09_statistics" / "coverage.csv")
    avail = _read_csv(rd / "05_raw_metrics" / "availability.csv")
    primary = summary.get("primary")
    per_sample = _read_csv(rd / "12_tables" / "per_sample_primary.csv")
    overall = _read_csv(rd / "12_tables" / "results_overall.csv")
    run_status = status or "COMPLETE"
    real_n = summary.get("n_real_samples", 0)
    rm = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")) if (rd / "run_manifest.json").exists() else {}
    hooks = rm.get("test_hooks") or {}

    L = [f"# CAPE-Pins yakuniy hisobot — `{ctx.run_id}`", ""]
    if hooks:
        L += [f"> **OGOHLANTIRISH:** bu run test hook'lari bilan bajarilgan ({hooks}); natijalari ilmiy natija emas.", ""]
    L += [f"- **Run holati:** {run_status}" + (f" — {message}" if message else ""),
         f"- **Ilmiy natija (asosiy juftlik, real namunalar):** {summary.get('scientific_outcome', 'NO_REAL_DATA')}",
         f"- **Rejim:** {ctx.cfg['mode']}; config hash `{str(ctx.hashes.get('config'))[:12]}`; "
         f"source hash `{str(ctx.hashes.get('source'))[:12]}`",
         f"- **O'lchovlar:** {summary.get('n_measurements', 0)} ta (OK: {summary.get('n_ok', 0)}); "
         f"task holatlari: {counts}",
         f"- **Namunalar:** {real_n} ta real, {summary.get('n_synthetic_samples', 0)} ta sintetik "
         "(sintetik natijalar real jadvalga qo'shilmaydi)", "",
         "## 1. Bosqichlar", "",
         "INIT va PREFLIGHT `run_all.py` ichida bajariladi (`14_logs/preflight.json`). Hisobot RENDERED bosqichida "
         "yoziladi; VERIFIED va PACKAGED natijasi `15_reports/verification.json`, `SUCCESS.json` va "
         "`run_manifest.json` da.", "",
         _md_table(_stage_rows(stages),
                   [("stage", "Bosqich"), ("status", "Holat"), ("started", "Boshlandi"), ("finished", "Tugadi"),
                    ("detail", "Izoh")]),
         "## 2. Asosiy taqqoslash (oldindan belgilangan juftlik)", ""]
    experimental = {r["method"] for r in avail if str(r.get("experimental", "")).lower() == "true"}
    if primary and primary.get("new") in experimental:
        L += [f"> **[EXPERIMENTAL]** `{primary['new']}` eksperimental usul (v2.1 qarori): u g'olib yoki yangi "
              "standart usul sifatida talqin qilinmaydi; bu juftlik faqat tarixiy (oldindan ro'yxatdan o'tgan) taqqoslash.", ""]
    if primary:
        ci = primary.get("total_ratio_ci95")
        L += [f"`{primary['new']}` va `{primary['base']}`, panel B, {primary['n_samples']} ta real namuna, "
              f"{primary['n_clusters']} ta klaster ({primary['interval_kind']}).", "",
              f"- Jami bayt nisbati: **{primary['total_ratio']:.5f}** (yutuq {primary['total_gain_percent']:.3f}%), "
              f"95% klaster-bootstrap CI: {ci}",
              f"- Namuna bo'yicha yutuq: median {primary['median_sample_gain_percent']:.3f}%, "
              f"min {primary['min_sample_gain_percent']:.3f}%, max {primary['max_sample_gain_percent']:.3f}%; "
              f"regressiyalar: {primary['n_regressions']}",
              f"- Encode tezlashuvi (geometrik o'rtacha): {primary['geo_speedup_encode']:.3f}, CI "
              f"{primary.get('geo_speedup_encode_ci95')}; decode: {primary['geo_speedup_decode']:.3f}", "",
              "Har bir namuna (manfiy yutuq = CAPE kattaroq; hech qaysi satr olib tashlanmagan):", "",
              _md_table(per_sample, [("sample_id", "Namuna"), ("new_bytes", "CAPE bayt"), ("base_bytes", "Stock bayt"),
                                     ("gain_percent", "Yutuq %"), ("encode_speedup", "Enc. tezl."),
                                     ("label_format_base", "Stock formati")])]
    else:
        L += ["Real namunalarda asosiy juftlik o'lchanmagan — real siqish xulosasi **yo'q** "
              "(sabab: real ma'lumot yo'q yoki usul ishlamadi; quyidagi coverage jadvaliga qarang).", ""]
    L += ["## 3. Panel B: barcha usullar (real namunalar)", "",
          f"Nisbat va regressiyalar `{ctx.cfg['primary']['baseline']}` ga nisbatan (wrap qilingan qatorlar bir xil "
          "wrapper'li bazaviy usul bilan) olingan; m5 qatorlar ham m0 bazaviy bilan solishtirilgan.", "",
          _md_table(overall, [("method", "Usul"), ("ok_samples", "OK"), ("total_bytes", "Jami bayt"),
                              ("ratio_vs_baseline", "Nisbat (bazaviy)"), ("median_encode_ms", "Enc ms"),
                              ("median_decode_ms", "Dec ms"), ("regressions_vs_baseline", "Regressiya"),
                              ("statuses", "Holatlar")]),
          "## 4. Qo'shimcha juftliklar va panel A (selektor sababiyati)", "",
          _md_table([{"name": k, "n": (v or {}).get("n_samples"), "ratio": (v or {}).get("total_ratio"),
                      "ci": (v or {}).get("total_ratio_ci95"), "reg": (v or {}).get("n_regressions"),
                      "kind": (v or {}).get("interval_kind")} for k, v in summary.get("comparisons", {}).items()],
                    [("name", "Juftlik"), ("n", "Namuna"), ("ratio", "Bayt nisbati"), ("ci", "95% CI"),
                     ("reg", "Regressiya"), ("kind", "Interval")]),
          "## 5. Usullar mavjudligi", "",
          _md_table(avail, [("method", "Usul"), ("status", "Holat"), ("version", "Versiya"), ("reason", "Sabab")]),
          "## 6. Coverage (rejalashtirilgan va bajarilgan)", "",
          _md_table(cov, [("method", "Usul"), ("panel", "Panel"), ("planned", "Reja"), ("ok", "OK"),
                          ("pending", "Kutilmoqda"), ("n_FAILED_LOSSLESS", "Lossless xato"), ("n_UNAVAILABLE", "Mavjud emas"),
                          ("n_UNSUPPORTED_DTYPE", "dtype"), ("n_OOM", "OOM"), ("n_TIMEOUT", "Timeout")]),
          "## 6b. Muvaffaqiyatsiz va qo'llanmagan o'lchovlar (holat bo'yicha)", "",
          _md_table(_failure_summary(ctx), [("status", "Holat"), ("count", "Soni"), ("methods", "Usullar"),
                                            ("example_reason", "Misol sabab")]),
          "## 7. Sertifikat va optimallik", "",
          f"Oracle audit: {json.dumps(summary.get('oracle'), default=str)[:600]}", "",
          "Sertifikatlar faqat ko'rsatilgan model doirasida (certificate_scope) amal qiladi; bu butun Crackle "
          "formatining global optimumi degani emas. Batafsil: `06_solver_certificates/`.", "",
          "## 8. Claim gate", "",
          _md_table([{"flag": k, "value": v.get("value"), "evidence": v.get("evidence"), "reason": v.get("reason")}
                     for k, v in gate.items()], [("flag", "Da'vo"), ("value", "Ruxsat"), ("evidence", "Dalil"),
                                                  ("reason", "Sabab")]),
          "## 9. Cheklovlar", "",
          "- H01 va MICrONS yuklab olinmagan (foydalanuvchi qarori, 2026-11-05): mustaqil test oilasi yo'q, RQ6 qisman.",
          _depth_regime_note(ctx),
          *_independence_notes(ctx),
          "- Faqat Windows native (MinGW g++) track; Linux/WSL canonical track bajarilmagan.",
          _csgv_note(avail),
          "- Timing bitta P-core'da, bitta thread; boshqa protsesslar ta'siri to'liq istisno qilinmaydi.", "",
          "## 10. Fayllar", "", "To'liq ro'yxat: `15_reports/RESULTS_INDEX.md`.", ""]
    written = []
    atomic_write_text(rd / "15_reports" / "final_report_UZ.md", "\n".join(L))
    written.append(str(rd / "15_reports" / "final_report_UZ.md"))
    write_paper_assets(ctx, summary, gate)
    written.append(str(write_results_index(ctx, run_status, figures)))
    return written


def write_paper_assets(ctx, summary: dict, gate: dict) -> None:
    pa = ctx.run_dir / "13_paper_assets"
    cfg = ctx.cfg
    docs = ROOT / "docs"
    methods_txt = (docs / "algorithm.md").read_text(encoding="utf-8") if (docs / "algorithm.md").exists() else \
        "See docs/algorithm.md in the source release."
    atomic_write_text(pa / "methods.md", "# Method (CAPE-Pins)\n\n" + methods_txt)
    env_path = ctx.run_dir / "01_environment" / "environment.json"
    env = json.loads(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
    atomic_write_text(pa / "experimental_setup.md", "\n".join([
        "# Experimental setup", "",
        f"- CPU: {env.get('os', {}).get('processor_name')}; timing CPU {env.get('timing_cpu')}",
        f"- RAM: {env.get('memory', {}).get('total_bytes')} bytes; OS: {env.get('os', {}).get('platform')}",
        f"- Compiler: {env.get('toolchain', {}).get('g++')}; Python {env.get('python', {}).get('version')}",
        f"- Protocol: {cfg['benchmark']['warmups']} warm-up + {cfg['benchmark']['repeats']} timed repeats, "
        f"min batch {cfg['benchmark']['min_batch_ms']} ms, {cfg['benchmark']['threads']} thread(s), method order "
        "shuffled per repeat with a fixed seed; memory measured in separate fresh processes.",
        f"- Primary pair: {cfg['primary']['new']} vs {cfg['primary']['baseline']} (pre-registered).",
        f"- Statistics: cluster bootstrap over {cfg['stats']['cluster_by']} ({cfg['stats']['bootstrap_resamples']} "
        "resamples), geometric-mean speedups, Holm-adjusted Wilcoxon as secondary.", ""]))
    atomic_write_text(pa / "limitations.md", "\n".join([
        "# Limitations", "",
        "- Results are restricted to the samples listed in the dataset provenance table.",
        "- Optimality certificates hold for the stated restricted model (certificate_scope), not for every "
        "possible Crackle-compatible stream.",
        "- No independent human (H01) or MICrONS test family was downloaded for this run.",
        "- Depth-width regimes are not exercised by volumes with Z <= 256.",
        "- Comparators that were unavailable are listed with their reasons; no published numbers were copied.", ""]))
    lines = ["# Supported claims (generated from claim_gate.json)", ""]
    for k, v in gate.items():
        lines.append(f"- `{k}`: {'SUPPORTED' if v.get('value') else 'NOT SUPPORTED'} — "
                     f"{v.get('evidence') if v.get('value') else v.get('reason')}")
    atomic_write_text(pa / "supported_claims.md", "\n".join(lines) + "\n")
    caps = ["# Figure captions", ""]
    for fid, text in FIGURE_CAPTIONS.items():
        caps.append(f"- **{fid}** — {text}")
    atomic_write_text(pa / "captions.md", "\n".join(caps) + "\n")
    atomic_write_text(pa / "references.bib", REFERENCES_BIB)
    atomic_write_text(pa / "reproducibility_checklist.md", "\n".join([
        "# Reproducibility checklist", "",
        "- [x] Pinned sources (sources.lock.json) and hashed dependency lock (requirements.lock)",
        "- [x] Config, manifest/split and source hashes recorded in run_manifest.json and protocol_freeze.json",
        "- [x] Every number in tables/figures links to measurement ids in run.sqlite",
        "- [x] One-command reproduction: run_experiment.cmd (see docs/REPRODUCE_UZ.md)",
        "- [x] Negative results, failures and unavailable comparators are reported",
        "- [ ] Data redistribution: not included (licenses unknown); fetch via scripts/fetch_data.py", ""]))
    if (docs / "mathematics.md").exists():
        atomic_write_text(pa / "mathematics.md", (docs / "mathematics.md").read_text(encoding="utf-8"))


FIGURE_CAPTIONS = {
    "F01_algorithm": "CAPE pipeline: format-compatible candidates, safe reductions, independent components, exact "
                     "DP on small components, local search on large ones, integer dual certificate.",
    "F02_bpv_vs_encode": "Bits per voxel vs encode time (single thread); native and externally wrapped streams in "
                         "separate panels.",
    "F03_bpv_vs_decode": "Bits per voxel vs CPU decode time.",
    "F04_per_dataset_gain": "Per-sample size gain of the primary pair; regressions are shown, not removed.",
    "F05_component_distribution": "CC-weighted distribution of component sizes after reductions.",
    "F06_reduction_time_memory": "Candidate reductions: remaining candidates per stage and reduction time.",
    "F07_gap_vs_cost": "Certified gap (UB-LB) of the label section against encode cost.",
    "F08_ablation": "Ablations in the forced pins format (panel A): bytes relative to the full CAPE selector.",
    "F09_scaling": "Encode time vs volume size.",
    "F10_byte_breakdown": "Stream composition: label section vs crack codes and headers.",
    "F11_roi_latency": "Chunk-level ROI latency (second-stage panel).",
}


def write_results_index(ctx, run_status: str, figures: dict | None) -> Path:
    rd = ctx.run_dir
    lines = [f"# RESULTS INDEX — `{ctx.run_id}`", "", f"Run holati: **{run_status}**. Bu fayl natijalarni "
             "ko'rish uchun yetarli kirish nuqtasi.", "",
             "Qayta hisobot (tajribasiz): `run_experiment.cmd --stage report --latest`", ""]
    for sec in ["01_environment", "02_data_manifest", "03_bitstreams", "04_roundtrip", "05_raw_metrics",
                "06_solver_certificates", "07_component_stats", "08_ablations", "09_statistics", "10_plot_data",
                "11_figures", "12_tables", "13_paper_assets", "14_logs", "15_reports"]:
        d = rd / sec
        files = sorted(p for p in d.rglob("*") if p.is_file() and not p.name.endswith(".tmp")) if d.exists() else []
        st_path = d / "STATUS.json"
        st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
        lines.append(f"## {sec} — {st.get('status', 'PENDING')}")
        if st.get("reason"):
            lines.append(f"_{st['reason']}_")
        shown = [f for f in files if f.name != "STATUS.json"]
        if sec == "03_bitstreams":
            lines.append(f"- {len(shown)} bitstream fayl (sha256 nomli)")
        else:
            for f in shown[:60]:
                lines.append(f"- [{f.relative_to(rd).as_posix()}]({f.relative_to(rd).as_posix()}) ({f.stat().st_size} B)")
            if len(shown) > 60:
                lines.append(f"- ... yana {len(shown) - 60} fayl")
        lines.append("")
    if figures:
        lines += ["## Figuralar holati", ""] + [f"- {k}: {v.get('status')} {v.get('reason') or ''}"
                                                 for k, v in figures.items()] + [""]
    p = rd / "15_reports" / "RESULTS_INDEX.md"
    atomic_write_text(p, "\n".join(lines))
    return p
