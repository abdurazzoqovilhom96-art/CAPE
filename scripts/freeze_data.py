"""Freeze real-data crops (spec section 18): choose spatially separated macroblocks on a
deterministic grid (seed 20261105) BEFORE any codec runs, write the exact voxel-coordinate table
and materialize canonical crops + manifests.

CREMI: sample A -> development (data/manifests/pilot.jsonl), B and C -> held-out
(data/manifests/benchmark.jsonl). Crop sizes: pilot (256,256,64) plus the scale crop
(128,128,64) nested in the same macroblock (same split). Sizes that do not fit the source are
recorded as NOT_APPLICABLE, never padded.

    python scripts/freeze_data.py --cremi-dir data/downloads/cremi [--per-volume 6]
"""

from __future__ import annotations

import argparse
import csv
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

CREMI_KEY = "volumes/labels/neuron_ids"
PILOT_CROP = (256, 256, 64)
SCALE_CROPS = [(128, 128, 64), (256, 256, 128), (512, 512, 128), (512, 512, 256)]


def cremi_rows(cremi_dir: Path, per_volume: int, seed: int) -> tuple[list[dict], list[dict]]:
    import h5py

    rows, table = [], []
    files = sorted(cremi_dir.glob("sample_[ABC]_*.hdf"))
    log_p = cremi_dir / "download_log.json"
    provenance = {}
    if log_p.exists():
        for rec in json.loads(log_p.read_text(encoding="utf-8")).get("files", []):
            provenance[rec["name"]] = rec
    for f in files:
        prov = provenance.get(f.name, {})
        src_url = prov.get("url", "https://cremi.org/data/")
        src_version = f"{f.name}; {prov.get('source', 'source not logged (placed manually)')}"
        letter = f.name.split("_")[1]
        split = "development" if letter == "A" else "heldout"
        with h5py.File(f, "r") as fh:
            ds = fh[CREMI_KEY]
            shape_zyx = ds.shape
            res = tuple(float(v) for v in ds.attrs.get("resolution", (40.0, 4.0, 4.0)))
        shape_xyz = [shape_zyx[2], shape_zyx[1], shape_zyx[0]]
        sha = file_sha256(f)
        boxes = data_prep.macroblock_grid(shape_xyz, PILOT_CROP, per_volume, seed + ord(letter))
        for b in boxes:
            mb = f"x{b[0][0]}_y{b[1][0]}_z{b[2][0]}"
            for crop in [PILOT_CROP] + [c for c in SCALE_CROPS if c != PILOT_CROP]:
                fits_source = all(crop[i] <= shape_xyz[i] for i in range(3))
                fits_block = all(crop[i] <= (b[i][1] - b[i][0]) for i in range(3))
                bb = [[b[i][0], b[i][0] + crop[i]] for i in range(3)]
                sid = f"cremi_{letter}_{mb}_{crop[0]}x{crop[1]}x{crop[2]}"
                rec = {"sample_id": sid, "source": f.name, "split": split, "macroblock_id": f"cremi_{letter}:{mb}",
                       "bbox_xyz": json.dumps(bb), "crop_xyz": json.dumps(list(crop)),
                       "status": "OK" if fits_source and fits_block else
                       ("NOT_APPLICABLE: source too small" if not fits_source else "NOT_APPLICABLE: exceeds macroblock")}
                table.append(rec)
                if rec["status"] != "OK":
                    continue
                raw = read_raw(f, CREMI_KEY, bbox_xyz=bb, source_axes="ZYX")
                canon, _ = to_canonical(raw, "ZYX")
                rows.append(data_prep.make_row(
                    canon, ROOT / "data" / "real" / "cremi_crops" / f"{sid}.npy", sample_id=sid, family_id="cremi",
                    source_id=f"cremi:{letter}", specimen_id=f"cremi:{letter}", macroblock_id=f"cremi_{letter}:{mb}",
                    split=split, is_synthetic=False, source_url=src_url, source_version=src_version,
                    license="unknown - cremi.org terms; not redistributed", citation="S10", array_key=CREMI_KEY,
                    source_axes="ZYX", bbox_xyz=bb, spacing_xyz=[res[2], res[1], res[0]],
                    original_path=data_prep.rel(f), original_file_sha256=sha,
                    selection_rule=f"macroblock_grid crop={list(PILOT_CROP)} n={per_volume} seed={seed}+ord('{letter}'); "
                                   f"nested crop {list(crop)} at the macroblock origin"))
    return rows, table


def crackle_width_rows(seed: int) -> list[dict]:
    """Spec 39.2 width sensitivity (Z = 512 exercises depth regimes) and scale-panel crops from the
    512^3 Crackle repository samples (development split)."""
    out_dir = ROOT / "data" / "real" / "crackle_width"
    rows = data_prep.crackle_sample_rows(out_dir, crop_xyz=(256, 256, 512), per_file={"connectomics": 1, "ws": 1},
                                         seed=seed)
    for crop in ((512, 512, 128), (512, 512, 256)):
        rows += data_prep.crackle_sample_rows(out_dir, crop_xyz=crop, per_file={"connectomics": 1}, seed=seed)
    return rows


V2_TEST_NOTE = ("plan v2 frozen test: crops from slices z 64-123 of CREMI B/C that no v1 or v2-development "
                "measurement touched (zero voxel overlap, checked). NOT an independent acquisition or volume "
                "family: same two volumes as the v1 held-out set, so this tests within-volume generalization only.")


def _overlap(a, b) -> bool:
    return all(a[i][0] < b[i][1] and b[i][0] < a[i][1] for i in range(3))


def cremi_v2_unseen_rows(cremi_dir: Path, per_volume: int, seed: int) -> tuple[list[dict], list[dict]]:
    """Plan v2: unseen, non-overlapping CREMI B/C crops below every previously measured crop."""
    import h5py

    used = []
    for name in ("pilot.jsonl", "benchmark.jsonl", "dev_v2.jsonl"):
        p = ROOT / "data" / "manifests" / name
        if p.exists():
            used += [(r["source_id"], r["bbox_xyz"]) for r in load_manifest(p)]
    rows, table = [], []
    z0, depth = 64, 60
    crops = [(256, 256, depth), (128, 128, depth)]
    for f in sorted(cremi_dir.glob("sample_[BC]_*.hdf")):
        letter = f.name.split("_")[1]
        with h5py.File(f, "r") as fh:
            ds = fh[CREMI_KEY]
            shape_zyx = ds.shape
            res = tuple(float(v) for v in ds.attrs.get("resolution", (40.0, 4.0, 4.0)))
        if shape_zyx[0] < z0 + depth:
            raise SystemExit(f"BLOCKED_DATA: {f.name} has only {shape_zyx[0]} slices")
        sha = file_sha256(f)
        boxes = data_prep.macroblock_grid([shape_zyx[2], shape_zyx[1], depth], crops[0], per_volume, seed + ord(letter))
        for b in boxes:
            b = [b[0], b[1], [z0, z0 + depth]]
            mb = f"x{b[0][0]}_y{b[1][0]}_z{z0}"
            for crop in crops:
                bb = [[b[i][0], b[i][0] + crop[i]] for i in range(3)]
                clash = [u for u in used if u[0] == f"cremi:{letter}" and _overlap(u[1], bb)]
                if clash:
                    raise SystemExit(f"internal: v2 test crop {bb} overlaps a measured crop {clash[0]}")
                sid = f"cremi_{letter}_{mb}_{crop[0]}x{crop[1]}x{crop[2]}"
                table.append({"sample_id": sid, "source": f.name, "split": "heldout",
                              "macroblock_id": f"cremi_{letter}:{mb}", "bbox_xyz": json.dumps(bb),
                              "crop_xyz": json.dumps(list(crop)), "status": "OK"})
                raw = read_raw(f, CREMI_KEY, bbox_xyz=bb, source_axes="ZYX")
                canon, _ = to_canonical(raw, "ZYX")
                row = data_prep.make_row(
                    canon, ROOT / "data" / "real" / "cremi_crops_v2" / f"{sid}.npy", sample_id=sid, family_id="cremi",
                    source_id=f"cremi:{letter}", specimen_id=f"cremi:{letter}", macroblock_id=f"cremi_{letter}:{mb}",
                    split="heldout", is_synthetic=False, source_url="see data/downloads/cremi/download_log.json",
                    source_version=f.name, license="unknown - cremi.org terms; not redistributed", citation="S10",
                    array_key=CREMI_KEY, source_axes="ZYX", bbox_xyz=bb, spacing_xyz=[res[2], res[1], res[0]],
                    original_path=data_prep.rel(f), original_file_sha256=sha,
                    selection_rule=f"v2 unseen: macroblock_grid crop={list(crops[0])} on z [{z0}, {z0 + depth}) "
                                   f"n={per_volume} seed={seed}+ord('{letter}'); nested crop {list(crop)}")
                row["v2_independence"] = V2_TEST_NOTE
                rows.append(row)
    return rows, table


SNEMI_NOTE = ("plan v2.1 confirmatory source, frozen before any codec ran on it: SNEMI3D training labels "
              "(mouse somatosensory cortex, Lichtman lab ATUM-SEM, manual labels by D. R. Berger; Zenodo "
              "10.5281/zenodo.7142003, CC-BY-4.0). Independent of CREMI in species, lab, imaging and annotators. "
              "Limits: ONE volume (16 macroblock clusters), so it is an independent dataset family but not a "
              "multi-volume population; uint16 labels (CREMI is uint64).")
SNEMI_LABELS = ROOT / "data" / "downloads" / "snemi3d" / "labels" / "train_labels_0.tif"


def snemi3d_confirm_rows() -> tuple[list[dict], list[dict]]:
    """Plan v2.1: every cell of a 4x4 grid of 256x256 XY macroblocks on z [0, 64), plus the nested
    central 128x128x64 crop of each (no content-based selection; z 64-99 stay in reserve)."""
    import tifffile

    if not SNEMI_LABELS.exists():
        raise SystemExit("BLOCKED_DATA: run scripts/fetch_snemi3d.py first (SNEMI3D labels missing)")
    log = json.loads((SNEMI_LABELS.parents[1] / "download_log.json").read_text(encoding="utf-8"))
    vol = tifffile.imread(SNEMI_LABELS)  # (Z, Y, X)
    if vol.ndim != 3:
        raise SystemExit(f"BLOCKED_DATA: SNEMI3D labels have ndim={vol.ndim}")
    Z, Y, X = vol.shape
    z0, depth, step = 0, 64, 256
    if Z < depth or Y % step or X % step:
        raise SystemExit(f"BLOCKED_DATA: unexpected SNEMI3D label shape {vol.shape}")
    sha = file_sha256(SNEMI_LABELS)
    rows, table = [], []
    for y in range(0, Y, step):
        for x in range(0, X, step):
            mb = f"x{x}_y{y}_z{z0}"
            for crop, off in (((256, 256, depth), 0), ((128, 128, depth), 64)):
                bb = [[x + off, x + off + crop[0]], [y + off, y + off + crop[1]], [z0, z0 + depth]]
                sid = f"snemi3d_{mb}_{crop[0]}x{crop[1]}x{crop[2]}"
                table.append({"sample_id": sid, "source": "seg/train-labels.tif", "split": "heldout",
                              "macroblock_id": f"snemi3d:{mb}", "bbox_xyz": json.dumps(bb),
                              "crop_xyz": json.dumps(list(crop)), "status": "OK"})
                sub = vol[bb[2][0]:bb[2][1], bb[1][0]:bb[1][1], bb[0][0]:bb[0][1]]
                canon, _ = to_canonical(np.ascontiguousarray(sub), "ZYX")
                row = data_prep.make_row(
                    canon, ROOT / "data" / "real" / "snemi3d_crops" / f"{sid}.npy", sample_id=sid,
                    family_id="snemi3d", source_id="snemi3d:train", specimen_id="snemi3d:kasthuri2015_s1",
                    macroblock_id=f"snemi3d:{mb}", split="heldout", is_synthetic=False,
                    source_url=f"https://doi.org/{log['doi']}", source_version=f"zenodo record {log['record']} "
                    f"snemi.zip md5 {log['md5']}", license="CC-BY-4.0 (Zenodo 10.5281/zenodo.7142003); never redistributed",
                    citation="SNEMI3D", array_key="seg/train-labels.tif", source_axes="ZYX", bbox_xyz=bb,
                    spacing_xyz=None, original_path=data_prep.rel(SNEMI_LABELS), original_file_sha256=sha,
                    null_reasons={"spacing_xyz": "not stated inside the archive"},
                    selection_rule=f"v2.1 confirm: all 16 cells of a 4x4 grid of 256x256 XY macroblocks on z "
                                   f"[{z0}, {z0 + depth}); nested central crop {list(crop)}; no content-based selection")
                row["v21_independence"] = SNEMI_NOTE
                rows.append(row)
    return rows, table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v2-unseen-test", action="store_true",
                    help="write data/manifests/test_v2_unseen.jsonl (unseen CREMI B/C crops, z 64-123) and exit")
    ap.add_argument("--cremi-dir", default="data/downloads/cremi")
    ap.add_argument("--per-volume", type=int, default=6)
    ap.add_argument("--seed", type=int, default=data_prep.SEED)
    ap.add_argument("--with-crackle-samples", action="store_true", help="add Crackle repository crops to pilot")
    ap.add_argument("--crackle-width-sensitivity", action="store_true",
                    help="write data/manifests/width_sensitivity.jsonl (Z=512 and scale crops) and exit")
    ap.add_argument("--snemi3d-confirm", action="store_true",
                    help="write data/manifests/confirm_snemi3d.jsonl (SNEMI3D, CREMI-independent) and exit")
    args = ap.parse_args(argv)
    if args.snemi3d_confirm:
        out = ROOT / "data" / "manifests"
        if (out / "confirm_snemi3d.jsonl").exists():
            print("confirm_snemi3d.jsonl already frozen - not rewritten (delete it explicitly to re-freeze)")
            return 0
        rows, table = snemi3d_confirm_rows()
        with open(out / "crop_table_snemi3d.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
        write_manifest(out / "confirm_snemi3d.jsonl", rows)
        load_manifest(out / "confirm_snemi3d.jsonl")
        print(f"SNEMI3D confirm: {len(rows)} crops -> data/manifests/confirm_snemi3d.jsonl")
        return 0
    if args.v2_unseen_test:
        rows, table = cremi_v2_unseen_rows(ROOT / args.cremi_dir, args.per_volume, 20261106)
        out = ROOT / "data" / "manifests"
        with open(out / "crop_table_cremi_v2_unseen.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
        write_manifest(out / "test_v2_unseen.jsonl", rows)
        load_manifest(out / "test_v2_unseen.jsonl")
        print(f"v2 unseen test: {len(rows)} crops -> data/manifests/test_v2_unseen.jsonl")
        return 0
    if args.crackle_width_sensitivity:
        rows = crackle_width_rows(args.seed)
        write_manifest(ROOT / "data" / "manifests" / "width_sensitivity.jsonl", rows)
        load_manifest(ROOT / "data" / "manifests" / "width_sensitivity.jsonl")
        print(f"width sensitivity / scale: {len(rows)} crops -> data/manifests/width_sensitivity.jsonl")
        return 0
    cdir = ROOT / args.cremi_dir
    if not any(cdir.glob("sample_[ABC]_*.hdf")):
        print(f"BLOCKED_DATA: no CREMI sample_[ABC]_*.hdf files in {cdir}; run scripts/fetch_data.py cremi", file=sys.stderr)
        return 2
    rows, table = cremi_rows(cdir, args.per_volume, args.seed)
    if args.with_crackle_samples:
        rows += data_prep.crackle_sample_rows(ROOT / "data" / "real" / "crackle_crops", crop_xyz=(256, 256, 64),
                                              per_file={"connectomics": 3, "ws": 3}, seed=args.seed)
    out = ROOT / "data" / "manifests"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "crop_table_cremi.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    write_manifest(out / "pilot.jsonl", [r for r in rows if r["split"] == "development"])
    write_manifest(out / "benchmark.jsonl", [r for r in rows if r["split"] == "heldout"])
    for name in ("pilot.jsonl", "benchmark.jsonl"):
        load_manifest(out / name)  # schema + split integrity
    print(f"pilot: {sum(r['split'] == 'development' for r in rows)} crops; benchmark (held-out): "
          f"{sum(r['split'] == 'heldout' for r in rows)} crops; coordinate table: data/manifests/crop_table_cremi.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
