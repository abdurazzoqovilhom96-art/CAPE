"""CAPE v3 stage AUDIT (plan CAPE v3, sections 1, 3.1, 15): recompute earlier claims from raw run files, audit the
model / factor names / certificates, inventory sources and data, and check SNEMI3D independence.

    python scripts/audit_v3.py            # -> analysis/v3_audit/

Every number written here is recomputed from results/<run>/05_raw_metrics/run.sqlite (status OK rows only);
nothing is copied from reports. A claim that cannot be recomputed is marked NOT_RECOMPUTABLE with the reason.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "analysis" / "v3_audit"

RUNS = {
    "v1_test": "20261105T122347Z_all_d1a76eb7",
    "v1_width": "20261105T145305Z_development_c1d12b3e",
    "v2_pilot": "20261106T041741Z_pilot_ca467036",
    "v2_test": "20261106T044558Z_all_83c337ae",
    "v2_width": "20261106T062540Z_development_0227806a",
    "v21_scaling": "20261106T091815Z_development_73f40dd8",
    "v21_scaling_stock": "20261106T100701Z_development_9be56574",
    "v21_equal_infra_test": "20261106T110439Z_development_8fdf0a60",
    "v21_equal_infra_scaling_partial": "20261106T111350Z_development_e91c32fe",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rows(run: str, where: str = "status='OK'") -> list[dict]:
    p = ROOT / "results" / run / "05_raw_metrics" / "run.sqlite"
    if not p.exists():
        return []
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = [dict(r) for r in con.execute(f"select * from measurements where {where}")]
    con.close()
    return out


def table(run: str, wrapper: str = "none") -> dict:
    """(sample, method) -> {bytes, enc (median ns), dec, n, peak (median MEM row), extra}"""
    acc = defaultdict(lambda: {"bytes": set(), "enc": [], "dec": [], "peak": [], "extra": None})
    for r in rows(run):
        key = (r["sample_id"], r["method_id"])
        if r["panel"] == "MEM":
            if r["peak_rss_bytes"]:
                acc[key]["peak"].append(r["peak_rss_bytes"])
            continue
        if r["wrapper"] != wrapper:
            continue
        a = acc[key]
        a["bytes"].add(r["total_bytes"])
        a["enc"].append(r["encode_ns"])
        a["dec"].append(r["decode_ns"])
        if a["extra"] is None and r["extra_json"]:
            a["extra"] = json.loads(r["extra_json"])
    out = {}
    for k, a in acc.items():
        if not a["enc"] and not a["peak"]:
            continue
        out[k] = {"bytes": (min(a["bytes"]) if len(a["bytes"]) == 1 else None) if a["bytes"] else None,
                  "bytes_vary": len(a["bytes"]) > 1, "enc": st.median(a["enc"]) if a["enc"] else None,
                  "dec": st.median(a["dec"]) if a["dec"] else None, "n": len(a["enc"]),
                  "peak": st.median(a["peak"]) if a["peak"] else None, "extra": a["extra"] or {}}
    return out


def paired(t: dict, new: str, base: str, samples=None) -> dict:
    ks = sorted({s for s, m in t if m == new} & {s for s, m in t if m == base})
    if samples is not None:
        ks = [s for s in ks if s in samples]
    bn = [t[(s, new)]["bytes"] for s in ks]
    bb = [t[(s, base)]["bytes"] for s in ks]
    en = [t[(s, new)]["enc"] for s in ks]
    eb = [t[(s, base)]["enc"] for s in ks]
    out = {"n": len(ks), "samples": ks}
    if ks and None not in bn and None not in bb:
        out["bytes_new"] = sum(bn)
        out["bytes_base"] = sum(bb)
        out["saving_pct"] = 100 * (1 - sum(bn) / sum(bb))
        out["smaller"] = sum(a < b for a, b in zip(bn, bb))
        out["equal"] = sum(a == b for a, b in zip(bn, bb))
        out["larger"] = sum(a > b for a, b in zip(bn, bb))
    if ks and None not in en and None not in eb:
        out["geo_speedup"] = math.exp(st.mean(math.log(b / a) for a, b in zip(en, eb)))
        out["sum_time_ratio_base_over_new"] = sum(eb) / sum(en)
        out["mean_time_ratio_base_over_new"] = st.mean(eb) / st.mean(en)
        out["median_delta_ms"] = st.median((a - b) / 1e6 for a, b in zip(en, eb))
    return out


def claim(cid, text, source, value, target, tol, unit, detail="") -> dict:
    if value is None:
        status = "NOT_RECOMPUTABLE"
    else:
        status = "MATCH" if abs(value - target) <= tol else "DIFFERS"
    return {"claim_id": cid, "claim": text, "source": source, "recomputed": None if value is None else round(value, 6),
            "stated": target, "tolerance": tol, "unit": unit, "status": status, "detail": detail}


# ----------------------------------------------------------------------------- 1. earlier claims
def recheck_claims() -> tuple[list[dict], dict]:
    out, extra = [], {}
    t = table(RUNS["v2_test"])
    p = paired(t, "cape_fast_m0", "crackle_pins_opt_corrected_m0")
    out.append(claim("C1", "CREMI v2 test: CAPE-FAST smaller than corrected stock", "V2_YAKUNIY_HISOBOT_UZ.md",
                     p.get("saving_pct"), 0.1071, 0.0005, "% bytes", f"n={p['n']} smaller/equal/larger="
                     f"{p.get('smaller')}/{p.get('equal')}/{p.get('larger')}"))
    out.append(claim("C2", "CREMI v2 test: CAPE-FAST encode speed-up vs corrected stock ('geometric 5.63x')",
                     "V2_YAKUNIY_HISOBOT_UZ.md (table: 'stock'dan tez x')", p.get("geo_speedup"), 5.63, 0.05, "x",
                     f"geometric over samples = {p.get('geo_speedup', 0):.3f}; ratio of summed medians = "
                     f"{p.get('sum_time_ratio_base_over_new', 0):.3f}; ratio of mean medians = "
                     f"{p.get('mean_time_ratio_base_over_new', 0):.3f}. The stated 5.63 matches the "
                     + ("geometric mean over samples" if abs(p.get('geo_speedup', 0) - 5.63) <= 0.05 else
                        "ratio of summed medians" if abs(p.get('sum_time_ratio_base_over_new', 0) - 5.63) <= 0.05 else
                        "none of the three definitions")))
    extra["v2_test_fast_vs_corrected"] = p
    tz = table(RUNS["v2_test"], wrapper="none")
    pr = paired(tz, "safe_refine_e24_m0_zstd9", "safe_archive_m0_zstd9")
    out.append(claim("C3", "Refine on the v2 test: bytes saved vs SAFE", "V2_YAKUNIY_HISOBOT_UZ.md",
                     None if "bytes_base" not in pr else pr["bytes_base"] - pr["bytes_new"], 42, 0, "B",
                     f"saving {pr.get('saving_pct', 0):.4f}%"))
    out.append(claim("C4", "Refine on the v2 test: encode time multiplier", "V2_YAKUNIY_HISOBOT_UZ.md",
                     None if "geo_speedup" not in pr else 1 / pr["geo_speedup"], 2.73, 0.03, "x",
                     f"1/geo = {1 / pr['geo_speedup']:.3f}; sum ratio = {1 / pr['sum_time_ratio_base_over_new']:.3f}"
                     if "geo_speedup" in pr else ""))
    extra["v2_test_refine"] = pr
    # scaling: v2.1 stock run (crops <= 2^25 voxels), both methods in the same run
    ts = table(RUNS["v21_scaling_stock"])
    ps = paired(ts, "cape_fast_m0", "crackle_pins_opt_corrected_m0")
    out.append(claim("C5", "Scaling (crops <= 2^25 voxels): CAPE-FAST smaller than corrected stock",
                     "user summary / V21_HISOBOT_UZ.md", ps.get("saving_pct"), 0.64, 0.05, "% bytes",
                     f"n={ps['n']} (seen development crops, nested)"))
    out.append(claim("C6", "Scaling: CAPE-FAST encode speed-up vs corrected stock", "user summary",
                     ps.get("geo_speedup"), 5.1, 0.2, "x", f"geometric; summed-median ratio "
                     f"{ps.get('sum_time_ratio_base_over_new', 0):.2f}"))
    extra["v21_scaling_fast_vs_corrected"] = ps
    # depth regimes on Z=512 crops (scaling run): cape_m0 (full search) vs cape_fast_m0
    tsc = table(RUNS["v21_scaling"])
    z512 = sorted({s for s, _ in tsc if s.endswith("x512")})
    reg = []
    for s in z512:
        if (s, "cape_m0") in tsc and (s, "cape_fast_m0") in tsc:
            a, b = tsc[(s, "cape_m0")]["bytes"], tsc[(s, "cape_fast_m0")]["bytes"]
            reg.append({"sample": s, "regimes_bytes": a, "fast_bytes": b, "saving_pct": 100 * (1 - a / b),
                        "regimes_time_ratio": tsc[(s, "cape_m0")]["enc"] / tsc[(s, "cape_fast_m0")]["enc"]})
    tw = table(RUNS["v2_width"])
    for s in sorted({s for s, _ in tw if s.endswith("x512")}):
        if (s, "cape_m0") in tw and (s, "cape_fast_m0") in tw:
            a, b = tw[(s, "cape_m0")]["bytes"], tw[(s, "cape_fast_m0")]["bytes"]
            reg.append({"sample": s, "regimes_bytes": a, "fast_bytes": b, "saving_pct": 100 * (1 - a / b),
                        "regimes_time_ratio": tw[(s, "cape_m0")]["enc"] / tw[(s, "cape_fast_m0")]["enc"],
                        "run": "v2_width"})
    sav = [r["saving_pct"] for r in reg]
    out.append(claim("C7", "Depth regimes on some Z=512 crops: full search ~0.64-0.69% smaller than FAST",
                     "user summary", max(sav) if sav else None, 0.69, 0.02, "% bytes (max over Z=512 crops)",
                     "; ".join(f"{r['sample']}: {r['saving_pct']:.3f}% (time x{r['regimes_time_ratio']:.2f})"
                               for r in reg)))
    extra["depth_regimes_z512"] = reg
    return out, extra


# ----------------------------------------------------------------------------- 2. certificates / losslessness
def certificate_and_lossless_audit() -> dict:
    cert = []
    lossless = defaultdict(lambda: defaultdict(int))
    for tag, run in RUNS.items():
        for r in rows(run, "1=1"):
            if r["status"] == "FAILED_LOSSLESS":
                lossless[tag][r["method_id"]] += 1
            if r["certificate_valid"] is not None and r["panel"] != "MEM":
                cert.append({"run": tag, "run_id": run, "sample_id": r["sample_id"], "method_id": r["method_id"],
                             "valid": int(r["certificate_valid"]), "lb_bytes": r["lb_bytes"], "ub_bytes": r["ub_bytes"]})
    invalid = [c for c in cert if not c["valid"]]
    by = defaultdict(int)
    for c in invalid:
        by[(c["run"], c["method_id"], c["sample_id"])] += 1
    return {"certificate_rows": len(cert), "certificate_invalid_rows": len(invalid),
            "invalid_groups": [{"run": k[0], "method": k[1], "sample": k[2], "rows": v} for k, v in sorted(by.items())],
            "failed_lossless_by_run_method": {k: dict(v) for k, v in lossless.items()}, "_rows": cert}


def compaction_audit() -> list[dict]:
    """How often the written depth width compacts below the regime width in FAST rows (the root cause of the
    v2.1 fixed-depth Regime-certificate defect)."""
    out = []
    for tag in ("v2_width", "v21_scaling"):
        t = table(RUNS[tag])
        for (s, m), v in sorted(t.items()):
            if m != "cape_fast_m0":
                continue
            e = v["extra"]
            if "regime_w_D" in e and "w_D" in e:
                out.append({"run": tag, "sample_id": s, "regime_w_D": e["regime_w_D"], "written_w_D": e["w_D"],
                            "compacted": int(e["w_D"] < e["regime_w_D"])})
    return out


# ----------------------------------------------------------------------------- 3. data / SNEMI3D
def snemi_status() -> dict:
    used = []
    for m in (ROOT / "results").glob("*/run_manifest.json"):
        d = json.loads(m.read_text(encoding="utf-8"))
        if "snemi" in (str(d.get("manifest_arg")) + str(d.get("config_path"))).lower():
            used.append(m.parent.name)
    return {"runs_using_snemi3d": used, "compressed_before_v3": bool(used)}


def boundary(sl: np.ndarray) -> np.ndarray:
    b = np.zeros(sl.shape, np.float32)
    b[:, :-1] += sl[:, 1:] != sl[:, :-1]
    b[:-1, :] += sl[1:, :] != sl[:-1, :]
    return (b > 0).astype(np.float32)


def snemi_crackle_overlap(max_slices: int = 8) -> dict:
    """Sampled check: does any sampled 512x512 Crackle slice's label-boundary pattern appear (translation only, same
    voxel grid) inside any SNEMI3D slice? Score = fraction of the Crackle slice's boundary pixels matched at the best
    offset (1.0 = identical cut-out; unrelated images give roughly the SNEMI boundary density)."""
    import tifffile

    snemi_p = ROOT / "data" / "downloads" / "snemi3d" / "labels" / "train_labels_0.tif"
    srcs = {"connectomics": ROOT / "data/real/scaling_v21/scale_crackle_connectomics_512x512x512.npy",
            "ws": ROOT / "data/real/scaling_v21/scale_crackle_ws_512x512x512.npy"}
    if not snemi_p.exists() or not all(p.exists() for p in srcs.values()):
        return {"status": "NOT_TESTED", "reason": "SNEMI3D labels or Crackle 512^3 volumes missing"}
    snemi = tifffile.imread(snemi_p)  # (100, 1024, 1024)
    P = 1536
    crk = []
    for name, p in srcs.items():
        v = np.load(p, mmap_mode="r")
        for z in np.linspace(0, v.shape[0] - 1, max_slices).astype(int):
            b = boundary(np.asarray(v[z]))
            pad = np.zeros((P, P), np.float32)
            pad[:b.shape[0], :b.shape[1]] = b[::-1, ::-1]  # flipped: convolution == correlation
            crk.append((name, int(z), float(b.sum()), np.fft.rfft2(pad)))
    best = {"score": 0.0}
    density = []
    for zs in range(snemi.shape[0]):
        sb = boundary(snemi[zs])
        density.append(float(sb.mean()))
        pad = np.zeros((P, P), np.float32)
        pad[:sb.shape[0], :sb.shape[1]] = sb
        F = np.fft.rfft2(pad)
        for name, z, tot, G in crk:
            corr = np.fft.irfft2(F * G, s=(P, P))
            # valid placements of a 512x512 window inside 1024x1024: correlation index (511..1023)
            win = corr[511:1024, 511:1024]
            sc = float(win.max() / tot) if tot else 0.0
            if sc > best["score"]:
                best = {"score": sc, "snemi_z": zs, "crackle": name, "crackle_z": z}
    return {"status": "PARTIAL_CHECK", "best": best, "snemi_boundary_density_mean": float(np.mean(density)),
            "slices_checked": {"snemi": int(snemi.shape[0]), "crackle_per_volume": max_slices},
            "verdict": ("no translated cut-out found on the shared voxel grid" if best["score"] < 0.5
                        else "POSSIBLE OVERLAP - investigate"),
            "limits": "translation only, same voxel grid, sampled Crackle slices; rescaled / rotated / re-segmented "
                      "versions of the same tissue are NOT excluded (Crackle sample provenance is undocumented)"}


def data_audit() -> list[dict]:
    from cape.dataset_manifest import load_manifest

    out = []
    for name in ("v3_dev_core.jsonl", "scaling_v21.jsonl", "v3_dev_quality.jsonl", "confirm_snemi3d.jsonl"):
        p = ROOT / "data" / "manifests" / name
        if not p.exists():
            continue
        for r in load_manifest(p):
            out.append({"manifest": name, "sample_id": r["sample_id"], "family_id": r["family_id"],
                        "source_id": r["source_id"], "macroblock_id": r["macroblock_id"], "split": r["split"],
                        "dtype": r["dtype"], "shape_zyx": r["shape"], "voxel_sha256": r["voxel_sha256"],
                        "original_path": r.get("original_path"), "license": r.get("license"),
                        "file_present": (ROOT / r["path"]).exists()})
    return out


# ----------------------------------------------------------------------------- 4. inventory / factors / model
def inventory() -> dict:
    from cape import provenance

    lock = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
    frozen = json.loads((ROOT / "snapshots" / "v21" / "FROZEN_V21.json").read_text(encoding="utf-8"))
    cpp = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "cpp").rglob("*.[ch]pp"))
    runs = []
    for m in sorted((ROOT / "results").glob("*/run_manifest.json")):
        d = json.loads(m.read_text(encoding="utf-8"))
        runs.append({"run_id": d["run_id"], "status": d.get("status"), "stage": d.get("stage"),
                     "config": Path(str(d.get("config_path", ""))).name, "source_hash": str(d.get("source_hash"))[:12]})
    return {"source_tree_hash_now": provenance.source_tree_hash(), "frozen_v21": frozen, "sources_lock": lock,
            "cpp_files": cpp, "vendor_dir_present": (ROOT / "vendor" / "crackle" / "src" / "crackle.hpp").exists(),
            "corrected_stock_patch": "cpp/src/upstream_bridge.cpp::condensed_pins_corrected (count-width fix only)",
            "oracle": "cape/oracle.py (CP-SAT)", "verifier": "cape/certificate_verify.py (independent)",
            "runs": runs}


def factor_audit() -> dict:
    src = (ROOT / "cpp" / "include" / "cape" / "types.hpp").read_text(encoding="utf-8")
    bits = dict(re.findall(r"kImpl(\w+) = (\d+)", src))
    return {
        "impl_bits": bits,
        "tests_32_combinations": "tests/test_impl_mask.py iterates impl_mask 0..31 = the five bits L(1) R(2) H(4) T(8) "
                                 "S(16); depth policy D is not an impl bit",
        "attribution_factorial": "scripts/speedup_attribution.py: 2^5 over L,H,T,S,D where L means layout+one-pass "
                                 "runs together (R folded into L; a separate 'FAST without R' variant is reported); D = "
                                 "depth regimes off (may change bytes)",
        "v3_bits": "A=32 C=64 G=128 F=256 B=512 (types.hpp); 1023 = every implementation bit",
    }


MODEL_NOTES = [
    ("byte model", "B_label = w_L + 8 + (K-1) w_L + Z w_G + 1 + 2 (K-1) w_N + P (w_I + w_D) + Q w_C; predict_label_bytes "
                   "equals the serializer length on every written stream (checked inside the encoder, error otherwise)"),
    ("selection-dependent global terms", "w_N (count width) = width of the largest per-label record count; w_D = width "
                                         "of the deepest chosen pin (compaction); background = argmax of the per-label "
                                         "cost. None of them is hidden in a constant: the LB uses w_N = 1 (valid for "
                                         "every count width) and min over backgrounds (formula 8)"),
    ("w_D compaction defect (v2.1)", "with a fixed depth width the stream may compact w_D below the regime width; the "
                                     "regime LB (pins priced w_I + w_D_regime) then does not bound the written stream. "
                                     "v2.1 FAST with certificate=regime reported lb_bytes > ub_bytes on such inputs "
                                     "(rows marked certificate_valid = False by the worker, never hidden). Fixed in v3 by "
                                     "adding the scaled full-width dual bound for every narrower width"),
    ("decomposition", "components are solved independently only inside one fixed regime and one background; the "
                      "background is chosen after pass 1 and written labels' U can only decrease"),
    ("raw vs zstd", "the dual bound and every exactness statement are about the raw labels section; zstd sizes are "
                    "measured, never bounded"),
]


PROOF_TEST_MATRIX = [
    {"invariant": "every v3 implementation bit combination writes the frozen v2.1 bytes", "spec": "11.1",
     "evidence": "test", "where": "tests/test_v3_invariants.py::test_every_v3_bit_combination_matches_frozen_v21 "
     "(36 cases x 2 depth policies x 32 v3 combos x 2 low masks; frozen digests from a separate process)"},
    {"invariant": "problem-describing diagnostics unchanged (candidates, classes, components)", "spec": "11.1",
     "evidence": "test", "where": "tests/test_v3_invariants.py::test_v3_fast_preset_matches_frozen_v21_same_as_stock"},
    {"invariant": "M1a neighbour-column rule never drops an equal-coverage class representative", "spec": "5.1",
     "evidence": "proof + test", "where": "docs/V3_MATHEMATICS.md M1a; byte identity tests; adjacency counts test"},
    {"invariant": "hash collisions never merge different coverage (with v3 bits)", "spec": "11.6",
     "evidence": "test", "where": "tests/test_v3_invariants.py::test_forced_hash_collisions_keep_bytes_with_v3_bits; "
     "tests/test_reduction_fast.py"},
    {"invariant": "exact roundtrip for every dtype / shape / edge case (0, uint64 max, Z=1, many labels)",
     "spec": "11.2-11.3", "evidence": "test", "where": "tests/test_v3_invariants.py::test_v3_roundtrip_edge_cases; "
     "tests/test_input_axes_dtype.py; worker verifies every measured row with the original decoder"},
    {"invariant": "F2 count-width reproducer; corrected stock = minimal diff", "spec": "11.4", "evidence": "test",
     "where": "tests/test_stock_corrected.py; docs/format_audit.md F2"},
    {"invariant": "32-bit candidate index overflow is reported, never silent", "spec": "11.7", "evidence": "test",
     "where": "tests/test_v3_invariants.py::test_candidate_index_guard_without_allocating"},
    {"invariant": "brute force = DP = CP-SAT on small cover problems", "spec": "11.8", "evidence": "test",
     "where": "tests/test_dp_oracle.py; cape/oracle.py (dev TRACKS panel)"},
    {"invariant": "reductions keep the optimum", "spec": "11.9", "evidence": "proof + test",
     "where": "docs/mathematics.md 4; tests/test_reduction_optimum.py"},
    {"invariant": "dual feasibility; LB <= exact optimum; scaled regime bound <= regime section", "spec": "11.10",
     "evidence": "proof + test", "where": "tests/test_dual_certificate.py; tests/test_v3_invariants.py::"
     "test_regime_gate_is_output_preserving_and_its_bound_is_valid, ::test_scaled_dual_bound_never_exceeds_*"},
    {"invariant": "reduced-cost fixing keeps the strict-improvement optimum ('Improved' = optimum, 'Proven' holds)",
     "spec": "11.11", "evidence": "proof + test", "where": "docs/V3_MATHEMATICS.md M3b; tests/test_v3_invariants.py::"
     "test_abstract_models_eager_rc_repair_against_brute_force (360 random models)"},
    {"invariant": "M4 repair: outside coverage kept, never above the incumbent, never below the optimum, lossless",
     "spec": "11.12", "evidence": "test", "where": "tests/test_v3_invariants.py (abstract models + real crops)"},
    {"invariant": "QUALITY never larger than FAST; raw and zstd costs never mixed", "spec": "11.13",
     "evidence": "test + design", "where": "tests/test_v3_invariants.py::test_quality_never_exceeds_fast_and_is_lossless; "
     "zstd only in wrappers / SAFE (measured, not bounded)"},
    {"invariant": "certificate LB <= written stream (incl. w_D compaction)", "spec": "6 / 11.10", "evidence": "test",
     "where": "tests/test_v3_invariants.py::test_quality_never_exceeds_fast_and_is_lossless (lb <= ub asserted); worker "
     "certificate_valid"},
    {"invariant": "SAFE candidates and headers counted; decoder needs only the stored file", "spec": "11.14",
     "evidence": "test", "where": "tests/test_safe_archive.py"},
    {"invariant": "resume keys, timeout / OOM logging, partial reports", "spec": "11.15", "evidence": "test",
     "where": "tests/test_runner_resume.py; tests/test_failure_finalization.py; acceptance T1-T12"},
    {"invariant": "M2 eager greedy = lazy greedy selection", "spec": "6", "evidence": "proof + test",
     "where": "docs/V3_MATHEMATICS.md M2; tests/test_v3_invariants.py::test_abstract_models_*; byte identity tests"},
    {"invariant": "M5b batched CC labeling = upstream labeling (ids, per-slice counts, crcs)", "spec": "9",
     "evidence": "test", "where": "byte identity tests (crcs and ids are part of the stream)"},
]


def write_csv(path: Path, rows_: list[dict]) -> None:
    if not rows_:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows_[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows_)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    claims, claim_extra = recheck_claims()
    cert = certificate_and_lossless_audit()
    comp = compaction_audit()
    snemi = snemi_status()
    overlap = snemi_crackle_overlap()
    data = data_audit()
    inv = inventory()
    fac = factor_audit()
    write_csv(OUT / "claims_recheck.csv", claims)
    write_csv(OUT / "certificate_rows.csv", cert.pop("_rows"))
    write_csv(OUT / "wD_compaction.csv", comp)
    write_csv(OUT / "data_audit.csv", data)
    write_csv(OUT / "proof_test_matrix.csv", PROOF_TEST_MATRIX)
    audit = {"generated_at": now(), "claims": claims, "claim_details": claim_extra, "certificates": cert,
             "wD_compaction": {"rows": len(comp), "compacted": sum(c["compacted"] for c in comp)},
             "snemi3d": snemi, "snemi_crackle_overlap": overlap, "inventory": inv, "factors": fac,
             "model_notes": dict(MODEL_NOTES),
             "interrupted_v21_run": {"run_id": RUNS["v21_equal_infra_scaling_partial"],
                                     "state": "SUPERSEDED: died at 307/400 tasks, source hash changed after INIT; "
                                              "kept on disk, not used in any v3 table"}}
    (OUT / "audit_v3.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    L = ["# CAPE v3 AUDIT (avtomatik, `scripts/audit_v3.py`)", "",
         f"Yaratilgan: {audit['generated_at']}. Har bir raqam `results/<run>/05_raw_metrics/run.sqlite` dagi OK "
         "qatorlardan qayta hisoblangan; hisobotlardan ko'chirilmagan.", "",
         "## 1. Oldingi da'volar qayta hisoblandi", "",
         "| ID | Da'vo | Manba | Qayta hisoblangan | Aytilgan | Birlik | Holat | Izoh |", "|---|---|---|---|---|---|---|---|"]
    for c in claims:
        L.append(f"| {c['claim_id']} | {c['claim']} | {c['source']} | {c['recomputed']} | {c['stated']} | {c['unit']} | "
                 f"**{c['status']}** | {c['detail']} |")
    L += ["", "## 2. Sertifikat va lossless", "",
          f"- Sertifikat qatorlari: {cert['certificate_rows']}; yaroqsiz (`lb_bytes > ub_bytes` yoki dual feasible emas): "
          f"**{cert['certificate_invalid_rows']}**."]
    for g in cert["invalid_groups"]:
        L.append(f"  - {g['run']} / {g['method']} / {g['sample']}: {g['rows']} qator")
    fl = cert['failed_lossless_by_run_method']
    L.append(f"- FAILED_LOSSLESS qatorlari audit qilingan run'larda (run -> metod -> soni): {json.dumps(fl) if fl else 'yo`q'}. "
             "(Upstream F2 xatosi faqat smoke run'dagi adversarial namunada ko'rinadi; u ro'yxatdagi run'larga kirmaydi.)")
    L.append(f"- FAST qatorlarida w_D siqilishi: {audit['wD_compaction']['compacted']} / {audit['wD_compaction']['rows']} "
             "namunada yozilgan w_D regime w_D dan kichik (sertifikat nuqsonining sababi, `wD_compaction.csv`).")
    L += ["", "## 3. Model auditi", ""] + [f"- **{k}:** {v}" for k, v in MODEL_NOTES]
    L += ["", "## 4. Faktor nomlari", "", f"- Bitlar (`types.hpp`): `{json.dumps(fac['impl_bits'])}`",
          f"- {fac['tests_32_combinations']}", f"- {fac['attribution_factorial']}", f"- v3: {fac['v3_bits']}"]
    L += ["", "## 5. SNEMI3D holati va mustaqillik", "",
          f"- SNEMI3D ishlatilgan run'lar: {snemi['runs_using_snemi3d'] or 'yo`q'} -> v3 uchun "
          f"{'holdout EMAS' if snemi['compressed_before_v3'] else 'hali siqilmagan: tasdiqlovchi holdout bo`la oladi'}.",
          f"- SNEMI3D <-> Crackle namunalari overlap tekshiruvi: **{overlap.get('status')}**; "
          f"{overlap.get('verdict', overlap.get('reason'))}. Eng yaxshi moslik: {json.dumps(overlap.get('best'))}; "
          f"SNEMI chegara zichligi ~{overlap.get('snemi_boundary_density_mean', float('nan')):.3f}.",
          f"- Cheklov: {overlap.get('limits', '')}"]
    L += ["", "## 6. Inventar", "",
          f"- Joriy source hash: `{inv['source_tree_hash_now']}`; muzlatilgan v2.1 binari sha256 "
          f"`{inv['frozen_v21']['sha256']}`, v2.1 source hash `{inv['frozen_v21']['source_tree_hash_at_snapshot']}`.",
          f"- Vendor Crackle mavjud: {inv['vendor_dir_present']}; tuzatilgan stock patch: {inv['corrected_stock_patch']}.",
          f"- Oracle: {inv['oracle']}; verifier: {inv['verifier']}.",
          f"- To'xtagan v2.1 run: `{audit['interrupted_v21_run']['run_id']}` - {audit['interrupted_v21_run']['state']}.",
          "", "| run | holat | stage | config | source hash |", "|---|---|---|---|---|"]
    for r in inv["runs"]:
        L.append(f"| {r['run_id']} | {r['status']} | {r['stage']} | {r['config']} | {r['source_hash']} |")
    L += ["", "Fayllar: `audit_v3.json`, `claims_recheck.csv`, `certificate_rows.csv`, `wD_compaction.csv`, "
              "`data_audit.csv`, `proof_test_matrix.csv`."]
    (OUT / "AUDIT_V3_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps({"claims": [(c["claim_id"], c["status"], c["recomputed"]) for c in claims],
                      "certificate_invalid": cert["certificate_invalid_rows"], "overlap": overlap.get("best"),
                      "snemi_used": snemi["runs_using_snemi3d"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
