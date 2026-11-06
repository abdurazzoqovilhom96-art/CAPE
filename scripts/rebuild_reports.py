"""Rebuild statistics, tables, figures, reports and the release from committed measurements
without encoding, decoding, downloading or tuning anything (spec section 40).

    python scripts/rebuild_reports.py --latest | --run-dir results/<run_id>
"""

from __future__ import annotations

import argparse
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
    from cape.cli import report_only
    from scripts.verify_results import resolve_run

    return report_only(resolve_run(args))


if __name__ == "__main__":
    sys.exit(main())
