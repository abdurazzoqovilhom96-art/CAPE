"""Build a manifest from a data directory, only when the layout is unambiguous (spec 30 --data).

Accepted layouts:
  * a CREMI download directory (sample_[ABC]_*.hdf) -> scripts/freeze_data.py logic;
  * a directory with manifest.jsonl -> validated and copied;
  * .npy files each with a sidecar <name>.axes (one line: e.g. ZYX or XYZ).
Anything else (unknown HDF5 key, TIFF stacks without a declared z order, missing axes) produces
data/manifests/TEMPLATE_<name>.jsonl listing the fields to fill, and exit code 2. Nothing is guessed.

    python scripts/make_manifest.py --data data/real --out data/manifests/pilot.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import data_prep  # noqa: E402
from cape.canonical import to_canonical  # noqa: E402
from cape.dataset_manifest import load_manifest, write_manifest  # noqa: E402
from cape.io import file_sha256  # noqa: E402

REQUIRED = ["sample_id", "family_id", "source_id", "specimen_id", "macroblock_id", "split", "path", "source_url",
            "source_version", "license", "citation", "array_key", "axes", "dtype", "shape", "bbox_xyz", "spacing_xyz",
            "original_file_sha256", "voxel_sha256", "is_synthetic", "selection_rule"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="data/manifests/pilot.jsonl")
    ap.add_argument("--split", default="development", choices=["development", "heldout"])
    args = ap.parse_args(argv)
    data = Path(args.data)
    data = data if data.is_absolute() else ROOT / data
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    if not data.exists():
        print(f"BLOCKED_DATA: {data} does not exist", file=sys.stderr)
        return 2
    cremi_dir = next((d for d in [data, data / "cremi", ROOT / "data" / "downloads" / "cremi"]
                      if d.exists() and any(d.glob("sample_[ABC]_*.hdf"))), None)
    if cremi_dir is not None:
        from scripts.freeze_data import main as freeze

        return freeze(["--cremi-dir", str(cremi_dir)])
    if (data / "manifest.jsonl").exists():
        load_manifest(data / "manifest.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(data / "manifest.jsonl", out)
        print(f"copied validated manifest -> {out}")
        return 0
    rows, missing = [], []
    import numpy as np

    for f in sorted(data.rglob("*.npy")):
        axes_file = f.with_suffix(".axes")
        if not axes_file.exists():
            missing.append({"file": str(f), "missing": ["axes (create <name>.axes with e.g. ZYX)", "license",
                                                        "source_url", "citation"]})
            continue
        axes = axes_file.read_text(encoding="utf-8").strip().upper()
        canon, _ = to_canonical(np.load(f, allow_pickle=False), axes)
        sid = f"user_{f.stem}"
        rows.append(data_prep.make_row(canon, ROOT / "data" / "real" / "user_crops" / f"{sid}.npy", sample_id=sid,
                                       family_id="user", source_id=f"user:{f.stem}", specimen_id=None,
                                       macroblock_id=f.stem, split=args.split, is_synthetic=False,
                                       license="unknown", source_axes=axes, original_path=str(f),
                                       original_file_sha256=file_sha256(f), selection_rule="whole user file",
                                       null_reasons={"specimen_id": "not provided", "source_url": "not provided"}))
    if missing or not rows:
        tmpl = out.with_name(f"TEMPLATE_{out.stem}.jsonl")
        tmpl.parent.mkdir(parents=True, exist_ok=True)
        tmpl.write_text("".join(json.dumps({k: None for k in REQUIRED} | {"__file__": m["file"],
                                                                            "__missing__": m["missing"]}) + "\n"
                                for m in missing) or json.dumps({k: None for k in REQUIRED}) + "\n", encoding="utf-8")
        print(f"BLOCKED_DATA: layout of {data} is ambiguous; fill {tmpl} (missing fields listed per file)",
              file=sys.stderr)
        return 2
    write_manifest(out, rows)
    print(f"{len(rows)} samples -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
