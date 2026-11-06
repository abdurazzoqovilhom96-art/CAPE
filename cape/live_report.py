"""Live progress (spec section 35.2): after every committed task progress.json is rewritten
atomically and the row is appended to results_live.csv; LIVE_REPORT_UZ.md is refreshed at most
once per second and at stage ends; PRELIMINARY figures every `live_plot_every` commits, always
between timed tasks (the worker is idle). A torn last CSV line after a hard kill is rebuilt from
SQLite by `--stage recover`."""

from __future__ import annotations

import csv
import io
import json
import os
import time
from collections import defaultdict

from cape.result_store import ALL_FIELDS, atomic_write_text, now_iso


class LiveReporter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.csv_path = ctx.path("05_raw_metrics", "results_live.csv")
        self.n_commits = 0
        self.last_report = 0.0
        self.status_counts: dict = defaultdict(int)
        self.last_commit = None
        self.started = time.time()
        self.t_per_task: list[float] = []
        self._last_t = time.time()
        if not self.csv_path.exists():
            self._rewrite_csv_from_store()

    def _rewrite_csv_from_store(self) -> None:
        rows = self.ctx.store.measurements()
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["measurement_id"] + ALL_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in ["measurement_id"] + ALL_FIELDS})
            self.status_counts[r["status"]] += 1
        atomic_write_text(self.csv_path, buf.getvalue())

    def _safe(self, name: str, fn) -> None:
        """Live files are conveniences rebuilt from SQLite; a failure (e.g. a file held open by
        a viewer) is logged and never stops the benchmark."""
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            self.ctx.log(f"live output {name} skipped this time: {exc}", "WARN")

    def update(self, row: dict) -> None:
        self.n_commits += 1
        self.status_counts[row["status"]] += 1
        self.last_commit = now_iso()
        now = time.time()
        self.t_per_task.append(now - self._last_t)
        self._last_t = now
        self._safe("results_live.csv", lambda: self._append_csv(row))
        self._safe("progress.json", self._progress)
        if now - self.last_report >= 1.0:
            self._safe("LIVE_REPORT_UZ.md", self._live_markdown)
            self.last_report = now
        every = self.ctx.cfg["outputs"]["live_plot_every"]
        if self.n_commits % every == 0:
            self._live_plots()

    def _append_csv(self, row: dict) -> None:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["measurement_id"] + ALL_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in ["measurement_id"] + ALL_FIELDS})
        with open(self.csv_path, "a", encoding="utf-8", newline="") as fh:
            fh.write(buf.getvalue())
            fh.flush()
            os.fsync(fh.fileno())

    def _progress(self) -> None:
        counts = self.ctx.store.task_counts()
        total = sum(counts.values())
        done = total - counts.get("PENDING", 0) - counts.get("RUNNING", 0)
        recent = self.t_per_task[-50:]
        eta = (sum(recent) / len(recent)) * (total - done) if recent else None
        atomic_write_text(self.ctx.path("15_reports", "progress.json"), json.dumps({
            "run_id": self.ctx.run_id, "stage": "BENCHMARK", "tasks_total": total, "tasks_done": done,
            "task_counts": counts, "measurement_status_counts": dict(self.status_counts),
            "failures": sum(v for k, v in self.status_counts.items() if k != "OK"), "last_commit": self.last_commit,
            "eta_seconds_estimate": round(eta, 1) if eta is not None else None,
            "note": "eta is an estimate from recent task durations, not a promise"}, indent=2))

    def _live_markdown(self) -> None:
        from cape import metrics

        rows = self.ctx.store.measurements()
        cells = metrics.aggregate_cells(rows)
        new, base = self.ctx.cfg["primary"]["new"], self.ctx.cfg["primary"]["baseline"]
        lines = [f"# LIVE REPORT (PRELIMINARY) — `{self.ctx.run_id}`", "",
                 f"Yangilangan: {now_iso()}; commit qilingan o'lchovlar: {len(rows)}; holatlar: "
                 f"{dict(self.status_counts)}", "",
                 "Bu oraliq holat: 7 repeat tugamaguncha median/CI yakuniy emas.", "",
                 f"## {new} va {base} (tugallangan namunalar)", "",
                 "| Namuna | CAPE bayt | Stock bayt | Yutuq % |", "|---|---|---|---|"]
        for (sid, key, panel), c in sorted(cells.items()):
            if key != new or panel != "B" or not c.get("total_bytes"):
                continue
            b = cells.get((sid, base, "B"))
            if b and b.get("total_bytes"):
                lines.append(f"| {sid} | {c['total_bytes']} | {b['total_bytes']} | "
                             f"{100 * (1 - c['total_bytes'] / b['total_bytes']):.3f} |")
        fails = [r for r in rows if r["status"] != "OK"][-15:]
        lines += ["", "## Oxirgi muvaffaqiyatsiz/qo'llanmagan o'lchovlar", ""]
        lines += [f"- {r['sample_id']} / {metrics.mkey(r)}: {r['status']} — {r['reason']}" for r in fails] or ["- yo'q"]
        atomic_write_text(self.ctx.path("15_reports", "LIVE_REPORT_UZ.md"), "\n".join(lines) + "\n")

    def _live_plots(self) -> None:
        try:
            from cape import plots

            plots.render_all(self.ctx, preliminary=True, only=["F02_bpv_vs_encode", "F04_per_dataset_gain"])
        except Exception as exc:  # noqa: BLE001 - live plots never stop a run
            self.ctx.log(f"live plot skipped: {exc}", "WARN")

    def flush(self, final: bool = False) -> None:
        self._safe("progress.json", self._progress)
        self._safe("LIVE_REPORT_UZ.md", self._live_markdown)
