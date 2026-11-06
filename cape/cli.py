"""Venv-side command dispatcher used by run_all.py (spec sections 30, 40).

    python -m cape.cli continue --run-dir DIR [--resume] [--skip-tests] [--manifest M] [--config C]
    python -m cape.cli report   --run-dir DIR   # statistics/tables/figures/reports from committed rows only
    python -m cape.cli recover  --run-dir DIR   # journal recovery + partial report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def report_only(run_dir: Path) -> int:
    """Rebuild every report artifact from committed measurements; never downloads, encodes,
    decodes or tunes anything."""
    from cape import finalizer, runner

    try:
        ctx = runner.load_context(run_dir, {"resume": True})
    except runner.StageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    if not (run_dir / "05_raw_metrics" / "run.sqlite").exists() or ctx.store.count_measurements() == 0:
        print("ERROR: this run has no committed measurements to report on", file=sys.stderr)
        return runner.EXIT_MISSING
    code = runner.EXIT_OK
    try:
        runner.stage_data_validated(ctx)
        runner.stage(ctx, "AGGREGATED", runner.stage_aggregated)
        runner.stage(ctx, "RENDERED", runner.stage_rendered)
        runner.stage(ctx, "VERIFIED", runner.stage_verified)
        runner.stage(ctx, "PACKAGED", runner.stage_packaged)
        status = "COMPLETE"
    except runner.StageError as exc:
        status, code = exc.run_status, exc.exit_code
        finalizer.finalize_partial(ctx, status, str(exc))
    runner.update_run_manifest(run_dir, report_rebuilt_at=__import__("cape.result_store").result_store.now_iso(),
                               report_status=status)
    runner._print_result_paths(run_dir, status, code)
    ctx.store.close()
    return code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cape.cli", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["continue", "report", "recover"])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--manifest")
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir).resolve()
    if not (run_dir / "run_manifest.json").exists():
        print(f"ERROR: {run_dir} is not a CAPE run directory", file=sys.stderr)
        return 2
    if args.command == "continue":
        from cape.runner import continue_run

        return continue_run(run_dir, {"resume": args.resume, "skip_tests": args.skip_tests,
                                      "manifest": args.manifest, "config": args.config})
    if args.command == "report":
        return report_only(run_dir)
    from cape.recovery import recover

    res = recover(run_dir, {"resume": True})
    print(f"recovered: {res['tasks_reset_to_pending']} task(s) back to PENDING; "
          f"{len(res['temp_files_removed'])} temp file(s) removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
