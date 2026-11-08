"""Check that the public API (cape.api.compress) reproduces, byte for byte, the streams that the final experiment
recorded for the evaluated method cape_q1_fast_m0, on the materialized test volumes.

    python tools/verify_public_api_streams.py [--per-dataset N]

Needs the data fetched by the pipeline (data/real/...) and the raw rows in `maqola uchun/raw_results/`. Writes
nothing; prints one line per volume and a summary. Volumes that are not on disk are reported as MISSING, not skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import api  # noqa: E402
from cape.dataset_manifest import load_manifest, verify_materialized  # noqa: E402

RAW = ROOT / "maqola uchun" / "raw_results"
SETS = {"j0126": "data/manifests/q1_external_j0126.jsonl", "snemi": "data/manifests/confirm_snemi3d.jsonl",
        "hemibrain": "data/manifests/q1_external_hemibrain.jsonl"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-dataset", type=int, default=0, help="0 = all volumes")
    a = ap.parse_args()
    n_ok = n_bad = n_missing = 0
    for ds, man in SETS.items():
        rows = pd.read_csv(RAW / f"{ds}_results.csv", low_memory=False)
        rec = rows[(rows.method_id == "cape_q1_fast_m0") & (rows.status == "OK")
                   & (rows.wrapper.fillna("none") == "none")
                   & rows.bitstream_sha256.notna()].groupby("sample_id").bitstream_sha256.agg(set)  # MEM rows: no hash
        manifest = {r["sample_id"]: r for r in load_manifest(ROOT / man)}
        ids = sorted(rec.index)
        if a.per_dataset:
            ids = ids[:a.per_dataset]
        for sid in ids:
            if sid not in manifest:
                print(f"{ds:9s} {sid}: MISSING (not in manifest)")
                n_missing += 1
                continue
            try:
                canon = verify_materialized(manifest[sid])
            except Exception as exc:  # file not fetched or hash mismatch
                print(f"{ds:9s} {sid}: MISSING ({exc})")
                n_missing += 1
                continue
            stream = api.compress(canon.T)  # canonical (Z,Y,X) -> crackle indexing [x, y, z]
            sha = hashlib.sha256(stream).hexdigest()
            same = rec[sid] == {sha}
            lossless = bool(np.array_equal(api.decompress(stream), canon.T))
            n_ok += same and lossless
            n_bad += not (same and lossless)
            print(f"{ds:9s} {sid}: {'IDENTICAL' if same else 'DIFFERENT'} sha256 {sha[:16]}  lossless {lossless}")
    print(f"summary: identical+lossless {n_ok}, different {n_bad}, missing {n_missing}")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
