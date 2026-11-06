"""CAPE-Pins v2.1 with one command (plan v2.1): no new mechanism, only measurements and preparation.

    run_v21.cmd                 # every step, resuming steps already DONE
    run_v21.cmd --restart       # forget the step state (finished runs stay on disk)
    run_v21.cmd --only report   # one step

Steps (state in analysis/v21_state.json, logs in analysis/v21_logs/):
  check_v2       the v2 pipeline (incl. the Z=512 width run) must be DONE; otherwise later timed steps wait
  build          rebuild the native modules (impl_mask switches)
  tests          pytest (non-acceptance): golden v1 bitstreams + every impl_mask combination byte-identical
  snemi_prepare  SNEMI3D download/verification + frozen confirm crops (NO compression on it)
  attribution    v1 -> v2 speed-up factorial (analysis/v21_speedup)
  scaling_prep   nested scaling crops from seen development sources
  scaling        CAPE-FAST / depth regimes / v1 legacy / SAFE / SAFE+refine (experimental) / flat
  scaling_stock  corrected stock vs CAPE-FAST on crops <= 2^25 voxels
  equal_infra_*  equal-infrastructure 2x2 (exact DP x local search) on the CAPE-FAST pipeline (v2 test crops +
                 corrected stock; scaling crops) - review item 4
  upstream_fast_* CAPE-FAST vs upstream's default fast pins encoder (allow_pins=1, PR #29) on the same crops
  audit          independent recomputation of the two scaling runs
  report         analysis/v21_final/V21_HISOBOT_UZ.md + figures + plot data
A step that cannot run is recorded as BLOCKED with its reason; nothing is fabricated.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "analysis" / "v21_state.json"
V2_STATE = ROOT / "analysis" / "v2_state.json"
LOGS = ROOT / "analysis" / "v21_logs"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
STEPS = ["check_v2", "build", "tests", "snemi_prepare", "attribution", "scaling_prep", "scaling", "scaling_stock",
         "equal_infra_test", "equal_infra_scaling", "upstream_fast_test", "upstream_fast_scaling", "audit", "report"]
TIMED = {"attribution", "scaling", "scaling_stock", "equal_infra_test", "equal_infra_scaling", "upstream_fast_test",
         "upstream_fast_scaling"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"created_at": now(), "steps": {}}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    os.replace(tmp, STATE)


def run(cmd: list, log_name: str) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{log_name}.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {now()} {' '.join(map(str, cmd))}\n")
        fh.flush()
        return subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)


def latest_run() -> str | None:
    p = ROOT / "results" / "LATEST_RUN.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def pipeline(stage: str, config: str, manifest: str, log: str, prev: dict) -> dict:
    # resume the same run directory if this step already started one
    before = latest_run()
    cmd = ["py", "-3.12", ROOT / "run_all.py", "--stage", stage, "--config", config, "--manifest", manifest, "--resume"]
    code = run(cmd, log)
    after = latest_run()
    rd = Path(after) if after else None
    if rd and not rd.is_absolute():
        rd = ROOT / rd
    status = None
    if rd and (rd / "run_manifest.json").exists():
        status = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")).get("status")
    ok = code == 0 and status == "COMPLETE"
    rel = None
    if rd:
        try:
            rel = str(rd.relative_to(ROOT))
        except ValueError:
            rel = str(rd)
    return {"status": "DONE" if ok else "FAILED", "exit_code": code, "run_dir": rel, "run_status": status,
            "detail": None if ok else f"run_all exit {code}, run status {status}"}


def step_check_v2(st):
    if not V2_STATE.exists():
        return {"status": "BLOCKED", "detail": "analysis/v2_state.json missing - run run_v2.cmd first"}
    v2 = json.loads(V2_STATE.read_text(encoding="utf-8"))["steps"]
    pending = {k: v.get("status") for k, v in v2.items() if v.get("status") != "DONE"}
    if pending:
        return {"status": "BLOCKED", "detail": f"v2 steps not DONE: {pending} (the Z=512 width run must finish first)"}
    return {"status": "DONE", "detail": f"v2 width run {v2['width'].get('run_dir')}", "width_run": v2["width"].get("run_dir"),
            "test_run": v2["test"].get("run_dir"), "pilot_run": v2["pilot"].get("run_dir")}


def step_build(st):
    code = run([PY, "scripts/build_native.py"], "build")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "build/native_build.json"}


def step_tests(st):
    LOGS.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([str(PY), "-m", "pytest", "-q", "tests", "-m", "not acceptance", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True)
    (LOGS / "tests.log").write_text(res.stdout + res.stderr, encoding="utf-8")
    tail = [line for line in res.stdout.splitlines() if " passed" in line or " failed" in line]
    return {"status": "DONE" if res.returncode == 0 else "FAILED", "exit_code": res.returncode,
            "detail": tail[-1] if tail else "no pytest summary"}


def step_snemi_prepare(st):
    c1 = run([PY, "scripts/fetch_snemi3d.py"], "snemi")
    if c1 != 0:
        return {"status": "BLOCKED", "exit_code": c1, "detail": "SNEMI3D download/verification failed (see snemi.log)"}
    c2 = run([PY, "scripts/freeze_data.py", "--snemi3d-confirm"], "snemi")
    return {"status": "DONE" if c2 == 0 else "FAILED", "exit_code": c2,
            "detail": "data/manifests/confirm_snemi3d.jsonl (frozen; no compression run on it)"}


def step_attribution(st):
    code = run([PY, "scripts/speedup_attribution.py", "--memory"], "attribution")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "analysis/v21_speedup"}


def step_scaling_prep(st):
    if (ROOT / "data" / "manifests" / "scaling_v21.jsonl").exists():
        return {"status": "DONE", "detail": "manifest already frozen (data/manifests/scaling_v21.jsonl)"}
    code = run([PY, "scripts/make_scaling_manifest.py"], "scaling_prep")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "data/manifests/scaling_v21*.jsonl"}


def step_scaling(st):
    return pipeline("development", "configs/scaling_v21.yaml", "data/manifests/scaling_v21.jsonl", "scaling",
                    st["steps"].get("scaling", {}))


def step_scaling_stock(st):
    return pipeline("development", "configs/scaling_v21_stock.yaml", "data/manifests/scaling_v21_stock.jsonl",
                    "scaling_stock", st["steps"].get("scaling_stock", {}))


def step_equal_infra_test(st):
    return pipeline("development", "configs/equal_infra_test_v21.yaml", "data/manifests/test_v2_unseen.jsonl",
                    "equal_infra_test", st["steps"].get("equal_infra_test", {}))


def step_equal_infra_scaling(st):
    return pipeline("development", "configs/equal_infra_scaling_v21.yaml", "data/manifests/scaling_v21.jsonl",
                    "equal_infra_scaling", st["steps"].get("equal_infra_scaling", {}))


def step_upstream_fast_test(st):
    return pipeline("development", "configs/upstream_fast_test_v21.yaml", "data/manifests/test_v2_unseen.jsonl",
                    "upstream_fast_test", st["steps"].get("upstream_fast_test", {}))


def step_upstream_fast_scaling(st):
    return pipeline("development", "configs/upstream_fast_scaling_v21.yaml", "data/manifests/scaling_v21.jsonl",
                    "upstream_fast_scaling", st["steps"].get("upstream_fast_scaling", {}))


AUDITED = ("scaling", "scaling_stock", "equal_infra_test", "equal_infra_scaling", "upstream_fast_test",
           "upstream_fast_scaling")


def step_audit(st):
    runs = [st["steps"][k]["run_dir"] for k in AUDITED
            if st["steps"].get(k, {}).get("status") == "DONE" and st["steps"][k].get("run_dir")]
    if not runs:
        return {"status": "BLOCKED", "detail": "no COMPLETE v2.1 scaling run to audit"}
    code = run([PY, "scripts/audit_report.py", "--runs", *runs, "--out", "v21_audit", "--new", "cape_fast_m0",
                "--base", "cape_m0_legacy", "--pairs", "cape_fast_m0:crackle_pins_opt_corrected_m0",
                "safe_refine_e24_m0_zstd9:safe_archive_m0_zstd9", "cape_fast_m0:weighted_greedy_fast_m0",
                "weighted_greedy_fast_m0:crackle_pins_opt_corrected_m0", "cape_fast_m0:crackle_pins_fast_m0"], "audit")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "analysis/v21_audit"}


def step_report(st):
    code = run([PY, "scripts/v21_report.py", "--state", str(STATE.relative_to(ROOT))], "report")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "analysis/v21_final/V21_HISOBOT_UZ.md"}


FUNCS = {s: globals()[f"step_{s}"] for s in STEPS}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=STEPS)
    ap.add_argument("--restart", action="store_true")
    args = ap.parse_args(argv)
    if not PY.exists():
        print("ERROR: .venv missing - run `run_experiment.cmd --stage smoke` once to bootstrap", file=sys.stderr)
        return 2
    st = {"created_at": now(), "steps": {}} if args.restart else load_state()
    todo = [args.only] if args.only else STEPS
    for name in todo:
        prev = st["steps"].get(name, {})
        if not args.only and prev.get("status") == "DONE" and name != "check_v2":
            print(f"[{name}] DONE (resume)")
            continue
        gate = None
        if name in ({"build", "tests"} | TIMED) and st["steps"].get("check_v2", {}).get("status") != "DONE":
            gate = "v2 pipeline (Z=512 width run) not finished - the running benchmark must not be disturbed"
        elif name in TIMED and st["steps"].get("tests", {}).get("status") != "DONE":
            gate = "tests not DONE - timed steps not started"
        elif name in TIMED and st["steps"].get("build", {}).get("status") != "DONE":
            gate = "native build not DONE"
        if gate and not args.only:
            st["steps"][name] = {"status": "BLOCKED", "detail": gate, "ended_at": now()}
            save_state(st)
            print(f"[{name}] BLOCKED {gate}", flush=True)
            continue
        t0 = time.time()
        st["steps"][name] = dict(prev, status="RUNNING", started_at=now())
        save_state(st)
        print(f"[{name}] running ...", flush=True)
        res = FUNCS[name](st)
        res.update(started_at=st["steps"][name]["started_at"], ended_at=now(), seconds=round(time.time() - t0, 1))
        st["steps"][name] = res
        save_state(st)
        print(f"[{name}] {res['status']} {res.get('detail') or ''}", flush=True)
    print("v21 state:", json.dumps({k: v.get("status") for k, v in st["steps"].items()}))
    return 0 if all(v.get("status") == "DONE" for v in st["steps"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
