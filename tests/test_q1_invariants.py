"""Q1 (task v3) invariants: the output-preserving encoder Eθ against the frozen original v3 binary E0.

* O1 (lean CC, 1024), O2 (exact runs, 2048) and O3 (compact uint16 chain, 4096) are implementation changes: every
  combination, on top of every v3 implementation mask, must write the bitstream of the FROZEN v3 binary
  (snapshots/v3, sha256 f1029e19...) byte for byte. The frozen digests are computed in a separate process.
* O3 falls back to the uint32 chain buffer when a slice has more than 65536 CCs; the bytes do not change.
* O2's exact run count V - z_pairs equals the number of runs produced.
* profile_memory only adds diagnostics.
* The frozen v3 adapter contract (cape_frozen_v3) is exercised in its own process.
"""

from __future__ import annotations

import hashlib
import json
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
FROZEN_V3 = ROOT / "snapshots" / "v3" / "_cape_native.cp312-win_amd64.pyd"
FROZEN_V3_SHA = "f1029e19992af218a73437050abf750da811f318d36c4993834262785b01e98c"

SYN = synthetic_cases()
REAL = real_cases()
CASES = {**SYN, **REAL}
EDGE = edge_cases()
Q1_BITS = [1024, 2048, 4096]
Q1_COMBOS = [sum(b for i, b in enumerate(Q1_BITS) if c >> i & 1) for c in range(8)]
# v3 implementation masks underneath: FAST (575), every v3 bit (1023), v2.1 fast + batched CC, no batched CC
BASE_MASKS = [575, 1023, 31 | 512, 31]


@pytest.fixture(scope="module")
def frozen_v3():
    if not FROZEN_V3.exists():
        pytest.skip("frozen v3 binary missing (snapshots/v3)")
    assert hashlib.sha256(FROZEN_V3.read_bytes()).hexdigest() == FROZEN_V3_SHA, "frozen v3 binary was modified"
    out = subprocess.run([sys.executable, str(ROOT / "tests" / "v3_frozen_digests.py"), str(FROZEN_V3)],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _enc(zyx, opts):
    return cn.encode(np.ascontiguousarray(zyx).T, opts)


def _digest(buf):
    return hashlib.sha256(buf).hexdigest(), len(buf)


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("depth", ["fixed_depth_width", "full_width_first"])
def test_every_q1_combination_matches_frozen_v3(frozen_v3, name, depth):
    zyx = CASES[name]
    sha, n, ref_diag = frozen_v3[request_key("cases", name, dict(BASE, depth_policy=depth))]
    for low in BASE_MASKS:
        for q1 in Q1_COMBOS:
            got, diag = _enc(zyx, dict(BASE, depth_policy=depth, impl_mask=low | q1))
            assert _digest(got) == (sha, n), f"{name}/{depth}: impl_mask={low | q1} changed the bitstream"
            for k in DIAG_KEYS:
                if k in ref_diag and k in diag:
                    assert diag[k] == ref_diag[k], f"{name}/{depth}/{low | q1}: {k} {diag[k]} != {ref_diag[k]}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_q1_fast_preset_matches_frozen_v3_same_as_stock(frozen_v3, name):
    zyx = CASES[name]
    sha, n, _ = frozen_v3[request_key("cases", name, dict(FAST_STOCK))]
    for q1 in Q1_COMBOS:
        got, _ = _enc(zyx, dict(FAST_STOCK, impl_mask=575 | q1))
        assert _digest(got) == (sha, n)


@pytest.mark.parametrize("name", sorted(EDGE))
def test_q1_edge_cases_match_frozen_v3(frozen_v3, name):
    zyx = EDGE[name]
    opts = dict(BASE, format_policy="same_as_stock", depth_policy="fixed_depth_width")
    sha, n, _ = frozen_v3[request_key("edge", name, opts)]
    for q1 in Q1_COMBOS:
        got, _ = _enc(zyx, dict(opts, impl_mask=575 | q1))
        assert _digest(got) == (sha, n), f"{name}: impl_mask {575 | q1}"
        dec = crackle.decompress(got)
        assert np.array_equal(np.asarray(dec), np.ascontiguousarray(zyx).T), f"{name}: not lossless"


def test_compact_chain_is_used_and_exact_runs_count():
    zyx = SYN["voronoi_u32"]
    _, d = _enc(zyx, dict(FAST_STOCK, impl_mask=575 | 7168))
    assert d["compact_chain"] == 1
    assert d["runs_expected"] == d["run_count"]
    _, d0 = _enc(zyx, dict(FAST_STOCK, impl_mask=575))
    assert "compact_chain" not in d0 or d0["compact_chain"] == 0
    assert d0["run_count"] == d["run_count"]


def test_compact_chain_falls_back_above_65536_ccs_per_slice():
    # checkerboard: every pixel is its own 4-connected CC -> 90 000 CCs per slice > 65 536
    yy, xx = np.mgrid[0:300, 0:300]
    sl = ((yy + xx) % 2).astype(np.uint8)
    zyx = np.stack([sl, sl, 1 - sl])
    opts = dict(BASE, depth_policy="fixed_depth_width")
    ref, _ = _enc(zyx, dict(opts, impl_mask=575))
    got, d = _enc(zyx, dict(opts, impl_mask=575 | 7168))
    assert d["compact_chain"] == 0, "a slice with > 65536 CCs must use the uint32 chain buffer"
    assert got == ref
    dec = np.asarray(crackle.decompress(got))
    assert np.array_equal(dec, np.ascontiguousarray(zyx).T)


def test_profile_memory_only_adds_diagnostics():
    zyx = SYN["walking_u64"]
    a, da = _enc(zyx, dict(FAST_STOCK, impl_mask=575 | 7168))
    b, db = _enc(zyx, dict(FAST_STOCK, impl_mask=575 | 7168, profile_memory=True))
    assert a == b
    extra = set(db) - set(da)
    assert extra and all(k.startswith(("mem_ws_", "mem_peak_")) for k in extra)


def test_q1_mask_range():
    zyx = SYN["blocky_u8"]
    _enc(zyx, dict(BASE, impl_mask=8191))
    with pytest.raises(ValueError):
        _enc(zyx, dict(BASE, impl_mask=8192))


FROZEN_ADAPTER_SCRIPT = r"""
import json, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
from cape.adapters.cape_frozen import CapeFrozenV3Adapter, load_frozen_module
from cape.adapters.cape_native import CapeNativeAdapter
opts = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape",
        "depth_policy": "fixed_depth_width", "certificate": "off", "impl_mask": 575}
rng = np.random.default_rng(7)
zyx = np.kron(rng.integers(0, 9, (4, 6, 6)), np.ones((5, 4, 4))).astype(np.uint32)
a = CapeFrozenV3Adapter("cape_v3frozen_fast_m0", opts)
assert a.availability()["status"] == "AVAILABLE", a.availability()
buf = a.encode(zyx)
dec = a.decode(buf)
errors = []
for bad in ({"impl_mask": 1024 | 575}, {"profile_memory": True}):
    try:
        CapeFrozenV3Adapter("x", dict(opts, **bad))
        errors.append(f"accepted {bad}")
    except ValueError:
        pass
print(json.dumps({"lossless": bool(np.array_equal(dec, zyx)), "bytes": len(buf), "errors": errors,
                  "version": a.version()}))
"""


def test_frozen_v3_adapter_contract_in_own_process():
    if not FROZEN_V3.exists():
        pytest.skip("frozen v3 binary missing")
    out = subprocess.run([sys.executable, "-c", FROZEN_ADAPTER_SCRIPT, str(ROOT)], cwd=ROOT, capture_output=True,
                         text=True, check=True)
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["lossless"] and r["bytes"] > 0 and not r["errors"], r
    assert "f1029e19" in r["version"]
