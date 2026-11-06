"""SAFE-ARCHIVE baseline (plan v2 P1.5): stored size == min(zstd(flat), zstd(CAPE-FAST)) with the
same zstd frame settings; ordinary zstd frame + ordinary Crackle stream; choice recorded."""

from __future__ import annotations

import crackle  # PyPI crackle-codec 0.53.0
import numpy as np
import pytest
import zstandard

from cape.adapters import make_adapter
from cape.config import load_methods
from golden_cases import real_cases, synthetic_cases

METHODS = load_methods()
CASES = {**synthetic_cases(), **real_cases()}
SAFE = ["safe_archive_m0_zstd3", "safe_archive_m0_zstd9", "safe_archive_m5_zstd3", "safe_archive_m5_zstd9"]


def _wrapped(method_id: str, zyx: np.ndarray) -> int:
    ad = make_adapter(method_id.split("+")[0], METHODS[method_id.split("+")[0]],
                      wrapper=method_id.split("+")[1] if "+" in method_id else "none")
    return len(ad.encode(zyx))


@pytest.mark.parametrize("mid", SAFE)
@pytest.mark.parametrize("name", ["syn_dense_voronoi", "syn_branching", "walking_u64", "blocky_u16", "noise",
                                  "syn_single_slice", "syn_count_width_adversarial"]
                         + sorted(n for n in CASES if n.startswith(("cremi", "crackle"))))
def test_safe_is_the_smaller_of_its_two_wrapped_streams(name, mid):
    zyx = CASES[name]
    ad = make_adapter(mid, METHODS[mid])
    out = ad.encode(zyx)
    d = ad.last_diagnostics
    sizes = [v for v in (d["safe_flat_wrapped_bytes"], d["safe_pins_wrapped_bytes"]) if v]
    assert len(out) == min(sizes)
    assert d["safe_choice"] in ("FLAT", "PINS_VARIABLE_WIDTH")
    # never larger than the included flat stream with the same level and Markov order
    lvl = "zstd3" if mid.endswith("zstd3") else "zstd9"
    m = "m5" if "_m5_" in mid else "m0"
    assert len(out) <= _wrapped(f"crackle_flat_{m}+{lvl}", zyx)
    # an ordinary zstd frame containing an ordinary Crackle v1 stream
    inner = zstandard.ZstdDecompressor().decompress(out)
    assert np.array_equal(crackle.decompress(inner), np.ascontiguousarray(zyx).T)
    assert np.array_equal(ad.decode(out), zyx)
    if d["safe_choice"] == "FLAT":
        assert "ub_bytes" not in d and "certificate_dual_feasible" not in d  # no certificate for a flat row


def test_safe_matches_flat_byte_for_byte_when_flat_wins():
    zyx = CASES["noise"]
    ad = make_adapter("safe_archive_m0_zstd9", METHODS["safe_archive_m0_zstd9"])
    out = ad.encode(zyx)
    if ad.last_diagnostics["safe_choice"] == "FLAT":
        ref = make_adapter("crackle_flat_m0", METHODS["crackle_flat_m0"], wrapper="zstd9").encode(zyx)
        assert out == ref
