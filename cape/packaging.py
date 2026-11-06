"""Release packaging (spec sections 31, 37.10): CAPE_PINS_SOURCE.zip (code, configs, tests,
docs, locks) and CAPE_PINS_RESULTS_<run_id>.zip (validated results and paper assets; bitstreams
only on request; a consistent SQLite snapshot instead of the live file), each carrying a
release_manifest.json of its own content (never including itself), plus SHA256SUMS.txt.
Data files are never packaged (licenses unknown). The ZIPs are re-opened and checked."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from cape.provenance import RELEASE_ROOT, ROOT, source_files
from cape.result_store import atomic_write_text, now_iso

EXTRA_SOURCE = ["README_UZ.md", "AGENTS.md", "THIRD_PARTY_NOTICES.md"]


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _zip(path: Path, items: list[tuple[str, bytes]]) -> dict:
    manifest = [{"path": n, "bytes": len(b), "sha256": _sha_bytes(b)} for n, b in items]
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n, b in items:
            z.writestr(n, b)
        z.writestr("release_manifest.json", json.dumps({"files": manifest, "created_at": now_iso()}, indent=2))
    tmp.replace(path)
    return {"files": len(items)}


def _verify_zip(path: Path) -> list[str]:
    problems = []
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            problems.append(f"{path.name}: corrupt member {bad}")
        man = json.loads(z.read("release_manifest.json"))
        for f in man["files"]:
            if f["path"] == "release_manifest.json":
                problems.append(f"{path.name}: manifest lists itself")
            data = z.read(f["path"])
            if _sha_bytes(data) != f["sha256"] or len(data) != f["bytes"]:
                problems.append(f"{path.name}: hash mismatch for {f['path']}")
    return problems


def package_run(ctx) -> dict:
    run_dir = ctx.run_dir
    out_dir = RELEASE_ROOT / ctx.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    src_items = []
    for p in source_files() + [ROOT / n for n in EXTRA_SOURCE] + sorted((ROOT / "docs").glob("*.md")):
        if p.exists() and p.is_file():
            src_items.append((p.relative_to(ROOT).as_posix(), p.read_bytes()))
    src_items = sorted(dict(src_items).items())
    src_zip = out_dir / "CAPE_PINS_SOURCE.zip"
    _zip(src_zip, src_items)

    snap = run_dir / "05_raw_metrics" / "run_snapshot.sqlite"
    ctx.store.backup(snap)
    include_bits = ctx.cfg["outputs"]["include_bitstreams_in_release"]
    res_items = []
    for p in sorted(run_dir.rglob("*")):
        if not p.is_file() or p.name.endswith(".tmp") or p.name in ("run.sqlite", "run.sqlite-journal", "SUCCESS.json"):
            continue
        relp = p.relative_to(run_dir).as_posix()
        if relp.startswith("03_bitstreams/") and not include_bits and p.suffix == ".bin":
            continue
        res_items.append((f"{ctx.run_id}/{relp}", p.read_bytes()))
    if not include_bits:
        listing = "\n".join(sorted(p.name for p in (run_dir / "03_bitstreams").glob("*.bin")))
        res_items.append((f"{ctx.run_id}/03_bitstreams/BITSTREAM_LIST.txt",
                          (listing + "\n(bitstreams excluded from the release; regenerate with the same config)\n").encode()))
    res_zip = out_dir / f"CAPE_PINS_RESULTS_{ctx.run_id}.zip"
    _zip(res_zip, res_items)
    snap.unlink(missing_ok=True)

    sums = "".join(f"{_sha_bytes(z.read_bytes())}  {z.name}\n" for z in (src_zip, res_zip))
    atomic_write_text(out_dir / "SHA256SUMS.txt", sums)
    problems = _verify_zip(src_zip) + _verify_zip(res_zip)
    for line in sums.splitlines():
        h, name = line.split("  ", 1)
        if _sha_bytes((out_dir / name).read_bytes()) != h:
            problems.append(f"SHA256SUMS mismatch for {name}")
    if problems:
        from cape.runner import EXIT_REPORT, StageError

        raise StageError("release verification failed: " + "; ".join(problems), EXIT_REPORT, "PARTIAL")
    result = {"source_zip": str(src_zip), "results_zip": str(res_zip), "sha256sums": str(out_dir / "SHA256SUMS.txt"),
              "source_files": len(src_items), "results_files": len(res_items), "bitstreams_included": include_bits}
    atomic_write_text(run_dir / "SUCCESS.json", json.dumps({
        "run_id": ctx.run_id, "stage": "PACKAGED", "meaning": "requested stage and its applicable artifacts "
        "completed and verified; this is NOT a statement that CAPE won", "release": result, "at": now_iso()},
        indent=2))
    return result
