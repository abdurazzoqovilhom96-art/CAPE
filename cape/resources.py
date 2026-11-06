"""Hardware topology, CPU pinning, memory and disk checks (spec sections 18, 20, 36).

* CPU topology on Windows comes from GetSystemCpuSetInformation (EfficiencyClass per
  logical processor), so hybrid P/E cores are identified from the OS, not guessed.
* Peak memory uses the OS-tracked peak working set of a fresh worker process
  (mode `win_peak_wset_fresh_process`): the profiling worker records the peak just
  before the measured call and right after it. If the peak did not grow during the
  call, only an upper bound is known and that is recorded explicitly.
* No device serial numbers or UUIDs are collected.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import struct
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import psutil
except ImportError:  # INIT/doctor must still work without third-party packages
    psutil = None


@dataclass(frozen=True)
class LogicalCpu:
    index: int  # logical processor number usable with process affinity
    group: int
    core_index: int
    efficiency_class: int  # higher = more performant (P-cores on hybrid Intel)
    llc_index: int
    numa_node: int


def _windows_cpu_sets() -> list[LogicalCpu] | None:
    if sys.platform != "win32":
        return None
    from ctypes import wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = k32.GetSystemCpuSetInformation
    fn.argtypes = [ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG), wt.HANDLE, wt.ULONG]
    fn.restype = wt.BOOL
    needed = wt.ULONG(0)
    fn(None, 0, ctypes.byref(needed), None, 0)
    if needed.value == 0:
        return None
    buf = ctypes.create_string_buffer(needed.value)
    if not fn(buf, needed, ctypes.byref(needed), None, 0):
        return None
    raw = buf.raw[: needed.value]
    cpus: list[LogicalCpu] = []
    off = 0
    while off + 8 <= len(raw):
        size, typ = struct.unpack_from("<II", raw, off)
        if size == 0:
            break
        if typ == 0 and off + 20 <= len(raw):  # CpuSetInformation
            _id, group, lp, core, llc, numa, eff, _flags = struct.unpack_from("<IHBBBBBB", raw, off + 8)
            cpus.append(LogicalCpu(index=lp + 64 * group, group=group, core_index=core,
                                   efficiency_class=eff, llc_index=llc, numa_node=numa))
        off += size
    return sorted(cpus, key=lambda c: c.index) or None


def cpu_topology() -> dict:
    cpus = _windows_cpu_sets()
    logical = os.cpu_count() or 0
    physical = psutil.cpu_count(logical=False) if psutil else None
    info: dict = {"logical_cpus": logical, "physical_cores": physical, "source": None, "cpus": []}
    if cpus:
        info["source"] = "GetSystemCpuSetInformation"
        info["cpus"] = [asdict(c) for c in cpus]
        classes = sorted({c.efficiency_class for c in cpus})
        info["efficiency_classes"] = classes
        info["hybrid"] = len(classes) > 1
        top = max(classes)
        p_cores = sorted({(c.group, c.core_index) for c in cpus if c.efficiency_class == top})
        e_cores = sorted({(c.group, c.core_index) for c in cpus if c.efficiency_class != top})
        info["performance_cores"] = len(p_cores)
        info["efficiency_cores"] = len(e_cores)
    else:
        info["source"] = "os.cpu_count only (topology unavailable)"
        info["hybrid"] = None
    return info


def timing_cpu(topology: dict | None = None) -> dict:
    """Pick the logical CPU used for the primary single-thread timing track.

    Policy (spec section 20): one physical performance core, never core 0 (it serves most
    interrupts), first SMT thread of that core; its sibling threads are recorded so the
    scheduler can keep them idle. Deterministic for a given machine.
    """
    topo = topology or cpu_topology()
    cpus = topo.get("cpus") or []
    if not cpus:
        return {"cpu": None, "siblings": [], "reason": "topology unavailable; affinity not applied"}
    top = max(c["efficiency_class"] for c in cpus)
    cores: dict[tuple[int, int], list[int]] = {}
    for c in cpus:
        if c["efficiency_class"] == top:
            cores.setdefault((c["group"], c["core_index"]), []).append(c["index"])
    keys = sorted(cores)
    key = keys[1] if len(keys) > 1 else keys[0]
    threads = sorted(cores[key])
    return {"cpu": threads[0], "siblings": threads[1:], "core": list(key),
            "efficiency_class": top, "reason": "second performance core, first SMT thread"}


def pin_current_process(cpu: int | None) -> bool:
    if cpu is None or psutil is None:
        return False
    try:
        psutil.Process().cpu_affinity([cpu])
        return True
    except (psutil.Error, OSError, ValueError):
        return False


def memory_info() -> dict:
    if psutil is None:
        return {"total_bytes": None, "available_bytes": None}
    vm = psutil.virtual_memory()
    return {"total_bytes": int(vm.total), "available_bytes": int(vm.available)}


def disk_free_bytes(path: str | os.PathLike) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return int(shutil.disk_usage(p).free)


def process_peak_rss() -> dict:
    """Current and OS-tracked peak working set of this process."""
    if psutil is None:
        return {"rss_bytes": None, "peak_rss_bytes": None, "mode": "unavailable"}
    mi = psutil.Process().memory_info()
    peak = getattr(mi, "peak_wset", None)
    return {"rss_bytes": int(mi.rss), "peak_rss_bytes": int(peak) if peak is not None else None,
            "mode": "win_peak_wset" if peak is not None else "rss_only"}


def _console_encoding() -> str:
    if sys.platform == "win32":
        try:
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except (AttributeError, OSError):
            pass
    return "utf-8"


def run_text(cmd: list[str], timeout: float = 60) -> tuple[int, str]:
    """Run a command and decode its output with the console code page (never raises on
    undecodable bytes; localized Windows tools print OEM-encoded text)."""
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""
    enc = _console_encoding()
    text = (out.stdout or b"").decode(enc, errors="replace")
    if not text.strip():
        text = (out.stderr or b"").decode(enc, errors="replace")
    return out.returncode, text


def gpu_info() -> list[dict]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    rc, text = run_text([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], 30)
    if rc != 0:
        return []
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            gpus.append({"name": parts[0], "memory_total": parts[1], "driver": parts[2]})
    return gpus


def power_scheme() -> str | None:
    if sys.platform != "win32":
        return None
    rc, text = run_text(["powercfg", "/getactivescheme"], 30)
    line = text.strip()
    if rc != 0 or not line:
        return None
    if "(" in line and line.endswith(")"):
        return line[line.rfind("(") + 1: -1]
    return line


def os_info() -> dict:
    return {"system": platform.system(), "release": platform.release(), "version": platform.version(),
            "platform": platform.platform(), "machine": platform.machine(),
            "processor_name": _cpu_name()}


def _cpu_name() -> str | None:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            return None
    return platform.processor() or None
