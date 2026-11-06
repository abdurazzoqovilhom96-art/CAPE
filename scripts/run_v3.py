"""CAPE v3 orchestrator (plan CAPE v3, sections 3.2 and 16): one entry point over the existing run_all.py pipeline.

    run_v3.cmd --stage all --resume      every stage in order; stages already DONE are skipped
    run_v3.cmd --stage develop           one stage (always re-run when named explicitly; finished runs resume)
    run_v3.cmd --stage report-status     print the stage table and exit

Stages (state in analysis/v3_state.json, logs in analysis/v3_logs/):
  audit     scripts/audit_v3.py: earlier claims recomputed, certificates, factors, SNEMI3D status and overlap
  build     scripts/build_native.py (v3 native module; the frozen v2.1 binary is never rebuilt)
  tests     pytest -m "not acceptance" (byte identity with the frozen v2.1 binary, invariants) + acceptance T1-T12
  develop   the four development panels of configs/v3_development.yaml (core, scale, quality, tracks)
  select    scripts/pilot_select_v3.py: pre-registered gates -> analysis/v3_select/selected_methods.json
  freeze    scripts/freeze_v3.py: frozen confirm configs + SNEMI3D scale manifest + hashes + git commit id
  confirm   frozen batch on SNEMI3D (32 frozen crops; then the whole-volume scale track)
  analyze   scripts/report_v3.py: statistics, figures, tables, claim ledger, ten-question analysis
  package   scripts/package_v3.py: results/v3_<id>/ 00_protocol ... 17_package, checksums
A stage whose script does not exist yet is recorded as BLOCKED with that reason; nothing is fabricated.
Exit codes: 0 every requested stage DONE, 1 some stage not DONE, 2 setup error.
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
STATE = ROOT / "analysis" / "v3_state.json"
LOGS = ROOT / "analysis" / "v3_logs"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROTOCOL = ROOT / "configs" / "v3_development.yaml"
STAGES = ["audit", "build", "tests", "develop", "select", "freeze", "confirm", "analyze", "package"]
PANELS = ["core", "scale", "quality", "tracks"]  # run order (most decision-relevant first)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"created_at": now(), "stages": {}, "panels": {}}


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


def protocol() -> dict:
    import yaml

    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def latest_run() -> str | None:
    p = ROOT / "results" / "LATEST_RUN.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def pipeline(config: str, manifest: str, log: str, stage: str = "development") -> dict:
    """One run_all.py run (resumes the same run directory when sources, config and manifest are unchanged)."""
    cmd = [PY, ROOT / "run_all.py", "--stage", stage, "--config", config, "--manifest", manifest, "--resume"]
    code = run(cmd, log)
    rd = latest_run()
    rdp = Path(rd) if rd else None
    if rdp and not rdp.is_absolute():
        rdp = ROOT / rdp
    status = None
    if rdp and (rdp / "run_manifest.json").exists():
        status = json.loads((rdp / "run_manifest.json").read_text(encoding="utf-8")).get("status")
    rel = None
    if rdp:
        try:
            rel = rdp.relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(rdp)
    ok = code == 0 and status == "COMPLETE"
    return {"status": "DONE" if ok else "FAILED", "exit_code": code, "run_dir": rel, "run_status": status,
            "detail": None if ok else f"run_all exit {code}, run status {status}"}


def script_stage(script: str, args: list[str], log: str, detail: str) -> dict:
    path = ROOT / "scripts" / script
    if not path.exists():
        return {"status": "BLOCKED", "detail": f"scripts/{script} not written yet"}
    code = run([PY, path, *args], log)
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": detail}


# ------------------------------------------------------------------------------------------------ stages
def stage_audit(st):
    return script_stage("audit_v3.py", [], "audit", "analysis/v3_audit/AUDIT_V3_UZ.md")


def stage_build(st):
    code = run([PY, "scripts/build_native.py"], "build")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code, "detail": "build/native_build.json"}


def stage_tests(st):
    LOGS.mkdir(parents=True, exist_ok=True)
    out = []
    for marker in ("not acceptance", "acceptance"):
        res = subprocess.run([str(PY), "-m", "pytest", "-q", "tests", "-m", marker, "-p", "no:cacheprovider"],
                             cwd=ROOT, capture_output=True, text=True)
        (LOGS / f"tests_{marker.replace(' ', '_')}.log").write_text(res.stdout + res.stderr, encoding="utf-8")
        tail = [line for line in res.stdout.splitlines() if " passed" in line or " failed" in line]
        out.append((marker, res.returncode, tail[-1] if tail else "no pytest summary"))
    ok = all(rc == 0 for _, rc, _ in out)
    return {"status": "DONE" if ok else "FAILED", "detail": "; ".join(f"{m}: {t}" for m, _, t in out)}


def stage_develop(st):
    proto = protocol()
    if not (ROOT / "data" / "manifests" / "v3_dev_core.jsonl").exists():
        code = run([PY, "scripts/make_v3_manifests.py", "--dev"], "develop")
        if code != 0:
            return {"status": "FAILED", "detail": "make_v3_manifests.py --dev failed"}
    results = {}
    for panel in PANELS:
        prev = st["panels"].get(panel, {})
        if prev.get("status") == "DONE":
            results[panel] = prev
            print(f"  [develop/{panel}] DONE (resume) {prev.get('run_dir')}", flush=True)
            continue
        spec = proto["panels"][panel]
        st["panels"][panel] = dict(prev, status="RUNNING", started_at=now())
        save_state(st)
        print(f"  [develop/{panel}] running {spec['config']} ...", flush=True)
        t0 = time.time()
        res = pipeline(spec["config"], spec["manifest"], f"develop_{panel}")
        res.update(started_at=st["panels"][panel]["started_at"], ended_at=now(), seconds=round(time.time() - t0, 1))
        st["panels"][panel] = res
        save_state(st)
        results[panel] = res
        print(f"  [develop/{panel}] {res['status']} {res.get('run_dir')}", flush=True)
    ok = all(r.get("status") == "DONE" for r in results.values())
    return {"status": "DONE" if ok else "FAILED", "detail": {p: r.get("run_dir") for p, r in results.items()}}


def _panel_run(st: dict, key: str, config: str, manifest: str) -> dict:
    prev = st["panels"].get(key, {})
    if prev.get("status") == "DONE":
        return prev
    st["panels"][key] = dict(prev, status="RUNNING", started_at=now())
    save_state(st)
    t0 = time.time()
    res = pipeline(config, manifest, key)
    res.update(started_at=st["panels"][key]["started_at"], ended_at=now(), seconds=round(time.time() - t0, 1))
    st["panels"][key] = res
    save_state(st)
    return res


def stage_select(st):
    """Phase 1 (gates on the development runs; at most one 15-repeat rerun under the inconclusive rule), then the
    QUALITY composite is measured on the development QUALITY crops, then phase 2 (QUALITY gate)."""
    if st["stages"].get("develop", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "develop not DONE"}
    script = ROOT / "scripts" / "pilot_select_v3.py"
    if not script.exists():
        return {"status": "BLOCKED", "detail": "scripts/pilot_select_v3.py not written yet"}
    args = ["--phase", "1", "--runs", *[f"{p}={st['panels'][p]['run_dir']}" for p in PANELS]]
    if all(st["panels"].get(f"rerun_{p}", {}).get("status") == "DONE" for p in ("core", "scale")):
        args += ["--rerun", *[f"{p}={st['panels'][f'rerun_{p}']['run_dir']}" for p in ("core", "scale")]]
    code = run([PY, script, *args], "select")
    if code == 3:  # inconclusive rule: one rerun with 15 repeats, then decide with the rerun only
        rr = json.loads((ROOT / "analysis" / "v3_select" / "rerun_required.json").read_text(encoding="utf-8"))
        for p in ("core", "scale"):
            res = _panel_run(st, f"rerun_{p}", rr["configs"][p], rr["manifests"][p])
            if res["status"] != "DONE":
                return {"status": "FAILED", "detail": f"rerun_{p}: {res.get('detail')}"}
        args += ["--rerun", *[f"{p}={st['panels'][f'rerun_{p}']['run_dir']}" for p in ("core", "scale")]]
        code = run([PY, script, *args], "select")
    if code != 0:
        return {"status": "FAILED", "exit_code": code, "detail": "pilot_select_v3.py phase 1 failed (see select.log)"}
    res = _panel_run(st, "quality_check", "configs/v3_dev_quality_check.yaml", "data/manifests/v3_dev_quality.jsonl")
    if res["status"] != "DONE":
        return {"status": "FAILED", "detail": f"quality_check: {res.get('detail')}"}
    code = run([PY, script, "--phase", "2", "--quality-check", res["run_dir"]], "select")
    return {"status": "DONE" if code == 0 else "FAILED", "exit_code": code,
            "detail": "analysis/v3_select/selected_methods.json"}


def stage_freeze(st):
    if st["stages"].get("select", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "select not DONE"}
    return script_stage("freeze_v3.py", [], "freeze", "analysis/v3_freeze/freeze.json")


def stage_confirm(st):
    if st["stages"].get("freeze", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "freeze not DONE: the holdout is never touched before the freeze"}
    freeze = json.loads((ROOT / "analysis" / "v3_freeze" / "freeze.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT))
    from cape.provenance import source_tree_hash

    src = source_tree_hash()
    if src != freeze["expected_source_hash"]:
        return {"status": "BLOCKED", "detail": f"source tree {src[:12]} differs from the freeze "
                f"{freeze['expected_source_hash'][:12]}: a frozen input changed (a new freeze = protocol amendment)"}
    out = {}
    for name, spec in freeze["confirm_runs"].items():
        key = f"confirm_{name}"
        prev = st["panels"].get(key, {})
        if prev.get("status") == "DONE":
            out[name] = prev
            continue
        st["panels"][key] = dict(prev, status="RUNNING", started_at=now())
        save_state(st)
        t0 = time.time()
        res = pipeline(spec["config"], spec["manifest"], key, stage="all")
        res.update(started_at=st["panels"][key]["started_at"], ended_at=now(), seconds=round(time.time() - t0, 1))
        st["panels"][key] = res
        save_state(st)
        out[name] = res
    ok = all(r.get("status") == "DONE" for r in out.values())
    return {"status": "DONE" if ok else "FAILED", "detail": {k: v.get("run_dir") for k, v in out.items()}}


def stage_analyze(st):
    if st["stages"].get("confirm", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "confirm not DONE"}
    return script_stage("report_v3.py", ["--state", str(STATE.relative_to(ROOT))], "analyze",
                        "analysis/v3_final/V3_YAKUNIY_TAHLIL_UZ.md")


def stage_package(st):
    if st["stages"].get("analyze", {}).get("status") != "DONE":
        return {"status": "BLOCKED", "detail": "analyze not DONE"}
    return script_stage("package_v3.py", ["--state", str(STATE.relative_to(ROOT))], "package", "results/v3_<id>/")


FUNCS = {s: globals()[f"stage_{s}"] for s in STAGES}


def print_status(st: dict) -> None:
    for s in STAGES:
        v = st["stages"].get(s, {})
        print(f"  {s:8s} {v.get('status', '-'):9s} {v.get('detail') if not isinstance(v.get('detail'), dict) else ''}")
    for p, v in st["panels"].items():
        print(f"    panel {p:16s} {v.get('status', '-'):9s} {v.get('run_dir')}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=STAGES + ["all", "report-status"], default="all")
    ap.add_argument("--resume", action="store_true", help="skip stages already DONE (default for --stage all)")
    ap.add_argument("--restart", action="store_true", help="forget the stage state (finished runs stay on disk)")
    args = ap.parse_args(argv)
    if not PY.exists():
        print("ERROR: .venv missing - run `run_experiment.cmd --stage smoke` once to bootstrap", file=sys.stderr)
        return 2
    st = {"created_at": now(), "stages": {}, "panels": {}} if args.restart else load_state()
    if args.stage == "report-status":
        print_status(st)
        return 0
    todo = STAGES if args.stage == "all" else [args.stage]
    for name in todo:
        prev = st["stages"].get(name, {})
        if (args.stage == "all" or args.resume) and prev.get("status") == "DONE":
            print(f"[{name}] DONE (resume)")
            continue
        t0 = time.time()
        st["stages"][name] = dict(prev, status="RUNNING", started_at=now())
        save_state(st)
        print(f"[{name}] running ...", flush=True)
        res = FUNCS[name](st)
        res.update(started_at=st["stages"][name]["started_at"], ended_at=now(), seconds=round(time.time() - t0, 1))
        st["stages"][name] = res
        save_state(st)
        print(f"[{name}] {res['status']} {res.get('detail') or ''}", flush=True)
        if args.stage == "all" and res["status"] != "DONE":
            print(f"[{name}] stopped: later stages depend on it")
            break
    print_status(st)
    return 0 if all(st["stages"].get(s, {}).get("status") == "DONE" for s in todo) else 1


if __name__ == "__main__":
    sys.exit(main())
