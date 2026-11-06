"""Recovery after a hard stop (spec sections 30, 36, 40 `--stage recover`).

Keeps every committed row, never promotes half-written *.tmp files, returns RUNNING tasks to
PENDING, rebuilds live exports from SQLite and writes a partial report. The next
`--stage all --resume` continues the same run."""

from __future__ import annotations

import json
from pathlib import Path

from cape.result_store import ResultStore, atomic_write_text, now_iso


def recover(run_dir: Path, args: dict | None = None) -> dict:
    from cape import finalizer, live_report
    from cape.runner import load_context, update_run_manifest

    run_dir = Path(run_dir)
    tmp_removed = []
    for p in run_dir.rglob("*.tmp"):
        tmp_removed.append(p.relative_to(run_dir).as_posix())
        p.unlink(missing_ok=True)
    for p in run_dir.rglob("*.tmp.*"):
        tmp_removed.append(p.relative_to(run_dir).as_posix())
        p.unlink(missing_ok=True)
    store = ResultStore(run_dir / "05_raw_metrics" / "run.sqlite")
    reset = store.reset_running()
    missing_bitstreams = [m["measurement_id"] for m in store.measurements("status='OK' AND bitstream_path IS NOT NULL")
                          if not (run_dir / m["bitstream_path"]).exists()]
    counts = store.task_counts()
    store.event("WARN", f"recovery: {reset} RUNNING tasks reset to PENDING; {len(tmp_removed)} temp files removed")
    store.close()
    ctx = load_context(run_dir, args or {})
    (run_dir / "05_raw_metrics" / "results_live.csv").unlink(missing_ok=True)
    live_report.LiveReporter(ctx).flush()
    result = {"recovered_at": now_iso(), "tasks_reset_to_pending": reset, "temp_files_removed": tmp_removed,
              "task_counts": counts, "ok_rows_missing_bitstream": missing_bitstreams}
    atomic_write_text(run_dir / "14_logs" / "recovery.json", json.dumps(result, indent=2))
    try:
        from cape.runner import stage_data_validated

        stage_data_validated(ctx)
    except Exception as exc:  # noqa: BLE001
        ctx.log(f"recovery: data validation for the partial report failed: {exc}", "WARN")
    finalizer.finalize_partial(ctx, "INTERRUPTED", f"recovered: {reset} interrupted task(s) returned to PENDING; "
                                                   "continue with --stage all --resume")
    update_run_manifest(run_dir, status="INTERRUPTED", recovered_at=result["recovered_at"])
    ctx.store.close()
    return result
