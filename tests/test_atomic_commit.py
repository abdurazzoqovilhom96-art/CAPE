"""SQLite journal semantics (spec sections 35.1, 36): one transaction per measurement, no
duplicate success, rollback on failure, statuses validated."""

from __future__ import annotations

import pytest

from cape.result_store import ResultStore, atomic_write_text


def _task(i: int) -> dict:
    return {"task_id": f"t{i}", "kind": "timed", "sample_id": "s", "method_id": "m", "wrapper": "none", "panel": "B",
            "repeat": i, "split": "development", "ordinal": i, "resume_key": f"k{i}"}


def test_commit_is_atomic_and_unique(tmp_path):
    st = ResultStore(tmp_path / "run.sqlite")
    assert st.add_tasks([_task(0), _task(1)]) == 2
    assert st.add_tasks([_task(0)]) == 0  # resume never duplicates tasks
    st.commit_measurement({"task_id": "t0", "status": "OK", "lossless": True, "total_bytes": 10}, "COMMITTED")
    with pytest.raises(ValueError):  # no duplicate success for a task
        st.commit_measurement({"task_id": "t0", "status": "OK", "lossless": True, "total_bytes": 10}, "COMMITTED")
    with pytest.raises(ValueError):
        st.commit_measurement({"task_id": "t1", "status": "WON", "total_bytes": 1}, "COMMITTED")
    with pytest.raises(Exception):  # unknown task id: foreign-key failure rolls back everything
        st.commit_measurement({"task_id": "nope", "status": "OK", "total_bytes": 1}, "COMMITTED")
    assert st.count_measurements() == 1
    assert {t["task_id"]: t["status"] for t in st.tasks()} == {"t0": "COMMITTED", "t1": "PENDING"}
    st.set_task("t1", "RUNNING")
    assert st.reset_running() == 1 and st.tasks("PENDING")[0]["task_id"] == "t1"
    st.close()


def test_atomic_write_survives_a_reader_holding_the_file(tmp_path):
    """Regression (pilot 2026-11-05): a viewer/monitor reading progress.json made os.replace fail
    with WinError 5 and stopped the benchmark."""
    import threading

    target = tmp_path / "progress.json"
    atomic_write_text(target, "old")
    fh = open(target, encoding="utf-8")  # held open like a viewer would
    threading.Timer(0.5, fh.close).start()
    atomic_write_text(target, "new")  # retries until the reader lets go
    assert target.read_text() == "new"


def test_live_output_failure_never_stops_the_run(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from cape import live_report

    logs = []
    ctx = SimpleNamespace(log=lambda msg, level="INFO": logs.append((level, msg)))
    rep = live_report.LiveReporter.__new__(live_report.LiveReporter)
    rep.ctx = ctx
    rep._safe("progress.json", lambda: (_ for _ in ()).throw(PermissionError("held open")))
    assert logs and logs[0][0] == "WARN"


def test_atomic_write_never_leaves_partial_target(tmp_path):
    target = tmp_path / "x.json"
    atomic_write_text(target, "old")
    try:
        atomic_write_text(target, object())  # type: ignore[arg-type]  - fails while writing the temp file
    except TypeError:
        pass
    assert target.read_text() == "old"
