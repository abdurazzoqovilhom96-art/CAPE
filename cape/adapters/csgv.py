"""CSGV via the authors' Volcanite executable (spec 17.2, S3/S5), brick 64, CLI round trip:
    volcanite --headless --threads N -b 64 -c out.csgv in.vraw      (compress)
    volcanite --headless --threads N -d out.vraw in.csgv            (decompress, lossless check)
Timing therefore includes process start-up and file I/O and is reported as a separate CLI
timing mode, never mixed with in-process library timings. A build that is missing or fails
is UNAVAILABLE_BUILD with its log; numbers from the papers are never copied in.

The Volcanite compressor reads only uint32 .vraw volumes (lib/vvv/src/reader/volcanite_raw.cpp:
first line "W H D", second line the type - the reverse of doc/Usage.md). uint8/uint16 are widened
and uint64 whose values all fit in uint32 is narrowed, both value-preserving and restored on
decode; the row records dtype_adapter so the conversion is never silent. uint64 IDs >= 2^32 are
UNSUPPORTED_DTYPE."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from cape.adapters.base import AdapterUnavailable, CodecAdapter, UnsupportedDtype, pack_container, unpack_container

ROOT = Path(__file__).resolve().parents[2]
CODEC_ID = 6
CANDIDATE_PATHS = ["vendor/volcanite/cmake-build-release/volcanite/volcanite.exe",
                   "vendor/volcanite/cmake-build-release/volcanite.exe",
                   "vendor/volcanite/cmake-build-release/volcanite/volcanite",
                   "vendor/volcanite/build/volcanite/volcanite"]


def find_volcanite() -> str | None:
    env = os.environ.get("CAPE_VOLCANITE")
    if env and Path(env).is_file():
        return env
    for rel in CANDIDATE_PATHS:
        p = ROOT / rel
        if p.is_file():
            return str(p)
    return shutil.which("volcanite")


class VolcaniteAdapter(CodecAdapter):
    adapter_name = "csgv"
    random_access = False
    timing_mode = "cli_process_file_to_file"

    def _exe(self) -> str:
        exe = find_volcanite()
        if exe is None:
            raise AdapterUnavailable("volcanite executable not found: build pending (Vulkan SDK + MinGW HEADLESS "
                                     "build, see docs/WINDOWS_UZ.md); CSGV claims are blocked until it exists")
        return exe

    def availability(self) -> dict:
        try:
            exe = self._exe()
        except AdapterUnavailable as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": f"volcanite --version failed: {exc}"}
        if out.returncode != 0:
            return {"status": "UNAVAILABLE_BUILD", "version": None,
                    "reason": "volcanite --version failed: " + (out.stderr or out.stdout).decode(errors="replace")[-300:]}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        try:
            out = subprocess.run([self._exe(), "--version"], capture_output=True, timeout=60)
            lines = (out.stdout + out.stderr).decode(errors="replace").splitlines()
            ver = next((ln.split("version:", 1)[1].strip() for ln in lines if "version:" in ln), "unknown")
            return f"volcanite {ver} (commit c760814, MinGW HEADLESS build, CLI)"
        except (AdapterUnavailable, OSError, subprocess.TimeoutExpired):
            return "volcanite (unknown version)"

    def _run(self, args: list[str]) -> None:
        """Volcanite prints "Application exit with return code N. Press any key to close." and then
        blocks on a console key press; the line is parsed and the process is closed."""
        import re
        import threading

        cmd = [self._exe(), "--headless", "--no-render", "--threads", str(self.threads), *args]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines: list[str] = []
        code: list[int] = []
        done = threading.Event()

        def reader():
            for raw in proc.stdout:
                line = raw.decode(errors="replace")
                lines.append(line)
                m = re.search(r"Application exit with return code (-?\d+)", line)
                if m:
                    code.append(int(m.group(1)))
                    done.set()
                    return
            done.set()

        threading.Thread(target=reader, daemon=True).start()
        finished = done.wait(timeout=3600)
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=30)
        rc = code[0] if code else proc.returncode
        if not finished or rc != 0:
            raise RuntimeError(f"volcanite failed ({rc if finished else 'timeout'}): " + "".join(lines)[-500:])

    @staticmethod
    def _narrow(array: np.ndarray) -> tuple[np.ndarray, str | None]:
        if array.dtype == np.uint64:
            if array.size and int(array.max()) > 0xFFFFFFFF:
                raise UnsupportedDtype("CSGV stores at most 32-bit labels and this volume has IDs >= 2^32")
            return array.astype(np.uint32), "narrow_uint64_to_uint32 (value preserving, restored on decode)"
        if array.dtype in (np.uint8, np.uint16):
            return array.astype(np.uint32), f"widen_{array.dtype}_to_uint32 (value preserving, restored on decode)"
        return array, None

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        work, adapter = self._narrow(np.ascontiguousarray(array))
        brick = int(self.options.get("brick", 64))
        tmp = Path(tempfile.mkdtemp(prefix="cape_csgv_"))
        try:
            vraw = tmp / "in.vraw"
            z, y, x = work.shape
            with open(vraw, "wb") as fh:
                fh.write(f"{x} {y} {z}\nuint32\n".encode())
                fh.write(memoryview(np.ascontiguousarray(work, dtype="<u4")).cast("B"))
            out = tmp / "out.csgv"
            args = ["-b", str(brick), "-c", str(out)]
            if self.random_access:
                args.append("--random-access")
            self._run(args + [str(vraw)])
            body = out.read_bytes()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        extra = struct.pack("<BB", np.dtype(work.dtype).itemsize, 1 if self.random_access else 0)
        stream, meta = pack_container(CODEC_ID, array.dtype, array.shape, body, extra)
        self.last_metadata_bytes = meta
        self.last_diagnostics = {"brick": brick, "random_access": self.random_access, "dtype_adapter": adapter,
                                 "timing_mode": self.timing_mode}
        return stream

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        dtype, shape, extra, body = unpack_container(payload, CODEC_ID)
        tmp = Path(tempfile.mkdtemp(prefix="cape_csgv_"))
        try:
            src = tmp / "in.csgv"
            src.write_bytes(bytes(body))
            dst = tmp / "out.vraw"
            self._run(["-d", str(dst), str(src)])
            raw = dst.read_bytes()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        nl1 = raw.index(b"\n")
        nl2 = raw.index(b"\n", nl1 + 1)
        x, y, z = (int(v) for v in raw[:nl1].split())
        stored = np.dtype(raw[nl1 + 1:nl2].decode().strip())
        arr = np.frombuffer(raw, dtype=stored.newbyteorder("<"), offset=nl2 + 1, count=x * y * z).reshape(z, y, x)
        if (z, y, x) != tuple(shape):
            raise RuntimeError(f"volcanite returned shape {(z, y, x)}, expected {shape}")
        return arr.astype(dtype) if arr.dtype != dtype else arr
