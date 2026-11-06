"""v2 speed work must not change a single v1 CAPE byte (plan v2, P1 verification 1)."""

from __future__ import annotations

import json

import pytest

from cape.config import load_methods, load_run_config
from golden_cases import GOLDEN_PATH, RUN_CONFIG, digest, native_options, real_cases, synthetic_cases

GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
METHODS = load_methods()
CFG = load_run_config(RUN_CONFIG, METHODS)
SYN = synthetic_cases()
REAL = real_cases()


@pytest.mark.parametrize("name", sorted(GOLDEN["cases"]))
def test_v1_bitstreams_are_reproduced(name):
    if name in SYN:
        zyx = SYN[name]
    elif name in REAL:
        zyx = REAL[name]
    else:
        pytest.skip(f"{name}: local data file not present on this machine (not redistributed)")
    for mid, (sha, n) in GOLDEN["cases"][name].items():
        got_sha, got_n = digest(zyx, native_options(mid, METHODS, CFG))
        assert (got_sha, got_n) == (sha, n), f"{name}/{mid}: v1 bitstream changed ({n} -> {got_n} bytes)"
