# Methods (B protocol)

Model: one fixed regime of the PINS labels section (mathematics/problem_definition.md). Candidate family:
CompleteWindows (proved complete: mathematics/dominance_completeness_theorem.md).

Prototype (not an encoder): native diagnostic encode of Eθ (impl_mask 6719) returns its CC ids, records, background,
regime widths and the dual-ascent bound; the instance is rebuilt from them and checked against the native counts and
selection (precheck T4). Column generation: LP restricted master over singletons + one window per useful run, solved
with HiGHS (scipy.optimize.linprog); one exact pricing pass over every useful run per iteration (prefix sums on
floor(lambda * 2^30), tolerance 1e-6); at most 50 000 new columns per iteration; budget 40 iterations or 1800 s per
sample. Integer solution: deterministic greedy over the generated columns, then redundant-pin removal. Certificate:
integer duals (q = 2^20), deterministic repair, independent full-family check, per-component ceiling.

Pseudocode (CG-implicit, one regime):
```
lam <- none; cols <- {one window per useful run} (deduplicated by CC set)
repeat (<= 40 iterations, <= 1800 s):
    (x, y, lam) <- LP(cols + singletons)               # HiGHS
    for each useful run: W*, t* <- max window of floor(lam*2^30) (prefix sums)
    V <- runs with W* > c (1 + tolerance); if V empty: stop (converged)
    cols <- cols + best window of the most violated runs (<= 50 000)
U  <- greedy(cols + singletons) + redundant-pin removal
L  <- integer_certificate(lam)                           # floor q=2^20, repair, re-check, ceil per component
```
Comparator: native Eθ on the same 11 development crops, same machine, one thread, pinned P-core, 2 warmups + 7 timed
repeats; one fresh-process memory measurement per sample (profile build for the memory marks and phase times).
Projection and gate: protocol section 10 (favourable to CG on purpose). The prototype's own Python time and peak are
recorded in raw_results/ only for information.
