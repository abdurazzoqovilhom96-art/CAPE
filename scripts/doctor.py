"""Environment and dependency check; writes environment.json (spec sections 20, 36 PREFLIGHT).

Usage:
    python scripts/doctor.py [--out PATH] [--require-native]

Collects OS/CPU topology/RAM/disk/GPU/power plan, compiler and package versions, pinned
source commits and native-module status. No device serials or UUIDs are collected.
Exit codes: 0 ok, 2 a required dependency is missing.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import importlib.metadata as md
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import PYPI_CRACKLE_VERSION, VENDOR_CRACKLE_SHA  # noqa: E402
from cape import resources  # noqa: E402

PACKAGES = ["numpy", "scipy", "pandas", "matplotlib", "h5py", "tifffile", "pyyaml", "jsonschema",
            "psutil", "pytest", "hypothesis", "pybind11", "scikit-build-core", "cmake", "ninja",
            "crackle-codec", "compresso", "compressed-segmentation", "zstandard", "blosc2", "ortools"]


def _first_line(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    _rc, text = resources.run_text([exe, *cmd[1:]])
    text = text.strip()
    return text.splitlines()[0] if text else None


def collect(require_native: bool) -> tuple[dict, list[str]]:
    problems: list[str] = []
    versions = {}
    for pkg in PACKAGES:
        try:
            versions[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            versions[pkg] = None
            problems.append(f"python package missing: {pkg}")
    if versions.get("crackle-codec") not in (None, PYPI_CRACKLE_VERSION):
        problems.append(f"crackle-codec {versions['crackle-codec']} != pinned {PYPI_CRACKLE_VERSION}")

    lock_path = ROOT / "sources.lock.json"
    sources = json.loads(lock_path.read_text(encoding="utf-8"))["sources"] if lock_path.exists() else {}
    crackle_src = sources.get("crackle", {})
    if crackle_src.get("commit") != VENDOR_CRACKLE_SHA:
        problems.append("vendor/crackle is not fetched at the pinned commit (run scripts/fetch_sources.py)")

    native = {}
    for mod in ("_crackle_vendor", "_cape_native"):
        try:
            m = importlib.import_module(f"cape.{mod}")
            native[mod] = {"available": True, "file": Path(m.__file__).name}
        except ImportError as exc:
            native[mod] = {"available": False, "error": str(exc)[:300]}
            if require_native:
                problems.append(f"native module {mod} unavailable: {exc}")

    build_report = ROOT / "build" / "native_build.json"
    topo = resources.cpu_topology()
    env = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "os": resources.os_info(),
        "cpu": topo,
        "timing_cpu": resources.timing_cpu(topo),
        "memory": resources.memory_info(),
        "disk_free_bytes": {"project": resources.disk_free_bytes(ROOT)},
        "gpu": resources.gpu_info(),
        "power_scheme": resources.power_scheme(),
        "python": {"version": sys.version.split()[0], "executable": sys.executable,
                   "implementation": sys.implementation.name},
        "toolchain": {"g++": _first_line(["g++", "--version"]), "cmake": _first_line(["cmake", "--version"]),
                      "ninja": _first_line(["ninja", "--version"]), "git": _first_line(["git", "--version"])},
        "packages": versions,
        "sources": sources,
        "native_modules": native,
        "native_build": json.loads(build_report.read_text(encoding="utf-8")) if build_report.exists() else None,
        "problems": problems,
    }
    if env["toolchain"]["g++"] is None:
        problems.append("g++ (MinGW-w64) not on PATH")
    return env, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "build" / "environment.json"))
    ap.add_argument("--require-native", action="store_true")
    args = ap.parse_args(argv)
    env, problems = collect(args.require_native)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    t = env["timing_cpu"]
    print(f"environment: {out}")
    print(f"cpu: {env['os']['processor_name']} | P-cores={env['cpu'].get('performance_cores')} "
          f"E-cores={env['cpu'].get('efficiency_cores')} | timing cpu={t['cpu']} siblings={t['siblings']}")
    for p in problems:
        print("PROBLEM: " + p, file=sys.stderr)
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
