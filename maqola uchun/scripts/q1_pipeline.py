"""CAPE Q1 single entry point (task v3, section 2): preflight -> frozen final experiment -> raw audit -> analysis ->
article package -> validation -> `maqola uchun/`.

    .venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode full --fresh-run --output "maqola uchun"
    .venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode full --resume-run q1_20261107T120000Z
    .venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode audit
    .venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode render --run-id q1_20261107T120000Z --output "maqola uchun"

--fresh-run   opens a new Q1 run id and measures every frozen cell anew (no earlier result is reused)
--resume-run  continues THAT run after an interruption; the source/config/manifest hashes must equal the freeze
--mode audit  diagnostics only (tools/q1_audit.py); not the final task
--mode render rebuilds the article package from a finished, verified run without measuring anything

State: results/<run_id>/q1_state.json (atomic). Each child measurement run is a normal run_all.py run directory.
Exit codes: 0 complete, 1 a stage failed or is PARTIAL, 2 usage/preflight error (nothing measured).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
FREEZE = ROOT / "analysis" / "q1_freeze"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def log(state_dir: Path, msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with open(state_dir / "q1_pipeline.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------------------------------- preflight
def preflight() -> tuple[bool, list[str], dict]:
    sys.path.insert(0, str(ROOT))
    from cape.provenance import source_tree_hash

    problems = []
    try:
        frz = json.loads((FREEZE / "freeze.json").read_text(encoding="utf-8"))
        plan = json.loads((FREEZE / "experiment_plan.json").read_text(encoding="utf-8"))
        json.loads((FREEZE / "success_criteria.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, [f"freeze missing: {exc} (run tools/q1_freeze.py)"], {}
    h = frz["hashes"]
    src = source_tree_hash()
    if src != frz["expected_source_hash"]:
        problems.append(f"source tree {src[:12]} != freeze {frz['expected_source_hash'][:12]} (a changed source needs a "
                        "new freeze = protocol amendment)")
    for key, rel in (("E0_binary", "snapshots/v3/_cape_native.cp312-win_amd64.pyd"),
                     ("v21_binary", "snapshots/v21/_cape_native.cp312-win_amd64.pyd"),
                     ("Etheta_binary", "cape/_cape_native.cp312-win_amd64.pyd")):
        if sha_file(ROOT / rel) != h[key]:
            problems.append(f"{key} {rel} changed since the freeze")
    for k, v in plan["runs"].items():
        if sha_file(ROOT / v["config"]) != h["configs"][k]:
            problems.append(f"config {v['config']} changed since the freeze")
    for m, s in h["manifests"].items():
        if sha_file(ROOT / m) != s:
            problems.append(f"manifest {m} changed since the freeze")
    issues = ROOT / "audit" / "issue_register.csv"
    if issues.exists():
        import csv

        with open(issues, encoding="utf-8") as fh:
            open_corr = [r["id"] for r in csv.DictReader(fh) if r["impact"] in ("correctness", "measurement validity")
                         and not r["status"].startswith(("FIXED", "VERIFIED", "DISCLOSED", "AUDITED"))]
        if open_corr:
            problems.append(f"open correctness/measurement issues: {open_corr}")
    else:
        problems.append("audit/issue_register.csv missing (run --mode audit first)")
    return not problems, problems, {"freeze": frz, "plan": plan}


# ---------------------------------------------------------------------------------------------- runs
def child_run(state: dict, state_dir: Path, key: str, spec: dict, resume: bool) -> dict:
    prev = state["runs"].get(key, {})
    if prev.get("status") == "DONE":
        return prev
    cmd = [PY, ROOT / "run_all.py", "--stage", "all", "--config", spec["config"], "--manifest", spec["manifest"]]
    if resume and prev.get("run_dir"):
        cmd.append("--resume")
    state["runs"][key] = dict(prev, status="RUNNING", started_at=now(), config=spec["config"],
                              manifest=spec["manifest"])
    save(state_dir / "q1_state.json", state)
    log(state_dir, f"run {key}: {' '.join(map(str, cmd[1:]))}")
    with open(state_dir / f"run_{key}.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {now()} {' '.join(map(str, cmd))}\n")
        fh.flush()
        code = subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    latest = (ROOT / "results" / "LATEST_RUN.txt").read_text(encoding="utf-8").strip()
    rd = Path(latest) if Path(latest).is_absolute() else ROOT / latest
    man = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")) if (rd / "run_manifest.json").exists() \
        else {}
    ok = code == 0 and man.get("status") == "COMPLETE"
    res = {"status": "DONE" if ok else "FAILED", "exit_code": code, "run_dir": rd.relative_to(ROOT).as_posix(),
           "run_status": man.get("status"), "source_hash": man.get("source_hash"), "config": spec["config"],
           "manifest": spec["manifest"], "started_at": state["runs"][key]["started_at"], "ended_at": now()}
    state["runs"][key] = res
    save(state_dir / "q1_state.json", state)
    log(state_dir, f"run {key}: {res['status']} {res['run_dir']} (exit {code}, {res['run_status']})")
    return res


def stage(state: dict, state_dir: Path, name: str, cmd: list) -> bool:
    if state["stages"].get(name, {}).get("status") == "DONE":
        return True
    state["stages"][name] = {"status": "RUNNING", "started_at": now()}
    save(state_dir / "q1_state.json", state)
    with open(state_dir / f"stage_{name}.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {now()} {' '.join(map(str, cmd))}\n")
        fh.flush()
        code = subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    state["stages"][name] = {"status": "DONE" if code == 0 else "FAILED", "exit_code": code,
                             "started_at": state["stages"][name]["started_at"], "ended_at": now()}
    save(state_dir / "q1_state.json", state)
    log(state_dir, f"stage {name}: {state['stages'][name]['status']} (exit {code})")
    return code == 0


def full(run_id: str | None, fresh: bool, output: str) -> int:
    ok, problems, ctx = preflight()
    if not ok:
        print("PREFLIGHT FAILED - nothing measured:\n  " + "\n  ".join(problems))
        return 2
    if fresh:
        run_id = "q1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        state_dir = ROOT / "results" / run_id
        if state_dir.exists():
            print(f"refusing: {state_dir} exists")
            return 2
        state = {"run_id": run_id, "created_at": now(), "mode": "fresh", "freeze": ctx["freeze"]["written_at"],
                 "expected_source_hash": ctx["freeze"]["expected_source_hash"], "runs": {}, "stages": {},
                 "output": output}
    else:
        state_dir = ROOT / "results" / run_id
        sp = state_dir / "q1_state.json"
        if not sp.exists():
            print(f"no such Q1 run: {run_id}")
            return 2
        state = json.loads(sp.read_text(encoding="utf-8"))
        if state["expected_source_hash"] != ctx["freeze"]["expected_source_hash"]:
            print("refusing to resume: the freeze changed since this run started (results would mix protocols)")
            return 2
        state["resumed_at"] = state.get("resumed_at", []) + [now()]
    state_dir.mkdir(parents=True, exist_ok=True)
    save(state_dir / "q1_state.json", state)
    (ROOT / "results" / "LATEST_Q1_RUN.txt").write_text(run_id, encoding="utf-8")
    log(state_dir, f"Q1 run {run_id} ({'fresh' if fresh else 'resume'}); freeze source "
                   f"{ctx['freeze']['expected_source_hash'][:12]}")
    plan = ctx["plan"]
    failed = []
    for key in plan["order"]:
        res = child_run(state, state_dir, key, plan["runs"][key], resume=not fresh)
        if res["status"] != "DONE":
            failed.append(key)
        elif res.get("source_hash") != ctx["freeze"]["expected_source_hash"]:
            failed.append(key)
            state["runs"][key]["status"] = "INVALIDATED"
            state["runs"][key]["reason"] = "run source hash differs from the freeze"
            save(state_dir / "q1_state.json", state)
    if failed:
        state["status"] = "PARTIAL"
        state["resume_command"] = f'.venv\\Scripts\\python.exe tools\\q1_pipeline.py --mode full --resume-run {run_id}'
        save(state_dir / "q1_state.json", state)
        log(state_dir, f"PARTIAL: runs not DONE {failed}; resume: {state['resume_command']}")
    rc = 0 if not failed else 1
    if not render(run_id, output, state=state, partial=bool(failed)):
        rc = 1
    return rc


def render(run_id: str, output: str, state: dict | None = None, partial: bool = False) -> bool:
    state_dir = ROOT / "results" / run_id
    state = state or json.loads((state_dir / "q1_state.json").read_text(encoding="utf-8"))
    for k in ("raw_audit", "article", "validate", "place"):
        state.setdefault("stages", {}).pop(k, None)  # always rebuilt from the raw data
    ok = stage(state, state_dir, "raw_audit", [PY, ROOT / "tools" / "q1_article.py", "--run-id", run_id, "--raw-audit"])
    ok = stage(state, state_dir, "article", [PY, ROOT / "tools" / "q1_article.py", "--run-id", run_id, "--build"]) and ok
    ok = stage(state, state_dir, "validate", [PY, ROOT / "tools" / "validate_article_package.py", "--run-id", run_id]) \
        and ok
    staging = state_dir / "article_staging"
    if staging.exists():
        place(staging, ROOT / output, run_id, complete=ok and not partial)
        state["stages"]["place"] = {"status": "DONE", "output": output, "complete": ok and not partial, "at": now()}
    state["status"] = "COMPLETE" if ok and not partial else "PARTIAL"
    save(state_dir / "q1_state.json", state)
    log(state_dir, f"Q1 run {run_id}: {state['status']} -> {output}")
    return ok


def place(staging: Path, out: Path, run_id: str, complete: bool) -> None:
    """Move the verified staging package into `maqola uchun/`; an earlier package is archived under its run id."""
    if out.exists():
        prev = out / "README_UZ.md"
        tag = "unknown"
        if prev.exists():
            for line in prev.read_text(encoding="utf-8").splitlines():
                if line.startswith("Run ID:"):
                    tag = line.split(":", 1)[1].strip().strip("`")
        arch = out.parent / f"{out.name}_archive_{tag}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        out.rename(arch)
    shutil.copytree(staging, out)
    if not complete:
        readme = out / "README_UZ.md"
        txt = readme.read_text(encoding="utf-8") if readme.exists() else ""
        if "PARTIAL" not in txt.splitlines()[0:3].__str__():
            readme.write_text("> **HOLAT: PARTIAL** - paket to'liq tugallanmagan; sababi `checks/` va "
                              "`YAKUNIY_AUDIT_VA_Q1_XULOSA_UZ.md` da.\n\n" + txt, encoding="utf-8")
    zp = out.parent / "maqola_uchun.zip"
    if zp.exists():
        zp.unlink()
    shutil.make_archive(str(zp.with_suffix("")), "zip", root_dir=out.parent, base_dir=out.name)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=["full", "audit", "render"])
    ap.add_argument("--fresh-run", action="store_true")
    ap.add_argument("--resume-run")
    ap.add_argument("--run-id")
    ap.add_argument("--output", default="maqola uchun")
    a = ap.parse_args(argv)
    if a.fresh_run and a.resume_run:
        ap.error("--fresh-run and --resume-run are mutually exclusive")
    if a.mode == "audit":
        return subprocess.call([str(PY), str(ROOT / "tools" / "q1_audit.py")], cwd=ROOT)
    if a.mode == "render":
        if not a.run_id:
            ap.error("--mode render needs --run-id")
        return 0 if render(a.run_id, a.output) else 1
    if not (a.fresh_run or a.resume_run):
        ap.error("--mode full needs --fresh-run or --resume-run RUN_ID")
    return full(a.resume_run, a.fresh_run, a.output)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # console/redirect encodings on Windows (cp1252)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
