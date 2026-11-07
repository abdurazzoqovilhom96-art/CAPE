"""Authorized download of the Q1 external validation sources (docs/q1/EXTERNAL_DATA_PLAN.md).

    .venv-fetch\\Scripts\\python scripts\\fetch_external_q1.py --j0126       # 33 dense GT volumes (official bucket)
    .venv-fetch\\Scripts\\python scripts\\fetch_external_q1.py --hemibrain   # 4 pre-registered hemibrain v1.2 cutouts

The script runs in the fetch-only venv (.venv-fetch: numpy, h5py, tensorstore) and never imports cape. It runs no codec.
The user authorized both sources on 2026-11-07. The data stays local and is never redistributed.

Outputs:
  data/downloads/j0126/{README.txt, gt_*.h5, download_log.json}
  data/downloads/hemibrain/{hemibrain_v1.2_x*_y*_z*_512x512x256.npy, candidates.json, download_log.json}
Manifests are built afterwards by scripts/make_q1_manifests.py (main venv).
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import importlib.metadata as md
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "cape-pins-data-fetch/0.1 (research download)"}

J_BUCKET = "j0126-nature-methods-data"
J_PREFIX = "GgwKmcKgrcoNxJccKuGIzRnQqfit9hnfK1ctZzNbnuU/"
J_README = f"https://storage.googleapis.com/{J_BUCKET}/{J_PREFIX}README.txt"
J_EXPECTED = 33

H_URL = "https://storage.googleapis.com/neuroglancer-janelia-flyem-hemibrain/v1.2/segmentation/"
H_BOX = (512, 512, 256)  # X, Y, Z voxels at scale 0 (8 nm)
H_SEED = 20261107
H_ACCEPT = 4
H_MAX_CANDIDATES = 40
H_MAX_BACKGROUND = 0.5


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def hashes(p: Path) -> tuple[str, str, int]:
    m, s, n = hashlib.md5(), hashlib.sha256(), 0
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            m.update(b)
            s.update(b)
            n += len(b)
    return m.hexdigest(), s.hexdigest(), n


def versions() -> dict:
    out = {"python": sys.version.split()[0]}
    for p in ("numpy", "h5py", "tensorstore"):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


# ---------------------------------------------------------------------------------------------- j0126
def j0126(out: Path) -> int:
    import h5py

    out.mkdir(parents=True, exist_ok=True)
    readme = get(J_README)
    (out / "README.txt").write_bytes(readme)
    listed = sorted(set(re.findall(r"gt_z\d+-\d+_y\d+-\d+_x\d+-\d+\.h5", readme.decode("utf-8", "replace"))))
    api = (f"https://storage.googleapis.com/storage/v1/b/{J_BUCKET}/o?prefix="
           f"{urllib.parse.quote(J_PREFIX, safe='')}&delimiter=/")
    objs = [o for o in json.loads(get(api))["items"] if re.search(r"/gt_.*\.h5$", o["name"])]
    names = sorted(o["name"].rsplit("/", 1)[-1] for o in objs)
    if len(names) != J_EXPECTED or names != listed:
        raise SystemExit(f"BLOCKED_DATA: bucket lists {len(names)} GT files, README lists {len(listed)}; expected "
                         f"{J_EXPECTED} equal lists")
    files = []
    for o in sorted(objs, key=lambda o: o["name"]):
        name = o["name"].rsplit("/", 1)[-1]
        dest = out / name
        want_md5 = base64.b64decode(o["md5Hash"]).hex()
        want_size = int(o["size"])
        if not (dest.exists() and hashes(dest)[0] == want_md5):
            tmp = dest.with_name(name + ".part")
            tmp.write_bytes(get(o["mediaLink"], timeout=600))
            tmp.replace(dest)
        m5, sha, n = hashes(dest)
        if m5 != want_md5 or n != want_size:
            dest.unlink(missing_ok=True)
            raise SystemExit(f"BLOCKED_DATA: {name}: md5 {m5} / {n} B != published {want_md5} / {want_size} B")
        with h5py.File(dest, "r") as f:
            ds = f["main"]
            shape, dtype = tuple(int(v) for v in ds.shape), str(ds.dtype)
        bb = [int(v) for v in re.fullmatch(r"gt_z(\d+)-(\d+)_y(\d+)-(\d+)_x(\d+)-(\d+)\.h5", name).groups()]
        z0, z1, y0, y1, x0, x1 = bb
        if shape != (z1 - z0, y1 - y0, x1 - x0):
            raise SystemExit(f"BLOCKED_DATA: {name}: dataset shape {shape} != name bbox")
        files.append({"name": name, "path": dest.relative_to(ROOT).as_posix(), "bytes": n, "md5": m5, "sha256": sha,
                      "gcs_generation": o.get("generation"), "dataset": "/main", "shape_zyx": list(shape),
                      "dtype": dtype, "bbox_zyx": [[z0, z1], [y0, y1], [x0, x1]]})
        print(f"OK {name} {shape} {dtype} md5={m5}", flush=True)
    log = {"source": "j0126 official bucket", "bucket": f"gs://{J_BUCKET}/{J_PREFIX}", "readme_url": J_README,
           "readme_sha256": hashlib.sha256(readme).hexdigest(), "paper_doi": "10.1038/s41592-018-0049-4",
           "licence": "not stated in the official README (HF mirror pytc/zebrafinch-j0126 is tagged 'mit')",
           "authorized_by_user": "2026-11-07 (Q1 task v3)", "files": files, "fetched_at": now(),
           "tools": versions(), "redistribution": "never (local only)"}
    (out / "download_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"j0126: {len(files)} files verified")
    return 0


# ---------------------------------------------------------------------------------------------- hemibrain
def hemibrain(out: Path) -> int:
    import numpy as np
    import tensorstore as ts

    out.mkdir(parents=True, exist_ok=True)
    info = get(H_URL + "info")
    (out / "info.json").write_bytes(info)
    t = ts.open({"driver": "neuroglancer_precomputed", "kvstore": H_URL, "scale_index": 0}, read=True).result()
    size = [int(t.domain.exclusive_max[i]) for i in range(3)]  # x, y, z
    rng = np.random.default_rng(H_SEED)
    accepted, cands = [], []
    for k in range(H_MAX_CANDIDATES):
        if len(accepted) >= H_ACCEPT:
            break
        org = []
        for ax in range(3):
            lo, hi = size[ax] // 4, 3 * size[ax] // 4 - H_BOX[ax]
            org.append(int(rng.integers(lo, hi + 1)) // 64 * 64)
        rec = {"k": k, "origin_xyz": org, "box_xyz": list(H_BOX)}
        overlap = any(all(org[a] < b[a] + H_BOX[a] and b[a] < org[a] + H_BOX[a] for a in range(3)) for b in accepted)
        if overlap:
            rec.update(decision="rejected", reason="overlaps an accepted box")
            cands.append(rec)
            continue
        x0, y0, z0 = org
        a = t[x0:x0 + H_BOX[0], y0:y0 + H_BOX[1], z0:z0 + H_BOX[2], 0].read().result()  # (X, Y, Z)
        zyx = np.ascontiguousarray(np.transpose(a, (2, 1, 0)))
        bg = float((zyx == 0).mean())
        rec["background_fraction"] = bg
        if bg > H_MAX_BACKGROUND:
            rec.update(decision="rejected", reason=f"background fraction {bg:.4f} > {H_MAX_BACKGROUND}")
            cands.append(rec)
            print(f"candidate {k} {org}: rejected (background {bg:.3f})", flush=True)
            continue
        name = f"hemibrain_v1.2_x{x0}_y{y0}_z{z0}_{H_BOX[0]}x{H_BOX[1]}x{H_BOX[2]}.npy"
        dest = out / name
        np.save(dest, zyx)
        _, sha, n = hashes(dest)
        rec.update(decision="accepted", file=dest.relative_to(ROOT).as_posix(), bytes=n, sha256=sha,
                   shape_zyx=list(zyx.shape), dtype=str(zyx.dtype), unique_ids=int(np.unique(zyx).size),
                   voxel_sha256=hashlib.sha256(zyx.tobytes()).hexdigest())
        accepted.append(org)
        cands.append(rec)
        print(f"candidate {k} {org}: accepted (background {bg:.3f}, {rec['unique_ids']} ids)", flush=True)
    status = "COMPLETE" if len(accepted) == H_ACCEPT else ("PARTIAL" if accepted else "BLOCKED")
    (out / "candidates.json").write_text(json.dumps(cands, indent=2), encoding="utf-8")
    log = {"source": "Janelia FlyEM hemibrain v1.2 segmentation", "url": H_URL, "scale": "8.0x8.0x8.0 (scale_index 0)",
           "info_sha256": hashlib.sha256(info).hexdigest(), "volume_size_xyz": size, "paper_doi": "10.7554/eLife.57443",
           "licence": "unverified primary statement; secondary sources: CC-BY 4.0 (Virtual Fly Brain, hemibrain v1.0.1) "
                      "or ODC-BY (third-party neuroglancer fork)",
           "rule": {"box_xyz": list(H_BOX), "seed": H_SEED, "origin": "uniform in [size/4, 3*size/4 - box], floored "
                    "to 64", "max_background_fraction": H_MAX_BACKGROUND, "accept": H_ACCEPT,
                    "max_candidates": H_MAX_CANDIDATES, "plan": "docs/q1/EXTERNAL_DATA_PLAN.md"},
           "status": status, "accepted": len(accepted), "candidates_examined": len(cands),
           "authorized_by_user": "2026-11-07 (Q1 task v3)", "fetched_at": now(), "tools": versions(),
           "redistribution": "never (local only)"}
    (out / "download_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"hemibrain: {status} ({len(accepted)} accepted of {len(cands)} candidates)")
    return 0 if accepted else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--j0126", action="store_true")
    ap.add_argument("--hemibrain", action="store_true")
    a = ap.parse_args(argv)
    if not (a.j0126 or a.hemibrain):
        ap.error("choose --j0126 and/or --hemibrain")
    rc = 0
    if a.j0126:
        rc |= j0126(ROOT / "data" / "downloads" / "j0126")
    if a.hemibrain:
        rc |= hemibrain(ROOT / "data" / "downloads" / "hemibrain")
    return rc


if __name__ == "__main__":
    sys.exit(main())
