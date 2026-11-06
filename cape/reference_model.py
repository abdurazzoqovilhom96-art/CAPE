"""Pure-Python reference model of CAPE (spec sections 4-13). TEST ORACLE ONLY.

Small, direct implementations used to validate the native core: CC labeling identical to
upstream, column runs, depth-window candidates (section 7), safe reductions (section 8),
components (section 9), exact bitmask DP (section 10), deterministic weighted greedy
(sections 5, 11), integer dual ascent (section 12) and background bounds (section 13).
Production code never imports this module on a timed path.

Conventions: canonical arrays are (Z, Y, X); a pin is (label, y, x, z0, length) and covers the
global CC ids cc[z0:z0+length, y, x]; its upstream start index is x + X*(y + Y*z0) and its
depth is length - 1.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Iterable, Sequence

import numpy as np

INF = float("inf")


# --------------------------------------------------------------------------- CCs

def cc_label(zyx: np.ndarray) -> tuple[np.ndarray, list[int], int]:
    """Per-slice 2D 4-connected labeling; components numbered by first raster occurrence
    (x fastest), global ids increasing with z. Identical to upstream cc3d (tested)."""
    from scipy import ndimage

    Z, Y, X = zyx.shape
    cc = np.empty(zyx.shape, dtype=np.int64)
    per_slice: list[int] = []
    offset = 0
    four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    for z in range(Z):
        sl = zyx[z]
        comp = np.zeros((Y, X), dtype=np.int64)
        nxt = 0
        for v in np.unique(sl):
            lab, n = ndimage.label(sl == v, structure=four)
            m = lab > 0
            comp[m] = lab[m] + nxt
            nxt += n
        flat = comp.ravel()
        uniq, first = np.unique(flat, return_index=True)
        rank = np.empty(len(uniq), dtype=np.int64)
        rank[np.argsort(first, kind="stable")] = np.arange(len(uniq))
        cc[z] = rank[np.searchsorted(uniq, flat)].reshape(Y, X) + offset
        per_slice.append(len(uniq))
        offset += len(uniq)
    return cc, per_slice, offset


def cc_label_values(zyx: np.ndarray, cc: np.ndarray, n: int) -> np.ndarray:
    lab = np.empty(n, dtype=np.uint64)
    lab[cc.ravel()] = zyx.ravel()
    return lab


# ------------------------------------------------------------------- runs / pins

@dataclass(frozen=True, order=True)
class Pin:
    label: int
    y: int
    x: int
    z0: int
    length: int

    @property
    def depth(self) -> int:
        return self.length - 1

    def start_index(self, X: int, Y: int) -> int:
        return self.x + X * (self.y + Y * self.z0)


def column_runs(zyx: np.ndarray) -> list[Pin]:
    """Maximal same-label z-runs of every (y, x) column, in raster order (y, then x)."""
    Z, Y, X = zyx.shape
    runs: list[Pin] = []
    for y in range(Y):
        for x in range(X):
            col = zyx[:, y, x]
            z0 = 0
            for z in range(1, Z + 1):
                if z == Z or col[z] != col[z0]:
                    runs.append(Pin(int(col[z0]), y, x, z0, z - z0))
                    z0 = z
    return runs


def depth_windows(runs: Iterable[Pin], h: int) -> list[Pin]:
    """Section 7 family: whole run if length <= h, else every length-h window."""
    out: list[Pin] = []
    for r in runs:
        if r.length <= h:
            out.append(r)
        else:
            out.extend(Pin(r.label, r.y, r.x, r.z0 + s, h) for s in range(r.length - h + 1))
    return out


def all_subsegments(runs: Iterable[Pin], h: int) -> list[Pin]:
    """Every valid pin (sub-segment of a run with length <= h): the full family."""
    out: list[Pin] = []
    for r in runs:
        for s in range(r.length):
            for ln in range(1, min(h, r.length - s) + 1):
                out.append(Pin(r.label, r.y, r.x, r.z0 + s, ln))
    return out


def coverage(cc: np.ndarray, p: Pin) -> tuple[int, ...]:
    return tuple(int(v) for v in cc[p.z0:p.z0 + p.length, p.y, p.x])


# ------------------------------------------------------------------- cover model

@dataclass
class CoverModel:
    """Weighted set cover of one label's CCs by pins and singletons (spec (1)-(2))."""

    label: int
    universe: tuple[int, ...]  # sorted CC ids
    pins: list[tuple[Pin, frozenset]]
    pin_cost: int
    single_cost: int
    log: list[str] = field(default_factory=list)

    def copy(self) -> "CoverModel":
        return CoverModel(self.label, self.universe, list(self.pins), self.pin_cost, self.single_cost, list(self.log))

    def cost(self, pins: Sequence[Pin], singles: Iterable[int]) -> int:
        return self.pin_cost * len(pins) + self.single_cost * len(set(singles))

    def is_cover(self, pins: Sequence[tuple[Pin, frozenset]] | Sequence[frozenset], singles: Iterable[int]) -> bool:
        covered = set(singles)
        for item in pins:
            covered |= item[1] if isinstance(item, tuple) else item
        return set(self.universe) <= covered


def build_models(zyx: np.ndarray, cc: np.ndarray, candidates: Iterable[Pin], pin_cost: int,
                 single_cost: int) -> dict[int, CoverModel]:
    n = int(cc.max()) + 1 if cc.size else 0
    lab = cc_label_values(zyx, cc, n)
    universes: dict[int, list[int]] = {}
    for u in range(n):
        universes.setdefault(int(lab[u]), []).append(u)
    models = {L: CoverModel(L, tuple(us), [], pin_cost, single_cost) for L, us in universes.items()}
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        models[p.label].pins.append((p, frozenset(coverage(cc, p))))
    for m in models.values():
        m.pins.sort(key=lambda t: t[0])
    return models


# -------------------------------------------------------------------- reductions

def pin_tie_key(p: Pin, X: int, Y: int) -> tuple[int, int]:
    return (p.start_index(X, Y), p.depth)


def reduce_equal_coverage(m: CoverModel, X: int, Y: int,
                          hash_fn: Callable[[frozenset], int] = hash) -> CoverModel:
    """8.1 + 39.8: one deterministic representative per identical coverage (equal costs).
    Buckets by hash, then confirms true equality, so collisions never merge distinct sets."""
    out = m.copy()
    buckets: dict[int, list[tuple[Pin, frozenset]]] = {}
    for item in m.pins:
        buckets.setdefault(hash_fn(item[1]), []).append(item)
    kept: list[tuple[Pin, frozenset]] = []
    removed = 0
    for items in buckets.values():
        classes: list[list[tuple[Pin, frozenset]]] = []
        for it in items:
            for cls in classes:
                if cls[0][1] == it[1]:
                    cls.append(it)
                    break
            else:
                classes.append([it])
        for cls in classes:
            rep = min(cls, key=lambda t: pin_tie_key(t[0], X, Y))
            kept.append(rep)
            removed += len(cls) - 1
    out.pins = sorted(kept, key=lambda t: t[0])
    out.log.append(f"equal_coverage removed {removed}")
    return out


def reduce_subset(m: CoverModel) -> CoverModel:
    """8.2: drop p if S_p is a proper subset of some S_q (all pins share one cost)."""
    out = m.copy()
    kept = [p for p in m.pins if not any(p[1] < q[1] for q in m.pins)]
    out.log.append(f"subset removed {len(m.pins) - len(kept)}")
    out.pins = kept
    return out


def reduce_singleton(m: CoverModel) -> CoverModel:
    """8.3: drop p if c_p >= sum of its singleton costs."""
    out = m.copy()
    kept = [p for p in m.pins if m.pin_cost < len(p[1]) * m.single_cost]
    out.log.append(f"singleton removed {len(m.pins) - len(kept)}")
    out.pins = kept
    return out


def reduce_all(m: CoverModel, X: int, Y: int) -> CoverModel:
    return reduce_subset(reduce_singleton(reduce_equal_coverage(m, X, Y)))


# -------------------------------------------------------------------- components

def components(m: CoverModel) -> list[CoverModel]:
    """Connected components of the CC-pin incidence graph (section 9)."""
    parent = {u: u for u in m.universe}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for _, s in m.pins:
        it = iter(s)
        first = next(it)
        for u in it:
            ra, rb = find(first), find(u)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for u in m.universe:
        groups.setdefault(find(u), []).append(u)
    comps = []
    for root in sorted(groups):
        us = tuple(sorted(groups[root]))
        uset = set(us)
        pins = [p for p in m.pins if next(iter(p[1])) in uset]
        comps.append(CoverModel(m.label, us, pins, m.pin_cost, m.single_cost))
    return comps


# ----------------------------------------------------------------- exact solvers

def _actions(m: CoverModel) -> tuple[list[int], list[int], list[object]]:
    index = {u: i for i, u in enumerate(m.universe)}
    masks, costs, ids = [], [], []
    for p, s in m.pins:
        masks.append(sum(1 << index[u] for u in s))
        costs.append(m.pin_cost)
        ids.append(p)
    for u in m.universe:
        masks.append(1 << index[u])
        costs.append(m.single_cost)
        ids.append(("single", u))
    return masks, costs, ids


def brute_force(m: CoverModel) -> tuple[int, list[object]]:
    masks, costs, ids = _actions(m)
    full = (1 << len(m.universe)) - 1
    best, best_sel = INF, []
    for r in range(len(masks) + 1):
        for comb in itertools.combinations(range(len(masks)), r):
            acc = 0
            for i in comb:
                acc |= masks[i]
            if acc == full:
                c = sum(costs[i] for i in comb)
                if c < best:
                    best, best_sel = c, [ids[i] for i in comb]
        if best < INF and r * min(costs, default=0) > best:
            break
    return int(best), best_sel


def dp_plain(m: CoverModel) -> tuple[int, int]:
    """Spec (6) verbatim: relax every action from every reachable mask in increasing order.
    Returns (optimum, transitions)."""
    masks, costs, _ = _actions(m)
    n = len(m.universe)
    full = (1 << n) - 1
    D = [INF] * (full + 1)
    D[0] = 0
    transitions = 0
    for t in range(full + 1):
        if D[t] == INF:
            continue
        for mk, c in zip(masks, costs):
            t2 = t | mk
            if t2 != t:
                transitions += 1
                if D[t] + c < D[t2]:
                    D[t2] = D[t] + c
    return int(D[full]), transitions


def dp_lowest_bit(m: CoverModel) -> tuple[int, list[object], int]:
    """Exact DP used by the native core: from mask t only actions covering the lowest
    uncovered element are relaxed (every cover can be ordered that way). Returns
    (optimum, selection, transitions)."""
    masks, costs, ids = _actions(m)
    n = len(m.universe)
    full = (1 << n) - 1
    by_bit: list[list[int]] = [[] for _ in range(n)]
    for a, mk in enumerate(masks):
        for b in range(n):
            if mk >> b & 1:
                by_bit[b].append(a)
    D = [INF] * (full + 1)
    pred: list[tuple[int, int]] = [(-1, -1)] * (full + 1)
    D[0] = 0
    transitions = 0
    for t in range(full):
        if D[t] == INF:
            continue
        low = (~t & (t + 1)).bit_length() - 1
        for a in by_bit[low]:
            t2 = t | masks[a]
            transitions += 1
            if D[t] + costs[a] < D[t2]:
                D[t2] = D[t] + costs[a]
                pred[t2] = (t, a)
    sel = []
    t = full
    while t:
        t_prev, a = pred[t]
        sel.append(ids[a])
        t = t_prev
    return int(D[full]), sel, transitions


# ------------------------------------------------------------------------ greedy

def greedy(m: CoverModel, X: int, Y: int) -> tuple[int, list[Pin], list[int]]:
    """Deterministic weighted greedy (spec 5/11): minimize cost/new_covered (exact rational
    comparison), ties by (cost, kind, start index or CC id, depth) with singletons (kind 0)
    before pins (kind 1): a pin is taken only when its ratio is strictly below the singleton
    cost. Then redundant records are removed in reverse selection order."""
    uncovered = set(m.universe)
    heap: list[tuple[Fraction, tuple, int]] = []
    items: list[tuple[str, object, frozenset, int]] = []
    for p, s in m.pins:
        items.append(("pin", p, s, m.pin_cost))
    for u in m.universe:
        items.append(("single", u, frozenset((u,)), m.single_cost))

    def key(i: int) -> tuple:
        kind, obj, _s, c = items[i]
        if kind == "pin":
            return (c, 1, obj.start_index(X, Y), obj.depth)
        return (c, 0, obj, 0)

    for i, (_k, _o, s, c) in enumerate(items):
        heapq.heappush(heap, (Fraction(c, len(s)), key(i), i))
    chosen: list[int] = []
    while uncovered:
        ratio, k, i = heapq.heappop(heap)
        new = len(items[i][2] & uncovered)
        if new == 0:
            continue
        cur = Fraction(items[i][3], new)
        if cur != ratio:
            heapq.heappush(heap, (cur, k, i))
            continue
        chosen.append(i)
        uncovered -= items[i][2]
    # redundancy elimination
    count: dict[int, int] = {}
    for i in chosen:
        for u in items[i][2]:
            count[u] = count.get(u, 0) + 1
    final = []
    for i in reversed(chosen):
        if all(count[u] >= 2 for u in items[i][2]):
            for u in items[i][2]:
                count[u] -= 1
        else:
            final.append(i)
    pins = sorted(items[i][1] for i in final if items[i][0] == "pin")
    singles = sorted(items[i][1] for i in final if items[i][0] == "single")
    return m.cost(pins, singles), pins, singles


# --------------------------------------------------------------------- dual bound

def dual_ascent(m: CoverModel, q: int = 1 << 20) -> tuple[dict[int, int], int]:
    """Integer dual ascent (section 12) in increasing CC id order. Returns (a_u, LB_int)."""
    slack = {p: q * m.pin_cost for p, _ in m.pins}
    incident: dict[int, list[Pin]] = {}
    for p, s in m.pins:
        for u in s:
            incident.setdefault(u, []).append(p)
    a: dict[int, int] = {}
    for u in m.universe:
        delta = q * m.single_cost
        for p in incident.get(u, ()):
            delta = min(delta, slack[p])
        a[u] = delta
        for p in incident.get(u, ()):
            slack[p] -= delta
    total = sum(a.values())
    return a, -(-total // q)


# ------------------------------------------------------------- background bounds

def background_bounds(U: dict[int, int], L: dict[int, int], H: int) -> tuple[int, int, int]:
    """Spec (8): (UB_all, LB_all, background candidate = argmax U, smallest label on ties)."""
    b = min(U, key=lambda k: (-U[k], k))
    ub = H + sum(U.values()) - U[b]
    lb = H + sum(L.values()) - max(L.values())
    return ub, lb, b
