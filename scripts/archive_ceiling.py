"""Archive ceiling of label-side changes (plan v2 P1.6, exploratory).

For each real sample, Markov order and zstd level:
    share = 1 - |zstd(stream without its labels section)| / |zstd(stream)|
for the CAPE-FAST pins stream (format forced to pins) and the flat stream. This is an estimate of
how much of the STORED file the labels section is responsible for: even a perfect label-side
refinement cannot remove more than about this share (zstd is not additive, so it is an estimate,
not a theorem). Pre-registered gate (plan v2): refinement is worth pursuing beyond P1 only if the
median pins-stream share is >= 3 %.

    python scripts/archive_ceiling.py --manifest data/manifests/pilot.jsonl --out pilot_v2
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GATE_PERCENT = 3.0


def strip_labels(stream: bytes) -> bytes:
    from cape import crackle_format as cf

    lay = cf.split_stream(stream)
    return stream[: lay.labels_offset] + stream[lay.labels_offset + len(lay.labels):]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", nargs="+", required=True)
    ap.add_argument("--out", default="archive_ceiling")
    args = ap.parse_args(argv)
    import crackle
    import zstandard

    from cape import _cape_native as cn
    from cape.canonical import crackle_view
    from cape.dataset_manifest import load_manifest, resolve_path
    from cape.result_store import atomic_write_text

    rows = []
    for mp in args.manifest:
        for r in load_manifest(ROOT / mp):
            if r["is_synthetic"]:
                continue
            zyx = np.load(resolve_path(r["path"]))
            xyz = crackle_view(zyx)
            for m in (0, 5):
                pins, d = cn.encode(xyz, {"format_policy": "force_pins", "markov_model_order": m,
                                          "depth_policy": "fixed_depth_width", "certificate": "off", "parallel": 1})
                flat = crackle.compress(xyz, allow_pins=0, markov_model_order=m, parallel=1)
                for lvl in (3, 9):
                    z = zstandard.ZstdCompressor(level=lvl, threads=0, write_checksum=False, write_content_size=True)
                    rec = {"sample_id": r["sample_id"], "source_id": r["source_id"], "markov": m, "zstd": lvl}
                    for tag, s in (("pins", pins), ("flat", flat)):
                        full, nolab = len(z.compress(s)), len(z.compress(strip_labels(s)))
                        lab = len(s) - len(strip_labels(s))
                        rec.update({f"{tag}_raw_bytes": len(s), f"{tag}_raw_label_share_pct": 100 * lab / len(s),
                                    f"{tag}_wrapped_bytes": full, f"{tag}_wrapped_without_labels": nolab,
                                    f"{tag}_archive_label_share_pct": 100 * (1 - nolab / full)})
                    rows.append(rec)
            print(r["sample_id"], "ok")
    out = ROOT / "analysis" / args.out
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "archive_ceiling.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summ = []
    for m in (0, 5):
        for lvl in (3, 9):
            sel = [r for r in rows if r["markov"] == m and r["zstd"] == lvl]
            summ.append({"markov": m, "zstd": lvl, "n": len(sel),
                         "pins_raw_label_share_median_pct": st.median(r["pins_raw_label_share_pct"] for r in sel),
                         "pins_archive_label_share_median_pct": st.median(r["pins_archive_label_share_pct"] for r in sel),
                         "pins_archive_label_share_max_pct": max(r["pins_archive_label_share_pct"] for r in sel),
                         "flat_archive_label_share_median_pct": st.median(r["flat_archive_label_share_pct"] for r in sel)})
    med = st.median(s["pins_archive_label_share_median_pct"] for s in summ)
    gate = {"gate_percent": GATE_PERCENT, "median_pins_archive_label_share_pct": med, "passed": med >= GATE_PERCENT,
            "meaning": "label side owns less than the gate share of the stored file: refinement can only move a small "
                       "fraction of bytes" if med < GATE_PERCENT else "label side owns a meaningful share of the stored file"}
    atomic_write_text(out / "archive_ceiling_summary.json", json.dumps({"summary": summ, "gate": gate}, indent=2))
    lines = ["# Archive ceiling (exploratory)", "",
             "share = 1 - |zstd(stream without labels)| / |zstd(stream)| - taxminiy yuqori chegara, teorema emas.", "",
             "| Markov | zstd | n | pins raw label % | pins archive label % (median) | max | flat archive label % |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {s['markov']} | {s['zstd']} | {s['n']} | {s['pins_raw_label_share_median_pct']:.2f} | "
              f"{s['pins_archive_label_share_median_pct']:.2f} | {s['pins_archive_label_share_max_pct']:.2f} | "
              f"{s['flat_archive_label_share_median_pct']:.2f} |" for s in summ]
    lines += ["", f"**Gate (>= {GATE_PERCENT}%):** {'passed' if gate['passed'] else 'NOT passed'} "
                  f"(median {med:.2f}%). {gate['meaning']}.", ""]
    atomic_write_text(out / "ARCHIVE_CEILING_UZ.md", "\n".join(lines))
    print(f"gate passed={gate['passed']} median={med:.2f}% -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
