"""Live outputs after every committed task (spec section 35.1/35.2)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from cape.live_report import LiveReporter
from cape.result_store import ResultStore


def test_each_commit_updates_live_files(tmp_path):
    for sec in ("05_raw_metrics", "15_reports", "11_figures", "10_plot_data", "14_logs"):
        (tmp_path / sec).mkdir()
    store = ResultStore(tmp_path / "05_raw_metrics" / "run.sqlite")
    tasks = [{"task_id": f"t{i}", "kind": "timed", "sample_id": "s", "method_id": "raw", "wrapper": "none",
              "panel": "B", "repeat": i, "split": "synthetic", "ordinal": i, "resume_key": f"k{i}"} for i in range(3)]
    store.add_tasks(tasks)
    ctx = SimpleNamespace(store=store, run_id="r", run_dir=tmp_path, cfg={"outputs": {"live_plot_every": 1000},
                                                                         "primary": {"new": "cape_m0",
                                                                                     "baseline": "crackle_pins_opt_m0"}},
                          path=lambda sec, name="": tmp_path / sec / name if name else tmp_path / sec,
                          log=lambda *a, **k: None, hashes={})
    live = LiveReporter(ctx)
    for i in range(3):
        row = {"task_id": f"t{i}", "status": "OK" if i < 2 else "TIMEOUT", "reason": None if i < 2 else "slow",
               "sample_id": "s", "method_id": "raw", "wrapper": "none", "panel": "B", "canonical_shape": [1, 1, 4],
               "original_dtype": "uint8", "is_synthetic": True, "lossless": i < 2, "total_bytes": 40 if i < 2 else None,
               "encode_ns": 5 if i < 2 else None, "decode_ns": 5 if i < 2 else None, "split": "synthetic"}
        store.commit_measurement(row, "COMMITTED" if i < 2 else "FAILED")
        live.update(row)
        lines = (tmp_path / "05_raw_metrics" / "results_live.csv").read_text(encoding="utf-8").splitlines()
        assert len(lines) == i + 2  # header + one line per committed task, immediately
        prog = json.loads((tmp_path / "15_reports" / "progress.json").read_text(encoding="utf-8"))
        assert prog["tasks_done"] == i + 1
    assert prog["failures"] == 1
    live.flush(final=True)
    assert "PRELIMINARY" in (tmp_path / "15_reports" / "LIVE_REPORT_UZ.md").read_text(encoding="utf-8")
    store.close()
