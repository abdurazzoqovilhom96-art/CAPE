"""Partial and blocker reports (spec sections 35, 36). Runs in `finally` paths: every
post-processing step is isolated, errors are logged, and SUCCESS.json is never written here.
blocker_report() uses only the standard library (it must work when installation failed)."""

from __future__ import annotations

import datetime as _dt
import json
import os
import traceback
from pathlib import Path

SECTIONS = ["01_environment", "02_data_manifest", "03_bitstreams", "04_roundtrip", "05_raw_metrics",
            "06_solver_certificates", "07_component_stats", "08_ablations", "09_statistics", "10_plot_data",
            "11_figures", "12_tables", "13_paper_assets", "14_logs", "15_reports"]


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def blocker_report(run_dir: Path, message: str, steps: list[dict] | None = None) -> None:
    run_dir = Path(run_dir)
    for sec in SECTIONS:
        (run_dir / sec).mkdir(parents=True, exist_ok=True)
        _write(run_dir / sec / "STATUS.json", json.dumps({
            "section": sec, "applicable": True, "completed": False, "status": "PARTIAL",
            "artifacts": [], "reason": f"run BLOCKED before results: {message}", "updated_at": _now()}, indent=2))
    lines = [f"# CAPE-Pins hisobot — BLOCKED", "", f"Vaqt: {_now()}", "",
             "Run real natija chiqarmasdan to'xtadi. Hech qanday raqamli natija yaratilmagan.", "",
             "## Sabab", "", f"```\n{message}\n```", ""]
    if steps:
        lines += ["## Bootstrap qadamlari", "", "| Qadam | Holat | Izoh |", "|---|---|---|"]
        lines += [f"| {s['step']} | {s['status']} | {s.get('detail', '')} |" for s in steps]
        lines.append("")
    lines += ["## Keyingi qadam", "", "Yuqoridagi sababni bartaraf etib, buyruqni qayta ishga tushiring "
              "(`--resume` bilan). Batafsil: `docs/REPRODUCE_UZ.md`, loglar: `14_logs/`.", ""]
    _write(run_dir / "15_reports" / "final_report_UZ.md", "\n".join(lines))
    _write(run_dir / "15_reports" / "RESULTS_INDEX.md",
           f"# RESULTS INDEX — BLOCKED\n\nSabab: {message}\n\nHisobot: 15_reports/final_report_UZ.md\n")
    _write(run_dir / "15_reports" / "LIVE_REPORT_UZ.md", f"# LIVE REPORT\n\nRun BLOCKED: {message}\n")


def finalize_partial(ctx, status: str, message: str) -> None:
    def attempt(name, fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            ctx.log(f"partial finalization step {name} failed: {exc}\n{traceback.format_exc()[-800:]}", "ERROR")

    from cape import artifact_manifest, plots, reporting

    figs = {}

    def do_figs():
        figs.update(plots.render_all(ctx, preliminary=False))

    attempt("aggregate", lambda: reporting.aggregate(ctx))
    attempt("figures", do_figs)
    attempt("reports", lambda: reporting.write_reports(ctx, figures=figs, status=status, message=message))
    attempt("statuses", lambda: artifact_manifest.write_statuses(ctx.run_dir, status))
    attempt("index", lambda: reporting.write_results_index(ctx, status, figs))
    ctx.log(f"partial report written (status {status}): {message}")
