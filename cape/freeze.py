"""Protocol freeze (spec sections 23, 30): before any held-out metric is computed, the config,
method set, split/data hashes and source hash are written to configs/frozen/. A freeze is
keyed by (config hash, split hash); an incompatible change produces a different key and
therefore a new run - an old result is never attached to a different protocol."""

from __future__ import annotations

import json

from cape.provenance import FREEZE_ROOT
from cape.result_store import atomic_write_text, now_iso


def ensure_freeze(ctx) -> dict:
    split_hash = ctx.hashes.get("manifest")
    if not split_hash:
        from cape.dataset_manifest import split_hash as sh

        split_hash = sh(ctx.rows)
        ctx.hashes["manifest"] = split_hash
    key = f"{ctx.cfg['mode']}_{ctx.hashes['config'][:12]}_{split_hash[:12]}"
    path = FREEZE_ROOT / f"{key}.json"
    record = {
        "freeze_id": key, "mode": ctx.cfg["mode"], "config_path": ctx.cfg["_path"], "config_hash": ctx.hashes["config"],
        "methods_hash": ctx.hashes["methods"], "split_hash": split_hash, "source_hash": ctx.hashes["source"],
        "algorithm": ctx.cfg["algorithm"], "methods": ctx.cfg["methods"], "primary": ctx.cfg["primary"],
        "splits": ctx.cfg["input"]["splits"],
        "selection_rule": "deterministic preset: the algorithm section of the run config is used as written; no "
                          "parameter is tuned on held-out data",
    }
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("source_hash") != record["source_hash"]:
            # new code (possibly new methods.yaml): a separate, versioned freeze; the old one stays
            record["created_at"] = now_iso()
            record["supersedes_source_hash"] = old.get("source_hash")
            path = path.with_name(f"{key}_{ctx.hashes['source'][:8]}.json")
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
            else:
                atomic_write_text(path, json.dumps(record, indent=2))
                return record
        for k in ("config_hash", "methods_hash", "split_hash"):
            if old.get(k) != record[k]:
                raise RuntimeError(f"freeze {path.name} exists with a different {k}; refusing to reuse it")
        return old
    record["created_at"] = now_iso()
    atomic_write_text(path, json.dumps(record, indent=2))
    return record
