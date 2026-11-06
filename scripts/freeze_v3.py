"""CAPE v3 stage FREEZE (plan CAPE v3, sections 3.2 step 6, 12.3): fix everything the confirmatory batch uses BEFORE
any codec runs on SNEMI3D.

    python scripts/freeze_v3.py

1. requires analysis/v3_select/selected_methods.json (phase 2) and that no run ever used SNEMI3D;
2. writes the SNEMI3D scale-track manifest (whole volume + 4 quadrants; scripts/make_v3_manifests.py --snemi-scale);
3. writes configs/v3_confirm_frozen.yaml (32 frozen crops, 7 repeats) and configs/v3_confirm_scale_frozen.yaml
   (scale track, 3 repeats) from the selection - one fixed batch each, no later edits;
4. writes analysis/v3_freeze/freeze.json: expected source hash (the confirm runs must record exactly this),
   parent git commit, frozen v2.1 sha256, resolved method definitions, config / manifest hashes, statistics plan
   and the pre-registered primary family; then commits everything on the current branch ("v3 FREEZE").
A later change of any frozen input makes run_v3.py refuse the confirm stage (a new freeze would be required and
would be reported as a protocol amendment).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

OUT = ROOT / "analysis" / "v3_freeze"
SEL = ROOT / "analysis" / "v3_select" / "selected_methods.json"
PROTO = ROOT / "configs" / "v3_development.yaml"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def confirm_methods(sel: dict) -> tuple[list[str], list[str]]:
    """Primary batch (32 frozen crops) and scale-track batch. Fixed lists; QUALITY only when selected."""
    primary = ["cape_v3_fast_m0", "cape_v21_fast_m0", "crackle_pins_opt_corrected_m0", "crackle_flat_m0",
               "crackle_pins_opt_m0", "crackle_pins_fast_m0", "crackle_vendor_pins_opt_m0",
               "v3_fast_weighted_greedy_m0", "v3_fast_greedy_local_m0",
               "cape_v3_certified_m0", "v3_fast_weighted_greedy_certified_m0",
               "safe_v3_fast_m0_zstd9", "safe_v3_fast_m0_zstd3", "safe_stock_m0_zstd9", "safe_stock_m0_zstd3",
               "cape_v3_fast_m5", "cape_v21_fast_m5", "crackle_pins_opt_corrected_m5", "crackle_flat_m5",
               "compresso_native", "neuroglancer_b8", "blosc2_bshuffle_zstd5", "zstd9", "lzma6_raw", "raw"]
    scale = ["cape_v3_fast_m0", "cape_v21_fast_m0", "crackle_flat_m0",
             "v3_fast_weighted_greedy_m0", "cape_v3_certified_m0", "safe_v3_fast_m0_zstd9"]
    if sel.get("memory_impl_mask") is not None and sel["memory_impl_mask"] != sel["fast_impl_mask"]:
        primary.append("cape_v3_memory_m0")
        scale.append("cape_v3_memory_m0")
    if sel.get("quality_selected"):
        primary.append("cape_v3_quality_m0")
        scale.append("cape_v3_quality_m0")
    return primary, scale


# the corrected stock pin optimizer only runs on volumes <= 2^25 voxels (v2.1 rule, data/manifests/
# scaling_v21_skipped.json: 269 s per encode already at 512x512x256); on the SNEMI3D scale track it therefore runs on
# the four quadrants (2^24.6 voxels each) with v3 FAST repeated in the same run as the matched reference
STOCK_MAX_VOXELS = 1 << 25
SCALE_STOCK_METHODS = ["cape_v3_fast_m0", "crackle_pins_opt_corrected_m0", "safe_v3_fast_m0_zstd9", "safe_stock_m0_zstd9"]


def stock_subset_manifest() -> tuple[str, list[dict]]:
    """confirm_snemi3d_v3_scale_stock.jsonl = rows of the scale manifest with <= 2^25 voxels (unchanged rows);
    every larger row is listed as SKIPPED_BUDGET with the reason. Written before any codec runs on SNEMI3D."""
    src = ROOT / "data" / "manifests" / "confirm_snemi3d_v3_scale.jsonl"
    out = ROOT / "data" / "manifests" / "confirm_snemi3d_v3_scale_stock.jsonl"
    keep, skipped = [], []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        shape = r.get("shape") or r.get("canonical_shape")
        vox = int(shape[0]) * int(shape[1]) * int(shape[2])
        if vox <= STOCK_MAX_VOXELS:
            keep.append(line)
        else:
            skipped.append({"sample_id": r["sample_id"], "voxels": vox, "method": "crackle_pins_opt_corrected_m0, "
                            "safe_stock_m0_zstd9", "status": "SKIPPED_BUDGET",
                            "reason": f"stock Crackle pin optimizer not run above {STOCK_MAX_VOXELS} voxels (v2.1 rule; "
                                      "269 s per encode already at 512x512x256 = 2^26)"})
    if not keep:
        raise SystemExit("BLOCKED: no SNEMI3D scale row within the stock budget")
    if out.exists() and out.read_text(encoding="utf-8") != "\n".join(keep) + "\n":
        raise SystemExit(f"REFUSED: {out.name} exists with different content")
    out.write_text("\n".join(keep) + "\n", encoding="utf-8")
    (ROOT / "data" / "manifests" / "confirm_snemi3d_v3_scale_skipped.json").write_text(json.dumps(skipped, indent=2),
                                                                                       encoding="utf-8")
    return out.relative_to(ROOT).as_posix(), skipped


def write_config(name: str, desc: str, manifest: str, methods: list[str], repeats: int, wrappers: list[str],
                 oracle: bool) -> Path:
    cfg = {"schema_version": 1, "project": "CAPE-Pins", "seed": 20261106, "mode": "benchmark", "description": desc,
           "input": {"manifest": manifest, "splits": ["heldout"], "require_real_data": True},
           "benchmark": {"warmups": 2, "repeats": repeats, "external_wrappers": wrappers, "task_timeout_s": 3600},
           "methods": methods, "panels": ["B"],
           "primary": {"new": "cape_v3_fast_m0", "baseline": "cape_v21_fast_m0"},
           "stats": {"bootstrap_resamples": 10000, "seed": 20261106, "cluster_by": "macroblock_id"},
           "oracle": {"enabled": oracle}}
    p = ROOT / "configs" / f"{name}.yaml"
    p.write_text(f"# GENERATED by scripts/freeze_v3.py at {now()} - CAPE v3 FROZEN confirm batch. Do not edit:\n"
                 "# any change invalidates analysis/v3_freeze/freeze.json and the confirm stage refuses to run.\n"
                 + yaml.safe_dump(cfg, sort_keys=False, width=118), encoding="utf-8")
    return p


def main() -> int:
    from cape import provenance
    from cape.config import load_methods, load_run_config
    from cape.dataset_manifest import load_manifest

    if not SEL.exists():
        print("BLOCKED: analysis/v3_select/selected_methods.json missing", file=sys.stderr)
        return 2
    sel = json.loads(SEL.read_text(encoding="utf-8"))
    if sel.get("phase") != 2:
        print("BLOCKED: selection phase 2 (QUALITY gate) not done", file=sys.stderr)
        return 2
    import make_v3_manifests

    used = make_v3_manifests._snemi_used()
    if used:
        print(f"REFUSED: SNEMI3D already used by {used}; it is no longer a holdout", file=sys.stderr)
        return 2
    make_v3_manifests.snemi_scale()
    primary, scale = confirm_methods(sel)
    c1 = write_config("v3_confirm_frozen", "CAPE v3 CONFIRM (frozen): SNEMI3D 32 crops frozen in v2.1, never compressed "
                      "before; all tracks in one batch", "data/manifests/confirm_snemi3d.jsonl", primary, 7,
                      ["none", "zstd3", "zstd9"], True)
    c2 = write_config("v3_confirm_scale_frozen", "CAPE v3 CONFIRM scale track (frozen): whole SNEMI3D volume + 4 "
                      "non-overlapping quadrants; one acquisition (conditional)",
                      "data/manifests/confirm_snemi3d_v3_scale.jsonl", scale, 3, ["none", "zstd9"], False)
    stock_manifest, skipped = stock_subset_manifest()
    c3 = write_config("v3_confirm_scale_stock_frozen", "CAPE v3 CONFIRM scale track, corrected stock (frozen): the "
                      "SNEMI3D scale rows <= 2^25 voxels (4 quadrants), v3 FAST repeated as the matched reference",
                      stock_manifest, SCALE_STOCK_METHODS, 3, ["none", "zstd9"], False)
    methods = load_methods()
    for c in (c1, c2, c3):
        load_run_config(c, methods)  # validates every method id
    proto = yaml.safe_load(PROTO.read_text(encoding="utf-8"))
    manifests = {}
    for name in ("confirm_snemi3d.jsonl", "confirm_snemi3d_v3_scale.jsonl", "confirm_snemi3d_v3_scale_stock.jsonl"):
        p = ROOT / "data" / "manifests" / name
        rows = load_manifest(p)
        manifests[name] = {"sha256": sha_file(p), "rows": len(rows),
                           "voxel_sha256": {r["sample_id"]: r["voxel_sha256"] for r in rows}}
    src = provenance.source_tree_hash()
    parent = git("rev-parse", "HEAD")
    frozen = json.loads((ROOT / "snapshots" / "v21" / "FROZEN_V21.json").read_text(encoding="utf-8"))
    rec = {
        "frozen_at": now(), "expected_source_hash": src, "parent_commit": parent, "branch": git("rev-parse",
                                                                                                 "--abbrev-ref", "HEAD"),
        "frozen_v21": {"sha256": frozen["sha256"], "file": "snapshots/v21/" + frozen["file"]},
        "selection": {k: sel.get(k) for k in ("fast_impl_mask", "memory_impl_mask", "quality_selected",
                                              "quality_composite_options")},
        "methods": {m: methods[m] for m in sorted(set(primary) | set(scale) | set(SCALE_STOCK_METHODS))},
        "configs": {c.relative_to(ROOT).as_posix(): sha_file(c) for c in (c1, c2, c3)},
        "manifests": manifests,
        "stock_budget": {"max_voxels": STOCK_MAX_VOXELS, "skipped": skipped},
        "confirm_runs": {"primary": {"config": c1.relative_to(ROOT).as_posix(),
                                     "manifest": "data/manifests/confirm_snemi3d.jsonl"},
                         "scale": {"config": c2.relative_to(ROOT).as_posix(),
                                   "manifest": "data/manifests/confirm_snemi3d_v3_scale.jsonl"},
                         "scale_stock": {"config": c3.relative_to(ROOT).as_posix(), "manifest": stock_manifest}},
        "statistics": proto["statistics"], "primary_family": proto["confirm"]["primary_family"],
        "secondary": proto["confirm"]["secondary"],
        "rules": ["the holdout is run once as a fixed batch; no budget, baseline or parameter changes after seeing it",
                  "a correctness bug found on the holdout keeps the failed run; the fix is a new commit and the data is "
                  "no longer called unseen",
                  "timing-noise fixes are protocol amendments and are written down"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "freeze.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", f"v3 FREEZE: confirm batch fixed before any codec ran on SNEMI3D (source {src[:12]})\n\n"
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    rec["freeze_commit"] = git("rev-parse", "HEAD")
    (OUT / "FREEZE_COMMIT.txt").write_text(rec["freeze_commit"] + "\n", encoding="utf-8")
    print(json.dumps({"expected_source_hash": src, "freeze_commit": rec["freeze_commit"], "primary_methods": len(primary),
                      "scale_methods": len(scale)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
