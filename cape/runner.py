"""Stage scheduler and benchmark controller (spec sections 30, 35, 36).

INIT and PREFLIGHT run in run_all.py with the standard library only; this module continues a
run inside the project venv:

  DATA_VALIDATED -> TESTED -> FROZEN -> BENCHMARK -> OPTIONAL_AUDIT -> AGGREGATED -> RENDERED
  -> VERIFIED -> PACKAGED

The controller is the only SQLite writer. Timed tasks run in a persistent worker pinned to the
timing CPU; memory profiles run in fresh processes. Every task, including ones that cannot run
(unavailable method, unsupported dtype), ends with a committed measurement row, so coverage
denominators are never silently reduced.
"""

from __future__ import annotations

import json
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from cape import resources
from cape.provenance import ROOT, json_hash, resume_key, source_tree_hash, task_id_from_key
from cape.result_store import ResultStore, atomic_write_text, now_iso

STAGES = ["INIT", "PREFLIGHT", "DATA_VALIDATED", "TESTED", "FROZEN", "BENCHMARK", "OPTIONAL_AUDIT", "AGGREGATED",
          "RENDERED", "VERIFIED", "PACKAGED"]
SECTIONS = ["01_environment", "02_data_manifest", "03_bitstreams", "04_roundtrip", "05_raw_metrics",
            "06_solver_certificates", "07_component_stats", "08_ablations", "09_statistics", "10_plot_data",
            "11_figures", "12_tables", "13_paper_assets", "14_logs", "15_reports"]

EXIT_OK, EXIT_MISSING, EXIT_LOSSLESS, EXIT_INCOMPLETE, EXIT_INTERRUPTED, EXIT_REPORT = 0, 2, 3, 4, 5, 6


class StageError(Exception):
    def __init__(self, message: str, exit_code: int, run_status: str = "FAILED"):
        super().__init__(message)
        self.exit_code = exit_code
        self.run_status = run_status


@dataclass
class RunContext:
    run_dir: Path
    run_id: str
    store: ResultStore
    cfg: dict
    methods: dict
    args: dict
    rows: list = field(default_factory=list)
    hashes: dict = field(default_factory=dict)
    live_rows: list = field(default_factory=list)
    timing_cpu: dict = field(default_factory=dict)

    def path(self, section: str, name: str = "") -> Path:
        p = self.run_dir / section
        return p / name if name else p

    def log(self, msg: str, level: str = "INFO") -> None:
        line = f"[{now_iso()}] {level} {msg}"
        with open(self.path("14_logs", "controller.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        try:
            self.store.event(level, msg)
        except Exception:  # noqa: BLE001 - logging must never break the run
            pass
        print(line, flush=True)


# ============================================================== worker handling
class WorkerCrashed(Exception):
    pass


class WorkerTimeout(Exception):
    pass


class WorkerProcess:
    """Persistent `python -m cape.worker --serve`; JSON lines; reader thread for timeouts."""

    def __init__(self, ctx: RunContext, cpu: int | None, mem_cap_bytes: int):
        self.ctx = ctx
        self.cpu = cpu
        self.mem_cap = mem_cap_bytes
        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue = queue.Queue()
        self.log_path: Path | None = None
        self.oom_killed = False

    def start(self) -> None:
        from cape.worker import worker_env

        cmd = [sys.executable, "-m", "cape.worker", "--serve"]
        if self.cpu is not None:
            cmd += ["--cpu", str(self.cpu)]
        self.log_path = self.ctx.path("14_logs", f"worker_{int(time.time() * 1000)}.log")
        self._log_fh = open(self.log_path, "ab")
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log_fh,
                                     env=worker_env(), text=True, encoding="utf-8", bufsize=1)
        self.q = queue.Queue()
        self.oom_killed = False
        threading.Thread(target=self._reader, args=(self.proc, self.q), daemon=True).start()
        threading.Thread(target=self._watchdog, args=(self.proc,), daemon=True).start()

    @staticmethod
    def _reader(proc, q):
        for line in proc.stdout:
            q.put(line)
        q.put(None)

    def _watchdog(self, proc):
        try:
            import psutil

            p = psutil.Process(proc.pid)
            while proc.poll() is None:
                try:
                    if p.memory_info().rss > self.mem_cap:
                        self.oom_killed = True
                        proc.kill()
                        return
                except psutil.Error:
                    return
                time.sleep(0.25)
        except Exception:  # noqa: BLE001
            return

    def request(self, req: dict, timeout_s: float) -> dict:
        if self.proc is None or self.proc.poll() is not None:
            self.start()
        req = dict(req, stdout_log=None, stderr_log=str(self.log_path.relative_to(self.ctx.run_dir)))
        try:
            self.proc.stdin.write(json.dumps(req, default=str) + "\n")
            self.proc.stdin.flush()
        except OSError as exc:
            raise WorkerCrashed(f"cannot write to worker: {exc}") from exc
        try:
            line = self.q.get(timeout=timeout_s)
        except queue.Empty as exc:
            self.kill()
            raise WorkerTimeout(f"task exceeded {timeout_s:.0f} s") from exc
        if line is None:
            code = self.proc.wait(timeout=10)
            raise WorkerCrashed(f"worker exited with code {code}" + (" (memory cap watchdog)" if self.oom_killed else ""))
        return json.loads(line)["row"]

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        self.proc = None

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(json.dumps({"op": "quit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.kill()
        self.proc = None


# ================================================================ task planning
def method_key(method_id: str, wrapper: str) -> str:
    return method_id if wrapper == "none" else f"{method_id}+{wrapper}"


def plan_tasks(ctx: RunContext) -> list[dict]:
    cfg, methods = ctx.cfg, ctx.methods
    panels = [p for p in cfg["panels"] if p != "C" or cfg["roi"]["enabled"]]
    wrappers = cfg["benchmark"]["external_wrappers"]
    tasks = []
    ordinal = 0
    for si, row in enumerate(sorted(ctx.rows, key=lambda r: r["sample_id"])):
        combos = []
        for mid in cfg["methods"]:
            spec = methods[mid]
            for panel in spec["panels"]:
                if panel not in panels:
                    continue
                for w in (wrappers if spec["wrappable"] and panel == "B" else ["none"]):
                    combos.append((mid, w, panel))
        for r in range(cfg["benchmark"]["repeats"]):
            order = list(combos)
            random.Random(cfg["seed"] * 1_000_003 + si * 1009 + r).shuffle(order)
            for mid, w, panel in order:
                key = resume_key(row["voxel_sha256"], ctx.hashes["source"], ctx.hashes["config"], mid, w, panel, r)
                tasks.append({"task_id": task_id_from_key(key), "kind": "timed", "sample_id": row["sample_id"],
                              "method_id": mid, "wrapper": w, "panel": panel, "repeat": r, "split": row["split"],
                              "ordinal": ordinal, "resume_key": key})
                ordinal += 1
        if cfg["benchmark"]["memory_profile_separate"] and not row["is_synthetic"]:
            for mid in cfg["methods"]:
                if "B" not in methods[mid]["panels"]:
                    continue
                key = resume_key(row["voxel_sha256"], ctx.hashes["source"], ctx.hashes["config"], mid, "none", "MEM", -1)
                tasks.append({"task_id": task_id_from_key(key), "kind": "memory", "sample_id": row["sample_id"],
                              "method_id": mid, "wrapper": "none", "panel": "MEM", "repeat": -1, "split": row["split"],
                              "ordinal": ordinal, "resume_key": key})
                ordinal += 1
    return tasks


def availability_table(ctx: RunContext) -> dict:
    from cape.adapters import make_adapter

    table = {}
    for mid in ctx.cfg["methods"]:
        spec = ctx.methods[mid]
        wrappers = ["none"] + ([w for w in ctx.cfg["benchmark"]["external_wrappers"] if w != "none"]
                               if spec["wrappable"] else [])
        for w in wrappers:
            try:
                ad = make_adapter(mid, spec, ctx.cfg, w)
                av = ad.availability()
                av["supported_dtypes"] = list(ad.supported_dtypes)
            except Exception as exc:  # noqa: BLE001
                av = {"status": "UNAVAILABLE", "version": None, "reason": f"adapter construction failed: {exc}",
                      "supported_dtypes": []}
            av.update(method_id=mid, wrapper=w, adapter=spec["adapter"], role=spec["role"],
                      panels=spec["panels"], citation=spec.get("citation", ""),
                      experimental=bool(spec.get("experimental", False)))
            table[method_key(mid, w)] = av
    return table


def _request(ctx: RunContext, task: dict, sample: dict) -> dict:
    return {"op": "task", "task": task, "sample": sample, "run_id": ctx.run_id, "run_dir": str(ctx.run_dir),
            "config_hash": ctx.hashes["config"], "source_hash": ctx.hashes["source"], "seed": ctx.cfg["seed"],
            "threads": ctx.cfg["benchmark"]["threads"], "benchmark": ctx.cfg["benchmark"],
            "method_spec": ctx.methods[task["method_id"]], "run_cfg": ctx.cfg,
            "timing_cpu": ctx.timing_cpu.get("cpu"), "write_bitstreams": ctx.cfg["outputs"]["write_bitstreams"]}


def _skeleton_row(ctx: RunContext, task: dict, sample: dict, status: str, reason: str) -> dict:
    from cape.worker import base_row

    row = base_row(_request(ctx, task, sample))
    row.update(status=status, reason=reason, worker_pid=None, timing_cpu=None)
    return row


def run_benchmark(ctx: RunContext) -> dict:
    """Execute every pending task; returns counts. Raises KeyboardInterrupt upward."""
    from cape import live_report

    store = ctx.store
    tasks = plan_tasks(ctx)
    added = store.add_tasks(tasks)
    ctx.log(f"task plan: {len(tasks)} tasks ({added} new)")
    avail = availability_table(ctx)
    atomic_write_text(ctx.path("05_raw_metrics", "availability.json"), json.dumps(avail, indent=2, default=str))
    samples = {r["sample_id"]: r for r in ctx.rows}
    bench = ctx.cfg["benchmark"]
    mem_cap = int(bench["process_memory_gib"] * (1 << 30))
    cpu = ctx.timing_cpu.get("cpu") if bench["pin_timing_cpu"] else None
    worker = WorkerProcess(ctx, cpu, mem_cap)
    live = live_report.LiveReporter(ctx)
    min_free = int(bench["min_free_disk_gib"] * (1 << 30))
    interrupt_after = int(os.environ.get("CAPE_TEST_INTERRUPT_AFTER", "0"))  # acceptance test T5 hook
    done = 0
    try:
        for task in store.tasks("PENDING"):
            sample = samples.get(task["sample_id"])
            if sample is None:
                continue  # sample filtered out by a later config of the same run (never silently mixed)
            if resources.disk_free_bytes(ctx.run_dir) < min_free:
                raise StageError("DISK_FULL: free space below benchmark.min_free_disk_gib", EXIT_INTERRUPTED,
                                 "INTERRUPTED")
            mk = method_key(task["method_id"], task["wrapper"])
            av = avail.get(mk, {"status": "UNAVAILABLE", "reason": "not in availability table"})
            if av["status"] != "AVAILABLE":
                status = "FAILED_BUILD" if av["status"] == "FAILED_BUILD" else "UNAVAILABLE"
                row = _skeleton_row(ctx, task, sample, status, f"{av['status']}: {av.get('reason')}")
                store.commit_measurement(row, "FAILED")
                live.update(row)
                continue
            if sample["dtype"] not in av.get("supported_dtypes", []):
                row = _skeleton_row(ctx, task, sample, "UNSUPPORTED_DTYPE",
                                    f"{mk} supports {av.get('supported_dtypes')}; input is {sample['dtype']} "
                                    "(no silent cast)")
                store.commit_measurement(row, "SKIPPED")
                live.update(row)
                continue
            store.set_task(task["task_id"], "RUNNING", attempt=True)
            req = _request(ctx, task, sample)
            if task["kind"] == "memory":
                row = _run_memory_task(ctx, req, cpu, bench["task_timeout_s"])
            else:
                try:
                    row = worker.request(req, bench["task_timeout_s"])
                except WorkerTimeout as exc:
                    row = _skeleton_row(ctx, task, sample, "TIMEOUT", str(exc))
                    worker.kill()
                except WorkerCrashed as exc:
                    status = "OOM" if worker.oom_killed else "FAILED_LOSSLESS"
                    reason = (f"OOM: worker RSS exceeded {bench['process_memory_gib']} GiB cap"
                              if worker.oom_killed else f"worker crashed: {exc}")
                    row = _skeleton_row(ctx, task, sample, status, reason)
                    worker.kill()
            final = "COMMITTED" if row["status"] == "OK" else ("SKIPPED" if row["status"] in
                                                               ("UNSUPPORTED_DTYPE", "NOT_APPLICABLE") else "FAILED")
            store.commit_measurement(row, final)
            done += 1
            live.update(row)
            if interrupt_after and done >= interrupt_after:
                raise KeyboardInterrupt(f"CAPE_TEST_INTERRUPT_AFTER={interrupt_after}")
    finally:
        worker.stop()
        live.flush(final=True)
    return store.task_counts()


def _run_memory_task(ctx: RunContext, req: dict, cpu, timeout_s: float) -> dict:
    from cape.worker import worker_env

    req_path = ctx.path("14_logs", f"memreq_{req['task']['task_id']}.json")
    atomic_write_text(req_path, json.dumps(req, default=str))
    cmd = [sys.executable, "-m", "cape.worker", "--memory-profile", str(req_path)]
    if cpu is not None:
        cmd += ["--cpu", str(cpu)]
    log = ctx.path("14_logs", f"memprofile_{req['task']['task_id']}.log")
    sample = req["sample"]
    try:
        with open(log, "wb") as err:
            out = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=err, env=worker_env(),
                                 timeout=timeout_s)
        req_path.unlink(missing_ok=True)
        if out.returncode != 0 or not out.stdout.strip():
            return _skeleton_row(ctx, req["task"], sample, "FAILED_LOSSLESS",
                                 f"memory profile process exited with {out.returncode}")
        row = json.loads(out.stdout.decode("utf-8").strip().splitlines()[-1])["row"]
        row["stderr_log"] = str(log.relative_to(ctx.run_dir))
        return row
    except subprocess.TimeoutExpired:
        return _skeleton_row(ctx, req["task"], sample, "TIMEOUT", f"memory profile exceeded {timeout_s} s")


# ==================================================================== stages
def stage(ctx: RunContext, name: str, fn, inputs_hash: str | None = None):
    """Every stage is idempotent and always re-runs on resume (BENCHMARK only executes
    PENDING tasks), so a resumed run is checked exactly like a fresh one."""
    ctx.store.reset_stages_after(name, STAGES)
    ctx.store.stage_start(name, inputs_hash)
    ctx.log(f"{name}: started")
    try:
        result = fn(ctx)
    except StageError as exc:
        ctx.store.stage_finish(name, exc.run_status, detail=str(exc))
        ctx.log(f"{name}: {exc.run_status} - {exc}", "ERROR")
        raise
    except KeyboardInterrupt:
        ctx.store.stage_finish(name, "INTERRUPTED", detail="KeyboardInterrupt")
        raise
    except Exception as exc:
        ctx.store.stage_finish(name, "FAILED", detail=traceback.format_exc()[-3000:])
        ctx.log(f"{name}: FAILED - {exc}", "ERROR")
        raise
    ctx.store.stage_finish(name, "COMPLETE", outputs=result if isinstance(result, (dict, list)) else None)
    ctx.store.set_meta(f"stage_result:{name}", result if isinstance(result, (dict, list)) else None)
    ctx.log(f"{name}: COMPLETE")
    return result


def stage_data_validated(ctx: RunContext) -> dict:
    from cape import data_prep
    from cape.dataset_manifest import ManifestError, load_manifest, resolve_path, split_hash, verify_materialized, \
        write_manifest

    manifest = ctx.args.get("manifest") or ctx.cfg["input"]["manifest"]
    mpath = resolve_path(manifest)
    if ctx.cfg["mode"] == "smoke" and not mpath.exists():
        ctx.log("smoke manifest missing: generating synthetic fixtures and Crackle sample crops")
        rows = data_prep.synthetic_rows(ROOT / "data" / "synthetic")
        rows += data_prep.crackle_sample_rows(ROOT / "data" / "real" / "crackle_crops")
        write_manifest(mpath, rows)
    if not mpath.exists():
        raise StageError(f"BLOCKED_DATA: manifest {mpath} does not exist (see docs/REPRODUCE_UZ.md: fetch data, "
                         "then scripts/make_manifest.py / freeze_data.py)", EXIT_MISSING, "BLOCKED")
    try:
        all_rows = load_manifest(mpath)
    except ManifestError as exc:
        raise StageError(f"manifest invalid: {exc}", EXIT_MISSING, "BLOCKED") from exc
    splits = ctx.cfg["input"]["splits"]
    rows = [r for r in all_rows if r["split"] in splits]
    real = [r for r in rows if not r["is_synthetic"]]
    if ctx.cfg["input"]["require_real_data"] and not real:
        raise StageError(f"BLOCKED_DATA: no real (non-synthetic) samples in splits {splits} of {mpath.name}",
                         EXIT_MISSING, "BLOCKED")
    if not rows:
        raise StageError(f"BLOCKED_DATA: no samples in splits {splits}", EXIT_MISSING, "BLOCKED")
    for r in rows:
        try:
            verify_materialized(r)
        except Exception as exc:  # noqa: BLE001
            raise StageError(f"data validation failed: {exc}", EXIT_MISSING, "BLOCKED") from exc
    ctx.rows = rows
    write_manifest(ctx.path("02_data_manifest", "manifest.normalized.jsonl"), rows)
    info = {"manifest": str(mpath), "manifest_sha256": json_hash(all_rows), "splits": splits,
            "n_samples": len(rows), "n_real": len(real), "n_synthetic": len(rows) - len(real),
            "split_hash": split_hash(rows), "by_split": {s: sum(r["split"] == s for r in rows) for s in splits}}
    atomic_write_text(ctx.path("02_data_manifest", "splits.json"), json.dumps(info, indent=2))
    ctx.hashes["manifest"] = info["split_hash"]
    return info


def stage_tested(ctx: RunContext) -> dict:
    if ctx.args.get("skip_tests"):
        atomic_write_text(ctx.path("14_logs", "tests.log"), "tests skipped by --skip-tests\n")
        return {"skipped": True}
    log = ctx.path("14_logs", "tests.log")
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not acceptance and not slow",
           str(ROOT / "tests")]
    # the code is tested in a clean environment: run-level test hooks (CAPE_*) must not leak in
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAPE_")}
    with open(log, "wb") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env).returncode
    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
    if rc != 0:
        raise StageError(f"tests failed ({tail}); see 14_logs/tests.log", EXIT_LOSSLESS)
    return {"returncode": rc, "summary": tail[0] if tail else ""}


def stage_frozen(ctx: RunContext) -> dict:
    from cape.freeze import ensure_freeze

    freeze = ensure_freeze(ctx)
    atomic_write_text(ctx.path("02_data_manifest", "protocol_freeze.json"), json.dumps(freeze, indent=2))
    return freeze


def stage_benchmark(ctx: RunContext) -> dict:
    counts = run_benchmark(ctx)
    pending = counts.get("PENDING", 0) + counts.get("RUNNING", 0)
    if pending:
        raise StageError(f"{pending} planned tasks not committed", EXIT_INCOMPLETE, "PARTIAL")
    return counts


def stage_audit(ctx: RunContext) -> dict:
    from cape.oracle import run_oracle_audit

    if not ctx.cfg["oracle"]["enabled"]:
        return {"status": "NOT_APPLICABLE", "reason": "oracle.enabled is false in the run config"}
    return run_oracle_audit(ctx)


def stage_aggregated(ctx: RunContext) -> dict:
    from cape import reporting

    return reporting.aggregate(ctx)


def stage_rendered(ctx: RunContext) -> dict:
    from cape import plots, reporting

    figs = plots.render_all(ctx, preliminary=False)
    reports = reporting.write_reports(ctx, figures=figs)
    failed = [k for k, v in figs.items() if v["status"] == "REPORT_FAILED"]
    if failed:  # spec 36: CSV/Markdown stay, but RENDERED is not COMPLETE
        raise StageError(f"REPORT_FAILED: figure rendering failed for {failed}", EXIT_REPORT, "PARTIAL")
    return {"figures": {k: v["status"] for k, v in figs.items()}, "reports": reports}


def stage_verified(ctx: RunContext) -> dict:
    from cape.artifact_manifest import verify_run

    result = verify_run(ctx.run_dir)
    if not result["ok"]:
        raise StageError("artifact verification failed: " + "; ".join(result["problems"][:8]), EXIT_REPORT, "PARTIAL")
    return result


def stage_packaged(ctx: RunContext) -> dict:
    from cape.packaging import package_run

    return package_run(ctx)


def load_context(run_dir: Path, args: dict) -> RunContext:
    from cape.config import ConfigError, load_methods, load_run_config

    store = ResultStore(run_dir / "05_raw_metrics" / "run.sqlite")
    run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    cfg_path = args.get("config") or run_manifest["config_path"]
    try:
        methods = load_methods()
        cfg = load_run_config(cfg_path, methods)
    except ConfigError as exc:
        raise StageError(f"config invalid: {exc}", EXIT_MISSING, "BLOCKED") from exc
    ctx = RunContext(run_dir=run_dir, run_id=run_manifest["run_id"], store=store, cfg=cfg, methods=methods, args=args)
    ctx.hashes = {"source": run_manifest["source_hash"], "config": cfg["_hash"], "methods": cfg["_methods_hash"]}
    env_path = run_dir / "01_environment" / "environment.json"
    if env_path.exists():
        env = json.loads(env_path.read_text(encoding="utf-8"))
        ctx.timing_cpu = env.get("timing_cpu") or {}
    return ctx


def update_run_manifest(run_dir: Path, **fields) -> dict:
    p = run_dir / "run_manifest.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.update(fields)
    data["updated_at"] = now_iso()
    atomic_write_text(p, json.dumps(data, indent=2, default=str))
    return data


def continue_run(run_dir: Path, args: dict) -> int:
    """Run DATA_VALIDATED..PACKAGED. Partial reports are produced on any failure/interrupt."""
    from cape import finalizer

    try:
        ctx = load_context(run_dir, args)
    except StageError as exc:
        finalizer.blocker_report(run_dir, str(exc))
        update_run_manifest(run_dir, status=exc.run_status, exit_code=exc.exit_code)
        return exc.exit_code
    status, code = "COMPLETE", EXIT_OK
    try:
        if source_tree_hash() != ctx.hashes["source"]:
            raise StageError("source tree changed since INIT; start a new run (results never mix sources)",
                             EXIT_MISSING, "BLOCKED")
        stage(ctx, "DATA_VALIDATED", stage_data_validated)
        stage(ctx, "TESTED", stage_tested)
        stage(ctx, "FROZEN", stage_frozen)
        update_run_manifest(run_dir, config_hash=ctx.hashes["config"], methods_hash=ctx.hashes["methods"],
                            split_hash=ctx.hashes.get("manifest"), status="RUNNING",
                            primary_new=ctx.cfg["primary"]["new"], primary_baseline=ctx.cfg["primary"]["baseline"])
        stage(ctx, "BENCHMARK", stage_benchmark)
        stage(ctx, "OPTIONAL_AUDIT", stage_audit)
        stage(ctx, "AGGREGATED", stage_aggregated)
        stage(ctx, "RENDERED", stage_rendered)
        stage(ctx, "VERIFIED", stage_verified)
        stage(ctx, "PACKAGED", stage_packaged)
        lossless_fail = ctx.store.measurements("status='FAILED_LOSSLESS' AND method_id LIKE 'cape%'")
        if lossless_fail:
            status, code = "COMPLETE", EXIT_LOSSLESS
            ctx.log(f"{len(lossless_fail)} CAPE rows FAILED_LOSSLESS: correctness failure (exit 3)", "ERROR")
    except StageError as exc:
        status, code = exc.run_status, exc.exit_code
        finalizer.finalize_partial(ctx, status, str(exc))
    except KeyboardInterrupt:
        status, code = "INTERRUPTED", EXIT_INTERRUPTED
        ctx.log("interrupted by user: committed results are kept; resume with --resume", "WARN")
        finalizer.finalize_partial(ctx, status, "interrupted (Ctrl+C)")
    except Exception as exc:  # noqa: BLE001
        status, code = "FAILED", EXIT_REPORT
        ctx.log(f"unexpected failure: {exc}", "ERROR")
        finalizer.finalize_partial(ctx, status, f"unexpected failure: {exc}")
    finally:
        update_run_manifest(run_dir, status=status, exit_code=code, finished_at=now_iso())
        _print_result_paths(run_dir, status, code)
        ctx.store.close()
    return code


def _print_result_paths(run_dir: Path, status: str, code: int) -> None:
    index = run_dir / "15_reports" / "RESULTS_INDEX.md"
    report = run_dir / "15_reports" / "final_report_UZ.md"
    print(f"\nRUN STATUS: {status} (exit {code})")
    print(f"Natijalar indeksi: {index.resolve()}")
    print(f"Yakuniy hisobot:  {report.resolve()}")
