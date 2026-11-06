"""Recover a run after a hard stop (spec sections 36, 40): committed rows kept, RUNNING tasks
back to PENDING, temp files discarded, live exports rebuilt, partial report written.

    python scripts/recover_run.py --latest | --run-dir results/<run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--latest", action="store_true")
    g.add_argument("--run-dir")
    args = ap.parse_args(argv)
    from cape.recovery import recover
    from scripts.verify_results import resolve_run

    print(json.dumps(recover(resolve_run(args), {"resume": True}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
