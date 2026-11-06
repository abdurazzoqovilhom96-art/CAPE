# Mathematics of CAPE-Pins

All statements are for the pinned Crackle v1 PINS_VARIABLE_WIDTH format (docs/format_audit.md).
Each is checked by tests (named in brackets); the tests do not replace the proofs.

## 1. Model

Volume `L` on `Ω = X×Y×Z`. CCs are the upstream per-slice 4-connected components (global ids,
increasing with z) [`test_cc_labeling_equals_upstream`]. For a regime `θ = (w_D, w_N, w_C)`
with fixed `w_L, w_I = width(V), w_G = width(XY)`, formula (3) is exact
[`test_pins_section_parse_serialize_formula3`]:

```
B_label(θ) = H(θ) + Σ_{ℓ≠b} ( (w_I + w_D)·P_ℓ + w_C·Q_ℓ ),
H(θ) = w_L + 8 + Z·w_G + 1 + (K−1)(w_L + 2 w_N).
```

For fixed θ and background `b`, each written label ℓ is an independent weighted set cover:
cover the CCs `U_ℓ` by pins (cost `c = w_I + w_D`, a pin covers the CCs it crosses in one
same-label z-run of one column) or singletons (cost `s = w_C`), (1)–(2). Uniform costs inside a
regime are what make the reductions below exact.

Upstream width facts used later: `w_I ≥ w_C` (N ≤ V), so `c = w_I + w_D > s`.

## 2. Depth-bounded complete windows (spec §7)

`h = min(Z, 2^{8 w_D})` is the longest admissible pin (depth `d ≤ 2^{8w_D} − 1`). Family `F_h`:
a run of length `k ≤ h` → the whole run; `k > h` → all `k − h + 1` windows of length `h`.

**Theorem.** With length-independent pin cost, `OPT(F_h) = OPT(all valid sub-segments of length ≤ h)`.
*Proof.* Any valid pin `q` lies in one maximal run (pins never cross another ID or a gap). If
`k ≤ h` the run contains `q`; if `k > h`, `|q| ≤ h` so some length-`h` window of the run contains
`q`. Replace `q` by that member `p` of `F_h`: `S_q ⊆ S_p`, equal cost, same label. Optimal value
cannot increase; `F_h` is a subset of the valid pins, so it cannot decrease. ∎
[`test_section34_windows_and_dominance_keep_optimum` (240 cases), `test_exhaustive_1d_runs`,
`test_property_windows_equal_full_family`].

Note: for `Z ≤ 256`, `w_D = 1` already admits every run, so `F_h` = maximal runs and the
depth-regime mechanism is **not exercised** (spec §39.2).

## 3. Safe reductions (spec §8, §39.8)

All pins of a regime cost `c`.

1. **Singleton dominance**: if `c ≥ |S_p|·s`, replacing `p` by singletons of `S_p` never costs
   more. Remove `p`.
2. **Equal coverage**: among pins with identical coverage keep one deterministic representative
   (smallest start index). Buckets are formed by a 64-bit hash, but members are merged only after
   an element-wise chain comparison, so a hash collision cannot merge different sets
   [`test_forced_hash_collision_never_merges_distinct_coverage`]. Two equal pins never remove each
   other [`test_equal_coverage_keeps_exactly_one_representative`].
3. **Proper-subset dominance**: if `S_p ⊂ S_q`, replace `p` by `q`. For column chains this means
   `q`'s z-range contains `p`'s and the CC ids agree on the overlap.

Each removal has a witness that is either "singletons" or a candidate with strictly larger or
equal-but-representative coverage; following witnesses strictly increases length (or ends at a
representative), so witness paths are acyclic and end at a surviving candidate. Hence every
cover of the original family maps to a cover of the reduced family of no larger cost: the
optimum is preserved [`test_each_reduction_keeps_optimum`]. The order singleton → equal → subset
yields the same surviving family as any other order (a subset of a singleton-dominated set is
singleton-dominated).

**Dual transfer.** If `a` is feasible for the reduced model it is feasible for every removed pin:
for a subset-dominated `p ⊂ q`, `Σ_{S_p} a ≤ Σ_{S_q} a ≤ q·c`; for a singleton-dominated `p`,
`Σ_{S_p} a ≤ |S_p|·q·s ≤ q·c`; equal coverage is identical. So the reduced-model lower bound is a
lower bound of the full family (spec §39.6).

## 4. Independent components (spec §9)

Components of the CC–pin incidence graph after reductions: no pin spans two components, so
(5) `OPT = Σ_j OPT_j` when the count width is not binding (fixed θ). With a narrow count width
the label's components are coupled through `max(P_ℓ, Q_ℓ) ≤ 2^{8w_N} − 1`; summing independent
optima is then not optimal — counterexample with 256 three-CC components
[`test_independent_optima_are_not_optimal_under_a_narrow_count_width`]. CAPE therefore solves
with a count-unconstrained (safe) width and compacts afterwards; the certificate scope says so.

## 5. Exact bitmask DP (spec §10)

Recurrence (6) over masks in increasing order is exact. CAPE relaxes, from each reachable mask
`t`, only actions covering the lowest uncovered CC `u(t)`. Exactness: every cover `A` can be
ordered so each applied action covers the lowest still-uncovered element (repeatedly pick an
action of `A` containing the current lowest uncovered CC); that ordered sequence is a path in the
restricted transition graph with the same cost. States and actions visited are subsets of the
plain recurrence's, so transitions never exceed (6) [`test_dp_matches_bruteforce_and_cpsat`].
Budgets: `n ≤ 20`, forecast `2^n·max_deg ≤ 5·10^7` per component, `2·10^8` per volume,
`12·2^n` bytes ≤ 64 MiB; counted in transitions (deterministic), never wall-clock.

## 6. Greedy and local search (spec §5, §11)

Greedy minimizes `cost/new` with exact integer cross-multiplication; ties by
`(cost, kind, start index | CC id, depth)` with singletons (kind 0) before pins (kind 1). With
uniform costs this equals: repeatedly take the pin with the most new CCs while `c < s·new`, then
singletons; redundant pins are removed in reverse order [`test_solve_abstract_matches_reference`].
Local search accepts a move only if the integer cost strictly decreases, so it terminates; it does
not certify optimality.

## 7. Integer dual lower bound (spec §12)

`a_u ≥ 0`, `Σ_{u∈S_p} a_u ≤ q·c`, `a_u ≤ q·s`. Summing coverage constraints weighted by
`a_u/q` gives `LB = ⌈Σ a_u / q⌉ ≤ OPT` (integer objective). The ascent processes CCs by
increasing id: `δ = min(q·s, min_{p∋u} slack_p)`.

**Fixed-point remark.** With integer costs every slack starts as a multiple of `q` and each `δ`
is a minimum of multiples of `q`, so all `a_u` stay multiples of `q`: the scale `q = 2^20` gives
exactly the same bound as `q = 1` [`test_v2_reference_checks` asserts this for 300 cases]. It is
kept for fidelity with the spec, not claimed as an accuracy gain. A corrupted witness is rejected
by the independent verifier [`test_verifier_rejects_corrupted_witness`].

## 8. Background without K re-solves (spec §13)

With `U_ℓ`, `L_ℓ` per label and a background-independent `H`:
`UB_all = H + ΣU − max U` (background = argmax U), `LB_all = H + ΣL − max L`.
Proof: for any background `b`, cost `≥ H + ΣL − L_b ≥ H + ΣL − max L`. CAPE picks the background
after pass 1 (greedy U), then refines only written labels, whose U can only decrease, so the
chosen label stays the argmax [`test_background_formula_matches_bruteforce`].

**Bounds reported.** `LB` is computed with `w_N = 1` (valid for every count width, since a wider
count field only adds bytes) and per depth regime; the global LB is the minimum over all evaluated
regimes (all of them for `depth_policy = full_width_first`). `UB` is the size of the stream
actually written. Mixing an LB of one header model with a UB of another is rejected
[`test_compact_header_shift_is_valid_but_scope_mixing_is_rejected`, acceptance T12].

## 9. Losslessness (spec §14)

Decoder semantics: every CC of a slice starts as the background; explicit CC ids are painted;
then each pin paints every CC its column crosses in `[z0, z0+depth]`. If the boundary payload is
unchanged (same CCs), every pin stays inside its own label's run, and every non-background CC is
covered by a pin or a singleton of its label, each voxel receives its CC's original label. CAPE
reuses upstream code for everything except the label section and checks every stream with the
original decoder [`test_cape_stream_is_lossless_with_original_decoders`].

## 10. Certificate scope (what is and is not claimed)

A certificate states: pins format, the candidate family, safe reductions, background chosen by (8),
count-unconstrained LB (`w_N ≥ 1`), and the depth regimes evaluated. It is **not** a claim of
optimality over every Crackle-compatible stream (e.g. the FLAT format, other CC numberings or a
coupled narrow count width are outside the model).
