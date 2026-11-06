"""Create (or check) the protocol freeze for a config + manifest without running anything
(spec sections 23, 30). `--stage all` does this automatically before held-out metrics.

    python scripts/freeze_protocol.py --config configs/benchmark.yaml --manifest data/manifests/benchmark.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _Ctx:
    def __init__(self, cfg, rows, hashes):
        self.cfg, self.rows, self.hashes = cfg, rows, hashes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args(argv)
    from cape.config import load_run_config
    from cape.dataset_manifest import load_manifest, split_hash
    from cape.freeze import ensure_freeze
    from cape.provenance import source_tree_hash

    cfg = load_run_config(args.config)
    rows = [r for r in load_manifest(args.manifest) if r["split"] in cfg["input"]["splits"]]
    if not rows:
        print("BLOCKED_DATA: no rows in the configured splits", file=sys.stderr)
        return 2
    ctx = _Ctx(cfg, rows, {"config": cfg["_hash"], "methods": cfg["_methods_hash"], "source": source_tree_hash(),
                           "manifest": split_hash(rows)})
    print(json.dumps(ensure_freeze(ctx), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
