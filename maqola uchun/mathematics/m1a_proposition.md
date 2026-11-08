# M1a: neighbour-column duplicate filter (proposition and proof)

Scope: the v3 implementation bit `kImplAdjDedup` (32), part of both E0 (impl_mask 575) and Eθ. M1a is not a new Q1
contribution. It is re-proved here because the Q1 task asks for the exact conditions under which it is valid
(task v3, section 5.1).

## 1. Objects (as implemented)
- **Volume.** `L : [0,X)×[0,Y)×[0,Z) → ℕ` holds the object IDs. Every value, including 0, is an ordinary label.
- **Columns.** Column index `col = x + X·y`.
- **2D components (CC).** For every slice z, the 4-connected components of equal-valued pixels. These come from
  upstream `crackle::cc3d::connected_components2d_4` (`vendor/crackle/src/cc3d.hpp:299`). Every pixel `(x, y, z)` has
  a global CC id `cc(x, y, z)`, and CCs of different slices are disjoint.
- **Runs.** A run is a maximal z-interval of one column on which `L` is constant (`cpp/src/runs.cpp`). Its dense label
  index is `l` (`LabelMap.cc_label`).
- **Candidates.** A candidate pin `p = (col, z_s, len)` lies inside one run (`cpp/include/cape/candidates.hpp`).
  - If the run length is at most `h = min(Z, 2^(8·w_D))`, the whole run is the only candidate.
  - Otherwise (policy CompleteWindows) every window of length `h` is a candidate.
  - Its coverage is the chain `C_p = (cc(x, y, z_s), …, cc(x, y, z_s + len − 1))`.
  - Its cost is `c = w_I + w_D`, the same for every candidate of the regime.
  - Its upstream start index is `σ(p) = col + X·Y·z_s`.
- **Equal-coverage reduction** (`cpp/src/reductions.cpp:99-177`). Among candidates of one label with identical
  chains, only the member with the smallest `σ` is kept; ties are broken by candidate index.
  - The hash only groups candidates. Every group is confirmed by exact comparison, and collisions are resolved.
  - The kept set is sorted by candidate index, so it does not depend on the hash function.
- **Singleton dominance** removes `p` if `len·s ≤ c`, where `s = w_C` is the singleton cost. This depends on `len` only.

## 2. Proposition
Let `p = (col, z_s, len)` be a candidate with label `l` at `(x, y)`. Suppose the left column `(x−1, y)` (x > 0) or the
upper column `(x, y−1)` (y > 0) holds a candidate `q` with the same `z_s`, `len` and label `l`. Then:
1. `C_p = C_q`.
2. `σ(q) < σ(p)`.
3. Therefore `p` is never the representative kept by the equal-coverage reduction. Dropping `p` at generation time
   leaves the kept set unchanged. With it, every later step and every written byte is unchanged.

## 3. Proof
1. For every `z ∈ [z_s, z_s+len)`, the two pixels `(x, y, z)` and `(x−1, y, z)` (or `(x, y−1, z)`) both have value
   `l`, because both candidates lie inside runs of label `l`. They are 4-neighbours in slice z. The upstream labeling
   puts 4-neighbours with equal values into the same component (the B/C tests at `cc3d.hpp:336-405` join equal
   left/up neighbours; `relabel()` maps equivalent provisional labels to one id). So `cc(x, y, z) = cc(x', y', z)` for
   every z of the range, and the chains are equal element by element.
2. `σ(q) − σ(p) = −1` (left neighbour) or `−X` (upper neighbour), because `z_s` is equal.
3. Every equivalence class of the reduction is a set of candidates with equal chains. By 1, `p` and `q` are in the
   same class. By 2, `p` is not the smallest-`σ` member, so `p` is never its representative. If `q` itself is dropped
   by the same rule, the representative is a member with an even smaller `σ` (induction on `σ`).
   - Singleton dominance cannot separate them: it depends only on `len`, which is equal.
   - Subset dominance (`reductions.cpp:215+`) runs on the kept set only, which is unchanged.
   - Hence the set of class representatives is identical with and without the filter. The components, solver,
     records, serializer and stream receive identical input. ∎

## 4. Conditions that the code checks (`cpp/src/candidate_store.cpp:has_twin`)
| Condition | Why it is needed | Code |
|---|---|---|
| same label `l` | equal values make the neighbours join | `q.label != label → false` |
| same `z_s` and `len` | chains must be element-wise equal (not only overlapping) | `q.z0 == zs && q.len == len` (whole-run case) |
| `q` is itself a candidate | `q` must exist in the same candidate family (same `h`, same policy) | whole run with `len ≤ h`, or a length-`h` window of a longer run under CompleteWindows |
| same regime | `c` and `h` are per regime; the filter is applied inside `solve_regime` for one `w_D` | `make_candidates_dedup(runs, h, policy, …)` |
| `len·s > c` (survives singleton dominance) | a candidate removed by singleton dominance is removed in both paths | `emit()` checks the singleton rule first |

## 5. What the proposition does NOT claim
- It does not say that all candidates with equal chains are adjacent. Non-adjacent duplicates are still removed by the
  hash-based equal-coverage reduction.
- It does not depend on the hash function, the background choice, the count widths `w_N`, or the depth width written
  (`w_D` compaction happens after selection). These are global quantities computed from the kept set, which is
  unchanged.
- It applies to the upstream 2D **4-connected** labeling only. With 8-connectivity, diagonal neighbours would also
  join, and the rule would remain valid but incomplete.

## 6. Edge cases (tested)
- x = 0 or y = 0 (no left/upper neighbour): `has_left` / `has_up` are false, so nothing is dropped.
- Equal label but different z-range in the neighbour: not dropped (`tests/test_v3_invariants.py`, 360 random models,
  real crops).
- Label 0: treated like any other label.
- Forced hash collisions (`debug_hash_bits`): the kept set is unchanged (`tests/test_v3_invariants.py`).
- Evidence: byte identity of every v3 bit combination with the frozen v2.1 binary on synthetic, real and edge cases
  (`tests/test_v3_invariants.py`). The Q1 bits are compared with the frozen v3 binary (`tests/test_q1_invariants.py`).
