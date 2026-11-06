"""Authorized download of SNEMI3D (CREMI-independent confirmatory source, plan v2.1).

    python scripts/fetch_snemi3d.py            # download, verify, extract the training labels

Source: Zenodo record 10.5281/zenodo.7142003 ("SNEMI3D: 3D Segmentation of neurites in EM images",
Arganda-Carreras, Seung, Vishwanathan, Berger; CC-BY-4.0). Download authorized by the user on
2026-11-06 for the next confirmatory experiment only; the data is never redistributed.

Integrity:
  * the Zenodo API metadata (file key, size, md5) must equal the values pinned below at the time
    of authorization - if the record changed, the script stops instead of trusting the new file;
  * the downloaded bytes must match that md5 and size; the SHA-256 is computed and logged;
  * only zip members whose names look like training *labels* are extracted, under fixed local
    names (no path from the archive is used on disk).
No compression is run here. Output: data/downloads/snemi3d/{snemi.zip, labels/, download_log.json}.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "downloads" / "snemi3d"
RECORD = 7142003
DOI = "10.5281/zenodo.7142003"
API = f"https://zenodo.org/api/records/{RECORD}"
PINNED = {"key": "snemi.zip", "size": 194_608_530, "md5": "3d25a7025f66698f33c7850ace885939",
          "license": "cc-by-4.0"}
UA = {"User-Agent": "cape-pins-data-fetch/0.1 (research download)"}
CAP = 400 << 20


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _hashes(p: Path) -> tuple[str, str, int]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    n = 0
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            md5.update(b)
            sha.update(b)
            n += len(b)
    return md5.hexdigest(), sha.hexdigest(), n


def check_record() -> dict:
    rec = _get_json(API)
    md = rec.get("metadata", {})
    files = [f for f in rec.get("files", []) if f.get("key") == PINNED["key"]]
    if len(files) != 1:
        raise SystemExit(f"BLOCKED_DATA: Zenodo record {RECORD} has no unique file {PINNED['key']}")
    f = files[0]
    md5 = str(f.get("checksum", "")).removeprefix("md5:")
    lic = (md.get("license") or {}).get("id")
    problems = []
    if int(f.get("size", -1)) != PINNED["size"]:
        problems.append(f"size {f.get('size')} != pinned {PINNED['size']}")
    if md5 != PINNED["md5"]:
        problems.append(f"md5 {md5} != pinned {PINNED['md5']}")
    if lic != PINNED["license"]:
        problems.append(f"license {lic} != pinned {PINNED['license']}")
    if problems:
        raise SystemExit("BLOCKED_DATA: the Zenodo record changed since authorization: " + "; ".join(problems))
    link = (f.get("links") or {}).get("self") or f"https://zenodo.org/records/{RECORD}/files/{PINNED['key']}?download=1"
    return {"title": md.get("title"), "creators": [c.get("name") for c in md.get("creators", [])],
            "license": lic, "publication_date": md.get("publication_date"), "doi": rec.get("doi") or DOI,
            "url": link, "published_md5": md5, "published_size": int(f["size"])}


def download(url: str, dest: Path) -> None:
    tmp = dest.with_name(dest.name + ".part")
    n = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as fh:
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            n += len(block)
            if n > CAP:
                fh.close()
                tmp.unlink(missing_ok=True)
                raise SystemExit(f"download exceeded the size cap ({CAP >> 20} MiB)")
            fh.write(block)
    tmp.replace(dest)


def is_train_label(name: str) -> bool:
    low = name.lower().replace("\\", "/")
    base = low.rsplit("/", 1)[-1]
    return base.endswith((".tif", ".tiff", ".h5", ".hdf", ".hdf5")) and "label" in low and "test" not in base \
        and not base.startswith("._")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / PINNED["key"]
    log_p = out / "download_log.json"
    if zpath.exists() and log_p.exists():
        # already fetched and verified: re-check offline, keep the original log (fetch time, Zenodo metadata)
        prev = json.loads(log_p.read_text(encoding="utf-8"))
        md5, sha, n = _hashes(zpath)
        extracted_ok = bool(prev.get("extracted")) and all(
            (ROOT / e["path"]).exists() and _hashes(ROOT / e["path"])[1] == e["sha256"] for e in prev["extracted"])
        if md5 == PINNED["md5"] and n == PINNED["size"] and sha == prev.get("sha256") and extracted_ok:
            print(f"OK already verified offline: snemi.zip md5={md5} sha256={sha[:16]}.. (log kept, no download)")
            return 0
        print("local SNEMI3D files do not match download_log.json - re-verifying against Zenodo", flush=True)
    meta = check_record()
    if not zpath.exists():
        print(f"downloading {meta['url']} ({PINNED['size'] >> 20} MiB) ...", flush=True)
        download(meta["url"], zpath)
    md5, sha, n = _hashes(zpath)
    if md5 != PINNED["md5"] or n != PINNED["size"]:
        zpath.unlink(missing_ok=True)
        raise SystemExit(f"BLOCKED_DATA: downloaded file md5 {md5} / {n} B != published {PINNED['md5']} / "
                         f"{PINNED['size']} B; deleted")
    members, extracted = [], []
    labels_dir = out / "labels"
    labels_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            members.append({"name": info.filename, "bytes": info.file_size, "crc32": f"{info.CRC:08x}"})
        picks = [i for i in zf.infolist() if not i.is_dir() and is_train_label(i.filename)]
        if not picks:
            raise SystemExit("BLOCKED_DATA: no training-label member in the archive: "
                             + ", ".join(m["name"] for m in members))
        for k, info in enumerate(picks):
            suffix = Path(info.filename).suffix.lower()
            dest = labels_dir / f"train_labels_{k}{suffix}"
            with zf.open(info) as src, open(dest, "wb") as dst:
                for b in iter(lambda: src.read(1 << 22), b""):
                    dst.write(b)
            _, esha, en = _hashes(dest)
            extracted.append({"member": info.filename, "path": dest.relative_to(ROOT).as_posix(), "bytes": en,
                              "sha256": esha})
    log = {"source": "zenodo", "record": RECORD, **meta, "authorized_by_user": "2026-11-06 (plan v2.1)",
           "path": zpath.relative_to(ROOT).as_posix(), "bytes": n, "md5": md5, "sha256": sha,
           "verified_against_published_md5": True, "members": members, "extracted": extracted,
           "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
           "redistribution": "never (data stays local; CC-BY-4.0 attribution in docs/MUSTAQIL_DATA_SNEMI3D_UZ.md)"}
    (out / "download_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"OK snemi.zip md5={md5} sha256={sha[:16]}..; extracted {[e['member'] for e in extracted]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
