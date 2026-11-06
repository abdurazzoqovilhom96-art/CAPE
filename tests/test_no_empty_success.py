"""Empty or placeholder outputs are never success (spec sections 35, 37): header-only CSVs,
zero-byte artifacts and real runs without a real measurement fail verification."""

from __future__ import annotations

import json

from cape.artifact_manifest import verify_run, write_statuses
from cape.provenance import ROOT
from cape.result_store import ResultStore


def _run_dir(tmp_path, require_real: bool):
    rd = tmp_path / "run"
    cfg = "configs/pilot.yaml" if require_real else "configs/smoke.yaml"
    (rd / "05_raw_metrics").mkdir(parents=True)
    (rd / "run_manifest.json").write_text(json.dumps({"run_id": "r", "config_path": str(ROOT / cfg)}))
    st = ResultStore(rd / "05_raw_metrics" / "run.sqlite")
    st.add_tasks([{"task_id": "t0", "kind": "timed", "sample_id": "s", "method_id": "raw", "wrapper": "none",
                   "panel": "B", "repeat": 0, "split": "synthetic", "ordinal": 0, "resume_key": "k"}])
    st.commit_measurement({"task_id": "t0", "status": "OK", "lossless": True, "total_bytes": 10, "encode_ns": 5,
                           "decode_ns": 5, "bitstream_sha256": "0" * 64, "panel": "B", "is_synthetic": True,
                           "method_id": "raw", "wrapper": "none", "sample_id": "s", "input_hash": "h",
                           "config_hash": "c", "canonical_shape": [1, 1, 10], "original_dtype": "uint8",
                           "split": "synthetic"}, "COMMITTED")
    st.close()
    (rd / "05_raw_metrics" / "results.csv").write_text("measurement_id,run_id\n")  # header only
    return rd


def test_header_only_results_fail(tmp_path):
    res = verify_run(_run_dir(tmp_path, require_real=False))
    assert not res["ok"]
    assert any("header-only" in p for p in res["problems"])


def test_real_run_without_real_measurement_fails(tmp_path):
    res = verify_run(_run_dir(tmp_path, require_real=True))
    assert any("real run without" in p for p in res["problems"])


def test_zero_byte_required_artifact_is_partial(tmp_path):
    rd = _run_dir(tmp_path, require_real=False)
    (rd / "15_reports").mkdir(parents=True, exist_ok=True)
    for name in ("LIVE_REPORT_UZ.md", "final_report_UZ.md", "RESULTS_INDEX.md"):
        (rd / "15_reports" / name).write_text("x")
    (rd / "15_reports" / "final_report_UZ.md").write_bytes(b"")
    st = write_statuses(rd)
    assert st["15_reports"]["status"] == "PARTIAL" and "final_report_UZ.md" in st["15_reports"]["reason"]
