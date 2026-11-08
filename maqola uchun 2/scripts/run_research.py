"""B protocol single entry point (docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md, section 12).

    python tools/run_research.py --mode full --fresh-run          # INVENTORY -> ... -> VALIDATION
    python tools/run_research.py --mode full --resume-run RUN_ID  # continue (finished stages / samples are kept)
    python tools/run_research.py --mode render --run-id RUN_ID    # ANALYSIS -> ARTICLE -> VALIDATION only

Stages: INVENTORY -> STAGE0_FIXES -> PRECHECKS (G1) -> NATIVE_BASELINE -> PROTOTYPE -> GATE (G2) -> ANALYSIS ->
ARTICLE -> VALIDATION. State: results/<run_id>/research_state.json (atomic). Native measurements reuse run_all.py
(cape/runner.py, SQLite store, resume keys). Prototype tasks: results/<run_id>/prototype.sqlite (one row per sample,
key = hash(source, input, mode, config, env lock)). Timing stages run alone: nothing CPU-heavy in parallel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PY = Path(sys.executable)
PROTOCOL = ROOT / "docs" / "CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md"
DEV_MANIFEST = ROOT / "data" / "manifests" / "q1b_dev.jsonl"
NATIVE_CONFIG = ROOT / "configs" / "q1b_dev_native.yaml"
PROTO = {"budget_s": 1800.0, "max_iter": 40, "k_add": 50_000, "hard_timeout_s": 3600}
STAGES = ["INVENTORY", "STAGE0_FIXES", "PRECHECKS", "NATIVE_BASELINE", "PROTOTYPE", "GATE", "ANALYSIS", "ARTICLE",
          "VALIDATION"]
DEV_SAMPLES = [  # frozen in the protocol (section 10) before any prototype result
    "cremi_A_x0_y768_z0_256x256x64", "cremi_A_x256_y0_z0_256x256x64", "cremi_A_x512_y0_z0_256x256x64",
    "cremi_B_x0_y256_z64_256x256x60", "cremi_B_x256_y0_z64_256x256x60", "cremi_B_x256_y512_z64_256x256x60",
    "cremi_C_x0_y256_z64_256x256x60", "cremi_C_x0_y768_z64_256x256x60", "cremi_C_x256_y512_z64_256x256x60",
    "crackle_connectomics_x256_y256_z0_256x256x512", "crackle_ws_x0_y0_z0_256x256x512"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def log(rd: Path, msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with open(rd / "research.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def env_lock_hash() -> str:
    return sha256_file(ROOT / "requirements.lock")[:16]


# ----------------------------------------------------------------------------------------------------- stages
def st_inventory(rd: Path, state: dict) -> None:
    from cape.provenance import source_tree_hash

    rows = [json.loads(x) for x in DEV_MANIFEST.read_text(encoding="utf-8").splitlines() if x.strip()]
    ids = [r["sample_id"] for r in rows]
    if ids != DEV_SAMPLES:
        raise SystemExit(f"dev manifest != frozen list: {ids}")
    miss = [r["path"] for r in rows if not (ROOT / r["path"]).exists()]
    if miss:
        raise SystemExit(f"BLOCKED_INPUT: missing {miss}")
    state["inventory"] = {"source_hash": source_tree_hash(), "git_head": git("rev-parse", "--short", "HEAD"),
                          "git_dirty_code": git("status", "--porcelain", "--", "cape", "cpp", "tools", "tests",
                                                "configs", "scripts"),
                          "env_lock_hash": env_lock_hash(), "protocol_sha256": sha256_file(PROTOCOL),
                          "dev_samples": [{"sample_id": r["sample_id"], "source_id": r.get("source_id"),
                                           "dtype": r["dtype"], "shape": r["shape"],
                                           "voxel_sha256": r.get("voxel_sha256")} for r in rows],
                          "prototype_config": PROTO}


def st_stage0(rd: Path, state: dict) -> None:
    """Stage 0 (Q1 package fixes) was done before this run; record its evidence (commit, amendment run, render)."""
    s0 = json.loads((ROOT / "results" / "q1b_stage0.json").read_text(encoding="utf-8"))
    if s0.get("status") != "DONE":
        raise SystemExit("Stage 0 not finished (results/q1b_stage0.json)")
    state["stage0"] = s0


def st_prechecks(rd: Path, state: dict) -> None:
    junit = rd / "prechecks_junit.xml"
    cmd = [str(PY), "-m", "pytest", "tests/test_cg_prechecks.py", "-q", "-p", "no:cacheprovider",
           f"--junitxml={junit}"]
    code = subprocess.call(cmd, cwd=ROOT, stdout=open(rd / "prechecks.log", "w", encoding="utf-8"),
                           stderr=subprocess.STDOUT)
    import xml.etree.ElementTree as ET

    counts = {}
    for tc in ET.parse(junit).getroot().iter("testcase"):
        name = tc.get("name", "")
        t = name.split("_")[1] if name.startswith("test_T") else "other"
        res = "failed" if tc.find("failure") is not None or tc.find("error") is not None else (
            "skipped" if tc.find("skipped") is not None else "passed")
        counts.setdefault(t, {"passed": 0, "failed": 0, "skipped": 0})[res] += 1
    g1_tests = code == 0 and all(v["failed"] == 0 for v in counts.values())
    state["prechecks"] = {"exit_code": code, "by_check": counts, "tests_pass": g1_tests}
    if not g1_tests:
        state["terminal"] = "BLOCKED_PRECHECK"
        raise StopRun("G1 failed in the synthetic/real prechecks")


def st_native(rd: Path, state: dict) -> None:
    prev = state.get("native", {})
    cmd = [str(PY), str(ROOT / "run_all.py"), "--stage", "all", "--config", str(NATIVE_CONFIG), "--manifest",
           str(DEV_MANIFEST)]
    if prev.get("run_dir"):
        cmd.append("--resume")
    log(rd, "native baseline (timing; nothing else runs)")
    with open(rd / "native_baseline.log", "a", encoding="utf-8") as fh:
        code = subprocess.call(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    latest = (ROOT / "results" / "LATEST_RUN.txt").read_text(encoding="utf-8").strip()
    run_dir = Path(latest) if Path(latest).is_absolute() else ROOT / latest
    man = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    state["native"] = {"run_dir": run_dir.relative_to(ROOT).as_posix(), "exit_code": code,
                       "status": man.get("status")}
    if code != 0 or man.get("status") != "COMPLETE":
        state["terminal"] = "COMPLETE_WITH_FAILURES"
        raise StopRun(f"native baseline failed (exit {code}, status {man.get('status')})")


def _proto_db(rd: Path) -> sqlite3.Connection:
    db = sqlite3.connect(rd / "prototype.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS task (task_key TEXT PRIMARY KEY, sample_id TEXT, status TEXT, "
               "attempts INTEGER, started_at TEXT, finished_at TEXT, json_path TEXT, exit_code INTEGER)")
    return db


def st_prototype(rd: Path, state: dict) -> None:
    import pandas as pd

    from cape.provenance import source_tree_hash

    src = source_tree_hash()
    rows = {r["sample_id"]: r for r in map(json.loads, DEV_MANIFEST.read_text(encoding="utf-8").splitlines()) if r}
    res = pd.read_csv(ROOT / state["native"]["run_dir"] / "05_raw_metrics" / "results.csv", low_memory=False)
    ok = res[(res.method_id == "cape_q1_fast_m0") & (res.status == "OK") & (res.panel == "B")]
    tb = ok.groupby("sample_id").total_bytes.first().to_dict()
    db = _proto_db(rd)
    (rd / "prototype").mkdir(exist_ok=True)
    for sid in DEV_SAMPLES:
        key = hashlib.sha256("|".join([src, rows[sid].get("voxel_sha256", ""), "cg_implicit", json.dumps(PROTO),
                                       env_lock_hash()]).encode()).hexdigest()[:20]
        cur = db.execute("SELECT status, attempts FROM task WHERE task_key=?", (key,)).fetchone()
        if cur and cur[0] in ("SUCCESS", "ERROR", "TIMEOUT") and (cur[0] == "SUCCESS" or cur[1] >= 2):
            continue  # terminal (bounded retry: at most one retry)
        att = (cur[1] if cur else 0) + 1
        out = rd / "prototype" / f"{sid}.json"
        db.execute("INSERT OR REPLACE INTO task VALUES (?,?,?,?,?,?,?,?)",
                   (key, sid, "RUNNING", att, now(), None, out.relative_to(ROOT).as_posix(), None))
        db.commit()
        cmd = [str(PY), str(ROOT / "tools" / "cg_prototype.py"), "--manifest", str(DEV_MANIFEST), "--sample-id", sid,
               "--out", str(out), "--budget-s", str(PROTO["budget_s"]), "--max-iter", str(PROTO["max_iter"]),
               "--k-add", str(PROTO["k_add"])]
        if sid in tb:
            cmd += ["--native-total-bytes", str(int(tb[sid]))]
        log(rd, f"prototype {sid} (attempt {att})")
        try:
            code = subprocess.call(cmd, cwd=ROOT, timeout=PROTO["hard_timeout_s"],
                                   stdout=open(rd / "prototype" / f"{sid}.log", "w", encoding="utf-8"),
                                   stderr=subprocess.STDOUT)
            status = "SUCCESS" if code == 0 and out.exists() else "ERROR"
        except subprocess.TimeoutExpired:
            code, status = -9, "TIMEOUT"
        db.execute("UPDATE task SET status=?, finished_at=?, exit_code=? WHERE task_key=?", (status, now(), code, key))
        db.commit()
        log(rd, f"prototype {sid}: {status}")
    state["prototype"] = {r[0]: {"status": r[1], "attempts": r[2], "json": r[3]} for r in db.execute(
        "SELECT sample_id, status, attempts, json_path FROM task ORDER BY sample_id")}


def st_gate(rd: Path, state: dict) -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from cg_article import evaluate_gate

    g = evaluate_gate(rd, state)
    save(rd / "gate.json", g)
    state["gate"] = {k: g[k] for k in ("G1", "G2", "terminal", "routes")}
    state["terminal"] = g["terminal"]


def st_article(rd: Path, state: dict, out_name: str) -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from cg_article import build

    state["article"] = build(rd, state, out_name)


def st_validate(rd: Path, state: dict, out_name: str) -> None:
    code = subprocess.call([str(PY), str(ROOT / "tools" / "validate_cg_package.py"), "--package",
                            str(ROOT / out_name), "--run-dir", str(rd)], cwd=ROOT)
    rep = json.loads((ROOT / out_name / "checks" / "validation_report.json").read_text(encoding="utf-8"))
    state["validation"] = {"exit_code": code, "summary": rep.get("summary")}


class StopRun(Exception):
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["full", "render"], default="full")
    ap.add_argument("--fresh-run", action="store_true")
    ap.add_argument("--resume-run")
    ap.add_argument("--run-id")
    ap.add_argument("--output", default="maqola uchun 2")
    a = ap.parse_args(argv)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if a.mode == "full":
        if bool(a.fresh_run) == bool(a.resume_run):
            ap.error("--mode full needs exactly one of --fresh-run / --resume-run")
        run_id = a.resume_run or "q1b_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    else:
        if not a.run_id:
            ap.error("--mode render needs --run-id")
        run_id = a.run_id
    rd = ROOT / "results" / run_id
    rd.mkdir(parents=True, exist_ok=True)
    sp = rd / "research_state.json"
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {"run_id": run_id, "created_at": now(),
                                                                            "stages": {}}
    (ROOT / "results" / "LATEST_Q1B_RUN.txt").write_text(run_id, encoding="utf-8")
    todo = STAGES if a.mode == "full" else ["ANALYSIS", "ARTICLE", "VALIDATION"]
    fn = {"INVENTORY": st_inventory, "STAGE0_FIXES": st_stage0, "PRECHECKS": st_prechecks,
          "NATIVE_BASELINE": st_native, "PROTOTYPE": st_prototype, "GATE": st_gate,
          "ANALYSIS": lambda r, s: None, "ARTICLE": lambda r, s: st_article(r, s, a.output),
          "VALIDATION": lambda r, s: st_validate(r, s, a.output)}
    stopped = None
    for stg in todo:
        if a.mode == "full" and state["stages"].get(stg, {}).get("status") == "DONE" and stg not in (
                "ANALYSIS", "ARTICLE", "VALIDATION"):
            continue
        if stopped and stg not in ("ANALYSIS", "ARTICLE", "VALIDATION"):
            state["stages"][stg] = {"status": "NOT_RUN_GATE_FAILED" if "GATE" in stopped or "G1" in stopped
                                    else "NOT_RUN", "reason": stopped}
            save(sp, state)
            continue
        state["stages"][stg] = {"status": "RUNNING", "started_at": now()}
        save(sp, state)
        log(rd, f"stage {stg}")
        try:
            fn[stg](rd, state)
            state["stages"][stg].update(status="DONE", finished_at=now())
        except StopRun as exc:
            stopped = str(exc)
            state["stages"][stg].update(status="STOPPED", finished_at=now(), reason=stopped)
            log(rd, f"stage {stg} stopped: {stopped}")
        save(sp, state)
    log(rd, f"terminal status: {state.get('terminal')}; package: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
