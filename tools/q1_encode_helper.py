"""Helper process: encode .npy files with ONE native module (a frozen snapshot path, or 'live') and print JSON.

    python tools/q1_encode_helper.py <module path | live> '<options json>' file1.npy [file2.npy ...]

One module per process (two pybind11 modules with the same C++ exception names share translators inside a process).
Prints {file: {sha256, bytes, lb_bytes, ub_bytes, label_lb_bytes, label_bytes, regimes, w_D, regime_w_D, lossless}}.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    which, opts, files = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3:]
    if which == "live":
        sys.path.insert(0, str(ROOT))
        from cape import _cape_native as mod
    else:
        spec = importlib.util.spec_from_file_location("_cape_native", which)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    import crackle

    out = {}
    for f in files:
        zyx = np.load(f)
        buf, d = mod.encode(np.ascontiguousarray(zyx).T, opts)
        dec = np.asarray(crackle.decompress(buf))
        out[f] = {"sha256": hashlib.sha256(buf).hexdigest(), "bytes": len(buf), "lb_bytes": d.get("lb_bytes"),
                  "ub_bytes": d.get("ub_bytes"), "label_lb_bytes": d.get("label_lb_bytes"),
                  "label_bytes": d.get("label_bytes"), "regimes": d.get("regimes"), "w_D": d.get("w_D"),
                  "regime_w_D": d.get("regime_w_D"), "certificate_dual_feasible": d.get("certificate_dual_feasible"),
                  "lossless": bool(np.array_equal(dec, np.ascontiguousarray(zyx).T))}
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
