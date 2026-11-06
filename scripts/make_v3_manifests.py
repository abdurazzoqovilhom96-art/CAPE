"""CAPE v3 manifests (plan CAPE v3, section 12). Content-agnostic; rows are copied, never re-cropped.

    python scripts/make_v3_manifests.py --dev           # development manifests (all data already seen)
    python scripts/make_v3_manifests.py --snemi-scale   # confirm scale track on SNEMI3D (before any codec ran on it)

--dev
  data/manifests/v3_dev_core.jsonl     CREMI A pilot (12) + CREMI B/C v2 "unseen" crops (24). Both were measured
                                       in v1/v2, so for v3 they are DEVELOPMENT data (original split kept in
                                       `v3_original_split`).
  data/manifests/v3_dev_quality.jsonl  the pre-registered Z > 256 group (every development crop with Z > 256 from
                                       width_sensitivity + scaling_v21) + the CREMI A pilot crops.
--snemi-scale
  data/manifests/confirm_snemi3d_v3_scale.jsonl   the whole SNEMI3D training-label volume (1024x1024x100) and its
                                       four non-overlapping 512x512x100 XY quadrants. Declared in the v3 freeze
                                       before any compression on SNEMI3D; refuses to run if any results/ run used a
                                       SNEMI3D manifest, and never overwrites an existing file.
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
from cape.io import file_sha256  # noqa: E402

MAN = ROOT / "data" / "manifests"


def _relabel(rows: list[dict], source: str) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        r["v3_original_split"] = r["split"]
        r["v3_role"] = "development"
        r["v3_source_manifest"] = source
        r["split"] = "development"
        out.append(r)
    return out


def dev() -> None:
    pilot = load_manifest(MAN / "pilot.jsonl")
    unseen = load_manifest(MAN / "test_v2_unseen.jsonl")
    core = _relabel(pilot, "pilot.jsonl") + _relabel(unseen, "test_v2_unseen.jsonl")
    write_manifest(MAN / "v3_dev_core.jsonl", core)
    deep = []
    for name in ("width_sensitivity.jsonl", "scaling_v21.jsonl"):
        for r in load_manifest(MAN / name):
            z = json.loads(r["shape"])[0] if isinstance(r["shape"], str) else r["shape"][0]
            if int(z) > 256:
                deep.extend(_relabel([r], name))
    quality = deep + _relabel(pilot, "pilot.jsonl")
    write_manifest(MAN / "v3_dev_quality.jsonl", quality)
    print(f"v3_dev_core.jsonl: {len(core)} rows; v3_dev_quality.jsonl: {len(quality)} rows "
          f"({len(deep)} with Z > 256: {[r['sample_id'] for r in deep]})")


def _snemi_used() -> list[str]:
    used = []
    for m in (ROOT / "results").glob("*/run_manifest.json"):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "snemi" in str(d.get("manifest_arg", "")).lower() or "snemi" in str(d.get("config_path", "")).lower():
            used.append(m.parent.name)
    return used


def snemi_scale() -> None:
    import tifffile

    out = MAN / "confirm_snemi3d_v3_scale.jsonl"
    if out.exists():
        print(f"{out.name} already frozen - not rewritten")
        return
    used = _snemi_used()
    if used:
        raise SystemExit(f"REFUSED: SNEMI3D was already used by runs {used}; the scale track must be declared before "
                         "any compression on it")
    labels = ROOT / "data" / "downloads" / "snemi3d" / "labels" / "train_labels_0.tif"
    if not labels.exists():
        raise SystemExit("BLOCKED_DATA: SNEMI3D labels missing (scripts/fetch_snemi3d.py)")
    log = json.loads((labels.parents[1] / "download_log.json").read_text(encoding="utf-8"))
    vol = tifffile.imread(labels)  # (Z, Y, X)
    Z, Y, X = vol.shape
    if (Z, Y, X) != (100, 1024, 1024):
        raise SystemExit(f"BLOCKED_DATA: unexpected SNEMI3D label shape {vol.shape}")
    sha = file_sha256(labels)
    note = ("CAPE v3 confirm scale track, declared in the v3 freeze before any codec ran on SNEMI3D: the whole "
            "training-label volume and its four non-overlapping XY quadrants (all z). ONE acquisition: results are "
            "conditional on this volume. The quadrants contain the 32 frozen confirm crops (z 0-63).")
    boxes = [("full", [[0, X], [0, Y], [0, Z]])]
    for qy in (0, Y // 2):
        for qx in (0, X // 2):
            boxes.append((f"q_x{qx}_y{qy}", [[qx, qx + X // 2], [qy, qy + Y // 2], [0, Z]]))
    rows = []
    for tag, bb in boxes:
        shape = (bb[0][1] - bb[0][0], bb[1][1] - bb[1][0], bb[2][1] - bb[2][0])
        sid = f"snemi3d_v3_{tag}_{shape[0]}x{shape[1]}x{shape[2]}"
        sub = vol[bb[2][0]:bb[2][1], bb[1][0]:bb[1][1], bb[0][0]:bb[0][1]]
        canon, _ = to_canonical(np.ascontiguousarray(sub), "ZYX")
        row = data_prep.make_row(
            canon, ROOT / "data" / "real" / "snemi3d_v3_scale" / f"{sid}.npy", sample_id=sid,
            family_id="snemi3d", source_id="snemi3d:train", specimen_id="snemi3d:kasthuri2015_s1",
            macroblock_id=f"snemi3d_v3:{tag}", split="heldout", is_synthetic=False,
            source_url=f"https://doi.org/{log['doi']}",
            source_version=f"zenodo record {log['record']} snemi.zip md5 {log['md5']}",
            license="CC-BY-4.0 (Zenodo 10.5281/zenodo.7142003); never redistributed", citation="SNEMI3D",
            array_key="seg/train-labels.tif", source_axes="ZYX", bbox_xyz=bb, spacing_xyz=None,
            original_path=data_prep.rel(labels), original_file_sha256=sha,
            null_reasons={"spacing_xyz": "not stated inside the archive"},
            selection_rule="v3 confirm scale track: whole volume + 4 non-overlapping XY quadrants; no content-based "
                           "selection")
        row["v3_role"] = "confirm_scale"
        row["v3_note"] = note
        rows.append(row)
    write_manifest(out, rows)
    load_manifest(out)
    print(f"{out.name}: {len(rows)} rows {[r['sample_id'] for r in rows]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--snemi-scale", action="store_true")
    a = ap.parse_args(argv)
    if not (a.dev or a.snemi_scale):
        ap.error("choose --dev and/or --snemi-scale")
    if a.dev:
        dev()
    if a.snemi_scale:
        snemi_scale()
    return 0


if __name__ == "__main__":
    sys.exit(main())
