"""Check that the crack-code section of every CAPE stream (public API) equals that of upstream Crackle flat
encoding (PyPI crackle-codec) on the 69 test volumes. Needs the materialized volumes (data/real/...)."""

from __future__ import annotations

import sys
import os
from pathlib import Path

import numpy as np

ROOT = Path(os.environ["CAPE_REPO"]) if os.environ.get("CAPE_REPO") else next(
    q for q in Path(__file__).resolve().parents if (q / "cape").is_dir() and (q / "maqola uchun").is_dir())
sys.path.insert(0, str(ROOT))

import crackle  # noqa: E402

from cape import api  # noqa: E402
from cape.dataset_manifest import load_manifest, verify_materialized  # noqa: E402

n = same = 0
for man in ["q1_external_j0126", "confirm_snemi3d", "q1_external_hemibrain"]:
    for r in load_manifest(ROOT / "data" / "manifests" / f"{man}.jsonl"):
        a = verify_materialized(r).T
        s_cape, s_flat = api.compress(a), crackle.compress(a, parallel=1)
        c1 = bytes(np.asarray(crackle.components(s_cape)["crack_codes"]))
        c2 = bytes(np.asarray(crackle.components(s_flat)["crack_codes"]))
        n += 1
        same += c1 == c2
        print(f"{r['sample_id']}: {'IDENTICAL' if c1 == c2 else 'DIFFERENT'} ({len(c1)} bytes)")
print(f"summary: crack-code section identical on {same}/{n} volumes")
sys.exit(0 if same == n else 1)
