"""Acceptance tests T1-T12 (spec section 38): the automatic-export contract, exercised by
running the real entry point (run_all.py) on tiny fixtures in an isolated results root.
Fault injection uses test hooks that are recorded in run_manifest.json and in the report."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from cape import data_prep
from cape import synthetic as syn
from cape.canonical import to_canonical
from cape.certificate_verify import verify_scope
from cape.dataset_manifest import write_manifest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
pytestmark = pytest.mark.acceptance

BASE_CFG = {
    "schema_version": 1, "project": "CAPE-Pins", "seed": 20261105, "mode": "smoke",
    "description": "acceptance fixture (not a paper result)",
    "input": {"manifest": "data/manifests/unused.jsonl", "splits": ["synthetic", "development"]},
    "algorithm": {"exact_max_transitions_total": 5_000_000, "local_checks_total": 20_000},
    "benchmark": {"warmups": 0, "repeats": 2, "min_batch_ms": 0, "small_task_ms": 0, "task_timeout_s": 120,
                  "process_memory_gib": 4, "max_total_working_memory_gib": 6, "memory_profile_separate": False,
                  "external_wrappers": ["none"], "min_free_disk_gib": 1, "pin_timing_cpu": False},
    "outputs": {"live_plot_every": 1000},
    "methods": ["cape_m0", "crackle_pins_opt_m0", "zstd3", "raw", "cape_core", "stock_cover"],
    "panels": ["A", "B"],
    "oracle": {"enabled": True, "max_cc": 30, "max_components": 20, "time_limit_s": 5},
}


@pytest.fixture(scope="module")
def area(tmp_path_factory):
    base = tmp_path_factory.mktemp("acceptance")
    (base / "cfg").mkdir()
    data = base / "data"
    rows = []
    for name, vol in (("cyl", syn.vertical_cylinders((12, 24, 24), n=5, seed=3)),
                      ("noise", syn.noise((6, 12, 12), n_labels=4, seed=4))):
        canon, _ = to_canonical(vol, "ZYX")
        rows.append(data_prep.make_row(canon, data / f"syn_{name}.npy", sample_id=f"syn_{name}", family_id="synthetic",
                                       source_id=f"synthetic:{name}", specimen_id=None, macroblock_id=f"syn_{name}",
                                       split="synthetic", is_synthetic=True, license="generated",
                                       selection_rule="acceptance fixture"))
    real = data_prep.crackle_sample_rows(data / "real", crop_xyz=(32, 32, 16), per_file={"connectomics": 2})
    assert len(real) == 2, "the Crackle repository sample is required for the acceptance fixtures"
    dev, held = real
    write_manifest(base / "tiny.jsonl", rows + [dev])
    write_manifest(base / "synthetic_only.jsonl", rows)
    held = dict(held, split="heldout")
    write_manifest(base / "heldout.jsonl", [held])
    return base


def run_cape(area: Path, args: list[str], cfg: dict | None = None, env: dict | None = None, name: str = "cfg",
             timeout: int = 900) -> tuple[int, Path | None, str]:
    cmd = [sys.executable, str(ROOT / "run_all.py"), *args]
    if cfg is not None:
        p = area / "cfg" / f"{name}.yaml"
        p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        cmd += ["--config", str(p)]
    e = dict(os.environ, CAPE_RESULTS_ROOT=str(area / "results"), CAPE_RELEASE_ROOT=str(area / "release"),
             CAPE_FREEZE_ROOT=str(area / "frozen"), CAPE_METHODS_FILE=str(FIX / "methods_test.yaml"),
             PYTHONIOENCODING="utf-8")
    e.update(env or {})
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, env=e)
    run_dir = None
    for line in out.stdout.splitlines():
        if line.startswith("run: "):
            run_dir = Path(line[5:].strip())
    return out.returncode, run_dir, out.stdout + out.stderr


def db_rows(run_dir: Path, sql: str):
    con = sqlite3.connect(run_dir / "05_raw_metrics" / "run.sqlite")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def complete_run(area):
    rc, run_dir, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl")], BASE_CFG, name="t1")
    return rc, run_dir, log


def test_T1_normal_completion(complete_run, area):
    rc, rd, log = complete_run
    assert rc == 0, log[-3000:]
    for rel in ["05_raw_metrics/results.csv", "05_raw_metrics/measurements.jsonl", "12_tables/results_overall.csv",
                "12_tables/results_overall.md", "12_tables/results_overall.tex", "11_figures/F01_algorithm.png",
                "11_figures/F02_bpv_vs_encode.pdf", "15_reports/final_report_UZ.md", "15_reports/RESULTS_INDEX.md",
                "15_reports/claim_gate.json", "09_statistics/summary.json", "SUCCESS.json"]:
        assert (rd / rel).exists() and (rd / rel).stat().st_size > 0, rel
    assert sum(1 for _ in open(rd / "05_raw_metrics" / "results.csv", encoding="utf-8")) > 1
    zips = list((area / "release" / rd.name).glob("*.zip"))
    assert len(zips) == 2 and (area / "release" / rd.name / "SHA256SUMS.txt").exists()
    assert "test_hooks" in json.loads((rd / "run_manifest.json").read_text(encoding="utf-8"))


def test_T2_negative_result_is_reported(area):
    # Genuine negative result on this fixture: on a 32x32x16 crop the Crackle container overhead
    # (per-slice z-index and CRCs) makes CAPE larger than a plain zstd3 stream.
    cfg = dict(BASE_CFG, primary={"new": "cape_m0", "baseline": "zstd3"})
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests"], cfg,
                           name="t2")
    assert rc == 0, log[-3000:]
    with open(rd / "12_tables" / "per_sample_primary.csv", encoding="utf-8") as fh:
        import csv

        rows = list(csv.DictReader(fh))
    assert rows and all(float(r["gain_percent"]) < 0 for r in rows)  # negative gains kept, not clipped
    summary = json.loads((rd / "09_statistics" / "summary.json").read_text(encoding="utf-8"))
    assert summary["scientific_outcome"] == "REGRESSED"
    assert summary["primary"]["n_regressions"] == len(rows)
    report = (rd / "15_reports" / "final_report_UZ.md").read_text(encoding="utf-8")
    assert all(r["sample_id"] in report for r in rows)


def test_T3_worker_failure_is_isolated(area):
    cfg = dict(BASE_CFG, methods=BASE_CFG["methods"] + ["test_raising"])
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests"], cfg,
                           name="t3")
    assert rc == 0, log[-3000:]
    bad = db_rows(rd, "SELECT status, reason FROM measurements WHERE method_id='test_raising'")
    assert bad and all(s == "FAILED_LOSSLESS" and "injected adapter failure" in r for s, r in bad)
    ok = db_rows(rd, "SELECT COUNT(*) FROM measurements WHERE method_id='cape_m0' AND status='OK'")[0][0]
    assert ok > 0
    assert "| FAILED_LOSSLESS |" in (rd / "15_reports" / "final_report_UZ.md").read_text(encoding="utf-8")


def test_T4_lossless_failure_never_wins(area):
    cfg = dict(BASE_CFG, methods=BASE_CFG["methods"] + ["test_corrupting"])
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests"], cfg,
                           name="t4")
    assert rc == 0, log[-3000:]
    rows = db_rows(rd, "SELECT status, lossless FROM measurements WHERE method_id='test_corrupting'")
    assert rows and all(s == "FAILED_LOSSLESS" and not lossless for s, lossless in rows)
    with open(rd / "12_tables" / "results_overall.csv", encoding="utf-8") as fh:
        import csv

        t = {r["method"]: r for r in csv.DictReader(fh)}
    assert t["test_corrupting"]["ok_samples"] == "0" and t["test_corrupting"]["total_bytes"] == ""
    gate = json.loads((rd / "15_reports" / "claim_gate.json").read_text(encoding="utf-8"))
    assert gate["lossless"]["value"] is True  # CAPE rows unaffected


def test_T5_controlled_interrupt_keeps_commits(area):
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests"],
                           BASE_CFG, env={"CAPE_TEST_INTERRUPT_AFTER": "5"}, name="t5")
    assert rc == 5, log[-3000:]
    assert db_rows(rd, "SELECT COUNT(*) FROM measurements")[0][0] == 5
    assert db_rows(rd, "SELECT COUNT(*) FROM tasks WHERE status='PENDING'")[0][0] > 0
    assert json.loads((rd / "run_manifest.json").read_text(encoding="utf-8"))["status"] == "INTERRUPTED"
    assert "INTERRUPTED" in (rd / "15_reports" / "final_report_UZ.md").read_text(encoding="utf-8")
    assert not (rd / "SUCCESS.json").exists()


def test_T6_hard_kill_and_recovery(area):
    cfg = dict(BASE_CFG, benchmark=dict(BASE_CFG["benchmark"], repeats=25))  # long enough to kill mid-run
    p = area / "cfg" / "t6.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    env = dict(os.environ, CAPE_RESULTS_ROOT=str(area / "results"), CAPE_RELEASE_ROOT=str(area / "release"),
               CAPE_FREEZE_ROOT=str(area / "frozen"), CAPE_METHODS_FILE=str(FIX / "methods_test.yaml"))
    proc = subprocess.Popen([sys.executable, str(ROOT / "run_all.py"), "--stage", "smoke", "--manifest",
                             str(area / "tiny.jsonl"), "--skip-tests", "--config", str(p)], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    run_dir = None
    deadline = time.time() + 300
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line.startswith("run: "):
            run_dir = Path(line[5:].strip())
            break
    assert run_dir is not None
    db = run_dir / "05_raw_metrics" / "run.sqlite"
    while time.time() < deadline:
        if db.exists():
            try:
                if db_rows(run_dir, "SELECT COUNT(*) FROM measurements")[0][0] >= 3:
                    break
            except sqlite3.Error:
                pass
        time.sleep(0.2)
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    proc.wait(timeout=60)
    committed = db_rows(run_dir, "SELECT COUNT(*) FROM measurements")[0][0]
    assert committed >= 3
    rc, _, log = run_cape(area, ["--stage", "recover", "--run-dir", str(run_dir)])
    assert rc == 0, log[-3000:]
    assert db_rows(run_dir, "SELECT COUNT(*) FROM tasks WHERE status='RUNNING'")[0][0] == 0
    assert db_rows(run_dir, "SELECT COUNT(*) FROM measurements")[0][0] >= committed  # nothing lost
    rc, rd2, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests",
                                   "--resume", "--config", str(p)])
    assert rc == 0, log[-3000:]
    assert rd2 == run_dir
    n_tasks = db_rows(run_dir, "SELECT COUNT(*) FROM tasks")[0][0]
    n_meas, n_distinct = db_rows(run_dir, "SELECT COUNT(*), COUNT(DISTINCT task_id) FROM measurements")[0]
    assert n_meas == n_distinct == n_tasks  # interrupted task re-ran once, no duplicates


def test_T7_report_only_rebuild(complete_run, area):
    _rc, rd, _ = complete_run
    n_before = db_rows(rd, "SELECT COUNT(*) FROM measurements")[0][0]
    for f in list((rd / "11_figures").glob("*.png")) + list((rd / "12_tables").glob("*.md")):
        f.unlink()
    rc, _, log = run_cape(area, ["--stage", "report", "--run-dir", str(rd)])
    assert rc == 0, log[-3000:]
    assert (rd / "11_figures" / "F01_algorithm.png").exists() and (rd / "12_tables" / "results_overall.md").exists()
    assert db_rows(rd, "SELECT COUNT(*) FROM measurements")[0][0] == n_before  # no new encoding


def test_T8_empty_artifact_blocks_success(complete_run, area):
    _rc, rd, _ = complete_run
    copy = area / "results" / (rd.name + "_t8copy")
    shutil.copytree(rd, copy)
    (copy / "12_tables" / "results_overall.csv").write_bytes(b"")
    (copy / "SUCCESS.json").unlink()
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_results.py"), "--run-dir", str(copy)],
                         cwd=ROOT, capture_output=True, text=True, env=dict(os.environ,
                                                                           CAPE_METHODS_FILE=str(FIX / "methods_test.yaml")))
    assert out.returncode == 6, out.stdout + out.stderr
    assert "12_tables" in (copy / "15_reports" / "artifact_missing.csv").read_text(encoding="utf-8")
    assert not (copy / "SUCCESS.json").exists()


def test_T9_no_real_data_is_blocked(area):
    cfg = dict(BASE_CFG, input={"manifest": "x.jsonl", "splits": ["synthetic", "development"], "require_real_data": True})
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "synthetic_only.jsonl"), "--skip-tests"],
                           cfg, name="t9")
    assert rc == 2, log[-3000:]
    report = (rd / "15_reports" / "final_report_UZ.md").read_text(encoding="utf-8")
    assert "BLOCKED_DATA" in report
    dbp = rd / "05_raw_metrics" / "run.sqlite"
    assert not dbp.exists() or db_rows(rd, "SELECT COUNT(*) FROM measurements")[0][0] == 0  # no synthetic fallback
    assert not (rd / "SUCCESS.json").exists()


def test_T10_plot_failure_is_explicit(area):
    rc, rd, log = run_cape(area, ["--stage", "smoke", "--manifest", str(area / "tiny.jsonl"), "--skip-tests"],
                           BASE_CFG, env={"CAPE_TEST_FAIL_FIGURE": "F02_bpv_vs_encode"}, name="t10")
    assert rc == 6, log[-3000:]
    st = json.loads((rd / "11_figures" / "figures_status.json").read_text(encoding="utf-8"))
    assert st["F02_bpv_vs_encode"]["status"] == "REPORT_FAILED"
    assert not (rd / "11_figures" / "F02_bpv_vs_encode.png").exists()  # no fake figure
    assert (rd / "12_tables" / "results_overall.md").exists() and (rd / "05_raw_metrics" / "results.csv").exists()
    assert not (rd / "SUCCESS.json").exists()
    stages = dict(db_rows(rd, "SELECT name, status FROM stages"))
    assert stages["RENDERED"] != "COMPLETE"


def test_T11_auto_freeze_before_heldout_metrics(area):
    cfg = dict(BASE_CFG, mode="benchmark", input={"manifest": "x.jsonl", "splits": ["heldout"], "require_real_data": True})
    before = set((area / "frozen").glob("*.json")) if (area / "frozen").exists() else set()
    rc, rd, log = run_cape(area, ["--stage", "all", "--manifest", str(area / "heldout.jsonl"), "--skip-tests"], cfg,
                           name="t11")
    assert rc == 0, log[-3000:]
    new = set((area / "frozen").glob("*.json")) - before
    assert len(new) == 1
    freeze = json.loads(next(iter(new)).read_text(encoding="utf-8"))
    first = db_rows(rd, "SELECT MIN(committed_at) FROM measurements")[0][0]
    assert freeze["created_at"] <= first
    gate = json.loads((rd / "15_reports" / "claim_gate.json").read_text(encoding="utf-8"))
    assert gate["heldout_complete"]["value"] is True


def test_T12_mixed_scope_is_rejected(complete_run):
    _rc, rd, _ = complete_run
    certs = [json.loads(line) for line in open(rd / "06_solver_certificates" / "certificates.jsonl", encoding="utf-8")]
    assert certs
    c = certs[0]
    assert c["verifier_result"] == "VALID" and c["lb_bytes"] <= c["ub_bytes"]
    ub_scope = {"regime_id": c["regime_id"], "header_bytes": c["label_ub_bytes"] - c["label_lb_bytes"],
                "candidate_policy": c["candidate_policy"], "background": c["background"]}
    lb_scope = dict(ub_scope, regime_id=c["regime_id"] + "-safe-count", header_bytes=ub_scope["header_bytes"] + 2)
    assert verify_scope(ub_scope, ub_scope) == []
    assert verify_scope(ub_scope, lb_scope)
