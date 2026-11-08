"""Rebuild the evaluated volumes (data/real/...) from the downloaded sources, using the FROZEN manifests in
data/manifests/, and check every volume against the manifest's voxel SHA-256 before it is written.

    python scripts/materialize_from_manifest.py data/manifests/q1_external_j0126.jsonl [more manifests]
    python scripts/materialize_from_manifest.py --check-only data/manifests/*.jsonl   # recompute hashes, write nothing

Run the download scripts first (scripts/fetch_snemi3d.py, scripts/fetch_external_q1.py). A volume whose source file
is missing is reported as MISSING; a hash mismatch is reported as MISMATCH and nothing is written for it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape.canonical import to_canonical, voxel_sha256  # noqa: E402
from cape.dataset_manifest import load_manifest, resolve_path  # noqa: E402
from cape.io import read_raw, save_canonical  # noqa: E402

WHOLE_FILE = {"j0126", "hemibrain"}  # the downloaded file is the evaluated volume itself (bbox = global coordinates)


def build(row: dict) -> np.ndarray:
    src = resolve_path(row["original_path"])
    if not src.exists():
        raise FileNotFoundError(f"source missing: {src}")
    if row["family_id"] in WHOLE_FILE:
        key = (row.get("array_key") or "").lstrip("/") if src.suffix in (".h5", ".hdf5") else None
        arr = read_raw(src, array_key=key)
    else:
        arr = read_raw(src, array_key=None, bbox_xyz=row.get("bbox_xyz"), source_axes=row.get("source_axes"))
    canon, _ = to_canonical(np.ascontiguousarray(arr), row.get("source_axes") or row.get("axes") or "ZYX")
    return canon


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifests", nargs="+")
    ap.add_argument("--check-only", action="store_true", help="recompute and compare hashes; write nothing")
    ap.add_argument("--overwrite", action="store_true", help="rewrite volumes that already exist")
    a = ap.parse_args()
    counts = {"OK": 0, "WRITTEN": 0, "EXISTS": 0, "MISSING": 0, "MISMATCH": 0}
    for man in a.manifests:
        for row in load_manifest(man):
            out = resolve_path(row["path"])
            if out.exists() and not (a.check_only or a.overwrite):
                counts["EXISTS"] += 1
                continue
            try:
                canon = build(row)
            except FileNotFoundError as exc:
                print(f"MISSING  {row['sample_id']}: {exc}")
                counts["MISSING"] += 1
                continue
            if voxel_sha256(canon) != row["voxel_sha256"] or list(canon.shape) != list(row["shape"]):
                print(f"MISMATCH {row['sample_id']}: rebuilt volume differs from the frozen manifest")
                counts["MISMATCH"] += 1
                continue
            if a.check_only:
                counts["OK"] += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            save_canonical(out, canon)
            counts["WRITTEN"] += 1
    print("summary:", ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 1 if counts["MISMATCH"] or counts["MISSING"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
