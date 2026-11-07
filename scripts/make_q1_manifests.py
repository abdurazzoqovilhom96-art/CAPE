"""Q1 external-test manifests (docs/q1/EXTERNAL_DATA_PLAN.md). Content-agnostic, written before any codec ran.

    python scripts/make_q1_manifests.py

  data/manifests/q1_external_j0126.jsonl      all 33 j0126 dense GT volumes, unmodified (cluster = volume)
  data/manifests/q1_external_hemibrain.jsonl  the 4 pre-registered hemibrain v1.2 cutouts (512x512x256)

The script refuses to run if a results/ run already used one of these manifests. It never overwrites an existing
manifest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import data_prep  # noqa: E402
from cape.canonical import to_canonical  # noqa: E402
from cape.dataset_manifest import load_manifest, write_manifest  # noqa: E402

MAN = ROOT / "data" / "manifests"
NOTE = ("Q1 external test, declared before any codec ran on this source (docs/q1/EXTERNAL_DATA_PLAN.md). "
        "Never used for development or tuning.")


def _used(tag: str) -> list[str]:
    used = []
    for m in (ROOT / "results").glob("*/run_manifest.json"):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if tag in str(d.get("manifest_arg", "")).lower() or tag in str(d.get("config_path", "")).lower():
            used.append(m.parent.name)
    return used


def j0126() -> None:
    out = MAN / "q1_external_j0126.jsonl"
    if out.exists():
        print(f"{out.name} already frozen - not rewritten")
        return
    if _used("j0126"):
        raise SystemExit(f"REFUSED: j0126 already used by {_used('j0126')}")
    log = json.loads((ROOT / "data" / "downloads" / "j0126" / "download_log.json").read_text(encoding="utf-8"))
    rows = []
    for f in log["files"]:
        src = ROOT / f["path"]
        with h5py.File(src, "r") as h:
            vol = np.asarray(h["main"])
        canon, _ = to_canonical(np.ascontiguousarray(vol), "ZYX")
        (z0, z1), (y0, y1), (x0, x1) = f["bbox_zyx"]
        sid = f"j0126_z{z0}_y{y0}_x{x0}_{x1 - x0}x{y1 - y0}x{z1 - z0}"
        row = data_prep.make_row(
            canon, ROOT / "data" / "real" / "j0126" / f"{sid}.npy", sample_id=sid, family_id="j0126",
            source_id="j0126:areaX", specimen_id="j0126:zebrafinch_areaX", macroblock_id=f"j0126:{sid}",
            split="heldout", is_synthetic=False,
            source_url=log["bucket"].replace("gs://", "https://storage.googleapis.com/") + f["name"],
            source_version=f"GCS generation {f['gcs_generation']} md5 {f['md5']}",
            license=log["licence"] + "; never redistributed",
            citation="Januszewski et al. 2018, Nat. Methods 15:605 (doi:10.1038/s41592-018-0049-4)",
            array_key="/main", source_axes="ZYX", bbox_xyz=[[x0, x1], [y0, y1], [z0, z1]], spacing_xyz=[9, 9, 20],
            original_path=f["path"], original_file_sha256=f["sha256"],
            selection_rule="all 33 dense ground-truth volumes of the official bucket, unmodified; no content-based "
                           "selection")
        row["q1_role"] = "external_test"
        row["q1_note"] = NOTE + " One acquisition (SBEM, 9x9x20 nm): the volumes are clusters, not acquisitions."
        rows.append(row)
    write_manifest(out, rows)
    load_manifest(out)
    print(f"{out.name}: {len(rows)} rows")


def hemibrain() -> None:
    out = MAN / "q1_external_hemibrain.jsonl"
    if out.exists():
        print(f"{out.name} already frozen - not rewritten")
        return
    if _used("hemibrain"):
        raise SystemExit(f"REFUSED: hemibrain already used by {_used('hemibrain')}")
    base = ROOT / "data" / "downloads" / "hemibrain"
    log = json.loads((base / "download_log.json").read_text(encoding="utf-8"))
    cands = json.loads((base / "candidates.json").read_text(encoding="utf-8"))
    rows = []
    for c in cands:
        if c.get("decision") != "accepted":
            continue
        src = ROOT / c["file"]
        vol = np.load(src)
        canon, _ = to_canonical(np.ascontiguousarray(vol), "ZYX")
        x0, y0, z0 = c["origin_xyz"]
        bx, by, bz = c["box_xyz"]
        sid = f"hemibrain_x{x0}_y{y0}_z{z0}_{bx}x{by}x{bz}"
        row = data_prep.make_row(
            canon, ROOT / "data" / "real" / "hemibrain" / f"{sid}.npy", sample_id=sid, family_id="hemibrain",
            source_id="hemibrain:v1.2", specimen_id="hemibrain:drosophila_cb", macroblock_id=f"hemibrain:{sid}",
            split="heldout", is_synthetic=False, source_url=log["url"],
            source_version=f"v1.2 segmentation, info sha256 {log['info_sha256'][:16]}",
            license=log["licence"] + "; never redistributed",
            citation="Scheffer et al. 2020, eLife 9:e57443 (doi:10.7554/eLife.57443)",
            array_key="scale 8.0x8.0x8.0", source_axes="ZYX",
            bbox_xyz=[[x0, x0 + bx], [y0, y0 + by], [z0, z0 + bz]], spacing_xyz=[8, 8, 8],
            original_path=c["file"], original_file_sha256=c["sha256"],
            selection_rule="pre-registered cutout rule (seed 20261107, central half, background <= 50%, no overlap, "
                           "first 4 accepted); see docs/q1/EXTERNAL_DATA_PLAN.md")
        row["q1_role"] = "external_test_descriptive"
        row["q1_note"] = NOTE + (f" Proofread automated segmentation; background fraction "
                                 f"{c['background_fraction']:.4f}. One acquisition (FIB-SEM 8 nm).")
        rows.append(row)
    write_manifest(out, rows)
    load_manifest(out)
    skipped = [{"sample_id": r["sample_id"], "voxels": int(np.prod(r["shape"])), "status": "SKIPPED_BUDGET",
                "methods": ["crackle_pins_opt_corrected_m0", "crackle_pins_opt_m0", "crackle_vendor_pins_opt_m0",
                            "safe_stock_m0_zstd9", "safe_stock_m0_zstd3"],
                "reason": "v2.1 stock budget rule: stock pins_opt only on volumes <= 2^25 voxels (269 s/encode at "
                          "512x512x256 measured in v2.1); each cutout has 2^26 voxels"} for r in rows]
    (MAN / "q1_external_hemibrain_skipped.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows")


if __name__ == "__main__":
    j0126()
    hemibrain()
