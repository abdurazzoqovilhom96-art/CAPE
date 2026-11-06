"""Count-width coupling and certificate scope (spec sections 6, 9, 29, 39.1; acceptance T12).

The MVP solves each component independently with a count width wide enough for any
record count; the result is then compacted. Independent optima are NOT the optimum of the
narrow-count model: this test builds the counterexample and checks that scopes cannot be
mixed."""

from __future__ import annotations

from cape import certificate_verify as cvf
from cape import reference_model as rm

PIN_COST, SINGLE_COST, OTHER_LABELS = 5, 2, 3  # w_I + w_D = 5, w_C = 2, K - 1 = 3 written labels
COUNT_CAPACITY = {1: 255, 2: 65535}


def _label_with_triples(n: int) -> list[rm.CoverModel]:
    """n independent components; each has three CCs coverable by one pin (5 < 3 * 2)."""
    comps = []
    for j in range(n):
        us = (3 * j, 3 * j + 1, 3 * j + 2)
        comps.append(rm.CoverModel(1, us, [(rm.Pin(1, 0, j, 0, 3), frozenset(us))], PIN_COST, SINGLE_COST))
    return comps


def _total(payload: int, max_count: int) -> int:
    w_n = 1 if max_count <= COUNT_CAPACITY[1] else 2
    return payload + 2 * OTHER_LABELS * w_n


def _scope(regime: str, header: int) -> dict:
    return {"regime_id": regime, "header_bytes": header, "candidate_policy": "depth_bounded_complete_windows",
            "background": 0}


def test_independent_optima_are_not_optimal_under_a_narrow_count_width():
    comps = _label_with_triples(256)
    mvp_payload = sum(rm.dp_lowest_bit(c)[0] for c in comps)
    assert mvp_payload == 256 * PIN_COST  # every component's own optimum is its pin
    mvp_total = _total(mvp_payload, max_count=256)  # P = 256 -> w_N = 2
    # coupled alternative: one component uses three singletons -> P = 255, Q = 3 -> w_N = 1
    alt_total = _total(255 * PIN_COST + 3 * SINGLE_COST, max_count=255)
    assert alt_total < mvp_total
    # => the MVP certificate is valid only for the count-unconstrained (safe width) model
    assert cvf.verify_scope(_scope("wD1-wNsafe", 12), _scope("wD1-wNsafe", 12)) == []


def test_compact_header_shift_is_valid_but_scope_mixing_is_rejected():
    comps = _label_with_triples(10)
    lb_payload = sum(rm.dual_ascent(c)[1] for c in comps)
    opt_payload = sum(rm.dp_lowest_bit(c)[0] for c in comps)
    assert lb_payload <= opt_payload
    h_safe, h_compact = 2 * OTHER_LABELS * 2, 2 * OTHER_LABELS * 1
    # 39.1: only the count header changes and the compact solution fits (max count 10),
    # so unrestricted payload LB + compact header bounds the compact model from below.
    assert lb_payload + h_compact <= opt_payload + h_compact
    # Mixing models inverts the bound: a safe-header LB exceeds the compact-header UB.
    assert lb_payload + h_safe > opt_payload + h_compact
    problems = cvf.verify_scope(_scope("wD1-wN1", h_compact), _scope("wD1-wNsafe", h_safe))
    assert any("regime_id" in p for p in problems) and any("header_bytes" in p for p in problems)
