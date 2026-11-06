"""Corrected stock baseline (plan v2 P1.4, format_audit F2): upstream's own pin selection,
background and serializer, with only the count width fixed.

Three lineages are kept apart in reports: historical stock (PyPI 0.53.0 / vendor 14b39b1),
corrected stock (this selector) and CAPE."""

from __future__ import annotations

import crackle  # PyPI crackle-codec 0.53.0
import numpy as np
import pytest

from cape import _cape_native as cn
from cape import _crackle_vendor as cv
from cape import synthetic as syn
from conftest import as_xyz
from golden_cases import synthetic_cases

CASES = synthetic_cases()


def _enc(xyz, selector, policy="force_pins", markov=0):
    return cn.encode(xyz, {"selector": selector, "format_policy": policy, "markov_model_order": markov})


@pytest.mark.parametrize("markov", [0, 5])
@pytest.mark.parametrize("name", sorted(CASES))
def test_identical_to_stock_wherever_stock_is_correct(name, markov):
    xyz = as_xyz(CASES[name])
    stock, ds = _enc(xyz, "stock_greedy", markov=markov)
    fixed, df = _enc(xyz, "stock_greedy_corrected", markov=markov)
    stock_ok = np.array_equal(crackle.decompress(stock), xyz)
    if stock_ok:
        assert fixed == stock
        assert df.get("stock_count_width_widened", 0) == 0
    assert np.array_equal(crackle.decompress(fixed), xyz)
    assert np.array_equal(cv.decompress(fixed), xyz)


def test_corrected_stock_fixes_the_count_width_corruption():
    xyz = as_xyz(syn.count_width_adversarial())
    stock, _ = _enc(xyz, "stock_greedy")
    assert not np.array_equal(crackle.decompress(stock), xyz)  # historical stock: silent corruption
    fixed, d = _enc(xyz, "stock_greedy_corrected")
    assert d["stock_count_width_widened"] == 1
    assert np.array_equal(crackle.decompress(fixed), xyz)
    assert np.array_equal(cv.decompress(fixed), xyz)
    assert len(fixed) > len(stock)  # the fix costs bytes on this input; it is not a compression gain


def test_same_as_stock_policy_matches_pypi_pins_opt_on_a_regular_volume():
    xyz = as_xyz(syn.walking_cylinders((24, 48, 48), dtype=np.uint32, seed=31))
    fixed, d = _enc(xyz, "stock_greedy_corrected", policy="same_as_stock")
    ref = crackle.compress(xyz, allow_pins=2)  # 2 = optimized pins (crackle_pins_opt)
    if d["label_format"] == "PINS_VARIABLE_WIDTH":
        assert np.array_equal(crackle.decompress(ref), xyz)
        assert len(fixed) == len(ref)  # same selection rule and widths (background ties may reorder bytes)
    assert np.array_equal(crackle.decompress(fixed), xyz)


def test_f2_recheck_on_current_upstream_head():
    """Plan v2 P1.4: the bug is re-checked on the current upstream HEAD, never assumed."""
    try:
        from cape import _crackle_head as ch
    except ImportError:
        pytest.skip("optional _crackle_head module not built (vendor/crackle_head absent)")
    xyz = as_xyz(syn.count_width_adversarial())
    buf = ch.compress(xyz, allow_pins=2)
    wrong = int((ch.decompress(buf) != xyz).sum())
    # Recorded result for HEAD 3426263 (2026-11-06): the corruption is still present. If upstream
    # fixes it, this assertion fails on purpose so the documentation is updated.
    assert wrong == 256
