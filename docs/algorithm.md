# CAPE algorithm and implementation

Native core: `cpp/` (C++20, g++ -O3), exposed as `cape._cape_native.encode(labels_xyz_f, options)`.

## Pipeline

1. **Scan** (bridge): max label → stored width `w_L`; `pixel_pairs` → upstream pins/flat rule and
   crack format (`IMPERMISSIBLE` iff pairs ≥ V/2).
2. **Format decision** (`format_policy`): `same_as_stock` (primary; pins only where upstream would
   use pins), `force_pins` (panel A), `min_exact` (secondary: exact min of flat and CAPE pins).
   FLAT streams are produced by upstream code and are byte-identical to stock.
3. **Boundary payload** (bridge): upstream crack codes (+ Markov model when order > 0).
4. **CC labeling** (bridge): upstream per-slice CCs, global ids, per-slice CC crc32c.
5. **Runs**: maximal same-label z-runs per column, computed slice by slice (contiguous reads).
6. **Depth regimes**: full width `width(Z−1)` first, then narrower regimes (only when Z > 256).
   For each regime: candidates `(run, offset, length)` (no materialized CC lists), memory forecast
   (exceeding the cap → `OOM_PREVENTED`, never silent pruning).
7. **Reductions**: singleton dominance → equal coverage (hash buckets + exact chain comparison) →
   proper-subset dominance via the CC→candidate CSR (bounded by `subset_checks_total`; when the
   budget ends, remaining candidates are simply kept).
8. **Components**: union-find over CCs connected by surviving candidates; numbered by smallest CC.
9. **Pass 1** (every component): greedy UB, integer dual LB + feasibility self-check.
10. **Background**: argmax of label UB (ties: larger LB, then smaller label).
11. **Pass 2** (written labels only, components with UB > LB, largest gap first): exact DP when
    `n ≤ exact_max_cc` and the transition forecast fits; otherwise (or after budget exhaustion)
    local search. Every accepted selection is re-checked as a cover.
12. **Compaction**: `w_N = width(max_ℓ max(P_ℓ, Q_ℓ))`, `w_D = width(max chosen depth)`.
13. **Serialize** explicit records (strict overflow checks) and assemble the stream exactly like
    `crackle::compress_helper`; the byte model must equal the serialized length (checked).

## Data structures and complexity

- `Run {col, z0, len, label}`; `Candidate {run, off, len}` — a candidate's CC at offset `t` is
  `cc[col + XY·(z0 + off + t)]`.
- Incidence `E = Σ |S_p|`: `E = V` when `h ≥ Z`; up to `O(V·h)` for windowed regimes (forecast first).
- Time: CC labeling and runs `O(V)`; hashing `O(E)`; subset dominance bounded by its check budget;
  greedy `O(E log M)`; dual `O(E + N)`; DP `O(2^n · deg)` per small component.
- Memory forecast: `4V + 16R + 40M + 32N + 8E` bytes.

## Determinism

No randomness, no wall-clock budgets inside the encoder: identical input and options give
identical bytes (`test_encoding_is_deterministic`). Ties are broken by start index/depth/CC id.

## Methods built from the same core

| Method | Options |
|---|---|
| `cape_m0`, `cape_m5` | full CAPE, stock pins/flat rule, Markov 0/5 |
| `cape_core` | full CAPE, forced pins (panel A) |
| `weighted_greedy` | no reductions, no DP, no local search |
| `greedy_local` | no reductions, no DP, local search |
| `stock_cover` | `selector=stock_greedy`: upstream selection + serializer, forced pins |
| ablations | `cape_no_dedup`, `cape_no_dominance`, `cape_no_exact`, `cape_no_local`, `cape_no_dual_gate`, `cape_stock_background`, `cape_fixed_depth_width`, `cape_maximal_runs_only` |

## Diagnostics returned per encode

Candidate counts before/after each reduction, incidences, components and size histogram
(CC-weighted), component statuses (trivial / LB-tight / exact DP / heuristic), exact CC and cost
fractions, DP transitions, local-search checks, per-phase nanoseconds, widths, P, Q, background,
UB/LB bytes and the certificate scope string.
