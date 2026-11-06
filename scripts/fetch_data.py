"""Explicit, authorized dataset downloads (spec section 18).

    python scripts/fetch_data.py cremi          # CREMI A/B/C labeled training volumes

Order of sources for CREMI:
  1. the official page https://cremi.org/data/ (links resolved from the page, never invented);
  2. only if the official host is unreachable AND configs/datasets.yaml records an authorized
     mirror: that mirror (Hugging Face pytc/tutorial, approved by the user on 2026-11-05). Every
     mirror file must match the SHA-256 published in the mirror's LFS metadata; a mismatch deletes
     the file and fails. The manifest records the mirror as the source ("not the official host").
File hashes are computed after download and stored in download_log.json; a disk preflight and a
total size cap (default 20 GiB) apply. H01 and MICrONS are refused unless --i-have-authorization.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREMI_PAGE = "https://cremi.org/data/"
UA = {"User-Agent": "cape-pins-data-fetch/0.1 (research download)"}


def _get(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def resolve_cremi_official() -> list[dict]:
    html = _get(CREMI_PAGE).decode("utf-8", errors="replace")
    links = sorted(set(re.findall(r'href="([^"]*sample_[ABC]_\d{8}\.hdf)"', html)))
    return [{"url": link if link.startswith("http") else urllib.request.urljoin(CREMI_PAGE, link),
             "name": link.rsplit("/", 1)[-1], "expected_sha256": None, "expected_bytes": None,
             "source": "official cremi.org"} for link in links]


def resolve_cremi_mirror(spec: dict) -> list[dict]:
    if spec.get("provider") != "huggingface" or not spec.get("authorized"):
        return []
    api = f"https://huggingface.co/api/datasets/{spec['repo']}/tree/main/{spec['path']}"
    items = json.loads(_get(api).decode("utf-8"))
    out = []
    for it in items:
        name = it["path"].rsplit("/", 1)[-1]
        if name not in spec["files"]:
            continue
        lfs = it.get("lfs") or {}
        if not lfs.get("oid"):
            raise RuntimeError(f"mirror file {name} has no LFS SHA-256; refusing an unverifiable download")
        out.append({"url": f"https://huggingface.co/datasets/{spec['repo']}/resolve/main/{it['path']}", "name": name,
                    "expected_sha256": lfs["oid"], "expected_bytes": it.get("size"),
                    "source": f"mirror huggingface:{spec['repo']} ({spec.get('provenance_note', 'not official')})"})
    return sorted(out, key=lambda d: d["name"])


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def download(item: dict, dest: Path, cap_bytes: int) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(item, path=str(dest))
    if dest.exists():
        rec.update(bytes=dest.stat().st_size, sha256=_sha(dest), skipped=True)
    else:
        tmp = dest.with_name(dest.name + ".part")
        h = hashlib.sha256()
        n = 0
        with urllib.request.urlopen(urllib.request.Request(item["url"], headers=UA), timeout=120) as r, \
                open(tmp, "wb") as fh:
            while True:
                block = r.read(1 << 20)
                if not block:
                    break
                n += len(block)
                if n > cap_bytes:
                    fh.close()
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(f"download exceeded the size cap ({cap_bytes >> 30} GiB)")
                h.update(block)
                fh.write(block)
        tmp.replace(dest)
        rec.update(bytes=n, sha256=h.hexdigest(), skipped=False)
    if item.get("expected_sha256") and rec["sha256"] != item["expected_sha256"]:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{item['name']}: SHA-256 {rec['sha256']} != published {item['expected_sha256']}; deleted")
    rec["verified_against_published_hash"] = bool(item.get("expected_sha256"))
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", choices=["cremi", "h01", "microns"])
    ap.add_argument("--cap-gib", type=float, default=20.0)
    ap.add_argument("--min-free-gib", type=float, default=5.0)
    ap.add_argument("--i-have-authorization", action="store_true")
    ap.add_argument("--no-freeze", action="store_true", help="download only; do not materialize crops/manifests")
    args = ap.parse_args(argv)
    if args.dataset in ("h01", "microns") and not args.i_have_authorization:
        print(f"REFUSED: downloading {args.dataset} was not authorized for this workspace (decision 2026-11-05). "
              "Ask for explicit approval, then rerun with --i-have-authorization.", file=sys.stderr)
        return 2
    if args.dataset != "cremi":
        print("ERROR: only CREMI downloads are implemented for this workspace", file=sys.stderr)
        return 2
    free = shutil.disk_usage(ROOT).free
    if free < args.min_free_gib * (1 << 30):
        print(f"BLOCKED: only {free >> 30} GiB free (< {args.min_free_gib} GiB)", file=sys.stderr)
        return 2
    import yaml

    spec = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))["datasets"]["cremi"]
    attempts = []
    try:
        items = resolve_cremi_official()
        if not items:
            raise RuntimeError("no sample_[ABC]_YYYYMMDD.hdf links on the official page")
        attempts.append({"source": CREMI_PAGE, "result": "ok"})
    except (OSError, RuntimeError) as exc:
        attempts.append({"source": CREMI_PAGE, "result": f"unreachable: {exc}",
                         "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")})
        mirror = spec.get("mirror") or {}
        if not mirror.get("authorized"):
            print(f"BLOCKED: official CREMI host unreachable ({exc}) and no authorized mirror", file=sys.stderr)
            return 2
        print(f"official host unreachable ({exc}); using the authorized mirror {mirror['repo']}", flush=True)
        try:
            items = resolve_cremi_mirror(mirror)
        except (OSError, RuntimeError) as exc2:
            print(f"BLOCKED: mirror unavailable too: {exc2}", file=sys.stderr)
            return 2
        attempts.append({"source": f"huggingface:{mirror['repo']}", "result": "ok"})
    dest_dir = ROOT / "data" / "downloads" / "cremi"
    cap = int(args.cap_gib * (1 << 30))
    log = []
    for item in items:
        print(f"downloading {item['url']} ...", flush=True)
        try:
            rec = download(item, dest_dir / item["name"], cap)
        except (OSError, RuntimeError) as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        cap -= rec["bytes"]
        rec["downloaded_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        log.append(rec)
        print(f"  {rec['bytes'] >> 20} MiB sha256={rec['sha256'][:16]} verified={rec['verified_against_published_hash']}"
              f"{' (already present)' if rec['skipped'] else ''}")
    (dest_dir / "download_log.json").write_text(json.dumps({"attempts": attempts, "files": log}, indent=2),
                                                encoding="utf-8")
    if args.no_freeze:
        return 0
    sys.path.insert(0, str(ROOT))
    from scripts.freeze_data import main as freeze

    return freeze(["--cremi-dir", str(dest_dir)])


if __name__ == "__main__":
    sys.exit(main())
