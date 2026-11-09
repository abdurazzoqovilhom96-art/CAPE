"""Targeted synthetic checks for the 2026-11-09 technical revision (not biological evidence).

The checks compare the CAPE encoder with an *independent* exact optimum of the true serialized label-section size,
computed by CP-SAT without any of CAPE's reductions. The CP-SAT model includes:
  * every valid pin (all sub-intervals of same-label column runs; only candidates with identical label and coverage are
    merged, keeping the one with the narrower depth class, which can never be worse);
  * the background choice (one label is the default and needs no records);
  * the count width w_N in {1, 2} bytes (capacity 255 / 65,535 per label and record type) and its header cost;
  * the depth width w_D in {1, 2} bytes (a pin of length > h1 forces w_D = 2, which costs one byte per pin).

    OPT_ser = min_{b, S}  H(w_N(S)) + (w_I + w_D(S)) P(S) + w_C Q(S)

Checks:
  T1  CAPE (evaluated configuration) on small random volumes (Z <= 8):  L <= OPT_ser(all pins) <= U, lossless decode.
  T2  Complete-window theorem in the serialized model, with a reduced depth limit h1 and reduced count capacity so
      that windows and the count-width coupling are both active:  OPT_ser(all pins) == OPT_ser(complete windows).
  T3  Depth-width boundaries Z = 256, 257, 258, 300, 600, long and mixed runs, 1->2 byte transition:
      L <= OPT_ser(complete windows) <= U, lossless decode, written w_D consistent with the chosen pins.
  T4  Singleton dominance at the count-width boundary: the reduction keeps the payload optimum but not the serialized
      optimum (Q = 257 explicit records force w_N = 2); the lower bound stays valid; decoding stays lossless.
  T5  Count width switches exactly between 255 and 256 explicit records of one label; both streams decode losslessly.
  T6  Integer headroom of the q-scaled dual ascent (q = 2^20).

Run (from the repository root):  python <path>/scripts/test_revision_math.py     (writes evidence/logs/...)
or:                               python -m pytest <path>/scripts/test_revision_math.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

MS = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["CAPE_REPO"]) if os.environ.get("CAPE_REPO") else next(
    q for q in Path(__file__).resolve().parents if (q / "cape").is_dir() and (q / "maqola uchun").is_dir())
sys.path.insert(0, str(ROOT))

import crackle  # noqa: E402  PyPI crackle-codec 0.53.0: the unmodified decoder
from ortools.sat.python import cp_model  # noqa: E402

from cape import _cape_native as cn  # noqa: E402
from cape import crackle_format as cf  # noqa: E402
from cape import reference_model as rm  # noqa: E402
from cape import synthetic as syn  # noqa: E402
from cape.canonical import crackle_view  # noqa: E402

# Evaluated configuration (configs/q1_methods.yaml: cape_q1_certified_m0) with PINS forced so that every case has a
# label section; format_policy only decides PINS versus flat output and does not change the selection.
EVALUATED = {"markov_model_order": 0, "format_policy": "force_pins", "selector": "cape",
             "depth_policy": "fixed_depth_width", "certificate": "all_regimes", "impl_mask": 6719, "parallel": 1}
FULL_WIDTH_FIRST = dict(EVALUATED, depth_policy="full_width_first", certificate="regime")
RESULTS: list[dict] = []


# ----------------------------------------------------------------------------------------------- exact optimum
def instance(zyx: np.ndarray):
    cc, _, n = rm.cc_label(zyx)
    lab = rm.cc_label_values(zyx, cc, n)
    runs = rm.column_runs(zyx)
    Z, Y, X = zyx.shape
    w = {"w_L": cf.byte_width(int(zyx.max())), "w_I": cf.byte_width(zyx.size), "w_G": cf.byte_width(X * Y),
         "w_C": cf.byte_width(n)}
    return cc, lab, n, runs, w


def exact_serialized(zyx: np.ndarray, family: str = "all", h1: int = 256, cap1: int = 255, cap2: int = 65535,
                     time_limit: float = 120.0) -> dict:
    """Exact minimum of the serialized label-section size over the chosen pin family (CP-SAT, proven optimal)."""
    cc, lab, n, runs, w = instance(zyx)
    Z = zyx.shape[0]
    labels = sorted(set(int(v) for v in lab))
    K = len(labels)
    if family == "all":
        cands = rm.all_subsegments(runs, Z)
    else:  # complete windows of both depth regimes: h1 (1-byte depth) and Z (2-byte depth)
        cands = rm.depth_windows(runs, min(Z, h1)) + rm.depth_windows(runs, Z)
    best: dict[tuple, int] = {}  # (label, coverage) -> narrowest depth class
    for p in cands:
        key = (p.label, rm.coverage(cc, p))
        cls = 1 if p.length <= h1 else 2
        best[key] = min(best.get(key, 3), cls)
    m = cp_model.CpModel()
    x = {key: m.NewBoolVar("") for key in best}
    y = [m.NewBoolVar("") for _ in range(n)]
    z = {l: m.NewBoolVar("") for l in labels}
    d2 = m.NewBoolVar("d2")
    n2 = m.NewBoolVar("n2")
    m.AddExactlyOne(z.values())
    cover: list[list] = [[] for _ in range(n)]
    for key, v in x.items():
        for u in set(key[1]):
            cover[u].append(v)
        if best[key] == 2:
            m.AddImplication(v, d2)
    for u in range(n):
        m.AddBoolOr(cover[u] + [y[u], z[int(lab[u])]])
    e = {}
    for key, v in x.items():  # e = x AND d2: the extra depth byte of a pin when w_D = 2
        e[key] = m.NewBoolVar("")
        m.Add(e[key] >= v + d2 - 1)
    for l in labels:
        m.Add(sum(v for key, v in x.items() if key[0] == l) <= cap1 + (cap2 - cap1) * n2)
        m.Add(sum(y[u] for u in range(n) if int(lab[u]) == l) <= cap1 + (cap2 - cap1) * n2)
    H1 = w["w_L"] + 8 + Z * w["w_G"] + 1 + (K - 1) * (w["w_L"] + 2)
    m.Minimize(H1 + (w["w_I"] + 1) * sum(x.values()) + sum(e.values()) + w["w_C"] * sum(y) + 2 * (K - 1) * n2)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = 8  # only proven-optimal values and structural descriptors are reported, never
    s.parameters.random_seed = 20261109  # features of one of several optimal solutions (those may differ between runs)
    status = s.Solve(m)
    assert status == cp_model.OPTIMAL, f"CP-SAT status {s.StatusName(status)}"
    return {"opt": int(round(s.ObjectiveValue())), "n_cc": n, "K": K, "candidates": len(best),
            "w_N": 2 if s.Value(n2) else 1, "w_D": 2 if s.Value(d2) else 1,
            "background": [l for l in labels if s.Value(z[l])][0], "P": sum(s.Value(v) for v in x.values()),
            "Q": sum(s.Value(v) for v in y)}


def cape(zyx: np.ndarray, opts: dict) -> dict:
    xyz = crackle_view(zyx)
    buf, d = cn.encode(xyz, opts)
    out = crackle.decompress(buf)
    lossless = bool(out.dtype == xyz.dtype and np.array_equal(out, xyz))
    lay = cf.split_stream(buf)
    assert lay.header.label_format == cf.PINS_VARIABLE_WIDTH
    sec = cf.parse_pins_section(lay.labels, lay.header)
    maxdepth = max([0] + [dep for pl in sec.pins for _, dep in pl])
    return {"U": int(d["label_bytes"]), "L": int(d["label_lb_bytes"]), "w_N": int(d["w_N"]), "w_D": int(d["w_D"]),
            "P": int(d["P"]), "Q": int(d["Q"]), "lossless": lossless, "w_D_parsed": sec.depth_width,
            "w_D_needed": cf.byte_width(maxdepth), "w_N_parsed": sec.num_pins_width}


def record(test: str, name: str, zyx: np.ndarray, **kv) -> dict:
    r = {"test": test, "case": name, "shape_zyx": list(zyx.shape), **kv}
    RESULTS.append(r)
    return r


# ----------------------------------------------------------------------------------------------- volumes
def random_volumes() -> list[tuple[str, np.ndarray]]:
    vols = []
    for s in range(20):
        vols.append((f"blocky{s}", syn.blocky((6, 6, 6), n_labels=4, block=(2, 2, 2), dtype=np.uint16, seed=s)))
    for s in range(20):
        vols.append((f"noise{s}", syn.noise((5, 4, 5), n_labels=3, dtype=np.uint16, seed=100 + s)))
    for s in range(10):
        vols.append((f"cyl{s}", syn.vertical_cylinders((8, 7, 7), n=3, radius=(1, 2), dtype=np.uint16, seed=200 + s)))
    for s in range(10):
        vols.append((f"voronoi{s}", syn.dense_drifting_voronoi((6, 8, 8), n_seeds=6, dtype=np.uint16, seed=300 + s)))
    return vols


def column_volume(Z: int, segments: list[list[tuple[int, int]]], X: int = 2) -> np.ndarray:
    """Columns given as lists of (label, run length); Y = 1. Labels alternate so that adjacent runs differ."""
    vol = np.zeros((Z, 1, X), dtype=np.uint16)
    for xi, segs in enumerate(segments):
        z = 0
        for labl, ln in segs:
            vol[z:z + ln, 0, xi] = labl
            z += ln
        assert z == Z, (xi, z, Z)
    return vol


def depth_volumes() -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(20261109)
    vols = [
        ("Z256_full_run", column_volume(256, [[(5, 256)], [(3, 100), (4, 156)]])),
        ("Z257_full_run", column_volume(257, [[(5, 257)], [(3, 1), (4, 256)]])),
        ("Z258_mixed", column_volume(258, [[(5, 258)], [(3, 255), (4, 3)], [(6, 2), (3, 256)]], X=3)),
        ("Z300_boundary", syn.depth_boundary(256, xy=(4, 4), pad=22).astype(np.uint16)),
        ("Z600_long_runs", column_volume(600, [[(5, 600)], [(3, 300), (4, 300)], [(6, 257), (3, 343)],
                                               [(4, 1), (5, 256), (6, 343)]], X=4)),
    ]
    for k in range(4):  # random mixed run lengths around the 256 boundary
        Z = int(rng.integers(257, 520))
        segs = []
        for _ in range(3):
            col, z, lab = [], 0, 1
            while z < Z:
                ln = int(min(Z - z, rng.choice([1, 2, 7, 100, 255, 256, 257, 300])))
                col.append((lab, ln))
                z += ln
                lab = 1 + lab % 4
            segs.append(col)
        vols.append((f"mixed_random{k}_Z{Z}", column_volume(Z, segs, X=3)))
    return vols


def boundary_volume(n_label1: int, double_column: bool, n_label2: int = 400) -> np.ndarray:
    """Z = 2, 200 x 200 (V = 80,000, so w_I = 4; N > 255, so w_C = 2; c = 5, s = 2).
    Label 1: n_label1 isolated CCs; with double_column, two of them form one column run of 2 slices (a pin over 2 CCs:
    c = 5 >= 2 s = 4, removed by singleton dominance). Label 2: n_label2 isolated CCs (the costliest label, so CAPE's
    background). Label 0 surrounds everything (one CC per slice)."""
    vol = np.zeros((2, 200, 200), dtype=np.uint16)
    pos = [(y, x) for y in range(2, 200, 2) for x in range(2, 200, 2)]
    k = 0
    if double_column:
        vol[0:2, pos[k][0], pos[k][1]] = 1
        k += 1
        n_single = n_label1 - 2
    else:
        n_single = n_label1
    for _ in range(n_single):
        vol[0, pos[k][0], pos[k][1]] = 1
        k += 1
    for _ in range(n_label2):
        vol[1, pos[k][0], pos[k][1]] = 2
        k += 1
    return vol


# ----------------------------------------------------------------------------------------------- checks
def check_T1():
    gaps = []
    for name, zyx in random_volumes():
        ex = exact_serialized(zyx, "all")
        for pol, opts in (("fixed_depth_width", EVALUATED), ("full_width_first", FULL_WIDTH_FIRST)):
            c = cape(zyx, opts)
            record("T1", name, zyx, policy=pol, OPT_ser=ex["opt"], **c, n_cc=ex["n_cc"], K=ex["K"])
            assert c["lossless"], name
            assert c["L"] <= ex["opt"] <= c["U"], (name, pol, c["L"], ex["opt"], c["U"])
            gaps.append(c["U"] - ex["opt"])
    return gaps


def check_T2():
    rng = np.random.default_rng(7)
    n = 0
    for s in range(40):
        Z = int(rng.integers(4, 9))
        zyx = syn.blocky((Z, 3, 3), n_labels=3, block=(int(rng.integers(2, 5)), 1, 2), dtype=np.uint16, seed=500 + s)
        runs = rm.column_runs(zyx)
        for h1, cap in ((2, 3), (3, 2), (3, 4)):
            a = exact_serialized(zyx, "all", h1=h1, cap1=cap)
            b = exact_serialized(zyx, "windows", h1=h1, cap1=cap)
            u = exact_serialized(zyx, "all", h1=h1, cap1=65535)  # count capacity lifted: no coupling constraint
            # deterministic descriptors (optimal values and structure only; not features of one optimal solution)
            record("T2", f"blocky{500 + s}_h{h1}_cap{cap}", zyx, OPT_all=a["opt"], OPT_windows=b["opt"],
                   OPT_uncoupled=u["opt"], coupling_active=a["opt"] != u["opt"],
                   windows_active=any(r.length > h1 for r in runs), candidates_all=a["candidates"],
                   candidates_windows=b["candidates"])
            assert a["opt"] == b["opt"], (s, h1, cap, a, b)
            assert u["opt"] <= a["opt"]
            n += 1
    return n


def check_T3():
    for name, zyx in depth_volumes():
        ex = exact_serialized(zyx, "windows")
        for pol, opts in (("fixed_depth_width", EVALUATED), ("full_width_first", FULL_WIDTH_FIRST)):
            c = cape(zyx, opts)
            record("T3", name, zyx, policy=pol, OPT_ser_windows=ex["opt"], OPT_w_D=ex["w_D"], **c)
            assert c["lossless"], name
            assert c["L"] <= ex["opt"] <= c["U"], (name, pol, c["L"], ex["opt"], c["U"])
            assert c["w_D"] == c["w_D_parsed"] == c["w_D_needed"], (name, c)


def check_T4():
    zyx = boundary_volume(257, double_column=True)
    ex = exact_serialized(zyx, "windows")
    c = cape(zyx, EVALUATED)
    r = record("T4", "singleton_dominance_Q257", zyx, OPT_ser=ex["opt"], OPT_w_N=ex["w_N"], OPT_P=ex["P"],
               OPT_Q=ex["Q"], **c, excess_bytes=c["U"] - ex["opt"])
    assert c["lossless"]
    assert c["w_N"] == 2 and ex["w_N"] == 1
    assert c["L"] <= ex["opt"] < c["U"]
    assert r["excess_bytes"] == 3  # +2(K-1) header bytes for w_N = 2, -1 payload byte (two records instead of a pin)
    return r


def check_T5():
    out = {}
    for q in (255, 256):
        zyx = boundary_volume(q, double_column=False)
        c = cape(zyx, EVALUATED)
        record("T5", f"label1_Q{q}", zyx, **c)
        assert c["lossless"]
        out[q] = c["w_N"]
    assert out == {255: 1, 256: 2}, out
    return out


def check_T6():
    q, c_max, s_max, n_max = 1 << 20, 8 + 4, 8, 1 << 32  # w_I <= 8, w_D <= 4 (Z - 1 < 2^32), w_C <= 8
    worst_sum = n_max * q * s_max
    assert q * c_max < 2**63 and worst_sum < 2**63
    RESULTS.append({"test": "T6", "case": "headroom", "q": q, "max_slack": q * c_max, "max_component_sum": worst_sum,
                    "uint64_max": 2**64 - 1})


# pytest entry points
def test_T1_cape_vs_exact_serialized_optimum():
    check_T1()


def test_T2_complete_windows_in_serialized_model():
    check_T2()


def test_T3_depth_width_boundaries():
    check_T3()


def test_T4_singleton_dominance_at_count_boundary():
    check_T4()


def test_T5_count_width_255_256():
    check_T5()


def test_T6_integer_headroom():
    check_T6()


def main() -> int:
    t0 = time.time()
    summary = {}
    gaps = check_T1()
    summary["T1"] = {"cases": len(gaps), "U_equals_OPT": sum(g == 0 for g in gaps), "max_U_minus_OPT": max(gaps),
                     "mean_U_minus_OPT": float(np.mean(gaps))}
    summary["T2"] = {"cases": check_T2()}
    t2 = [r for r in RESULTS if r["test"] == "T2"]
    summary["T2"].update(count_width_coupling_active=sum(bool(r["coupling_active"]) for r in t2),
                         two_byte_depth_active=sum(bool(r["windows_active"]) for r in t2))
    check_T3()
    t3 = [r for r in RESULTS if r["test"] == "T3"]
    summary["T3"] = {"cases": len(t3), "volumes": len(t3) // 2}
    for pol in ("fixed_depth_width", "full_width_first"):
        ex = [r["U"] - r["OPT_ser_windows"] for r in t3 if r["policy"] == pol]
        summary["T3"][pol] = {"U_equals_OPT": sum(v == 0 for v in ex), "max_U_minus_OPT": max(ex),
                              "L_equals_OPT": sum(r["L"] == r["OPT_ser_windows"] for r in t3 if r["policy"] == pol)}
    r4 = check_T4()
    summary["T4"] = {k: r4[k] for k in ("U", "L", "OPT_ser", "excess_bytes", "w_N", "OPT_w_N", "Q", "OPT_P", "OPT_Q")}
    summary["T5"] = check_T5()
    check_T6()
    summary["T6"] = "ok"
    summary["seconds"] = round(time.time() - t0, 1)
    summary["all_passed"] = True
    logs = MS / "evidence" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "revision_math_tests.json").write_text(json.dumps({"summary": summary, "rows": RESULTS}, indent=1),
                                                   encoding="utf-8")
    lines = ["Revision math tests (synthetic; not biological evidence)", f"crackle-codec decoder {crackle.__version__}"
             if hasattr(crackle, "__version__") else "crackle-codec decoder (PyPI)", json.dumps(summary, indent=1)]
    (logs / "revision_math_tests.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
