"""Resumable environment bootstrap (stdlib only; spec sections 30 and 36 INIT).

Steps (each skipped when its fingerprint is unchanged):
  1. venv      .venv with CPython 3.12
  2. deps      pip install --require-hashes -r requirements.lock (only when the lock changed;
               pip itself is never upgraded from the internet on a normal run)
  3. sources   scripts/fetch_sources.py (pinned commits)
  4. native    scripts/build_native.py (when C++ sources, vendor commit or compiler changed)
  5. doctor    scripts/doctor.py -> environment.json

Usable as a library (run_all.py INIT calls `bootstrap()`) or as a CLI:
    py -3.12 scripts/bootstrap.py [--log PATH] [--env-out PATH] [--force]
Exit codes: 0 ok, 2 missing dependency / toolchain / build failure.
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

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MARKER = VENV / "cape_bootstrap.json"
LOCKFILE = ROOT / "requirements.lock"
REQUIRED_PY = (3, 12)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _sha256_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda q: q.as_posix()):
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _native_fingerprint() -> str:
    files = [ROOT / "CMakeLists.txt"]
    for sub in ("cpp",):
        files += [p for p in (ROOT / sub).rglob("*") if p.is_file()]
    lock = ROOT / "sources.lock.json"
    extra = lock.read_text(encoding="utf-8") if lock.exists() else ""
    gxx = subprocess.run(["g++", "--version"], capture_output=True).stdout[:200] if _which("g++") else b""
    return hashlib.sha256(_sha256_files(files).encode() + extra.encode() + gxx).hexdigest()


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


class Logger:
    def __init__(self, path: Path | None, quiet: bool):
        self.path = path
        self.quiet = quiet
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        line = f"[{_now()}] {msg}"
        if not self.quiet:
            print(line, flush=True)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def run(self, cmd: list[str]) -> int:
        self(f"$ {' '.join(str(c) for c in cmd)}")
        proc = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True)
        out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(out)
        if proc.returncode != 0 and not self.quiet:
            print(out[-3000:], file=sys.stderr)
        return proc.returncode


def _load_marker() -> dict:
    try:
        return json.loads(MARKER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_marker(data: dict) -> None:
    tmp = MARKER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, MARKER)


def bootstrap(log_path: Path | None = None, env_out: Path | None = None, force: bool = False,
              quiet: bool = False) -> tuple[bool, list[dict]]:
    """Run all steps; returns (ok, step records). Never raises for expected failures."""
    log = Logger(log_path, quiet)
    steps: list[dict] = []

    def step(name: str, status: str, detail: str = "") -> None:
        steps.append({"step": name, "status": status, "detail": detail, "at": _now()})
        log(f"{name}: {status} {detail}".rstrip())

    # 1. venv -----------------------------------------------------------------
    if not VENV_PY.exists():
        if sys.version_info[:2] != REQUIRED_PY:
            step("venv", "FAILED", f"needs CPython {REQUIRED_PY[0]}.{REQUIRED_PY[1]} to create .venv "
                 f"(running {sys.version.split()[0]}); run via 'py -3.12'")
            return False, steps
        if log.run([sys.executable, "-m", "venv", str(VENV)]) != 0:
            step("venv", "FAILED", "python -m venv failed")
            return False, steps
        step("venv", "CREATED", str(VENV))
    else:
        step("venv", "OK", str(VENV))
    ver = subprocess.run([str(VENV_PY), "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                         capture_output=True, text=True).stdout.strip()
    if ver != f"{REQUIRED_PY[0]}.{REQUIRED_PY[1]}":
        step("venv", "FAILED", f".venv uses Python {ver}, expected 3.12; delete .venv and rerun")
        return False, steps

    marker = _load_marker()

    # 2. dependencies ---------------------------------------------------------
    if not LOCKFILE.exists():
        step("deps", "FAILED", "requirements.lock missing")
        return False, steps
    lock_sha = hashlib.sha256(LOCKFILE.read_bytes()).hexdigest()
    if force or marker.get("lock_sha256") != lock_sha:
        rc = log.run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
                      "--require-hashes", "-r", str(LOCKFILE)])
        if rc != 0:
            step("deps", "FAILED", "pip install --require-hashes failed (network or lock problem); see log")
            return False, steps
        marker["lock_sha256"] = lock_sha
        marker["deps_installed_at"] = _now()
        _save_marker(marker)
        step("deps", "INSTALLED", lock_sha[:16])
    else:
        step("deps", "OK", f"lock {lock_sha[:16]} unchanged")

    # 3. sources --------------------------------------------------------------
    if log.run([str(VENV_PY), str(ROOT / "scripts" / "fetch_sources.py")]) != 0:
        step("sources", "FAILED", "pinned sources unavailable (git/network); see log")
        return False, steps
    step("sources", "OK")

    # 4. native build ---------------------------------------------------------
    fp = _native_fingerprint()
    have_modules = all(any((ROOT / "cape").glob(f"{m}*.pyd")) or any((ROOT / "cape").glob(f"{m}*.so"))
                       for m in ("_crackle_vendor", "_cape_native"))
    if force or marker.get("native_fingerprint") != fp or not have_modules:
        if log.run([str(VENV_PY), str(ROOT / "scripts" / "build_native.py")]) != 0:
            step("native", "FAILED", "native build failed; see build/native_build.log")
            return False, steps
        marker["native_fingerprint"] = fp
        marker["native_built_at"] = _now()
        _save_marker(marker)
        step("native", "BUILT", fp[:16])
    else:
        step("native", "OK", f"fingerprint {fp[:16]} unchanged")

    # 5. doctor ---------------------------------------------------------------
    cmd = [str(VENV_PY), str(ROOT / "scripts" / "doctor.py"), "--require-native"]
    if env_out:
        cmd += ["--out", str(env_out)]
    if log.run(cmd) != 0:
        step("doctor", "FAILED", "environment check reported problems; see environment.json")
        return False, steps
    step("doctor", "OK")
    return True, steps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", type=Path, default=ROOT / "build" / "bootstrap.log")
    ap.add_argument("--env-out", type=Path, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    ok, steps = bootstrap(args.log, args.env_out, args.force, args.quiet)
    if not ok:
        failed = [s for s in steps if s["status"] == "FAILED"]
        print("BOOTSTRAP FAILED: " + "; ".join(f"{s['step']}: {s['detail']}" for s in failed), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
