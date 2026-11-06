"""Data manifest handling (spec sections 18, 27): JSONL rows validated against
schemas/dataset.schema.json, split integrity, and materialized-crop verification."""

from __future__ import annotations

import json
from pathlib import Path

from cape.provenance import ROOT, json_hash

SPLITS = ("synthetic", "development", "heldout")


class ManifestError(ValueError):
    pass


def _validator():
    import jsonschema

    schema = json.loads((ROOT / "schemas" / "dataset.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def resolve_path(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def load_manifest(path: str | Path) -> list[dict]:
    path = resolve_path(str(path))
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    rows = []
    validator = _validator()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"{path.name}:{lineno}: invalid JSON ({exc})") from exc
        errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
        if errors:
            e = errors[0]
            raise ManifestError(f"{path.name}:{lineno}: {'.'.join(map(str, e.path)) or '<row>'}: {e.message}")
        rows.append(row)
    check_integrity(rows)
    return rows


def check_integrity(rows: list[dict]) -> None:
    ids = [r["sample_id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ManifestError(f"duplicate sample_id: {sorted(dup)[:5]}")
    split_of_block: dict[str, str] = {}
    for r in rows:
        key = f"{r['source_id']}/{r['macroblock_id']}"
        prev = split_of_block.setdefault(key, r["split"])
        if prev != r["split"]:
            raise ManifestError(f"macroblock {key} appears in two splits ({prev}, {r['split']})")
        if r["is_synthetic"] and r["split"] != "synthetic":
            raise ManifestError(f"{r['sample_id']}: synthetic sample outside the synthetic split")
        if not r["is_synthetic"] and r["split"] == "synthetic":
            raise ManifestError(f"{r['sample_id']}: real sample in the synthetic split")


def write_manifest(path: str | Path, rows: list[dict]) -> None:
    check_integrity(rows)
    path = resolve_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: r["sample_id"])),
                   encoding="utf-8")
    tmp.replace(path)


def split_hash(rows: list[dict]) -> str:
    return json_hash(sorted((r["sample_id"], r["split"], r["voxel_sha256"]) for r in rows))


def verify_materialized(row: dict):
    """Load the canonical crop and check shape, dtype and voxel hash. Returns the array."""
    from cape.canonical import voxel_sha256
    from cape.io import load_canonical

    path = resolve_path(row["path"])
    if not path.exists():
        raise ManifestError(f"{row['sample_id']}: file missing ({path})")
    arr = load_canonical(path)
    if list(arr.shape) != list(row["shape"]):
        raise ManifestError(f"{row['sample_id']}: shape {list(arr.shape)} != manifest {row['shape']}")
    if str(arr.dtype) != row["dtype"]:
        raise ManifestError(f"{row['sample_id']}: dtype {arr.dtype} != manifest {row['dtype']}")
    vh = voxel_sha256(arr)
    if vh != row["voxel_sha256"]:
        raise ManifestError(f"{row['sample_id']}: voxel hash mismatch")
    return arr
