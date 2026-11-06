"""Artifact manifest, per-section STATUS.json and run verification (spec sections 28, 37).

verify_run implements the checks of spec 37 (1-9; the ZIP check 10 is in packaging):
complete task accounting, valid OK rows with existing hashed bitstreams, no header-only CSV,
referenced files present and non-empty, paired comparisons on identical inputs/configs,
plot data equal to values recomputed from the records, figures that open and plot the
recorded number of points, explicit artifact_missing.csv, and a final report that shows
failures and regressions."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path

from cape.result_store import atomic_write_text, now_iso

SECTIONS = ["01_environment", "02_data_manifest", "03_bitstreams", "04_roundtrip", "05_raw_metrics",
            "06_solver_certificates", "07_component_stats", "08_ablations", "09_statistics", "10_plot_data",
            "11_figures", "12_tables", "13_paper_assets", "14_logs", "15_reports"]
POINT_RULES = {  # figure -> how n_points follows from its plot-data rows
    "F01_algorithm": lambda rows: len(rows), "F02_bpv_vs_encode": lambda rows: len(rows),
    "F03_bpv_vs_decode": lambda rows: len(rows), "F04_per_dataset_gain": lambda rows: len(rows),
    "F05_component_distribution": lambda rows: len(rows), "F06_reduction_time_memory": lambda rows: 5 * len(rows),
    "F07_gap_vs_cost": lambda rows: len(rows), "F08_ablation": lambda rows: len({r["variant"] for r in rows}),
    "F09_scaling": lambda rows: len(rows), "F10_byte_breakdown": lambda rows: 2 * len({r["method"] for r in rows}),
}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _rules() -> dict:
    import yaml

    from cape.provenance import ROOT

    return yaml.safe_load((ROOT / "configs" / "artifacts.yaml").read_text(encoding="utf-8"))


def _db(run_dir: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{run_dir / '05_raw_metrics' / 'run.sqlite'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def conditions(run_dir: Path) -> dict:
    rm = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    out = {"always": True, "paper_assets": True, "roi_enabled": False}
    dbp = run_dir / "05_raw_metrics" / "run.sqlite"
    if not dbp.exists():
        return dict(out, any_measurement=False, any_ok_measurement=False, cape_measured=False, ablations_measured=False,
                    primary_pair_measured=False, multiple_sizes=False, crackle_family_measured=False,
                    any_empirical_figure=False)
    db = _db(run_dir)
    q = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    out["any_measurement"] = q("SELECT COUNT(*) FROM measurements") > 0
    out["any_ok_measurement"] = q("SELECT COUNT(*) FROM measurements WHERE status='OK' AND panel IN ('A','B')") > 0
    out["cape_measured"] = q("SELECT COUNT(*) FROM measurements WHERE status='OK' AND method_id LIKE 'cape%' "
                             "AND ub_bytes IS NOT NULL") > 0
    out["ablations_measured"] = q("SELECT COUNT(*) FROM measurements WHERE status='OK' AND panel='A' "
                                  "AND method_id <> 'cape_core'") > 0
    out["crackle_family_measured"] = q("SELECT COUNT(*) FROM measurements WHERE status='OK' AND label_bytes IS NOT NULL "
                                       "AND is_synthetic=0") > 0
    out["multiple_sizes"] = q("SELECT COUNT(DISTINCT canonical_shape) FROM measurements WHERE status='OK' "
                              "AND is_synthetic=0") > 1
    out["primary_pair_measured"] = q("SELECT COUNT(DISTINCT method_id) FROM measurements WHERE status='OK' AND "
                                     "is_synthetic=0 AND panel='B' AND (wrapper='none' OR wrapper IS NULL) AND "
                                     f"method_id IN ('{rm.get('primary_new', 'cape_m0')}', "
                                     f"'{rm.get('primary_baseline', 'crackle_pins_opt_m0')}')") == 2
    db.close()
    fs = run_dir / "11_figures" / "figures_status.json"
    figs = json.loads(fs.read_text(encoding="utf-8")) if fs.exists() else {}
    out["any_empirical_figure"] = any(v.get("status") == "COMPLETE" for k, v in figs.items() if k != "F01_algorithm")
    return out


def write_statuses(run_dir: Path, run_status: str | None = None) -> dict:
    rules = _rules()["sections"]
    cond = conditions(run_dir)
    out = {}
    for sec in SECTIONS:
        d = run_dir / sec
        d.mkdir(parents=True, exist_ok=True)
        rule = rules.get(sec, {"when": "always"})
        applicable = bool(cond.get(rule.get("when", "always"), False))
        files = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file() and p.name != "STATUS.json"
                       and not p.name.endswith(".tmp"))
        missing = []
        if applicable:
            for name in rule.get("required", []):
                p = d / name
                if not p.exists() or p.stat().st_size == 0:
                    missing.append(name)
            if "required_glob" in rule:
                hits = [p for p in d.glob(rule["required_glob"]) if p.stat().st_size > 0]
                if len(hits) < rule.get("min_count", 1):
                    missing.append(rule["required_glob"])
        if not applicable:
            status, reason = "NOT_APPLICABLE", f"condition '{rule.get('when')}' is false for this run"
        elif missing:
            status, reason = "PARTIAL", f"missing or empty: {missing}"
        else:
            status, reason = "COMPLETE", None
        rec = {"section": sec, "applicable": applicable, "completed": status == "COMPLETE", "status": status,
               "artifacts": files, "reason": reason, "updated_at": now_iso()}
        atomic_write_text(d / "STATUS.json", json.dumps(rec, indent=2))
        out[sec] = rec
    return out


def build_manifest(run_dir: Path) -> list[dict]:
    entries = []
    for sec in SECTIONS:
        d = run_dir / sec
        for p in sorted(d.rglob("*")) if d.exists() else []:
            if not p.is_file() or p.name.endswith(".tmp") or p.name == "STATUS.json" or p.suffix == ".sqlite-journal":
                continue
            prov = p.with_suffix(".provenance.json") if p.suffix in (".pdf", ".png") else None
            ids = []
            if prov and prov.exists():
                ids = json.loads(prov.read_text(encoding="utf-8")).get("measurement_ids", [])
            entries.append({"artifact_id": p.relative_to(run_dir).as_posix(), "path": p.relative_to(run_dir).as_posix(),
                            "bytes": p.stat().st_size, "sha256": _sha(p), "generator": _generator(sec, p),
                            "source_measurements": ids, "created_at": now_iso(),
                            "status": "PRELIMINARY" if "PRELIMINARY" in p.name else "COMPLETE"})
    atomic_write_text(run_dir / "artifact_manifest.json", json.dumps(entries, indent=2))
    return entries


def _generator(sec: str, p: Path) -> str:
    return {"03_bitstreams": "cape.worker", "05_raw_metrics": "cape.result_store", "10_plot_data": "cape.plots",
            "11_figures": "cape.plots", "12_tables": "cape.tables/cape.reporting", "15_reports": "cape.reporting",
            "06_solver_certificates": "cape.reporting/cape.oracle", "14_logs": "cape.runner"}.get(sec, "cape.reporting")


def verify_run(run_dir: Path) -> dict:
    import yaml  # noqa: F401  (rules loader dependency)

    problems: list[str] = []
    checks: dict = {}
    rm = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    cfg_path = rm.get("config_path")
    from cape.config import load_run_config

    cfg = load_run_config(cfg_path)
    db = _db(run_dir)
    tasks = [dict(r) for r in db.execute("SELECT * FROM tasks")]
    ms = [dict(r) for r in db.execute("SELECT * FROM measurements")]
    db.close()
    # 1. task accounting
    unfinished = [t for t in tasks if t["status"] in ("PENDING", "RUNNING")]
    with_row = {m["task_id"] for m in ms}
    no_row = [t for t in tasks if t["status"] in ("COMMITTED", "FAILED", "SKIPPED") and t["task_id"] not in with_row]
    checks["tasks_planned"] = len(tasks)
    checks["tasks_unfinished"] = len(unfinished)
    if unfinished:
        problems.append(f"{len(unfinished)} planned tasks unfinished")
    if no_row:
        problems.append(f"{len(no_row)} finished tasks without a measurement row")
    # 2. OK rows valid, bitstreams present
    bad_ok = 0
    for m in ms:
        if m["status"] != "OK":
            continue
        if m["panel"] == "MEM":  # memory profile rows: no timing, no stored bitstream
            bad_ok += not ((m["total_bytes"] or 0) > 0 and m["lossless"] == 1 and (m["peak_rss_bytes"] or 0) > 0)
            continue
        valid = (m["total_bytes"] or 0) > 0 and (m["lossless"] == 1) and isinstance(m["bitstream_sha256"], str) \
            and len(m["bitstream_sha256"]) == 64 and (m["encode_ns"] or 0) > 0 and (m["decode_ns"] or 0) > 0
        if valid and m["bitstream_path"]:
            bp = run_dir / m["bitstream_path"]
            valid = bp.exists() and bp.stat().st_size == m["total_bytes"]
        bad_ok += not valid
    checks["ok_rows"] = sum(m["status"] == "OK" for m in ms)
    if bad_ok:
        problems.append(f"{bad_ok} OK rows fail validity checks (bytes/time/lossless/hash/bitstream)")
    bitstreams = list((run_dir / "03_bitstreams").glob("*.bin"))
    sample = bitstreams[:: max(1, len(bitstreams) // 25)]
    for bp in sample:
        if _sha(bp) != bp.stem:
            problems.append(f"bitstream hash mismatch: {bp.name}")
    # 3. CSV not header-only; real data requirement
    res_csv = run_dir / "05_raw_metrics" / "results.csv"
    n_lines = sum(1 for _ in open(res_csv, encoding="utf-8")) if res_csv.exists() else 0
    if ms and n_lines <= 1:
        problems.append("results.csv is header-only although measurements exist")
    if cfg["input"]["require_real_data"] and not any(m["status"] == "OK" and not m["is_synthetic"] for m in ms):
        problems.append("real run without a single valid real measurement")
    # 4/6/7. figures: files open, provenance matches plot data
    fig_status_p = run_dir / "11_figures" / "figures_status.json"
    figs = json.loads(fig_status_p.read_text(encoding="utf-8")) if fig_status_p.exists() else {}
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg

    for fid, st in figs.items():
        if st.get("status") != "COMPLETE":
            continue
        prov_p = run_dir / "11_figures" / f"{fid}.provenance.json"
        if not prov_p.exists():
            problems.append(f"{fid}: provenance missing")
            continue
        prov = json.loads(prov_p.read_text(encoding="utf-8"))
        data_p = run_dir / "10_plot_data" / prov["data_csv"]
        if not data_p.exists() or hashlib.sha256(data_p.read_bytes()).hexdigest() != prov["data_sha256"]:
            problems.append(f"{fid}: plot data missing or changed after rendering")
            continue
        with open(data_p, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if fid in POINT_RULES and POINT_RULES[fid](rows) != prov["n_points"]:
            problems.append(f"{fid}: plotted points {prov['n_points']} != data rule {POINT_RULES[fid](rows)}")
        for name in prov["files"]:
            fp = run_dir / "11_figures" / name
            if not fp.exists() or fp.stat().st_size == 0:
                problems.append(f"{fid}: figure file missing/empty {name}")
            elif fp.suffix == ".png":
                try:
                    img = mpimg.imread(fp)
                    if img.size == 0:
                        problems.append(f"{fid}: empty PNG")
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{fid}: PNG does not open ({exc})")
            elif fp.suffix == ".pdf" and not fp.read_bytes()[:5] == b"%PDF-":
                problems.append(f"{fid}: PDF header invalid")
    # 6. plot data recomputation for F02/F03
    from cape import metrics

    cells = metrics.aggregate_cells([_row(m) for m in ms])
    for fid, key in (("F02_bpv_vs_encode", "encode_ns_median"), ("F03_bpv_vs_decode", "decode_ns_median")):
        if figs.get(fid, {}).get("status") != "COMPLETE":
            continue
        with open(run_dir / "10_plot_data" / f"{fid}.csv", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                c = cells.get((r["sample_id"], r["method"], "B"))
                if c is None or not math.isclose(float(r["bpv"]), c["bpv"], rel_tol=1e-9) or \
                        not math.isclose(float(r["time_ms"]), c[key] / 1e6, rel_tol=1e-9):
                    problems.append(f"{fid}: plot value for {r['sample_id']}/{r['method']} differs from records")
                    break
    # 5. paired comparisons share inputs/configs and have the planned repeats
    reps = cfg["benchmark"]["repeats"]
    new, base = cfg["primary"]["new"], cfg["primary"]["baseline"]
    for sid in {m["sample_id"] for m in ms}:
        a = [m for m in ms if m["sample_id"] == sid and m["method_id"] == new and m["panel"] == "B" and m["wrapper"] == "none"]
        b = [m for m in ms if m["sample_id"] == sid and m["method_id"] == base and m["panel"] == "B" and m["wrapper"] == "none"]
        if a and b:
            if {m["input_hash"] for m in a} != {m["input_hash"] for m in b} or \
                    {m["config_hash"] for m in a} != {m["config_hash"] for m in b}:
                problems.append(f"{sid}: primary pair measured on different inputs/configs")
            if len(a) != reps or len(b) != reps:
                problems.append(f"{sid}: primary pair repeats {len(a)}/{len(b)} != planned {reps}")
    # 8. missing applicable artifacts
    statuses = write_statuses(run_dir)
    missing_rows = [{"section": s, "reason": v["reason"]} for s, v in statuses.items() if v["status"] == "PARTIAL"]
    buf = "section,reason\n" + "".join(f"{r['section']},\"{r['reason']}\"\n" for r in missing_rows)
    atomic_write_text(run_dir / "15_reports" / "artifact_missing.csv", buf)
    for r in missing_rows:
        problems.append(f"{r['section']}: {r['reason']}")
    # 9. final report shows failures and regressions
    rep = run_dir / "15_reports" / "final_report_UZ.md"
    text = rep.read_text(encoding="utf-8") if rep.exists() else ""
    for status in sorted({m["status"] for m in ms if m["status"] != "OK"}):
        if f"| {status} |" not in text:
            problems.append(f"final report does not list failure status {status}")
    pps = run_dir / "12_tables" / "per_sample_primary.csv"
    if pps.exists():
        with open(pps, encoding="utf-8", newline="") as fh:
            regressions = [r["sample_id"] for r in csv.DictReader(fh) if float(r["gain_percent"] or 0) < 0]
        for sid in regressions:
            if sid not in text:
                problems.append(f"final report hides regression on {sid}")
    if not text:
        problems.append("final_report_UZ.md missing")
    manifest = build_manifest(run_dir)
    checks["artifacts"] = len(manifest)
    result = {"ok": not problems, "problems": problems, "checks": checks, "verified_at": now_iso()}
    atomic_write_text(run_dir / "15_reports" / "verification.json", json.dumps(result, indent=2))
    return result


def _row(m: dict) -> dict:
    m = dict(m)
    m["lossless"] = None if m["lossless"] is None else bool(m["lossless"])
    m["is_synthetic"] = None if m["is_synthetic"] is None else bool(m["is_synthetic"])
    return m
