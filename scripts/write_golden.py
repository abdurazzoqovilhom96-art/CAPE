"""Write tests/fixtures/golden_cape_v1.json from the CURRENT (v1) native build.

Run once, before any v2 change to the native selector. Refuses to overwrite an existing golden
file: a golden mismatch is a regression to fix, not a file to regenerate.

    python scripts/write_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main() -> int:
    from golden_cases import GOLDEN_METHODS, GOLDEN_PATH, RUN_CONFIG, digest, native_options, real_cases, synthetic_cases

    from cape.config import load_methods, load_run_config
    from cape.result_store import atomic_write_text

    if GOLDEN_PATH.exists():
        print(f"refusing to overwrite {GOLDEN_PATH}", file=sys.stderr)
        return 2
    methods = load_methods()
    cfg = load_run_config(RUN_CONFIG, methods)
    cases = {**synthetic_cases(), **real_cases()}
    out = {"note": "v1 CAPE bitstreams (sha256, bytes); written once from the v1 build",
           "run_config": RUN_CONFIG, "methods": GOLDEN_METHODS, "cases": {}}
    for name, zyx in cases.items():
        out["cases"][name] = {}
        for mid in GOLDEN_METHODS:
            sha, n = digest(zyx, native_options(mid, methods, cfg))
            out["cases"][name][mid] = [sha, n]
        print(name, "ok")
    atomic_write_text(GOLDEN_PATH, json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN_PATH} ({len(cases)} cases x {len(GOLDEN_METHODS)} methods)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
