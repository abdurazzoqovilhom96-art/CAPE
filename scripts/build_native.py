"""Configure and build the native modules with CMake + Ninja + MinGW g++ (stdlib only).

Run with the project venv interpreter:
    .venv\\Scripts\\python scripts\\build_native.py [--target NAME] [--clean]

Outputs cape/_crackle_vendor*.pyd and cape/_cape_native*.pyd, then verifies that each module
imports and that no MinGW runtime DLL (libstdc++, libgcc, libwinpthread) is required.
Writes build/native_build.json (compiler, flags, versions, output hashes).
Exit codes: 0 ok, 2 missing toolchain/dependency, 6 build or verification failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "native"
REPORT = ROOT / "build" / "native_build.json"
LOG = ROOT / "build" / "native_build.log"
MODULES = ("_crackle_vendor", "_cape_native")
FORBIDDEN_DLLS = ("libstdc++", "libgcc", "libwinpthread")


def _tool(name: str) -> str | None:
    venv_scripts = Path(sys.executable).parent
    for cand in (venv_scripts / f"{name}.exe", venv_scripts / name):
        if cand.exists():
            return str(cand)
    return shutil.which(name)


def _first_line(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    text = (out.stdout or out.stderr or b"").decode("utf-8", errors="replace").strip()
    return text.splitlines()[0] if text else "unavailable"


def _cached_compiler() -> str | None:
    cache = BUILD / "CMakeCache.txt"
    if not cache.exists():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_CXX_COMPILER:"):
            return line.split("=", 1)[1].strip()
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dll_imports(path: Path) -> list[str] | None:
    objdump = shutil.which("objdump")
    if objdump is None:
        return None
    out = subprocess.run([objdump, "-p", str(path)], capture_output=True, text=True)
    return [ln.split("DLL Name:")[1].strip() for ln in out.stdout.splitlines() if "DLL Name:" in ln]


def _run(cmd: list[str], log) -> int:
    log.write("$ " + " ".join(cmd) + "\n")
    log.flush()
    proc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", action="append", default=[], help="build only this target")
    ap.add_argument("--clean", action="store_true", help="remove the build directory first")
    args = ap.parse_args(argv)

    cmake, ninja, gxx = _tool("cmake"), _tool("ninja"), shutil.which("g++")
    missing = [n for n, p in (("cmake", cmake), ("ninja", ninja), ("g++ (MinGW-w64)", gxx)) if p is None]
    try:
        import pybind11  # noqa: PLC0415
    except ImportError:
        missing.append("pybind11 (pip)")
    if missing:
        print("ERROR: missing build dependencies: " + ", ".join(missing), file=sys.stderr)
        return 2
    if not (ROOT / "vendor" / "crackle" / "src" / "crackle.hpp").exists():
        print("ERROR: vendor/crackle missing; run scripts/fetch_sources.py", file=sys.stderr)
        return 2

    gxx = str(Path(gxx).resolve())
    cached = _cached_compiler()
    if cached is not None and Path(cached).resolve().as_posix().lower() != Path(gxx).as_posix().lower():
        args.clean = True  # a compiler change makes CMake drop the cache mid-configure
    if args.clean and BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.parent.mkdir(parents=True, exist_ok=True)
    env_note = {"CXX": gxx}
    with LOG.open("w", encoding="utf-8") as log:
        log.write(f"# build started {_dt.datetime.now().isoformat(timespec='seconds')}\n")
        rc = _run([cmake, "-S", str(ROOT), "-B", str(BUILD), "-G", "Ninja",
                   "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_CXX_COMPILER={gxx}",
                   f"-DCMAKE_MAKE_PROGRAM={ninja}", f"-DPython_EXECUTABLE={sys.executable}",
                   f"-Dpybind11_DIR={pybind11.get_cmake_dir()}"], log)
        if rc == 0:
            cmd = [cmake, "--build", str(BUILD), "--parallel"]
            for t in args.target:
                cmd += ["--target", t]
            rc = _run(cmd, log)
    if rc != 0:
        print(f"ERROR: native build failed (see {LOG})", file=sys.stderr)
        print("".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines(True)[-40:]), file=sys.stderr)
        return 6

    wanted = args.target or list(MODULES)
    outputs, problems = {}, []
    for mod in wanted:
        hits = sorted((ROOT / "cape").glob(f"{mod}*.pyd")) + sorted((ROOT / "cape").glob(f"{mod}*.so"))
        if not hits:
            problems.append(f"{mod}: no output module found")
            continue
        path = hits[-1]
        imports = _dll_imports(path)
        bad = [d for d in (imports or []) if any(d.lower().startswith(f) for f in FORBIDDEN_DLLS)]
        if bad:
            problems.append(f"{mod}: depends on MinGW runtime DLLs {bad}")
        check = subprocess.run([sys.executable, "-c", f"import cape.{mod} as m; print(m.__name__)"],
                               cwd=ROOT, capture_output=True, text=True)
        if check.returncode != 0:
            problems.append(f"{mod}: import failed: {check.stderr.strip()[-400:]}")
        outputs[mod] = {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path),
                        "dll_imports": imports}

    report = {
        "built_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "compiler": _first_line([gxx, "--version"]),
        "cmake": _first_line([cmake, "--version"]),
        "ninja": _first_line([ninja, "--version"]),
        "python": sys.version.split()[0],
        "pybind11": pybind11.__version__,
        "opt_flags": ["-O3", "-msse4.2", "-mpclmul", "-std=c++20", "-static (link)"],
        "env": env_note,
        "outputs": outputs,
        "problems": problems,
    }
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, REPORT)
    if problems:
        for p in problems:
            print("ERROR: " + p, file=sys.stderr)
        return 6
    for mod, info in outputs.items():
        print(f"{mod}: {info['file']} ({info['bytes']} B) sha256={info['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
