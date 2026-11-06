"""Blocker and partial reports (spec sections 35, 36): stdlib-only blocker report with no
numbers; partial finalization isolates failing steps and never writes SUCCESS.json."""

from __future__ import annotations

import json

from cape import finalizer


def test_blocker_report_has_reason_and_no_numbers(tmp_path):
    finalizer.blocker_report(tmp_path, "PREFLIGHT failed: compiler missing",
                             [{"step": "native", "status": "FAILED", "detail": "g++ not found"}])
    rep = (tmp_path / "15_reports" / "final_report_UZ.md").read_text(encoding="utf-8")
    assert "BLOCKED" in rep and "compiler missing" in rep and "g++ not found" in rep
    for sec in finalizer.SECTIONS:
        st = json.loads((tmp_path / sec / "STATUS.json").read_text(encoding="utf-8"))
        assert st["status"] == "PARTIAL" and st["completed"] is False
    assert not (tmp_path / "SUCCESS.json").exists()


def test_partial_finalization_isolates_failing_steps(tmp_path, monkeypatch):
    from cape import artifact_manifest, plots, reporting

    calls = []
    monkeypatch.setattr(reporting, "aggregate", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(plots, "render_all", lambda ctx, preliminary=False: calls.append("plots") or {})
    monkeypatch.setattr(reporting, "write_reports", lambda ctx, **kw: calls.append(("reports", kw["status"])))
    monkeypatch.setattr(artifact_manifest, "write_statuses", lambda rd, s=None: calls.append("statuses"))
    monkeypatch.setattr(reporting, "write_results_index", lambda ctx, s, f: calls.append("index"))
    logs = []

    class Ctx:
        run_dir = tmp_path

        def log(self, msg, level="INFO"):
            logs.append((level, msg))

    finalizer.finalize_partial(Ctx(), "INTERRUPTED", "test")
    assert calls == ["plots", ("reports", "INTERRUPTED"), "statuses", "index"]  # continued after the failure
    assert any(level == "ERROR" and "aggregate" in msg for level, msg in logs)
    assert not (tmp_path / "SUCCESS.json").exists()
