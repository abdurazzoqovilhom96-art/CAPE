"""Isolated task executor (spec sections 20, 25 `worker`, 35.1).

Modes
  python -m cape.worker --serve [--cpu N]     persistent timed worker; JSON lines on stdin/stdout
  python -m cape.worker --memory-profile REQ  fresh process, one encode + decode, peak memory

A timed task: warm-up (first use of method/wrapper/sample in this process), timed encode,
timed decode, then - outside the timed region - voxel-exact verification against the
canonical input, an optional second-decoder check, hashing and an atomic bitstream write.
The controller is the only database writer; the worker returns a measurement packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
              "NUMEXPR_MAX_THREADS": "1", "BLOSC_NTHREADS": "1", "PYTHONHASHSEED": "0"}


def worker_env() -> dict:
    env = dict(os.environ)
    env.update(THREAD_ENV)
    return env


CAPE_DIAG_FIELDS = ("candidate_count_before", "candidate_count_after", "incidence_count", "component_count",
                    "max_component_cc", "exact_cc_fraction", "ub_bytes", "lb_bytes", "certificate_scope")


class TaskContext:
    """Per-process caches: current sample array and constructed adapters."""

    def __init__(self):
        self.sample_key = None
        self.array = None
        self.adapters: dict = {}
        self.warmed: set = set()

    def load(self, row: dict):
        from cape.dataset_manifest import resolve_path
        from cape.io import load_canonical

        key = (row["sample_id"], row["voxel_sha256"])
        if key != self.sample_key:
            self.array = None
            self.array = load_canonical(resolve_path(row["path"]))
            self.sample_key = key
        return self.array

    def adapter(self, method_id: str, spec: dict, run_cfg: dict, wrapper: str):
        from cape.adapters import make_adapter

        k = (method_id, wrapper)
        if k not in self.adapters:
            self.adapters[k] = make_adapter(method_id, spec, run_cfg, wrapper)
        return self.adapters[k]


def _status_for_exception(exc: BaseException, phase: str) -> tuple[str, str]:
    from cape.adapters import AdapterUnavailable, UnsupportedDtype

    name = type(exc).__name__
    msg = str(exc)[:500]
    if isinstance(exc, UnsupportedDtype):
        return "UNSUPPORTED_DTYPE", msg
    if isinstance(exc, AdapterUnavailable):
        return "UNAVAILABLE", msg
    if name == "MemoryCapExceeded" or "OOM_PREVENTED" in msg:
        return "OOM", f"OOM_PREVENTED: {msg}"
    if isinstance(exc, MemoryError):
        return "OOM", f"MemoryError during {phase}"
    if name == "UnsupportedInput":
        return "NOT_APPLICABLE", msg
    return "FAILED_LOSSLESS", f"{phase} raised {name}: {msg}"


def base_row(req: dict) -> dict:
    t = req["task"]
    s = req["sample"]
    return {
        "run_id": req["run_id"], "task_id": t["task_id"], "sample_id": t["sample_id"], "method_id": t["method_id"],
        "method_version": None, "config_hash": req["config_hash"], "source_hash": req["source_hash"],
        "input_hash": s["voxel_sha256"], "panel": t["panel"], "split": t["split"], "repeat": t["repeat"],
        "seed": req["seed"], "threads": req["threads"], "status": None, "reason": None,
        "original_dtype": s["dtype"], "canonical_shape": s["shape"], "input_bytes": None, "payload_bytes": None,
        "metadata_bytes": None, "total_bytes": None, "label_bytes": None, "encode_ns": None, "decode_ns": None,
        "conversion_ns": None, "verify_ns": None, "peak_rss_bytes": None,
        "rss_measurement_mode": "separate_profile_run", "lossless": None, "candidate_count_before": None,
        "candidate_count_after": None, "incidence_count": None, "component_count": None, "max_component_cc": None,
        "exact_cc_fraction": None, "ub_bytes": None, "lb_bytes": None, "certificate_scope": None,
        "certificate_valid": None, "bitstream_sha256": None, "bitstream_path": None,
        "stdout_log": req.get("stdout_log"), "stderr_log": req.get("stderr_log"), "wrapper": t["wrapper"],
        "family_id": s["family_id"], "source_id": s["source_id"], "macroblock_id": s["macroblock_id"],
        "is_synthetic": s["is_synthetic"], "label_format_actual": None, "encode_iterations": None,
        "encode_batch_ns": None, "decode_iterations": None, "decode_batch_ns": None,
        "timing_cpu": req.get("timing_cpu"), "dtype_adapter": None, "worker_pid": os.getpid(), "extra_json": None,
    }


def _fill_codec_fields(row: dict, adapter, payload: bytes, arr) -> dict:
    diag = dict(adapter.last_diagnostics or {})
    row["input_bytes"] = int(arr.nbytes)
    row["total_bytes"] = len(payload)
    row["metadata_bytes"] = int(adapter.last_metadata_bytes)
    row["payload_bytes"] = len(payload) - int(adapter.last_metadata_bytes)
    row["conversion_ns"] = 0  # canonical -> codec layout is a zero-copy view for every adapter
    row["dtype_adapter"] = diag.get("dtype_adapter")
    if adapter.crackle_format:
        row["label_format_actual"] = diag.get("label_format")
        row["label_bytes"] = diag.get("label_bytes")
    for f in CAPE_DIAG_FIELDS:
        if f in diag:
            row[f] = diag[f]
    if "certificate_dual_feasible" in diag:
        row["certificate_valid"] = bool(diag["certificate_dual_feasible"] == 1 and diag["lb_bytes"] <= diag["ub_bytes"])
    keep = {k: v for k, v in diag.items() if k not in CAPE_DIAG_FIELDS and k != "records"}
    return keep


def run_timed(req: dict, ctx: TaskContext) -> dict:
    import numpy as np

    from cape.timing import time_call

    row = base_row(req)
    t = req["task"]
    bench = req["benchmark"]
    extra: dict = {}
    try:
        arr = ctx.load(req["sample"])
        adapter = ctx.adapter(t["method_id"], req["method_spec"], req["run_cfg"], t["wrapper"])
        row["method_version"] = adapter.version()
        adapter.check_dtype(arr.dtype)
        wkey = (t["method_id"], t["wrapper"], t["sample_id"])
        if wkey not in ctx.warmed:
            for _ in range(int(bench["warmups"])):
                adapter.decode(adapter.encode(arr))
            ctx.warmed.add(wkey)
        min_batch = int(bench["min_batch_ms"]) * 1_000_000
        small = int(bench["small_task_ms"]) * 1_000_000
        phase = "encode"
        enc = time_call(lambda: adapter.encode(arr), min_batch, small)
        payload = enc.result
        extra.update(_fill_codec_fields(row, adapter, payload, arr))
        phase = "decode"
        dec = time_call(lambda: adapter.decode(payload), min_batch, small)
        row.update(encode_ns=enc.per_call_ns, encode_iterations=enc.iterations, encode_batch_ns=enc.batch_ns,
                   decode_ns=dec.per_call_ns, decode_iterations=dec.iterations, decode_batch_ns=dec.batch_ns)
        phase = "verify"
        v0 = time.perf_counter_ns()
        out = dec.result
        lossless = bool(out.shape == arr.shape and out.dtype == arr.dtype and np.array_equal(out, arr))
        del out
        checks = adapter.secondary_check(payload, arr) if lossless else {}
        extra["secondary_checks"] = checks
        lossless = lossless and all(checks.values())
        row["verify_ns"] = time.perf_counter_ns() - v0
        row["lossless"] = lossless
        sha = hashlib.sha256(payload).hexdigest()
        row["bitstream_sha256"] = sha
        if req.get("write_bitstreams", True):
            from cape.result_store import atomic_write_bytes

            rel = f"03_bitstreams/{sha}.bin"
            dest = Path(req["run_dir"]) / rel
            if not dest.exists():
                atomic_write_bytes(dest, payload)
            row["bitstream_path"] = rel
        if lossless:
            row["status"] = "OK"
        else:
            row["status"] = "FAILED_LOSSLESS"
            row["reason"] = "decoded volume differs from the input" + (f" (checks {checks})" if checks else "")
    except BaseException as exc:  # isolated: one task's failure never stops the run
        if isinstance(exc, KeyboardInterrupt):
            raise
        status, reason = _status_for_exception(exc, locals().get("phase", "setup"))
        row["status"] = status
        row["reason"] = reason
        extra["traceback"] = traceback.format_exc()[-2000:]
    row["extra_json"] = json.dumps(extra, default=str)
    return row


def memory_profile(req: dict) -> dict:
    """Fresh process: peak working set around one encode and one decode (+ polled children)."""
    import numpy as np

    from cape import resources

    row = base_row(req)
    t = req["task"]
    ctx = TaskContext()
    extra: dict = {}
    peak_tree = {"bytes": 0}
    stop = threading.Event()

    def poll():
        try:
            import psutil

            me = psutil.Process()
            while not stop.is_set():
                total = me.memory_info().rss
                for ch in me.children(recursive=True):
                    try:
                        total += ch.memory_info().rss
                    except psutil.Error:
                        pass
                peak_tree["bytes"] = max(peak_tree["bytes"], total)
                stop.wait(0.01)
        except Exception:  # noqa: BLE001
            pass

    try:
        arr = ctx.load(req["sample"])
        adapter = ctx.adapter(t["method_id"], req["method_spec"], req["run_cfg"], t["wrapper"])
        row["method_version"] = adapter.version()
        adapter.check_dtype(arr.dtype)
        before = resources.process_peak_rss()
        th = threading.Thread(target=poll, daemon=True)
        th.start()
        payload = adapter.encode(arr)
        after_enc = resources.process_peak_rss()
        out = adapter.decode(payload)
        after_dec = resources.process_peak_rss()
        stop.set()
        th.join(timeout=1)
        extra.update(_fill_codec_fields(row, adapter, payload, arr))
        row["lossless"] = bool(np.array_equal(out, arr))
        row["status"] = "OK" if row["lossless"] else "FAILED_LOSSLESS"
        row["peak_rss_bytes"] = after_dec["peak_rss_bytes"]
        row["rss_measurement_mode"] = "win_peak_wset_fresh_process"
        extra.update({"rss_before_encode": before["rss_bytes"], "peak_before_encode": before["peak_rss_bytes"],
                      "peak_after_encode": after_enc["peak_rss_bytes"], "peak_after_decode": after_dec["peak_rss_bytes"],
                      "polled_tree_peak_bytes": peak_tree["bytes"],
                      "peak_attribution": "codec raised the process peak" if (after_dec["peak_rss_bytes"] or 0) >
                      (before["peak_rss_bytes"] or 0) else "upper bound: peak predates the codec call",
                      "input_normalized_peak": (after_dec["peak_rss_bytes"] or 0) / max(1, int(arr.nbytes))})
    except BaseException as exc:
        stop.set()
        status, reason = _status_for_exception(exc, "memory profile")
        row["status"] = status
        row["reason"] = reason
        extra["traceback"] = traceback.format_exc()[-2000:]
    row["extra_json"] = json.dumps(extra, default=str)
    return row


def serve(cpu: int | None) -> int:
    from cape import resources

    if cpu is not None:
        resources.pin_current_process(cpu)
    ctx = TaskContext()
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        if req.get("op") == "quit":
            return 0
        if req.get("op") == "ping":
            out.write(json.dumps({"op": "pong", "pid": os.getpid()}) + "\n")
            out.flush()
            continue
        try:
            row = run_timed(req, ctx)
        except KeyboardInterrupt:
            return 130
        out.write(json.dumps({"op": "result", "row": row}, default=str) + "\n")
        out.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--cpu", type=int, default=None)
    ap.add_argument("--memory-profile", metavar="REQUEST_JSON")
    args = ap.parse_args(argv)
    if args.serve:
        return serve(args.cpu)
    if args.memory_profile:
        req = json.loads(Path(args.memory_profile).read_text(encoding="utf-8"))
        if args.cpu is not None:
            from cape import resources

            resources.pin_current_process(args.cpu)
        row = memory_profile(req)
        sys.stdout.write(json.dumps({"op": "result", "row": row}, default=str) + "\n")
        return 0
    ap.error("choose --serve or --memory-profile")
    return 2


if __name__ == "__main__":
    sys.exit(main())
