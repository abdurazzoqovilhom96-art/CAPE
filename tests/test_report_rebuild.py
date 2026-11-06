"""Report-only rebuild (spec section 40): refuses runs without committed measurements and never
encodes; the end-to-end rebuild is acceptance test T7."""

from __future__ import annotations

import json

from cape.cli import report_only
from cape.provenance import ROOT
from cape.result_store import ResultStore


def test_report_only_refuses_runs_without_measurements(tmp_path):
    rd = tmp_path / "run"
    (rd / "05_raw_metrics").mkdir(parents=True)
    (rd / "run_manifest.json").write_text(json.dumps({"run_id": "r", "config_path": str(ROOT / "configs/smoke.yaml"),
                                                      "source_hash": "x"}))
    ResultStore(rd / "05_raw_metrics" / "run.sqlite").close()
    assert report_only(rd) == 2
