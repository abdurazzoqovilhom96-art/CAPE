"""Run the offline CP-SAT audit (spec section 12) for an existing run's samples.

    python scripts/run_oracle.py --latest | --run-dir results/<run_id>
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
    from cape.oracle import run_oracle_audit
    from cape.runner import load_context, stage_data_validated
    from scripts.verify_results import resolve_run

    ctx = load_context(resolve_run(args), {"resume": True})
    stage_data_validated(ctx)
    summary = run_oracle_audit(ctx)
    ctx.store.close()
    print(json.dumps(summary, indent=2))
    return 3 if summary.get("contradictions") else 0


if __name__ == "__main__":
    sys.exit(main())
