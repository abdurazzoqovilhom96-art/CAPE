"""Fetch pinned third-party sources into vendor/ and write sources.lock.json (stdlib only).

Usage:
    python scripts/fetch_sources.py              # required sources (crackle)
    python scripts/fetch_sources.py --all        # also optional comparator sources
    python scripts/fetch_sources.py --only volcanite

Each source is fetched by exact commit (shallow fetch of that commit), verified, and its
git tree hash is recorded. An existing checkout at the right commit is left untouched.
Exit codes: 0 ok, 2 missing dependency (git) or fetch failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "sources.lock.json"

# Pinned sources. `required` sources are needed for every stage; optional ones only for
# their comparator adapters (spec section 17.2).
SOURCES = {
    "crackle": {
        "url": "https://github.com/seung-lab/crackle.git",
        "commit": "14b39b196a14b3b1ba7d1cd34f350c324308000f",
        "path": "vendor/crackle",
        "license": "BSD-3-Clause; src/cc3d.hpp is LGPL-3.0-or-later (reduced cc3d)",
        "role": "stock baseline (_crackle_vendor) and CAPE upstream bridge (header, CC labeling, crack codes, markov, CRC)",
        "required": True,
    },
    "crackle_head": {
        "url": "https://github.com/seung-lab/crackle.git",
        "commit": "3426263b0f0cd70bc2ee7d825566c0e6f566b48c",  # remote HEAD on 2026-11-06 (feat: add anisotropy)
        "path": "vendor/crackle_head",
        "license": "BSD-3-Clause; src/cc3d.hpp is LGPL-3.0-or-later (reduced cc3d)",
        "role": "re-check of format_audit F2 on the current upstream (optional _crackle_head module; never a benchmark row)",
        "required": False,
    },
    "volcanite": {
        "url": "https://github.com/max-pio/volcanite.git",
        "commit": "c760814a425aa02b0a7c27a7817a3b0d242ce55f",  # main HEAD on 2026-11-05 (commit 2026-06-10)
        "path": "vendor/volcanite",
        "license": "GPL-3.0 (external process only; not linked, not redistributed)",
        "role": "CSGV / CSGV-R comparator (separate executable)",
        "required": False,
    },
}


def _git(args: list[str], cwd: Path | None = None) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def _load_lock() -> dict:
    if LOCK.exists():
        return json.loads(LOCK.read_text(encoding="utf-8"))
    return {"schema_version": 1, "sources": {}}


def _write_lock(lock: dict) -> None:
    tmp = LOCK.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(LOCK)


def fetch(name: str, spec: dict) -> dict:
    if not spec["commit"]:
        raise RuntimeError(f"{name}: no commit pinned yet")
    dest = ROOT / spec["path"]
    if (dest / ".git").exists():
        head = _git(["rev-parse", "HEAD"], cwd=dest)
        if head != spec["commit"]:
            raise RuntimeError(f"{name}: {dest} is at {head}, expected {spec['commit']}; refusing to modify it")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        _git(["init", "-q"], cwd=dest)
        _git(["remote", "add", "origin", spec["url"]], cwd=dest)
        _git(["fetch", "-q", "--depth", "1", "origin", spec["commit"]], cwd=dest)
        _git(["-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD"], cwd=dest)
    head = _git(["rev-parse", "HEAD"], cwd=dest)
    if head != spec["commit"]:
        raise RuntimeError(f"{name}: checkout ended at {head}, expected {spec['commit']}")
    dirty = _git(["status", "--porcelain"], cwd=dest)
    return {
        "url": spec["url"],
        "commit": head,
        "tree": _git(["rev-parse", "HEAD^{tree}"], cwd=dest),
        "path": spec["path"],
        "license": spec["license"],
        "role": spec["role"],
        "required": spec["required"],
        "working_tree_clean": dirty == "",
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }


def check_latest(names: list[str]) -> int:
    """Plan v2 P1.4: never assume an upstream bug still exists - record the remote HEAD."""
    import json
    from datetime import datetime, timezone

    out = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": {}}
    for name in names:
        spec = SOURCES[name]
        try:
            line = _git(["ls-remote", spec["url"], "HEAD"]).split()
            head = line[0] if line else None
        except Exception as exc:  # noqa: BLE001 - network failure is reported, not hidden
            head, err = None, str(exc)
        else:
            err = None
        out["sources"][name] = {"url": spec["url"], "pinned": spec["commit"], "remote_head": head,
                                "same_as_pinned": head == spec["commit"] if head else None, "error": err}
        print(f"{name}: pinned {spec['commit'][:12]} remote HEAD {str(head)[:12]} "
              f"{'(same)' if head == spec['commit'] else '(DIFFERENT)' if head else '(unknown: ' + str(err) + ')'}")
    dest = ROOT / "build" / "upstream_latest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="also fetch optional comparator sources")
    ap.add_argument("--only", action="append", default=[], help="fetch only this source (repeatable)")
    ap.add_argument("--check-latest", action="store_true",
                    help="read-only: compare each pinned commit with the remote default branch (git ls-remote); "
                         "writes build/upstream_latest.json, changes no checkout and no pin")
    args = ap.parse_args(argv)
    if shutil.which("git") is None:
        print("ERROR: git is not on PATH (required to fetch pinned sources)", file=sys.stderr)
        return 2
    if args.check_latest:
        return check_latest(args.only or list(SOURCES))
    names = args.only or [n for n, s in SOURCES.items() if s["required"] or args.all]
    lock = _load_lock()
    status = 0
    for name in names:
        if name not in SOURCES:
            print(f"ERROR: unknown source {name}", file=sys.stderr)
            return 2
        try:
            entry = fetch(name, SOURCES[name])
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            status = 2
            continue
        prev = lock["sources"].get(name, {})
        if prev.get("commit") == entry["commit"] and prev.get("tree") == entry["tree"]:
            entry["fetched_at"] = prev.get("fetched_at", entry["fetched_at"])
        lock["sources"][name] = entry
        print(f"{name}: {entry['commit']} (tree {entry['tree']}) clean={entry['working_tree_clean']}")
    _write_lock(lock)
    return status


if __name__ == "__main__":
    sys.exit(main())
