# CAPE v3 - mathematics of the new mechanisms

Notation follows `docs/mathematics.md`. Within one depth regime `r` every pin costs `c_r = w_I + w_D(r)` and every
singleton costs `s = w_C`. A candidate `j` covers the CC chain `C_j` (one CC per slice, consecutive z). The labels
section is

`B(r) = H + (K-1)(w_L + 2 w_N) + c P + s Q`, with `w_N`, the written depth width and the background chosen by the
selection (they are global terms; section 6 below treats them). Every statement is about the raw labels section;
zstd sizes are measured, never bounded.

## M1a - neighbour-column duplicate filter (byte-preserving)

**Lemma 1.** Let `p` be a candidate in column `(x, y)` with z-range `[z_s, z_s + l)` and dense label `L`. If column
`(x-1, y)` (or `(x, y-1)`) holds a candidate `q` with the same z-range and label `L`, then `C_p = C_q` and
`start(q) < start(p)`.

*Proof.* For every `z` in the range both voxels carry label `L` (each lies in a maximal same-label z-run of its column
that contains the range). They are 4-neighbours in slice `z`. Crackle labels 2D components per slice with
4-connectivity (`crackle::cc3d::connected_components2d_4`), so both voxels get the same CC id. Hence the two chains are
equal element by element. `start = x + X (y + Y z_s)`, so `start(q) = start(p) - 1` or `start(p) - X`. []

**Lemma 2.** The equal-coverage reduction keeps, in every class of equal coverage, exactly its smallest-start member.
Removing any set `D` of candidates such that every `p in D` has an equal-coverage partner with a smaller start index
leaves the kept set unchanged.

*Proof.* No class minimum is in `D` (it has no partner with a smaller start). Every class keeps its minimum, and the
minimum of a class is unchanged by removing non-minimal members. []

With windows (`h < run length`) the rule checks whether the neighbour run that contains `z_s` produces a candidate
with exactly `[z_s, z_s + l)`: a whole run when its length is `<= h` (same `z0`, same length), a length-`h` window
otherwise (complete-windows policy only). Singleton dominance depends only on `l`, so `p` and `q` are removed or kept
together. Everything downstream (subset dominance, components, solvers) receives the same `alive` set **in the same
relative order** (the filtered vector preserves candidate order), so local ids and every tie-break are unchanged.
Diagnostics that count work (hash collisions) may differ; diagnostics that describe the problem do not (tested).
The filter is O(R) with two monotone pointers per column; it is disabled when the equal-coverage reduction is off.

## M1b - component-ordered CSR (byte-preserving)

The CSR stores, for every surviving candidate in component order, its chain mapped to component-local ids
(local id = rank of the CC inside its component, ascending global id) and its tie keys. `build_local_model_csr`
copies the component's slices into reused buffers. It produces exactly the arrays of `build_local_model` (same CC
order, same candidate order `Components::cands`, same element order), and `finalize_incidence` is reproduced with a
reused position buffer; hence every solver input is identical. The chains are read once, in ascending candidate
order (sequential in the column-major buffer).

## M2 - eager greedy (byte-preserving)

Both greedies select, at each step, the eligible candidate maximising `(g_j, -start_j, -depth_j, -j)`, where `g_j` is
the number of still-uncovered CCs of `j` and eligibility is `c < s g_j` (uniform costs make `c/g` minimal iff `g`
maximal).

*Lazy (v2.1).* Heap entries carry upper bounds `f >= g_j` (g only decreases). A popped entry whose recount equals `f`
is a true maximum: any other candidate `q` with a larger true key has an entry with key `>= ` its true key, which
would have been popped first and refreshed.

*Eager (v3).* `g_j` is maintained exactly: when a CC is covered for the first time, `g` of every candidate containing
it is decremented (CC -> candidate incidence); each decrement that leaves the candidate eligible pushes a fresh entry;
an entry is valid iff its key equals the current `g_j` and `j` is not chosen. The popped valid entry is the true
maximum by construction. Hence both produce the same selection sequence; redundancy elimination is the same code, so
the `Selection` is identical. Work: every incidence is decremented at most once (`sum |C_j| = E` decrements) plus
`O(E log E)` heap operations; this bounds the greedy only, not the codec.

This is the bookkeeping that upstream Crackle issue #19 ("Faster Pin Encoding", 2024-07, closed as completed
2025-01) proposes ("store which pins are associated with a ccid ... count the number of valid ccids per pin"). M2 is
not a new idea; it is the same inversion applied to CAPE's weighted greedy.

## M5a / M5b - fused scan, batched CC labeling (byte-preserving)

M5a computes `max(label)` and the count of equal consecutive voxels in one pass; both are associative scans, results
identical. M5b calls exactly the upstream function `connected_components2d_4(slice, X, Y, 1, out, N, n_z)` that
`crackle::cc3d::connected_components` calls for each slice, with the same running start label `N`, computes the same
per-slice CRC of `cc - N`, and writes 16 slices at a time into `colmajor[col * Z + z]`. Ids, per-slice counts and
CRCs are therefore identical (they are part of the stream, and every byte is tested). The z-major CC volume
(`4V` bytes) is never allocated.

## M3a - scaled-dual regime gate (output-preserving)

**Lemma 3.** Let `a` be the pass-1 dual of the full-width regime (`a_u <= q s`, `sum_{u in C_j} a_u <= q c_full` for
every surviving candidate `j`; trivial components contribute `a_u = q s`). Then `y = a c_r / (q c_full)` is a feasible
dual of regime `r` for every label.

*Proof.* Every full-width candidate removed by a reduction also satisfies the constraint: singleton-dominated
(`l s <= c_full`, and `a_u <= q s`), equal coverage (same set), subset-dominated (subset of a kept set, `a >= 0`).
Every candidate of regime `r` (a whole run of length `<= h_r` or a window of a longer run) is a subset of a
full-width candidate (a whole run). Scaling by `c_r / c_full <= 1` turns `q c_full` into `q c_r` and keeps
`y_u <= s`. Constraints never couple labels. []

So `L'_l = ceil(c_r sum_{u in l} a_u / (q c_full))` bounds the records cost of label `l` in regime `r` (128-bit
arithmetic, rounding up only on an integer optimum). With formula (8) and `w_N = 1`,
`LB_r = H + (K-1)(w_L + 2) + sum_l L'_l - max_l L'_l`. If `LB_r >= UB*` (best section so far) regime `r` cannot be
strictly smaller and is skipped; the regime loop keeps a regime only when it is strictly smaller, so the output is
identical to the full search (unless the shared deterministic DP / local-search budgets bind - with `full = 2` there
is no later regime). The scaling factor (`(w_I+1)/(w_I+2)`, about 0.83 here) makes the bound weak; it prunes only
when a narrower regime is far worse. Development measures it (`regime_gate_checked/pruned`).

## Certificate fix (w_D compaction)

With `depth_policy = fixed_depth_width` only the full-width regime is solved, but the written stream compacts `w_D`
to the deepest chosen pin. If no chosen pin is deeper than `2^{8w} - 1`, the stream is a cover by full-width runs of
length `<= h_w` priced at `c_w`, i.e. a stream of a narrower model that the full-width LB (pins priced `c_full`) does
not bound. v2.1 therefore could report `lb_bytes > ub_bytes` (12 rows of the `cape_fixed_depth_width` ablation on
Z=512 crops; `analysis/v3_audit`). v3 adds, for every narrower width `w`, the scaled bound of Lemma 3 (valid for runs
of length `<= h_w`, a subset of regime `w`'s family) to the minimum. The `all_regimes` certificate was already valid
(it adds dual-only bounds of the narrower regimes), and so is `full_width_first` (every regime evaluated).

## M3b - reduced-cost fixing and forcing (QUALITY)

For a feasible dual `a` of a component model and any cover `x` (pins and singletons),
`q cost(x) = sum_u a_u cov_x(u) + sum_j slack_j x_j >= sum_u a_u + sum_j slack_j x_j` with
`slack_j = q c_j - sum_{u in C_j} a_u >= 0` and `cov_x(u) >= 1`. A cover strictly cheaper than the incumbent `UB` has
integer cost `<= UB - 1`. Hence:

1. *fixing:* an item with `sum a + F + slack_j > q (UB - 1)` (F = slack of items already forced) is in no strictly
   cheaper cover;
2. *forcing:* if every remaining option of a CC is fixed except one, that item is in every strictly cheaper cover
   (its slack joins `F`, its CCs are covered);
3. a pin covering only covered CCs is never in an irredundant cover, and a cheapest cover is irredundant;
4. if some CC has no option left, or `sum a + F > q (UB - 1)`, no strictly cheaper cover exists: the incumbent is
   optimal for the component model (`LB = UB`, status exact).

Otherwise the residual (uncovered CCs, free pins restricted to them, singletons with their allowed flag) is solved by
the exact reachable-state DP when it has `<= 30` CCs and fits the deterministic transition / state budget. Every
strictly cheaper cover lies in the residual space, so a DP value `< UB` is the component optimum, and a value
`>= UB` (or infeasibility) proves the incumbent optimal. The result is checked (`is_cover`, cost) before use. This
is classical reduced-cost fixing applied to the CAPE component model; it is not claimed as new.

## M4 - bounded exact repair (QUALITY)

Release `A` (subset of the incumbent `S`), fix `F = S \ A`, re-cover `R = U \ cover(F)` (`|R| <= 30`) with a pool `P` of
pins meeting `R` (always containing `A`'s pins, so the old choice is feasible) and `R`'s singletons, by the exact DP
under a fixed budget. A move is applied only if the component cost strictly drops and the result is a cover. Because
the count width `w_N` and the depth width are global, the encoder keeps all M4 changes of a regime only if the
predicted labels section (byte model = serializer, checked) is strictly smaller than without them; otherwise every
M4 change of that regime is reverted. Accepted sequences never increase the raw size; no global optimality.
Neighbourhoods are deterministic (seed = selected pins by dual slack, then start; growth by incidence order).

## 6. Global terms and decomposition

`w_N` (count width), the written depth width and the background depend on the selection. The LB never hides them in
a constant: it uses `w_N = 1` (any wider count only adds bytes), the minimum over backgrounds (formula 8), and the
minimum over all depth widths a stream can be written with (section "Certificate fix"). Components are independent
only inside one regime and one background; M4's final acceptance is made on the whole section for that reason.
