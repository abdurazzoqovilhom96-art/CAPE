"""Generate the synthetic fixture set (spec section 22) and deterministic Crackle sample crops,
and write a manifest (default: the smoke manifest).

    python scripts/generate_fixtures.py [--out data/manifests/smoke.jsonl] [--no-crackle]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cape import data_prep  # noqa: E402
from cape.dataset_manifest import write_manifest  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/manifests/smoke.jsonl")
    ap.add_argument("--synthetic-dir", default="data/synthetic")
    ap.add_argument("--crop-dir", default="data/real/crackle_crops")
    ap.add_argument("--no-crackle", action="store_true")
    ap.add_argument("--seed", type=int, default=data_prep.SEED)
    args = ap.parse_args(argv)
    rows = data_prep.synthetic_rows(ROOT / args.synthetic_dir, args.seed)
    if not args.no_crackle:
        rows += data_prep.crackle_sample_rows(ROOT / args.crop_dir, seed=args.seed)
    write_manifest(args.out, rows)
    print(f"{len(rows)} samples -> {args.out} ({sum(r['is_synthetic'] for r in rows)} synthetic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
