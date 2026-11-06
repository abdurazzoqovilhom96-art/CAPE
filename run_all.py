"""CAPE-Pins one-command entry point (spec sections 30, 36, 40).

    python run_all.py --stage smoke
    python run_all.py --stage pilot --data data/real
    python run_all.py --stage all --manifest data/manifests/benchmark.jsonl --config configs/benchmark.yaml --resume
    python run_all.py --stage report --latest
    python run_all.py --stage recover --latest
    python run_all.py --fetch-data cremi

INIT and PREFLIGHT use only the standard library, so a failed installation still produces a
real BLOCKED report and logs. The remaining stages run inside the project venv.
Exit codes: 0 stage complete (not a claim that CAPE won), 2 missing config/data/dependency,
3 lossless/certificate failure, 4 incomplete required benchmark, 5 interruption, 6 report or
artifact verification failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cape.provenance import RESULTS_ROOT, active_test_hooks, source_tree_hash  # noqa: E402  (stdlib only)

VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STAGE_CONFIG = {"smoke": "configs/smoke.yaml", "pilot": "configs/pilot.yaml", "development": "configs/development.yaml",
                "oracle": "configs/oracle.yaml", "all": "configs/benchmark.yaml"}
SECTIONS = ["01_environment", "02_data_manifest", "03_bitstreams", "04_roundtrip", "05_raw_metrics",
            "06_solver_certificates", "07_component_stats", "08_ablations", "09_statistics", "10_plot_data",
            "11_figures", "12_tables", "13_paper_assets", "14_logs", "15_reports"]


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _results_root() -> Path:
    return RESULTS_ROOT


def _latest(args) -> Path:
    if args.run_dir:
        return Path(args.run_dir).resolve()
    ptr = _results_root() / "LATEST_RUN.txt"
    if not ptr.exists():
        raise SystemExit("ERROR: results/LATEST_RUN.txt not found: no run exists yet")
    p = Path(ptr.read_text(encoding="utf-8").strip())
    if not (p / "run_manifest.json").exists():
        raise SystemExit(f"ERROR: latest run pointer is stale: {p}")
    return p


def _identity(stage: str, config: Path, manifest: str | None, data: str | None, src: str) -> str:
    h = hashlib.sha256()
    h.update(stage.encode())
    h.update(config.read_bytes() if config.exists() else b"<missing config>")
    h.update((manifest or "").encode())
    if manifest and Path(manifest).exists():
        h.update(Path(manifest).read_bytes())
    h.update((data or "").encode())
    h.update(src.encode())
    return h.hexdigest()


def _find_resumable(identity: str) -> Path | None:
    best = None
    for rm in sorted(_results_root().glob("*/run_manifest.json")):
        try:
            data = json.loads(rm.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("identity") == identity and data.get("status") != "COMPLETE":
            best = rm.parent
    return best


def _venv_exec(cmd: list[str]) -> int:
    return subprocess.run([str(VENV_PY), *cmd], cwd=ROOT).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["smoke", "pilot", "development", "oracle", "all", "report", "recover"])
    ap.add_argument("--config")
    ap.add_argument("--manifest")
    ap.add_argument("--data")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--run-dir")
    ap.add_argument("--fetch-data", choices=["cremi"])
    ap.add_argument("--demo", action="store_true", help="alias of --stage smoke (synthetic + repository samples)")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args(argv)
    stage = "smoke" if args.demo else args.stage
    if stage is None and not args.fetch_data:
        ap.error("--stage is required (or --fetch-data)")

    from scripts.bootstrap import bootstrap  # standard library only

    if stage in ("report", "recover"):
        run_dir = _latest(args)
        if not VENV_PY.exists():
            ok, steps = bootstrap(run_dir / "14_logs" / "bootstrap.log", quiet=True)
            if not ok:
                print("ERROR: environment bootstrap failed; see " + str(run_dir / "14_logs" / "bootstrap.log"))
                return 2
        return _venv_exec(["-m", "cape.cli", stage, "--run-dir", str(run_dir)])

    if args.fetch_data:
        ok, _steps = bootstrap(ROOT / "build" / "bootstrap.log")
        if not ok:
            return 2
        rc = _venv_exec([str(ROOT / "scripts" / "fetch_data.py"), args.fetch_data])
        if rc != 0 or stage is None:
            return rc

    config = Path(args.config) if args.config else ROOT / STAGE_CONFIG[stage]
    if not config.is_absolute():
        config = (ROOT / config).resolve()
    src = source_tree_hash()
    identity = _identity(stage, config, args.manifest, args.data, src)
    run_dir = _find_resumable(identity) if args.resume else None
    resumed = run_dir is not None
    if run_dir is None:
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = _results_root() / f"{stamp}_{stage}_{identity[:8]}"
    for sec in SECTIONS:
        (run_dir / sec).mkdir(parents=True, exist_ok=True)
    rm_path = run_dir / "run_manifest.json"
    manifest = json.loads(rm_path.read_text(encoding="utf-8")) if rm_path.exists() else {}
    manifest.update({"run_id": run_dir.name, "identity": identity, "stage": stage, "config_path": str(config),
                     "manifest_arg": args.manifest, "data_arg": args.data, "source_hash": src,
                     "status": "RUNNING", "python_init": sys.version.split()[0],
                     "test_hooks": active_test_hooks()})
    manifest.setdefault("created_at", _now())
    manifest.setdefault("resumes", 0)
    if resumed:
        manifest["resumes"] += 1
    _write_json(rm_path, manifest)
    (_results_root() / "LATEST_RUN.txt").write_text(str(run_dir) + "\n", encoding="utf-8")
    with open(run_dir / "14_logs" / "controller.log", "a", encoding="utf-8") as fh:
        fh.write(f"[{_now()}] INFO INIT run {run_dir.name} ({'resumed' if resumed else 'new'}), stage {stage}\n")
    print(f"run: {run_dir}")

    # PREFLIGHT (standard library): environment, dependencies, native build, doctor
    ok, steps = bootstrap(run_dir / "14_logs" / "bootstrap.log", env_out=run_dir / "01_environment" / "environment.json",
                          quiet=True)
    _write_json(run_dir / "14_logs" / "preflight.json", steps)
    if not ok:
        from cape.finalizer import blocker_report

        failed = "; ".join(f"{s['step']}: {s['detail']}" for s in steps if s["status"] == "FAILED")
        blocker_report(run_dir, f"PREFLIGHT failed: {failed}", steps)
        manifest.update(status="BLOCKED", exit_code=2, finished_at=_now())
        _write_json(rm_path, manifest)
        print(f"BLOCKED: {failed}\nHisobot: {(run_dir / '15_reports' / 'final_report_UZ.md').resolve()}")
        return 2
    build_report = ROOT / "build" / "native_build.json"
    if build_report.exists():
        (run_dir / "01_environment" / "build_report.json").write_bytes(build_report.read_bytes())

    if args.data and stage in ("pilot", "development"):
        target = args.manifest or f"data/manifests/{stage if stage != 'development' else 'pilot'}.jsonl"
        rc = _venv_exec([str(ROOT / "scripts" / "make_manifest.py"), "--data", args.data, "--out", target])
        if rc != 0:
            from cape.finalizer import blocker_report

            blocker_report(run_dir, f"BLOCKED_DATA: could not build a manifest from {args.data} unambiguously; "
                                    f"see data/manifests/TEMPLATE_{Path(target).stem}.jsonl and the missing-field list")
            manifest.update(status="BLOCKED", exit_code=2, finished_at=_now())
            _write_json(rm_path, manifest)
            return 2
        args.manifest = target

    cmd = ["-m", "cape.cli", "continue", "--run-dir", str(run_dir), "--config", str(config)]
    if args.manifest:
        cmd += ["--manifest", args.manifest]
    if args.resume:
        cmd.append("--resume")
    if args.skip_tests:
        cmd.append("--skip-tests")
    return _venv_exec(cmd)


if __name__ == "__main__":
    sys.exit(main())
