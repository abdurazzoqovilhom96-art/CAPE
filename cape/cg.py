"""B protocol (docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md): exact window pricing, integer dual certificate and a
bounded column-generation (CG) prototype for CAPE's per-regime set-cover model over the CompleteWindows family.

Prototype only (Python + numpy + scipy/HiGHS). It never runs on the encoder path and never writes streams.

Model (certificate_model.md section 2), one fixed regime:
  * a run = maximal same-label z-interval of one column (x, y); CCs along it are distinct (one 2D CC per slice);
  * candidates (CompleteWindows): R <= h -> the whole run; R > h -> every length-h window;
  * pin cost c = w_I + w_D(regime), singleton cost s = w_C; background CCs are not covered;
  * a run is useful only if min(R, h) * s > c (otherwise every window is singleton-dominated, as in the native
    singleton rule), so only useful runs enter the LP and the pricing.
Column-major chain layout: position = col * Z + z with col = x + X * y (the native colmajor buffer)."""
from __future__ import annotations

import heapq
import threading
import time

import numpy as np

Q_SCALE = 1 << 20  # same scale as cpp/src/dual_bound.cpp


# ------------------------------------------------------------------------------------------- pricing (one run)
def best_window(a, h: int):
    """Exact maximum window weight over the CompleteWindows family of one run.

    a: weights along the run (length R >= 1), integers (exact) or floats; h >= 1.
    Returns (W_max, t_star, length): R <= h -> the whole run (t = 0, length R); otherwise the length-h window with the
    largest prefix-sum difference, ties broken by the smallest start t."""
    a = np.asarray(a)
    R = int(a.shape[0])
    if R < 1 or h < 1:
        raise ValueError("best_window: need R >= 1 and h >= 1")
    if a.dtype.kind in "iu":
        a = a.astype(np.int64)
        if a.size and int(np.abs(a).max()) * R >= (1 << 62):
            raise OverflowError("best_window: int64 window sum could overflow")
    if R <= h:
        return a.sum(), 0, R
    P = np.concatenate((np.zeros(1, dtype=a.dtype), np.cumsum(a)))
    W = P[h:] - P[:-h]
    t = int(np.argmax(W))  # first maximum = smallest t
    return W[t], t, h


def enumerate_windows(a, h: int):
    """Brute-force oracle over the same family (for tests): list of (W, t, length)."""
    a = [int(v) if isinstance(v, (int, np.integer)) else float(v) for v in a]
    R = len(a)
    if R <= h:
        return [(sum(a), 0, R)]
    return [(sum(a[t:t + h]), t, h) for t in range(R - h + 1)]


def max_any_interval(a, h: int):
    """Brute force over EVERY interval of length 1..min(R, h) (the wider family of the dominance theorem)."""
    a = list(a)
    R = len(a)
    best = None
    for i in range(R):
        for ln in range(1, min(h, R - i) + 1):
            w = sum(a[i:i + ln])
            if best is None or w > best:
                best = w
    return best


# --------------------------------------------------------------------------------- pricing (many runs at once)
def price_runs(weights: np.ndarray, starts: np.ndarray, lens: np.ndarray, h: int):
    """Vectorized best_window for many runs laid out in one chain array.

    weights: per chain position (int64 for exact integer pricing, float64 for LP pricing);
    starts/lens: run start positions and lengths (runs must not overlap). Returns (W_max, t_star) per run."""
    P = np.concatenate((np.zeros(1, dtype=weights.dtype), np.cumsum(weights)))
    n = starts.shape[0]
    W = np.zeros(n, dtype=weights.dtype)
    T = np.zeros(n, dtype=np.int64)
    short = lens <= h
    if short.any():
        W[short] = P[starts[short] + lens[short]] - P[starts[short]]
    lng = np.flatnonzero(~short)
    if lng.size:
        win = P[h:] - P[:-h]  # window weight starting at every chain position
        cnt = (lens[lng] - h + 1).astype(np.int64)
        seg = np.concatenate(([0], np.cumsum(cnt)[:-1]))
        idx = np.repeat(starts[lng].astype(np.int64), cnt) + (np.arange(int(cnt.sum())) - np.repeat(seg, cnt))
        vals = win[idx]
        mx = np.maximum.reduceat(vals, seg)
        pos = np.where(vals == np.repeat(mx, cnt), np.arange(vals.shape[0]), np.iinfo(np.int64).max)
        W[lng] = mx
        T[lng] = np.minimum.reduceat(pos, seg) - seg
    return W, T


# ------------------------------------------------------------------------------------------- instance building
def cc2d_python(labels_zyx: np.ndarray) -> np.ndarray:
    """Reference 2D 4-connected CC per slice (equal labels), ids in z-major raster order of first pixel.
    Small volumes only (tests)."""
    Z, Y, X = labels_zyx.shape
    cc = -np.ones((Z, Y, X), dtype=np.int64)
    nxt = 0
    for z in range(Z):
        for y in range(Y):
            for x in range(X):
                if cc[z, y, x] >= 0:
                    continue
                v = labels_zyx[z, y, x]
                stack = [(y, x)]
                cc[z, y, x] = nxt
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < Y and 0 <= nx < X and cc[z, ny, nx] < 0 and labels_zyx[z, ny, nx] == v:
                            cc[z, ny, nx] = nxt
                            stack.append((ny, nx))
                nxt += 1
    return cc


def build_instance(labels_zyx: np.ndarray, cc_zyx: np.ndarray, background, h: int, c: int, s: int) -> dict:
    """Set-cover instance of one regime from a label volume and its 2D CC ids (any consistent numbering)."""
    Z, Y, X = labels_zyx.shape
    lab = np.ascontiguousarray(labels_zyx.transpose(1, 2, 0)).ravel()
    cc = np.ascontiguousarray(cc_zyx.transpose(1, 2, 0)).ravel().astype(np.int64)
    V = lab.shape[0]
    zpos = np.arange(V, dtype=np.int64) % Z
    brk = np.ones(V, dtype=bool)
    brk[1:] = (lab[1:] != lab[:-1]) | (zpos[1:] == 0)
    starts = np.flatnonzero(brk).astype(np.int64)
    lens = np.diff(np.append(starts, V)).astype(np.int64)
    run_label = lab[starts]
    n_cc = int(cc.max()) + 1 if V else 0
    cc_label = np.zeros(n_cc, dtype=lab.dtype)
    cc_label[cc] = lab
    is_bg_cc = cc_label == background if background is not None else np.zeros(n_cc, dtype=bool)
    useful = (np.minimum(lens, h) * s > c)
    if background is not None:
        useful &= run_label != background
    u_starts, u_lens = starts[useful], lens[useful]
    pos_mask = np.zeros(V, dtype=bool)
    if u_starts.size:
        d = np.zeros(V + 1, dtype=np.int64)
        np.add.at(d, u_starts, 1)
        np.add.at(d, u_starts + u_lens, -1)
        pos_mask = np.cumsum(d[:-1]) > 0
    in_lp = np.zeros(n_cc, dtype=bool)
    in_lp[cc[pos_mask]] = True
    row_of_cc = np.full(n_cc, -1, dtype=np.int64)
    row_of_cc[in_lp] = np.arange(int(in_lp.sum()))
    row_of_pos = np.where(pos_mask, row_of_cc[cc], -1)
    n_lp = int(in_lp.sum())
    n_nonbg = int((~is_bg_cc).sum())
    return {"Z": Z, "Y": Y, "X": X, "V": V, "h": int(h), "c": int(c), "s": int(s), "background": background,
            "n_runs": int(starts.shape[0]), "n_cc": n_cc, "n_nonbg_cc": n_nonbg, "n_lp": n_lp,
            "n_fixed_single": n_nonbg - n_lp, "starts": u_starts, "lens": u_lens, "row_of_pos": row_of_pos,
            "row_of_cc": row_of_cc, "cc_label": cc_label, "all_starts": starts, "all_lens": lens,
            "run_label": run_label}


def window_rows(inst: dict, run: int, t: int) -> np.ndarray:
    g = int(inst["starts"][run])
    ln = int(min(inst["lens"][run], inst["h"]))
    if inst["lens"][run] <= inst["h"]:
        t = 0
    return inst["row_of_pos"][g + t:g + t + ln]


def all_windows(inst: dict) -> list[np.ndarray]:
    """Explicit CompleteWindows family over the useful runs (small instances / tests), deduplicated by CC set."""
    seen, out = set(), []
    for r in range(inst["starts"].shape[0]):
        R, h = int(inst["lens"][r]), inst["h"]
        for t in ([0] if R <= h else range(R - h + 1)):
            rows = window_rows(inst, r, t)
            key = tuple(sorted(int(v) for v in rows))
            if key not in seen:
                seen.add(key)
                out.append(np.array(key, dtype=np.int64))
    return out


def all_intervals(inst: dict) -> list[np.ndarray]:
    """Every interval of length 1..min(R, h) inside every useful run (the wider family of the theorem)."""
    seen, out = set(), []
    for r in range(inst["starts"].shape[0]):
        g, R, h = int(inst["starts"][r]), int(inst["lens"][r]), inst["h"]
        for i in range(R):
            for ln in range(1, min(h, R - i) + 1):
                key = tuple(sorted(int(v) for v in inst["row_of_pos"][g + i:g + i + ln]))
                if key not in seen:
                    seen.add(key)
                    out.append(np.array(key, dtype=np.int64))
    return out


def components(inst: dict):
    """CC components of the LP rows: CCs that share a useful run (every window of a useful run links its CCs, so the
    union over the run's windows links the whole run). Returns (n_components, label per LP row)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = inst["n_lp"]
    if n == 0:
        return 0, np.zeros(0, dtype=np.int64)
    st, ln, rp = inst["starts"], inst["lens"], inst["row_of_pos"]
    cnt = ln - 1
    seg = np.concatenate(([0], np.cumsum(cnt)[:-1]))
    p = np.repeat(st, cnt) + (np.arange(int(cnt.sum())) - np.repeat(seg, cnt))
    a, b = rp[p], rp[p + 1]
    g = coo_matrix((np.ones(a.shape[0], dtype=np.int8), (a, b)), shape=(n, n))
    k, lab = connected_components(g, directed=False)
    return int(k), lab.astype(np.int64)


# ------------------------------------------------------------------------------------- exact set cover (tests)
def exact_opt(n: int, cols: list[np.ndarray], c: int, s: int, fixed_single: int = 0) -> int:
    """Exact integer optimum of min c*sum x + s*sum y s.t. every row covered (scipy.milp / HiGHS)."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csc_matrix, hstack, identity

    if n == 0:
        return s * fixed_single
    m = len(cols)
    if m:
        ind = np.concatenate(cols)
        ptr = np.concatenate(([0], np.cumsum([len(x) for x in cols])))
        A = hstack([csc_matrix((np.ones(ind.shape[0]), ind, ptr), shape=(n, m)), identity(n, format="csc")])
    else:
        A = identity(n, format="csc")
    cost = np.concatenate((np.full(m, c, dtype=float), np.full(n, s, dtype=float)))
    r = milp(cost, constraints=LinearConstraint(A, lb=np.ones(n), ub=np.inf), integrality=np.ones(m + n),
             bounds=Bounds(0, 1))
    if r.status != 0:
        raise RuntimeError(f"milp failed: {r.message}")
    return int(round(r.fun)) + s * fixed_single


# --------------------------------------------------------------------------------------- integer certificate
def int_feasible(inst: dict, a: np.ndarray, q: int = Q_SCALE) -> tuple[bool, int]:
    """Independent integer feasibility check of scaled duals over the FULL family (every window of every useful
    run): 0 <= a_u <= q*s and window sums <= q*c. Returns (ok, number of violating runs)."""
    if a.shape[0] != inst["n_lp"] or (a < 0).any() or (a > q * inst["s"]).any():
        return False, -1
    if inst["n_lp"] == 0:
        return True, 0
    w = np.where(inst["row_of_pos"] >= 0, a[np.maximum(inst["row_of_pos"], 0)], 0).astype(np.int64)
    W, _ = price_runs(w, inst["starts"], inst["lens"], inst["h"])
    nv = int((W > q * inst["c"]).sum())
    return nv == 0, nv


def integer_certificate(inst: dict, lam: np.ndarray | None, q: int = Q_SCALE, max_passes: int = 500) -> dict:
    """Floor-scale LP duals, repair every violated window deterministically (reduce from the window's last position),
    verify independently, then L = sum over components of ceil(sum a / q) + s * (CCs outside the LP)."""
    n, s, c, h = inst["n_lp"], inst["s"], inst["c"], inst["h"]
    a = np.zeros(n, dtype=np.int64) if lam is None else np.clip(np.floor(np.asarray(lam) * q), 0, q * s).astype(
        np.int64)
    passes, repaired = 0, 0
    if n:
        st, ln, rp = inst["starts"], inst["lens"], inst["row_of_pos"]
        cap = q * c
        while passes < max_passes:
            w = np.where(rp >= 0, a[np.maximum(rp, 0)], 0).astype(np.int64)
            W, T = price_runs(w, st, ln, h)
            passes += 1
            bad = np.flatnonzero(W > cap)
            if not bad.size:
                break
            for r in bad:
                rows = window_rows(inst, int(r), int(T[r]))
                excess = int(a[rows].sum()) - cap
                for u in rows[::-1]:
                    if excess <= 0:
                        break
                    d = min(int(a[u]), excess)
                    a[u] -= d
                    excess -= d
                repaired += 1
    ok, nv = int_feasible(inst, a, q)
    k, comp = components(inst)
    if n:
        sums = np.zeros(k, dtype=np.int64)  # a_u <= q*s < 2^24 and n < 2^32: no int64 overflow
        np.add.at(sums, comp, a)
        L_lp = int((-(-sums // q)).sum())  # exact integer ceil per component (each component OPT is an integer)
    else:
        L_lp = 0
    return {"a": a, "feasible": bool(ok), "violations": nv, "repair_passes": passes, "repaired_windows": repaired,
            "L": int(L_lp) + s * inst["n_fixed_single"] if ok else None, "n_components": k, "q": q}


# -------------------------------------------------------------------------------------------- column generation
class _Poll:
    """Polls the process RSS in a thread to bound the memory a call allocates (LP solve)."""

    def __init__(self, interval=0.005):
        import psutil
        self.p, self.iv, self.peak, self._stop = psutil.Process(), interval, 0, threading.Event()

    def __enter__(self):
        self.base = self.p.memory_info().rss
        self.peak = self.base
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self.p.memory_info().rss)
            time.sleep(self.iv)

    def __exit__(self, *exc):
        self._stop.set()
        self.t.join()
        self.peak = max(self.peak, self.p.memory_info().rss)

    @property
    def delta(self):
        return max(0, self.peak - self.base)


def _splitmix(x: np.ndarray) -> np.ndarray:
    z = x.astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


class ColumnPool:
    """Generated pin columns, deduplicated by CC set (M1a twins and equal-coverage windows are one column)."""

    def __init__(self):
        self.cols: list[np.ndarray] = []
        self.keys: dict[tuple, list[int]] = {}
        self.nnz = 0

    def add(self, rows: np.ndarray) -> bool:
        srt = np.sort(rows)
        key = (int(_splitmix(srt).sum(dtype=np.uint64)), int(srt.shape[0]), int(srt[0]))
        for j in self.keys.get(key, []):
            if np.array_equal(self.cols[j], srt):
                return False
        self.keys.setdefault(key, []).append(len(self.cols))
        self.cols.append(srt)
        self.nnz += int(srt.shape[0])
        return True


def _solve_lp(n: int, pool: ColumnPool, c: int, s: int, time_limit: float):
    from scipy.optimize import linprog
    from scipy.sparse import csc_matrix, hstack, identity

    m = len(pool.cols)
    ind = np.concatenate(pool.cols) if m else np.zeros(0, dtype=np.int64)
    ptr = np.concatenate(([0], np.cumsum([x.shape[0] for x in pool.cols]))) if m else np.zeros(1, dtype=np.int64)
    A = hstack([csc_matrix((np.ones(ind.shape[0]), ind, ptr), shape=(n, m)), identity(n, format="csc")]).tocsr()
    cost = np.concatenate((np.full(m, float(c)), np.full(n, float(s))))
    r = linprog(cost, A_ub=-A, b_ub=-np.ones(n), bounds=(0, None), method="highs",
                options={"time_limit": max(1.0, float(time_limit)), "presolve": True})
    lam = None
    if r.status == 0 and r.ineqlin is not None and r.ineqlin.marginals is not None:
        lam = np.clip(-np.asarray(r.ineqlin.marginals, dtype=float), 0.0, float(s))
    return r, lam


def integer_greedy(inst: dict, pool: ColumnPool) -> dict:
    """Deterministic weighted greedy over the generated columns + singletons, then redundant-pin removal."""
    n, c, s = inst["n_lp"], inst["c"], inst["s"]
    covered = np.zeros(n, dtype=bool)
    heap = [(-x.shape[0], j) for j, x in enumerate(pool.cols)]
    heapq.heapify(heap)
    chosen = []
    while heap:
        negk, j = heapq.heappop(heap)
        k = int((~covered[pool.cols[j]]).sum())
        if k != -negk:
            if k > 0:
                heapq.heappush(heap, (-k, j))
            continue
        if k * s <= c:
            break
        chosen.append(j)
        covered[pool.cols[j]] = True
    cnt = np.zeros(n, dtype=np.int64)
    for j in chosen:
        cnt[pool.cols[j]] += 1
    keep = []
    for j in reversed(chosen):  # redundant-pin removal (unique coverage k: drop when k*s < c)
        rows = pool.cols[j]
        uniq = int((cnt[rows] == 1).sum())
        if uniq * s < c:
            cnt[rows] -= 1
        else:
            keep.append(j)
    P = len(keep)
    Qn = int((cnt == 0).sum()) + inst["n_fixed_single"]
    return {"P": P, "Q": Qn, "U": P * c + Qn * s, "pins": sorted(keep)}


PRICE_SCALE = 1 << 30  # LP pricing scale (exact int64 sums; lambda <= s <= 8 and R <= 2^16 keep sums < 2^49)


def column_generation(inst: dict, budget_s: float = 1800.0, max_iter: int = 40, k_add: int = 50_000,
                      initial_cols: list[np.ndarray] | None = None, eps: float = 1e-6) -> dict:
    """Bounded CG: singletons + one window per useful run (t = 0) [+ optional initial columns]; full pricing pass
    per iteration; stop when no violated window (verified by the last full pass) or the budget ends."""
    t_start = time.perf_counter()
    n, c, s, h = inst["n_lp"], inst["c"], inst["s"], inst["h"]
    st, ln, rp = inst["starts"], inst["lens"], inst["row_of_pos"]
    pool = ColumnPool()
    for r in range(st.shape[0]):
        pool.add(window_rows(inst, r, 0))
    for x in initial_cols or []:
        pool.add(np.asarray(x, dtype=np.int64))
    hist, lam, lp_time, price_time, lp_rss = [], None, 0.0, 0.0, 0
    passes, converged, stop = 0, False, "max_iter"
    if n == 0:
        converged, stop = True, "empty"
    for it in range(max_iter if n else 0):
        left = budget_s - (time.perf_counter() - t_start)
        if left <= 1.0:
            stop = "budget"
            break
        t0 = time.perf_counter()
        with _Poll() as pl:
            res, lam_new = _solve_lp(n, pool, c, s, left)
        lp_time += time.perf_counter() - t0
        lp_rss = max(lp_rss, pl.delta)
        if lam_new is None:
            stop = f"lp_status_{res.status}"
            break
        lam = lam_new
        t0 = time.perf_counter()
        # exact integer pricing on floor(lambda * 2^30): float prefix sums over ~10^7 positions carry ~1e-7 rounding,
        # which would flag the many W == c windows of an LP optimum as violated; tolerance eps (absolute)
        wi = np.where(rp >= 0, np.floor(lam[np.maximum(rp, 0)] * PRICE_SCALE), 0).astype(np.int64)
        W, T = price_runs(wi, st, ln, h)
        passes += 1
        price_time += time.perf_counter() - t0
        viol = np.flatnonzero(W > c * PRICE_SCALE + int(eps * PRICE_SCALE))
        hist.append({"iter": it, "lp_obj": float(res.fun), "dual_sum": float(lam.sum()) + s * inst["n_fixed_single"],
                     "violating_runs": int(viol.size), "columns": len(pool.cols), "nnz": pool.nnz,
                     "lp_s": round(lp_time, 3)})
        if not viol.size:
            converged, stop = True, "converged"
            break
        order = viol[np.argsort(-(W[viol] - c * PRICE_SCALE), kind="stable")][:k_add]
        added = sum(pool.add(window_rows(inst, int(r), int(T[r]))) for r in order)
        if not added:
            stop = "no_new_columns"
            break
    t0 = time.perf_counter()
    ig = integer_greedy(inst, pool)
    int_time = time.perf_counter() - t0
    return {"converged": converged, "stop": stop, "iterations": len(hist), "pricing_passes": passes,
            "columns": len(pool.cols), "nnz": pool.nnz, "lp_time_s": lp_time, "pricing_time_s": price_time,
            "int_time_s": int_time, "lp_rss_bytes": int(lp_rss), "history": hist, "lam": lam, "integer": ig,
            "wall_s": time.perf_counter() - t_start, "pool": pool}
