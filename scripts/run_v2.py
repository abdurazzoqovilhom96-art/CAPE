"""CAPE-Pins v2: the whole experiment with one command (plan v2).

    run_v2.cmd                 # every step, resuming steps already DONE
    run_v2.cmd --restart       # forget the step state (finished runs stay on disk)
    run_v2.cmd --only report   # one step

Steps (state in analysis/v2_state.json, logs in analysis/v2_logs/):
  tests    pytest (non-acceptance) - counts recorded; a failure stops the timed steps
  pilot    CREMI A development pilot          configs/pilot_v2.yaml
  freeze   pre-registered rule -> configs/test_v2_frozen.yaml   (needs a COMPLETE pilot)
  test     frozen test on unseen CREMI B/C crops of SEEN volumes (needs freeze)
  width    Z=512 / scale panel on seen Crackle crops            configs/width_v2.yaml
  ceiling  archive ceiling of label-side changes (pilot + test manifests)
  audit    independent recomputation of every run (+ bitstream identity vs v1)
  report   analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md + figures + plot data
A step that cannot run is recorded as BLOCKED with its reason; later independent steps still run.
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
STATE = ROOT / "analysis" / "v2_state.json"
LOGS = ROOT / "analysis" / "v2_logs"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
V1_HELDOUT = "results/20261105T122347Z_all_d1a76eb7"
STEPS = ["tests", "pilot", "freeze", "test", "width", "ceiling", "audit", "report"]


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


def run(cmd: list[str], log_name: str) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{log_name}.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {now()} {' '.join(map(str, cmd))}\n")
        fh.flush()
        return subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)


def latest_run() -> str | None:
    p = ROOT / "results" / "LATEST_RUN.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def pipeline(stage: str, config: str, manifest: str, log: str) -> dict:
    before = latest_run()
    code = run(["py", "-3.12", ROOT / "run_all.py", "--stage", stage, "--config", config, "--manifest", manifest,
                "--resume"], log)
    after = latest_run()
    rd = Path(after) if after and after != before else (Path(after) if after else None)
    status = None
    if rd and (rd / "run_manifest.json").exists():
        status = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")).get("status")
    ok = code == 0 and status == "COMPLETE"
    return {"status": "DONE" if ok else "FAILED", "exit_code": code, "run_dir": str(rd.relative_to(ROOT)) if rd else None,
            "run_status": status, "detail": None if ok else f"run_all exit {code}, run status {status}"}


def step_tests(st):
    LOGS.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([str(PY), "-m", "pytest", "-q", "tests", "-m", "not acceptance", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True)
    (LOGS / "tests.log").write_text(res.stdout + res.stderr, encoding="utf-8")
    tail = [line for line in res.stdout.splitlines() if " passed" in line or " failed" in line]
    return {"status": "DONE" if res.returncode == 0 else "FAILED", "exit_code": res.returncode,
            "detail": tail[-1] if tail else "no pytest summary"}


def step_pilot(st):
    return pipeline("pilot", "configs/pilot_v2.yaml", "data/manifests/pilot.jsonl", "pilot")


def step_freeze(st):
    p = st["steps"].get("pilot", {})
    if p.get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "pilot is not DONE (no frozen settings without a complete pilot)"}
    code = run([PY, "scripts/freeze_v2.py", "--pilot-run", p["run_dir"]], "freeze")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code,
            "detail": "analysis/v2_freeze/freeze.json, configs/test_v2_frozen.yaml"}


def step_test(st):
    if st["steps"].get("freeze", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "freeze is not DONE"}
    return pipeline("all", "configs/test_v2_frozen.yaml", "data/manifests/test_v2_unseen.jsonl", "test")


def step_width(st):
    return pipeline("development", "configs/width_v2.yaml", "data/manifests/width_sensitivity.jsonl", "width")


def step_ceiling(st):
    c1 = run([PY, "scripts/archive_ceiling.py", "--manifest", "data/manifests/pilot.jsonl", "--out", "v2_ceiling_pilot"], "ceiling")
    c2 = run([PY, "scripts/archive_ceiling.py", "--manifest", "data/manifests/test_v2_unseen.jsonl", "--out",
              "v2_ceiling_test"], "ceiling")
    return {"status": "DONE" if c1 == 0 and c2 == 0 else "FAILED", "exit_code": max(c1, c2),
            "detail": "analysis/v2_ceiling_pilot, analysis/v2_ceiling_test"}


def step_audit(st):
    runs = [st["steps"][k]["run_dir"] for k in ("pilot", "test", "width")
            if st["steps"].get(k, {}).get("status") == "DONE" and st["steps"][k].get("run_dir")]
    if not runs:
        return {"status": "BLOCKED", "detail": "no COMPLETE v2 run to audit"}
    code = run([PY, "scripts/audit_report.py", "--runs", *runs, "--out", "v2_audit", "--compare-to", V1_HELDOUT,
                "--new", "cape_fast_m0", "--base", "crackle_pins_opt_corrected_m0",
                "--pairs", "cape_m0:crackle_pins_opt_m0", "cape_fast_m0:crackle_pins_opt_m0",
                "cape_m0:cape_m0_legacy"], "audit")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "analysis/v2_audit"}


def step_report(st):
    code = run([PY, "scripts/v2_report.py", "--state", str(STATE.relative_to(ROOT))], "report")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code,
            "detail": "analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md"}


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
        if not args.only and prev.get("status") == "DONE":
            print(f"[{name}] DONE (resume)")
            continue
        if name in ("pilot", "test", "width") and st["steps"].get("tests", {}).get("status") == "FAILED":
            st["steps"][name] = {"status": "BLOCKED", "detail": "tests failed - timed runs not started", "ended_at": now()}
            save_state(st)
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
    bad = {k: v["status"] for k, v in st["steps"].items() if v.get("status") != "DONE"}
    print("v2 state:", json.dumps({k: v.get("status") for k, v in st["steps"].items()}))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
