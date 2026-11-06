"""v2.1 scaling panel (plan v2.1, B4.2): nested crops of growing size from SEEN development sources.

    python scripts/make_scaling_manifest.py

Sources (all already used for development; never a compression claim, only how time / memory /
candidate counts / component sizes grow with the volume):
  * Crackle connectomics (uint32, 512^3): XY in {64,128,256,512} x Z in {64,128,256,512}, origin-nested
  * Crackle ws (uint64): 128^3, 256^3, 512x512x256, 512^3 (only sizes that fit the source)
  * CREMI A (uint64, 1250x1250x125, development volume): XY in {128,256,512,1024,1250}, Z = 125
Writes data/real/scaling_v21/*.npy, data/manifests/scaling_v21.jsonl (every crop) and
data/manifests/scaling_v21_stock.jsonl (crops with <= 2^25 voxels: the stock Crackle pin optimizer
needs 269 s at 512x512x256, so larger crops are recorded as SKIPPED_BUDGET for stock, not run).
Nested crops share voxels, so fitted slopes are descriptive, not independent evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import data_prep  # noqa: E402
from cape.canonical import to_canonical  # noqa: E402
from cape.dataset_manifest import load_manifest, write_manifest  # noqa: E402
from cape.io import file_sha256, read_raw  # noqa: E402

OUT = ROOT / "data" / "real" / "scaling_v21"
STOCK_MAX_VOXELS = 1 << 25
CREMI_KEY = "volumes/labels/neuron_ids"


def crackle_rows(key: str, sizes: list[tuple[int, int, int]]) -> tuple[list[dict], list[dict]]:
    src = ROOT / "vendor" / "crackle" / f"{key}.npy.cpso.gz"
    if not src.exists():
        return [], [{"source": key, "status": "BLOCKED_DATA", "reason": f"{src} missing"}]
    full = read_raw(src)  # (x, y, z)
    sha = file_sha256(src)
    rows, skipped = [], []
    for (cx, cy, cz) in sizes:
        if cx > full.shape[0] or cy > full.shape[1] or cz > full.shape[2]:
            skipped.append({"source": key, "crop_xyz": [cx, cy, cz], "status": "NOT_APPLICABLE",
                            "reason": f"source shape {list(full.shape)}"})
            continue
        bb = [[0, cx], [0, cy], [0, cz]]
        canon, _ = to_canonical(np.ascontiguousarray(full[:cx, :cy, :cz]), "XYZ")
        sid = f"scale_crackle_{key}_{cx}x{cy}x{cz}"
        rows.append(data_prep.make_row(
            canon, OUT / f"{sid}.npy", sample_id=sid, family_id="crackle_samples", source_id=f"crackle:{key}",
            specimen_id=f"crackle:{key}", macroblock_id=f"crackle_{key}:origin_nested", split="development",
            is_synthetic=False, source_url=data_prep.CRACKLE_URL, source_version=data_prep.CRACKLE_SHA,
            license="unknown (data in BSD-3 code repository; data terms not stated)", citation="S1",
            array_key=None, source_axes="XYZ", bbox_xyz=bb, spacing_xyz=None, original_path=data_prep.rel(src),
            original_file_sha256=sha, null_reasons={"spacing_xyz": "not stated by the repository"},
            selection_rule="v2.1 scaling: origin-nested crop (descriptive scaling only)"))
    del full
    return rows, skipped


def cremi_rows(sizes_xy: list[int]) -> tuple[list[dict], list[dict]]:
    import h5py

    f = next((ROOT / "data" / "downloads" / "cremi").glob("sample_A_*.hdf"), None)
    if f is None:
        return [], [{"source": "cremi_A", "status": "BLOCKED_DATA", "reason": "sample_A missing"}]
    with h5py.File(f, "r") as fh:
        ds = fh[CREMI_KEY]
        Z, Y, X = ds.shape
        res = tuple(float(v) for v in ds.attrs.get("resolution", (40.0, 4.0, 4.0)))
    sha = file_sha256(f)
    rows, skipped = [], []
    for s in sizes_xy:
        if s > X or s > Y:
            skipped.append({"source": "cremi_A", "crop_xyz": [s, s, Z], "status": "NOT_APPLICABLE",
                            "reason": f"source XY {X}x{Y}"})
            continue
        bb = [[0, s], [0, s], [0, Z]]
        raw = read_raw(f, CREMI_KEY, bbox_xyz=bb, source_axes="ZYX")
        canon, _ = to_canonical(raw, "ZYX")
        sid = f"scale_cremi_A_{s}x{s}x{Z}"
        rows.append(data_prep.make_row(
            canon, OUT / f"{sid}.npy", sample_id=sid, family_id="cremi", source_id="cremi:A", specimen_id="cremi:A",
            macroblock_id="cremi_A:origin_nested", split="development", is_synthetic=False,
            source_url="see data/downloads/cremi/download_log.json", source_version=f.name,
            license="unknown - cremi.org terms; not redistributed", citation="S10", array_key=CREMI_KEY,
            source_axes="ZYX", bbox_xyz=bb, spacing_xyz=[res[2], res[1], res[0]], original_path=data_prep.rel(f),
            original_file_sha256=sha, selection_rule="v2.1 scaling: origin-nested crop (descriptive scaling only)"))
    return rows, skipped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    grid = [(s, s, z) for s in (64, 128, 256, 512) for z in (64, 128, 256, 512)]
    rows, skipped = [], []
    for key, sizes in (("connectomics", grid), ("ws", [(128, 128, 128), (256, 256, 256), (512, 512, 256),
                                                         (512, 512, 512)])):
        r, s = crackle_rows(key, sizes)
        rows += r
        skipped += s
    r, s = cremi_rows([128, 256, 512, 1024, 1250])
    rows += r
    skipped += s
    man = ROOT / "data" / "manifests"
    write_manifest(man / "scaling_v21.jsonl", rows)
    load_manifest(man / "scaling_v21.jsonl")
    stock = [x for x in rows if int(np.prod(x["shape"])) <= STOCK_MAX_VOXELS]
    write_manifest(man / "scaling_v21_stock.jsonl", stock)
    load_manifest(man / "scaling_v21_stock.jsonl")
    skipped += [{"source": x["source_id"], "sample_id": x["sample_id"], "status": "SKIPPED_BUDGET",
                 "reason": f"stock Crackle pin optimizer not run above {STOCK_MAX_VOXELS} voxels (269 s already at "
                           f"512x512x256 = 2^26)"} for x in rows if int(np.prod(x["shape"])) > STOCK_MAX_VOXELS]
    (man / "scaling_v21_skipped.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")
    print(f"scaling: {len(rows)} crops ({len(stock)} for stock) -> data/manifests/scaling_v21*.jsonl; "
          f"skipped/not-applicable: {len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
