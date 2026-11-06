"""Per-row and per-(sample, method) metrics (spec section 21).

bpv = 8B/V, CR = V*itemsize/B (original dtype), G_B = 100(1 - B_new/B_base),
S_E = T_base/T_new. A method key is `method_id` or `method_id+wrapper`."""

from __future__ import annotations

import json
import statistics as _st
from collections import defaultdict

ITEMSIZE = {"uint8": 1, "uint16": 2, "uint32": 4, "uint64": 8}


def mkey(row: dict) -> str:
    w = row.get("wrapper") or "none"
    return row["method_id"] if w == "none" else f"{row['method_id']}+{w}"


def voxels(row: dict) -> int:
    shape = row["canonical_shape"]
    if isinstance(shape, str):
        shape = json.loads(shape)
    v = 1
    for s in shape:
        v *= int(s)
    return v


def bpv(total_bytes: int, nvox: int) -> float:
    return 8.0 * total_bytes / nvox


def compression_ratio(total_bytes: int, nvox: int, dtype: str) -> float:
    return nvox * ITEMSIZE[dtype] / total_bytes


def gain_percent(b_new: float, b_base: float) -> float:
    return 100.0 * (1.0 - b_new / b_base)


def speedup(t_base: float, t_new: float) -> float:
    return t_base / t_new


def aggregate_cells(rows: list[dict]) -> dict:
    """(sample_id, method key) -> aggregate over timed repeats (panels A/B). Byte sizes must be
    identical across repeats of a deterministic codec; a difference is flagged, never averaged away."""
    cells: dict = defaultdict(lambda: {"rows": []})
    for r in rows:
        if r["panel"] in ("A", "B"):
            cells[(r["sample_id"], mkey(r), r["panel"])]["rows"].append(r)
    out = {}
    for (sid, key, panel), c in cells.items():
        rs = c["rows"]
        ok = [r for r in rs if r["status"] == "OK"]
        base = rs[0]
        agg = {"sample_id": sid, "method": key, "method_id": base["method_id"], "wrapper": base.get("wrapper") or "none",
               "panel": panel, "split": base["split"], "family_id": base.get("family_id"),
               "source_id": base.get("source_id"), "macroblock_id": base.get("macroblock_id"),
               "is_synthetic": bool(base.get("is_synthetic")), "dtype": base["original_dtype"],
               "voxels": voxels(base), "n_rows": len(rs), "n_ok": len(ok),
               "statuses": sorted({r["status"] for r in rs}), "reasons": sorted({r["reason"] for r in rs if r["reason"]}),
               "measurement_ids": [r["measurement_id"] for r in rs]}
        if ok:
            sizes = {r["total_bytes"] for r in ok}
            hashes = {r["bitstream_sha256"] for r in ok}
            agg["total_bytes"] = min(sizes)
            agg["size_varies"] = len(sizes) > 1
            agg["bitstream_varies"] = len(hashes) > 1
            agg["label_bytes"] = ok[0].get("label_bytes")
            agg["metadata_bytes"] = ok[0].get("metadata_bytes")
            agg["encode_ns_median"] = _st.median(r["encode_ns"] for r in ok)
            agg["decode_ns_median"] = _st.median(r["decode_ns"] for r in ok)
            agg["encode_ns_all"] = [r["encode_ns"] for r in ok]
            agg["decode_ns_all"] = [r["decode_ns"] for r in ok]
            agg["bpv"] = bpv(agg["total_bytes"], agg["voxels"])
            agg["cr"] = compression_ratio(agg["total_bytes"], agg["voxels"], agg["dtype"])
            agg["label_format_actual"] = ok[0].get("label_format_actual")
            for f in ("ub_bytes", "lb_bytes", "exact_cc_fraction", "component_count", "max_component_cc",
                      "candidate_count_before", "candidate_count_after", "incidence_count", "certificate_valid",
                      "certificate_scope"):
                agg[f] = ok[0].get(f)
            agg["extra"] = json.loads(ok[0]["extra_json"]) if ok[0].get("extra_json") else {}
        out[(sid, key, panel)] = agg
    return out


def memory_cells(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        if r["panel"] != "MEM":
            continue
        extra = json.loads(r["extra_json"]) if r.get("extra_json") else {}
        out[(r["sample_id"], mkey(r))] = {
            "sample_id": r["sample_id"], "method": mkey(r), "status": r["status"], "reason": r["reason"],
            "peak_rss_bytes": r.get("peak_rss_bytes"), "input_bytes": r.get("input_bytes"),
            "rss_measurement_mode": r.get("rss_measurement_mode"),
            "input_normalized_peak": extra.get("input_normalized_peak"),
            "peak_attribution": extra.get("peak_attribution"), "measurement_id": r["measurement_id"]}
    return out
