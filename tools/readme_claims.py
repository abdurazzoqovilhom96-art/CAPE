"""Recompute every headline number of README.md from the raw rows of the final run (`maqola uchun/raw_results/`).

    python tools/readme_claims.py            # prints the numbers as Markdown
    python tools/readme_claims.py --streams  # also needs the stored bitstreams (results/<run>/03_bitstreams)

Ratios: per volume the median over repeats, then the geometric mean over volumes (as in table T03). Memory is the
encode-inclusive process peak (extra_json.peak_after_encode) of the fresh-process memory rows (panel MEM).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "maqola uchun" / "raw_results"
NEW, CERT, FLAT = "cape_q1_fast_m0", "cape_q1_certified_m0", "crackle_flat_m0"
UPSTREAM = {"crackle_vendor_pins_opt_m0": "upstream pins_opt (vendor build, unmodified)",
            "crackle_pins_opt_m0": "upstream pins_opt (PyPI crackle-codec 0.53.0)",
            "crackle_pins_opt_corrected_m0": "upstream pins_opt, F2 count width fixed",
            "crackle_pins_fast_m0": "upstream pins_fast (PyPI)", FLAT: "Crackle flat (no pins)",
            "q1_fast_weighted_greedy_m0": "weighted greedy on the CAPE infrastructure"}


def gmean(x):
    x = [v for v in x if v and v > 0]
    return math.exp(sum(math.log(v) for v in x) / len(x)) if x else float("nan")


def load(ds):
    d = pd.read_csv(RAW / f"{ds}_results.csv", low_memory=False)
    d = d[(d.status == "OK") & (d.wrapper.fillna("none") == "none") & (d.is_synthetic != True)]  # noqa: E712
    tim = d[d.panel != "MEM"]
    mem = d[d.panel == "MEM"].copy()
    mem["peak_enc"] = [json.loads(x).get("peak_after_encode") if isinstance(x, str) else None for x in mem.extra_json]
    return tim, mem


def per_volume(df, col, a, b):
    m = df[df.method_id.isin([a, b])].groupby(["sample_id", "method_id"])[col].median().unstack().dropna()
    return m[a] / m[b] if a in m and b in m else pd.Series(dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--streams", action="store_true")
    a = ap.parse_args()
    print("| data | CAPE vs | volumes | smaller file | faster | lower peak | size change (pooled) | speed-up (geo) "
          "| peak ratio (geo) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for ds in ["j0126", "snemi", "hemibrain"]:
        tim, mem = load(ds)
        for b, label in UPSTREAM.items():
            if b not in set(tim.method_id):
                continue
            rs, rt, rm = (per_volume(tim, "total_bytes", NEW, b), per_volume(tim, "encode_ns", NEW, b),
                          per_volume(mem, "peak_enc", NEW, b))
            sz = tim[tim.method_id.isin([NEW, b])].groupby(["sample_id", "method_id"]).total_bytes.median().unstack()
            pooled = 100 * (sz[NEW].sum() / sz[b].sum() - 1)
            print(f"| {ds} | {label} | {len(rs)} | {(rs < 1).sum()}/{len(rs)} | {(rt < 1).sum()}/{len(rt)} | "
                  f"{(rm < 1).sum()}/{len(rm)} | {pooled:+.3f}% | {1 / gmean(rt):.2f}x | {gmean(rm):.3f} |")
    print()
    print("| data | time beyond flat: pins_opt | pins_fast | CAPE | CAPE with bound / CAPE time | label section share "
          "| crack-code share | bound gap, % of label section (median / max) | % of stream (median / max) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for ds in ["j0126", "snemi", "hemibrain"]:
        tim, _ = load(ds)

        def beyond(m):
            r = per_volume(tim, "encode_ns", m, FLAT)
            return f"{100 * (1 - 1 / gmean(r)):.0f}%" if len(r) else "not run"

        rc = per_volume(tim, "encode_ns", CERT, NEW)
        c = tim[tim.method_id == CERT].drop_duplicates("sample_id")
        gap = c.ub_bytes - c.lb_bytes
        pl, pf = 100 * gap / c.label_bytes, 100 * gap / c.ub_bytes
        x = tim[tim.method_id == NEW].groupby("sample_id")[["label_bytes", "total_bytes"]].median()
        lab = st.median(x.label_bytes / x.total_bytes)
        crack = "n/a"
        if a.streams:
            import crackle

            shares = []
            for _, r in tim[tim.method_id == NEW].drop_duplicates("sample_id").iterrows():
                for p in (ROOT / "results").glob(f"*/{r.bitstream_path}"):
                    cl = crackle.component_lengths(p.read_bytes())
                    shares.append(cl["crack_codes"] / sum(cl.values()))
                    break
            crack = f"{100 * st.median(shares):.1f}%" if shares else "streams missing"
        print(f"| {ds} | {beyond('crackle_vendor_pins_opt_m0')} | {beyond('crackle_pins_fast_m0')} | {beyond(NEW)} | "
              f"{gmean(rc):.3f} | {100 * lab:.1f}% | {crack} | {pl.median():.2f}% / {pl.max():.2f}% | "
              f"{pf.median():.4f}% / {pf.max():.4f}% |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
