"""CAPE v3 invariants (plan CAPE v3, section 11).

* M1/M2/M5 are implementation changes: every combination of the ten implementation bits must write the
  bitstream of the FROZEN v2.1 binary (snapshots/v21) byte for byte, with both depth policies.
* M3a (regime gate) must not change the full-regime search result; its bound must not exceed the regime it
  prunes or checks.
* M3b (reduced-cost fixing) and M4 (bounded repair) may change bytes, but only downwards: never above the
  FAST incumbent, always lossless with the original decoder, and on small abstract models the reduced-cost
  result equals the brute-force optimum whenever it claims "Improved", and a "Proven" verdict holds.
* M2 eager greedy returns exactly the lazy greedy selection.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from golden_cases import real_cases, synthetic_cases
from v3_cases import BASE, DIAG_KEYS, FAST_STOCK, edge_cases, request_key

cn = pytest.importorskip("cape._cape_native")
crackle = pytest.importorskip("crackle")

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "snapshots" / "v21" / "_cape_native.cp312-win_amd64.pyd"
FROZEN_SHA = "39dca94b1eeb1c59c98b1dcb117e2f46c3b4ddf6b3539dd067c2a4f40a4ff2cb"

SYN = synthetic_cases()
REAL = real_cases()
CASES = {**SYN, **REAL}
EDGE = edge_cases()
V3_BITS = [32, 64, 128, 256, 512]
ALL = 1023


@pytest.fixture(scope="module")
def frozen():
    """Digests of the frozen v2.1 binary, computed in a separate process (see tests/v3_cases.py)."""
    if not FROZEN.exists():
        pytest.skip("frozen v2.1 binary missing (snapshots/v21)")
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA, "frozen v2.1 binary was modified"
    out = subprocess.run([sys.executable, str(ROOT / "tests" / "v3_frozen_digests.py"), str(FROZEN)],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _enc(mod, zyx, opts):
    buf, diag = mod.encode(np.ascontiguousarray(zyx).T, opts)
    return buf, diag


def _digest(buf):
    return hashlib.sha256(buf).hexdigest(), len(buf)


# ------------------------------------------------------------------ 1. byte identity with frozen v2.1
@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("depth", ["fixed_depth_width", "full_width_first"])
def test_every_v3_bit_combination_matches_frozen_v21(frozen, name, depth):
    zyx = CASES[name]
    sha, n, _ = frozen[request_key("cases", name, dict(BASE, depth_policy=depth))]
    for combo in range(32):
        bits = sum(b for i, b in enumerate(V3_BITS) if combo >> i & 1)
        for low in (31, 0):  # with the v2.1 fast and legacy implementations underneath
            got, _ = _enc(cn, zyx, dict(BASE, depth_policy=depth, impl_mask=low | bits))
            assert _digest(got) == (sha, n), f"{name}/{depth}: impl_mask={low | bits} changed the bitstream"


@pytest.mark.parametrize("name", sorted(CASES))
def test_v3_fast_preset_matches_frozen_v21_same_as_stock(frozen, name):
    zyx = CASES[name]
    sha, n, rd = frozen[request_key("cases", name, dict(FAST_STOCK))]
    got, gd = _enc(cn, zyx, dict(FAST_STOCK, impl_mask=ALL))
    assert _digest(got) == (sha, n)
    # diagnostics that describe the problem (not the work) are unchanged as well
    for k in DIAG_KEYS:
        if k in rd:
            assert gd.get(k) == rd[k], f"{name}: diagnostic {k} changed ({rd[k]} -> {gd.get(k)})"


@pytest.mark.parametrize("bits", [2, 6, 12])
def test_forced_hash_collisions_keep_bytes_with_v3_bits(bits):
    """Equal-coverage grouping with very few hash bits (many collisions resolved exactly)."""
    for name in ("voronoi_u32", "branching_u32", "walking_u64"):
        zyx = SYN[name]
        ref, _ = _enc(cn, zyx, dict(BASE, depth_policy="full_width_first", impl_mask=31))
        got, d = _enc(cn, zyx, dict(BASE, depth_policy="full_width_first", impl_mask=ALL, debug_hash_bits=bits))
        assert got == ref, f"{name}: forced collisions changed the stream"


def test_adjacent_dedup_counts_are_consistent():
    zyx = SYN["cylinders_u16"]
    _, d = _enc(cn, zyx, dict(BASE, depth_policy="fixed_depth_width", impl_mask=ALL))
    assert d["candidates_after_adjacency"] + d["candidates_adjacent_dropped"] == d["candidates_after_singleton"]
    assert d["candidates_after_equal"] <= d["candidates_after_adjacency"] <= d["candidates_after_singleton"]
    assert d["batched_cc"] == 1


def test_batched_cc_is_skipped_when_the_cc_volume_is_requested():
    zyx = SYN["blocky_u16"]
    buf, d = _enc(cn, zyx, dict(BASE, depth_policy="fixed_depth_width", impl_mask=ALL, return_cc=True))
    assert d["batched_cc"] == 0 and d["cc_volume"].shape == zyx.shape
    ref, _ = _enc(cn, zyx, dict(BASE, depth_policy="fixed_depth_width", impl_mask=31))
    assert buf == ref


def test_impl_mask_range():
    zyx = SYN["blocky_u8"]
    _enc(cn, zyx, dict(BASE, impl_mask=ALL))
    with pytest.raises(ValueError):
        _enc(cn, zyx, dict(BASE, impl_mask=ALL + 1))


# ------------------------------------------------------------------ 2-3. roundtrip, dtypes, edge cases
QUALITY = dict(BASE, format_policy="same_as_stock", depth_policy="full_width_first", certificate="regime",
               impl_mask=ALL, regime_gate=True, rc_fixing=True, repair=True, repair_attempts=4)


@pytest.mark.parametrize("name", sorted(EDGE))
@pytest.mark.parametrize("mode", ["fast", "quality"])
def test_v3_roundtrip_edge_cases(frozen, name, mode):
    zyx = EDGE[name]
    opts = dict(BASE, format_policy="same_as_stock", depth_policy="fixed_depth_width", impl_mask=ALL) \
        if mode == "fast" else QUALITY
    buf, _ = _enc(cn, zyx, opts)
    back = crackle.decompress(buf)  # original upstream decoder, (x, y, z) F-order
    np.testing.assert_array_equal(np.ascontiguousarray(back.T), zyx)
    assert back.dtype == zyx.dtype
    if mode == "fast":
        sha, n, _ = frozen[request_key("edge", name, dict(BASE, format_policy="same_as_stock",
                                                          depth_policy="fixed_depth_width"))]
        assert _digest(buf) == (sha, n)


# ------------------------------------------------------------------ 4. uint32 index guard (mocked)
def test_candidate_index_guard_without_allocating():
    assert cn._v3_candidate_guard_raises()


# ------------------------------------------------------------------ M3a regime gate
@pytest.mark.parametrize("name", ["depth257", "depth258", "tall_u16"])
def test_regime_gate_is_output_preserving_and_its_bound_is_valid(name):
    zyx = SYN.get(name, EDGE.get(name))
    opts = dict(BASE, format_policy="force_pins", depth_policy="full_width_first", certificate="regime", impl_mask=ALL)
    ref, rd = _enc(cn, zyx, opts)
    got, gd = _enc(cn, zyx, dict(opts, regime_gate=True))
    assert got == ref
    # every gate bound printed in the regime log is <= the section bytes of the regime it describes
    log = gd["regimes"]
    sections = {int(p.split(":")[0][2:]): int(p.split(":")[1]) for p in rd["regimes"].split(";")
                if p.startswith("wD") and p.split(":")[1].isdigit()}
    for part in log.split(";"):
        if part.startswith("gate_lb_wD"):
            wd, lb = part[len("gate_lb_wD"):].split(":")
            assert int(lb) <= sections[int(wd)], f"{name}: gate bound {lb} exceeds regime wD{wd} section {sections[int(wd)]}"
        if part.startswith("wD") and "pruned_lb" in part:
            wd = int(part[2:].split(":")[0])
            lb = int(part.split("pruned_lb")[1])
            assert lb <= sections[wd]


def test_scaled_dual_bound_never_exceeds_the_regime_optimum_on_real_z512():
    p = ROOT / "data" / "real" / "scaling_v21" / "scale_crackle_connectomics_64x64x512.npy"
    if not p.exists():
        pytest.skip("scaling crop not present")
    zyx = np.load(p)
    opts = dict(BASE, format_policy="same_as_stock", depth_policy="full_width_first", certificate="regime", impl_mask=ALL)
    _, rd = _enc(cn, zyx, dict(opts, regime_gate=True))
    sections = {int(x.split(":")[0][2:]): int(x.split(":")[1]) for x in rd["regimes"].split(";")
                if x.startswith("wD") and x.split(":")[1].isdigit()}
    lbs = [x for x in rd["regimes"].split(";") if x.startswith("gate_lb_wD")]
    assert lbs, rd["regimes"]
    for x in lbs:
        wd, lb = x[len("gate_lb_wD"):].split(":")
        assert int(lb) <= sections[int(wd)]


# ------------------------------------------------------------------ M3b / M4 / M2 on abstract models
def _brute(n, sets, c, s):
    best = None
    for k in range(len(sets) + 1):
        for chosen in itertools.combinations(range(len(sets)), k):
            cov = set()
            for j in chosen:
                cov |= set(sets[j])
            cost = c * len(chosen) + s * (n - len(cov))
            best = cost if best is None or cost < best else best
    return best


def _random_models(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        n = rng.randint(1, 11)
        m = rng.randint(1, 12)
        sets = []
        for _ in range(m):
            k = rng.randint(1, min(n, 5))
            sets.append(sorted(rng.sample(range(n), k)))
        c = rng.randint(2, 7)
        s = rng.randint(1, 4)
        yield n, sets, c, s


@pytest.mark.parametrize("seed", range(6))
def test_abstract_models_eager_rc_repair_against_brute_force(seed):
    opts = {"exact_max_cc": 0, "rc_max_cc": 30, "repair_max_r": 30, "repair_max_pool": 64, "repair_attempts": 4}
    for n, sets, c, s in _random_models(60, 1000 + seed):
        r = cn.solve_abstract(n, sets, c, s, opts)
        opt = _brute(n, sets, c, s)
        assert r["greedy_is_cover"]
        # M2: identical selection
        assert (r["eager_cost"], r["eager_pins"], r["eager_singles"]) == (r["greedy_cost"], r["greedy_pins"],
                                                                          r["greedy_singles"])
        # M3b
        if r["rc_outcome"] == 1:  # Improved: claims the optimum
            assert r["rc_is_cover"] and r["rc_cost"] == opt < r["greedy_cost"]
        elif r["rc_outcome"] == 0:  # Proven: incumbent already optimal
            assert r["greedy_cost"] == opt
        # M4: feasible, never worse than the incumbent, never below the optimum
        assert r["repair_is_cover"]
        assert opt <= r["repair_cost"] <= r["greedy_cost"]


# ------------------------------------------------------------------ M3b / M4 on real crops
QUALITY_FILES = [
    "data/real/scaling_v21/scale_crackle_connectomics_64x64x512.npy",
    "data/real/crackle_crops/crackle_ws_x0_y384_z320_128x128x64.npy",
    "data/real/cremi_crops/cremi_A_x512_y0_z0_128x128x64.npy",
]


@pytest.mark.parametrize("rel", QUALITY_FILES)
def test_quality_never_exceeds_fast_and_is_lossless(rel):
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} not present")
    zyx = np.load(p)
    fast = dict(BASE, format_policy="same_as_stock", depth_policy="fixed_depth_width", certificate="regime",
                impl_mask=ALL)
    fbuf, fd = _enc(cn, zyx, fast)
    for extra in ({"rc_fixing": True}, {"repair": True, "repair_attempts": 4},
                  {"rc_fixing": True, "repair": True, "repair_attempts": 4}):
        buf, d = _enc(cn, zyx, dict(fast, **extra))
        assert len(buf) <= len(fbuf), f"{rel} {extra}: QUALITY step made the stream larger"
        np.testing.assert_array_equal(np.ascontiguousarray(crackle.decompress(buf).T), zyx)
        assert d["certificate_dual_feasible"] == 1
        assert d["lb_bytes"] <= d["ub_bytes"] == len(buf)
        if extra.get("repair"):
            assert d["repair_kept"] in (0, 1)
            if d["repair_kept"]:
                assert d["repair_section_delta"] > 0
    qbuf, _ = _enc(cn, zyx, dict(QUALITY, format_policy="same_as_stock"))
    assert len(qbuf) <= len(fbuf)
    np.testing.assert_array_equal(np.ascontiguousarray(crackle.decompress(qbuf).T), zyx)


# ------------------------------------------------------------------ frozen v2.1 adapter contract (own process)
FROZEN_ADAPTER_SCRIPT = r"""
import sys, numpy as np
sys.path.insert(0, sys.argv[1])
from cape.adapters import make_adapter
from cape.config import load_methods, load_run_config
from cape import synthetic as syn
M = load_methods(); RUN = load_run_config("configs/smoke.yaml", M)
vols = [syn.blocky((12, 24, 20), n_labels=9, dtype=np.uint16, seed=1),
        syn.dense_drifting_voronoi((10, 24, 28), n_seeds=15, dtype=np.uint32, seed=2), syn.large_ids((6, 16, 12), seed=3)]
for mid in ("cape_v21_fast_m0", "cape_v21_fast_m5"):
    for wrapper in ["none"] + (["zstd3", "zstd9"] if M[mid]["wrappable"] else []):
        ad = make_adapter(mid, M[mid], RUN, wrapper)
        assert ad.availability()["status"] == "AVAILABLE", mid
        for a in vols:
            s = ad.encode(a); out = ad.decode(s)
            assert out.shape == a.shape and out.dtype == a.dtype and np.array_equal(out, a), (mid, wrapper)
            assert all(v is True for v in ad.secondary_check(s, a).values())
assert "cape._cape_native" not in sys.modules, "frozen adapter imported the v3 module"
print("FROZEN_ADAPTER_OK")
"""


def test_frozen_v21_adapter_roundtrip_in_its_own_process():
    if not FROZEN.exists():
        pytest.skip("frozen v2.1 binary missing")
    out = subprocess.run([sys.executable, "-c", FROZEN_ADAPTER_SCRIPT, str(ROOT)], cwd=ROOT, capture_output=True,
                         text=True)
    assert out.returncode == 0 and "FROZEN_ADAPTER_OK" in out.stdout, out.stderr[-2000:]


def test_frozen_adapter_rejects_v3_options():
    from cape.adapters.cape_frozen import CapeFrozenV21Adapter

    with pytest.raises(ValueError):
        CapeFrozenV21Adapter("x", {"rc_fixing": True})
    with pytest.raises(ValueError):
        CapeFrozenV21Adapter("x", {"impl_mask": 1023})
