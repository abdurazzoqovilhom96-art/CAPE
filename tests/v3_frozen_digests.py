"""Helper process for tests/test_v3_invariants.py: encodes the shared requests with the FROZEN v2.1 binary only
(never imports cape._cape_native) and prints {request key: [sha256, bytes, diag subset]} as JSON."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from golden_cases import real_cases, synthetic_cases  # noqa: E402
from v3_cases import DIAG_KEYS, edge_cases, frozen_requests, request_key  # noqa: E402


def main() -> int:
    frozen = Path(sys.argv[1])
    spec = importlib.util.spec_from_file_location("_cape_native", frozen)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "cape._cape_native" not in sys.modules
    sets = {"cases": {**synthetic_cases(), **real_cases()}, "edge": edge_cases()}
    out = {}
    for case_set, name, opts in frozen_requests(sets["cases"], sets["edge"]):
        zyx = sets[case_set][name]
        buf, diag = mod.encode(np.ascontiguousarray(zyx).T, opts)
        out[request_key(case_set, name, opts)] = [hashlib.sha256(buf).hexdigest(), len(buf),
                                                  {k: diag[k] for k in DIAG_KEYS if k in diag}]
    assert "cape._cape_native" not in sys.modules
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
