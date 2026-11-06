"""Bounded archive-objective pin refinement (plan v2, user task 2e).

Objective: J(S) = |zstd_level( Crackle_v1_stream(X; S) )| - the size of the COMPLETE stored file,
header, z-index, labels section, Markov model, crack codes and every CRC included. J is not
additive over pins, so raw-model dominance and the dual lower bound say nothing about it; this
module only makes deterministic, budgeted local moves and accepts a move only when the true J
strictly decreases. There is no optimality claim.

Start: the raw-optimal CAPE-FAST records S0 (valid cover). Moves (both keep every CC of every
written label covered, never cover a CC of another label, keep exact original IDs):
  * unpin  - replace pins by explicit CC ids for the CCs that no remaining pin of the same label
             covers. Pins are grouped by their raw byte change (k * w_C - (w_I + w_D)) and tried
             in cumulative bulk classes, cheapest first; then single pins of the next class.
  * anchor - move a pin to another column whose CC chain over the same z-range is identical (same
             coverage, same raw size) when that shortens the index deltas to its neighbours; tried
             in bulk, then by halves.
Every candidate is serialized with the exact Crackle rules, rebuilt into a full stream (header
length/crc8 and labels crc32c recomputed) and compressed; the first build must reproduce S0's
stream byte for byte (self-check), so the serializer cannot drift from the format.
The decoder is the unmodified stock Crackle decoder; nothing here is needed to decode.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from cape import crackle_format as cf

MOVES = ("unpin", "anchor")


@dataclass(frozen=True)
class RefineConfig:
    max_evals: int = 24            # complete-file evaluations (serialize + rebuild + compress)
    moves: tuple = MOVES
    unpin_classes: int = 6         # cumulative raw-cost classes tried in bulk
    anchor_scan_cap: int = 4096    # columns scanned per pin when looking for an identical chain
    anchor_max_props: int = 256    # anchor proposals kept (deterministic order)
    anchor_pin_limit: int = 2000   # pins scanned for anchors (labels ascending, pins by start)

    def __post_init__(self):
        bad = set(self.moves) - set(MOVES)
        if bad:
            raise ValueError(f"unknown refinement move(s) {sorted(bad)}")
        if self.max_evals < 0:
            raise ValueError("max_evals must be >= 0")


@dataclass
class RefineResult:
    stream: bytes
    wrapped: bytes
    stats: dict = field(default_factory=dict)


def _bw(x: int) -> int:
    return cf.byte_width(int(x))


def _le(arr, width: int, what: str) -> bytes:
    """Little-endian fixed-width bytes; uint64 label values above 2^63 are supported."""
    if not isinstance(arr, np.ndarray):  # Python ints: never let numpy guess (it picks float64 for >2^63 mixes)
        vals = [int(v) for v in arr]
        if any(v < 0 for v in vals):
            raise cf.FormatError(f"{what}: negative value")
        arr = np.array(vals, dtype=np.uint64)
    a = arr
    if a.size == 0:
        return b""
    if a.dtype.kind == "i":
        if int(a.min()) < 0:
            raise cf.FormatError(f"{what}: negative value")
        a = a.astype(np.uint64)
    elif a.dtype.kind != "u":
        a = np.array([int(v) for v in a.ravel()], dtype=np.uint64)
    if width < 8 and int(a.max()) >= (1 << (8 * width)):
        raise cf.FormatError(f"{what}: value does not fit in {width} byte(s)")
    return a.astype("<u8").view(np.uint8).reshape(-1, 8)[:, :width].tobytes()


class StreamBuilder:
    """Rebuilds a Crackle v1 pins stream around a new labels section (everything else kept)."""

    def __init__(self, stream: bytes):
        from cape import _cape_native as cn

        self._crc32c = cn.crc32c
        lay = cf.split_stream(stream)
        self.header = lay.header
        self.z_index = stream[lay.header.header_bytes: lay.labels_offset]
        self.tail = lay.markov_model + lay.crack_codes
        self.cc_crcs = np.asarray(lay.cc_crcs, dtype="<u4").tobytes()
        self._fields = {k: getattr(self.header, k) for k in self.header.__dataclass_fields__ if k != "crc"}

    def build(self, labels: bytes) -> bytes:
        h = cf.Header(**dict(self._fields, num_label_bytes=len(labels)))
        out = [h.to_bytes(), self.z_index, labels, self.tail]
        if self.header.format_version > 0:
            out += [int(self._crc32c(labels)).to_bytes(4, "little"), self.cc_crcs]
        return b"".join(out)


class Records:
    """Explicit records (per written label: pins (start, depth) and CC ids) + exact serializer."""

    def __init__(self, records: list[dict], bgcolor: int, comps: list[int], widths: dict):
        self.labels = [int(r["label"]) for r in records]
        self.pins = [np.asarray(r["pins"], dtype=np.int64).reshape(-1, 2) for r in records]
        self.singles = [np.asarray(r["singletons"], dtype=np.int64) for r in records]
        self.w_L, self.w_I, self.w_G, self.w_C = (int(widths[k]) for k in ("w_L", "w_I", "w_G", "w_C"))
        head = [_le([bgcolor], self.w_L, "bgcolor"), _le([len(self.labels)], 8, "num_labels"),
                _le(self.labels, self.w_L, "label"), _le(comps, self.w_G, "components_per_grid")]
        self._head = b"".join(head)

    def serialize(self, pins: list[np.ndarray], singles: list[np.ndarray]) -> bytes:
        P = max([len(p) for p in pins] + [len(s) for s in singles] + [0])
        D = max([int(p[:, 1].max()) for p in pins if len(p)] + [0])
        w_N, w_D = _bw(P), _bw(D)
        combined = cf._log2_width(w_N) | (cf._log2_width(w_D) << 2) | (cf._log2_width(self.w_C) << 4)
        parts = [self._head, bytes([combined])]
        for p, s in zip(pins, singles):
            if len(p):
                o = np.lexsort((p[:, 1], p[:, 0]))  # same order as sorted((start, depth) tuples)
                st, dp = p[o, 0], p[o, 1]
                parts += [_le([len(p)], w_N, "num_pins"), _le(np.diff(st, prepend=0), self.w_I, "pin index delta"),
                          _le(dp, w_D, "pin depth")]
            else:
                parts.append(_le([0], w_N, "num_pins"))
            ss = np.sort(s)
            parts += [_le([len(ss)], w_N, "num_cc"), _le(np.diff(ss, prepend=0), self.w_C, "cc id delta")]
        return b"".join(parts)


def _chains(pins: np.ndarray, ccz: np.ndarray, XY: int) -> list[np.ndarray]:
    """CC ids covered by each pin (column `start % XY`, slices z0 .. z0 + depth)."""
    out = []
    for start, depth in pins:
        col, z0 = int(start) % XY, int(start) // XY
        out.append(ccz[z0: z0 + int(depth) + 1, col].astype(np.int64))
    return out


def _sig(x: np.ndarray) -> np.ndarray:
    """Significant little-endian bytes of non-negative deltas (0 -> 1 byte)."""
    x = np.maximum(np.asarray(x, dtype=np.int64), 1)
    return (np.floor(np.log2(x)).astype(np.int64) // 8) + 1


def refine(pins_stream: bytes, records: list[dict], bgcolor: int, comps: list[int], widths: dict,
           cc_volume: np.ndarray, compress, cfg: RefineConfig) -> RefineResult:
    t0 = time.perf_counter_ns()
    Z, Y, X = cc_volume.shape
    XY = X * Y
    ccz = cc_volume.reshape(Z, XY)
    rec = Records(records, bgcolor, comps, widths)
    builder = StreamBuilder(pins_stream)
    stats = {"refine_evals": 0, "refine_unpin_applied": 0, "refine_anchor_applied": 0,
             "refine_unpin_candidates": 0, "refine_anchor_candidates": 0}

    cur_pins = [p.copy() for p in rec.pins]
    cur_singles = [s.copy() for s in rec.singles]
    first = builder.build(rec.serialize(cur_pins, cur_singles))
    if first != pins_stream:  # the exact serializer must reproduce S0; never refine on a mismatch
        raise cf.FormatError("refinement self-check failed: re-serialized CAPE records differ from the stream")
    best_raw = first
    t_z = time.perf_counter_ns()
    best_wrapped = compress(first)
    stats["refine_J0_zstd_ns"] = time.perf_counter_ns() - t_z
    stats["refine_setup_ns"] = t_z - t0
    stats["refine_J0"] = len(best_wrapped)

    stats["refine_eval_serialize_ns"] = 0
    stats["refine_eval_zstd_ns"] = 0

    def evaluate(pins, singles):
        nonlocal best_raw, best_wrapped
        stats["refine_evals"] += 1
        t_a = time.perf_counter_ns()
        raw = builder.build(rec.serialize(pins, singles))
        t_b = time.perf_counter_ns()
        w = compress(raw)
        stats["refine_eval_serialize_ns"] += t_b - t_a
        stats["refine_eval_zstd_ns"] += time.perf_counter_ns() - t_b
        if len(w) < len(best_wrapped):
            best_raw, best_wrapped = raw, w
            return True
        return False

    # original coverage per label: union of pin chains and explicit CC ids
    chains = [_chains(p, ccz, XY) for p in cur_pins]
    required = [np.union1d(np.concatenate(ch) if ch else np.empty(0, np.int64), s)
                for ch, s in zip(chains, cur_singles)]

    def apply_unpin(selected: set[tuple[int, int]]):
        pins, singles = [], []
        for li in range(len(cur_pins)):
            keep = [j for j in range(len(cur_pins[li])) if (li, j) not in selected]
            if len(keep) == len(cur_pins[li]):
                pins.append(cur_pins[li])
                singles.append(cur_singles[li])
                continue
            kept_cov = (np.concatenate([chains[li][j] for j in keep]) if keep else np.empty(0, np.int64))
            missing = np.setdiff1d(required[li], np.union1d(kept_cov, cur_singles[li]))
            pins.append(cur_pins[li][keep])
            singles.append(np.union1d(cur_singles[li], missing))
        return pins, singles

    if "unpin" in cfg.moves and cfg.max_evals > 0:
        props = []
        cost_pin = rec.w_I  # + w_D, identical for every pin of the stream: ordering only needs w_C k - w_I
        for li, (ch, s) in enumerate(zip(chains, cur_singles)):
            if not ch:
                continue
            allc = np.concatenate(ch)
            uniq, cnt = np.unique(np.concatenate([allc, s]), return_counts=True)
            for j, c in enumerate(ch):
                only = np.isin(c, uniq[cnt == 1])
                props.append((int(only.sum()) * rec.w_C - cost_pin, li, int(cur_pins[li][j, 0]), j))
        props.sort()
        stats["refine_unpin_candidates"] = len(props)
        classes = sorted({p[0] for p in props})[: cfg.unpin_classes]
        best_sel: set = set()
        for t in classes:
            if stats["refine_evals"] >= cfg.max_evals:
                break
            sel = {(li, j) for d, li, _, j in props if d <= t}
            if evaluate(*apply_unpin(sel)):
                best_sel = sel
        nxt = [(li, j) for d, li, _, j in props if (li, j) not in best_sel]
        for li, j in nxt:  # first-improvement single pins after the best class
            if stats["refine_evals"] >= cfg.max_evals:
                break
            if evaluate(*apply_unpin(best_sel | {(li, j)})):
                best_sel = best_sel | {(li, j)}
        if best_sel:
            cur_pins, cur_singles = apply_unpin(best_sel)
            stats["refine_unpin_applied"] = len(best_sel)
            chains = [_chains(p, ccz, XY) for p in cur_pins]

    if "anchor" in cfg.moves and stats["refine_evals"] < cfg.max_evals:
        props = []  # (gain, li, j, new_start)
        scanned = 0
        for li, p in enumerate(cur_pins):
            if len(p) < 2:
                continue
            if scanned >= cfg.anchor_pin_limit:
                break
            order = np.lexsort((p[:, 1], p[:, 0]))
            st = p[order, 0]
            for k, j in enumerate(order):
                scanned += 1
                if scanned > cfg.anchor_pin_limit:
                    break
                start, depth = int(p[j, 0]), int(p[j, 1])
                col, z0 = start % XY, start // XY
                chain = ccz[z0: z0 + depth + 1, col]
                fp = np.flatnonzero(ccz[z0] == chain[0])[: cfg.anchor_scan_cap]
                if fp.size < 2:
                    continue
                ok = np.all(ccz[z0: z0 + depth + 1][:, fp] == chain[:, None], axis=0)
                alts = fp[ok] + XY * z0
                lo = int(st[k - 1]) if k > 0 else 0
                hi = int(st[k + 1]) if k + 1 < len(st) else None
                alts = alts[(alts >= lo) & ((alts <= hi) if hi is not None else True)]
                if alts.size < 2:
                    continue
                cost = _sig(alts - lo) + (_sig(hi - alts) if hi is not None else 0)
                cur = int(_sig(np.array([start - lo]))[0] + (_sig(np.array([hi - start]))[0] if hi is not None else 0))
                b = int(np.argmin(cost))
                if int(cost[b]) < cur:
                    props.append((cur - int(cost[b]), li, int(j), int(alts[b])))
        props.sort(key=lambda t: (-t[0], t[1], t[2]))
        props = props[: cfg.anchor_max_props]
        stats["refine_anchor_candidates"] = len(props)

        def apply_anchor(sel):
            pins = [p.copy() for p in cur_pins]
            for _, li, j, ns in sel:
                pins[li][j, 0] = ns
            return pins

        accepted: list = []
        queue = [props] if props else []
        while queue and stats["refine_evals"] < cfg.max_evals:  # bulk first, then halves
            chunk = queue.pop(0)
            if evaluate(apply_anchor(accepted + chunk), cur_singles):
                accepted += chunk
            elif len(chunk) > 1:
                queue += [chunk[: len(chunk) // 2], chunk[len(chunk) // 2:]]
        if accepted:
            cur_pins = apply_anchor(accepted)
            stats["refine_anchor_applied"] = len(accepted)

    stats["refine_J"] = len(best_wrapped)
    stats["refine_ns"] = time.perf_counter_ns() - t0
    return RefineResult(best_raw, best_wrapped, stats)
