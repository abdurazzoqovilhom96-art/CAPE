"""Verify a run's artifacts (spec section 37). Exit 0 if every check passes, 6 otherwise.

    python scripts/verify_results.py --latest | --run-dir results/<run_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def resolve_run(args) -> Path:
    if args.run_dir:
        return Path(args.run_dir).resolve()
    return Path((ROOT / "results" / "LATEST_RUN.txt").read_text(encoding="utf-8").strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--latest", action="store_true")
    g.add_argument("--run-dir")
    args = ap.parse_args(argv)
    from cape.artifact_manifest import verify_run

    res = verify_run(resolve_run(args))
    for p in res["problems"]:
        print("PROBLEM:", p)
    print("VERIFIED OK" if res["ok"] else f"VERIFICATION FAILED ({len(res['problems'])} problems)")
    return 0 if res["ok"] else 6


if __name__ == "__main__":
    sys.exit(main())
