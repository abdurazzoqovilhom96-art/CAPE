"""Package and verify the release ZIPs of a run (spec sections 31, 37.10).

    python scripts/package_release.py --latest | --run-dir results/<run_id>
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
    from cape.packaging import package_run
    from cape.runner import StageError, load_context
    from scripts.verify_results import resolve_run

    ctx = load_context(resolve_run(args), {"resume": True})
    try:
        print(json.dumps(package_run(ctx), indent=2))
    except StageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    finally:
        ctx.store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
