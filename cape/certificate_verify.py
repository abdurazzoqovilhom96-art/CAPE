"""Independent certificate verifier (spec sections 12, 27, 39.1, 39.6). Shares no code with the
solvers: it recomputes everything it accepts from the model description and the witness.

A certificate states, for one label and one model scope:
    pins:        list of coverage sets (iterables of CC ids) of the candidate family it bounds
    universe:    CC ids that must be covered
    pin_cost, single_cost, q (fixed-point scale)
    witness:     {cc_id: a_u} integer dual values
    lb:          claimed lower bound (bytes)
    ub:          claimed upper bound (bytes) and optionally the records achieving it
    scope:       dict; UB and LB must name the same regime/header (39.1)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass
class VerifyResult:
    valid: bool
    lb_recomputed: int | None
    problems: list[str]


def verify_dual(universe: Iterable[int], pins: Iterable[Iterable[int]], pin_cost: int, single_cost: int,
                witness: Mapping[int, int], q: int, claimed_lb: int | None = None) -> VerifyResult:
    problems: list[str] = []
    uni = list(universe)
    uset = set(uni)
    if q <= 0:
        problems.append("q must be positive")
    for u, a in witness.items():
        if u not in uset:
            problems.append(f"witness has value for CC {u} outside the universe")
        if not isinstance(a, int):
            problems.append(f"a_{u} is not an integer")
        elif a < 0:
            problems.append(f"a_{u} < 0")
        elif a > q * single_cost:
            problems.append(f"a_{u} = {a} exceeds q*s_u = {q * single_cost}")
    for k, s in enumerate(pins):
        tot = 0
        for u in s:
            if u not in uset:
                problems.append(f"pin {k} covers CC {u} outside the universe")
                continue
            tot += int(witness.get(u, 0))
        if tot > q * pin_cost:
            problems.append(f"pin {k}: sum a_u = {tot} exceeds q*c_p = {q * pin_cost}")
    total = sum(int(witness.get(u, 0)) for u in uni)
    lb = -(-total // q) if q > 0 else None
    if claimed_lb is not None and lb is not None and claimed_lb > lb:
        problems.append(f"claimed LB {claimed_lb} > recomputed LB {lb}")
    return VerifyResult(not problems, lb, problems)


def verify_cover(universe: Iterable[int], pin_sets: Iterable[Iterable[int]], singles: Iterable[int],
                 pin_cost: int, single_cost: int, claimed_ub: int | None = None) -> VerifyResult:
    problems: list[str] = []
    pin_sets = [set(s) for s in pin_sets]
    singles = set(singles)
    covered = set(singles)
    for s in pin_sets:
        covered |= s
    missing = set(universe) - covered
    if missing:
        problems.append(f"{len(missing)} CCs uncovered (e.g. {sorted(missing)[:5]})")
    ub = pin_cost * len(pin_sets) + single_cost * len(singles)
    if claimed_ub is not None and claimed_ub != ub:
        problems.append(f"claimed UB {claimed_ub} != recomputed cost {ub}")
    return VerifyResult(not problems, ub, problems)


def verify_scope(ub_scope: Mapping, lb_scope: Mapping) -> list[str]:
    """39.1/T12: UB and LB are comparable only within one model (same regime, header
    accounting and candidate family)."""
    problems = []
    for k in ("regime_id", "header_bytes", "candidate_policy", "background"):
        if ub_scope.get(k) != lb_scope.get(k):
            problems.append(f"scope mismatch on {k}: UB {ub_scope.get(k)!r} vs LB {lb_scope.get(k)!r}")
    return problems


def relative_gap(ub: int, lb: int) -> float | None:
    """Spec (7): (UB-LB)/LB, None when LB == 0 (absolute gap reported instead)."""
    if lb <= 0:
        return None
    return (ub - lb) / lb
