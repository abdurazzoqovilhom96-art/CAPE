# CAPE v3 - prior-art / novelty matrix (honest audit)

Read for this matrix: the pinned upstream Crackle code (`vendor/crackle`, 14b39b1) and current HEAD
(`vendor/crackle_head`, 3426263), in particular `src/pins.hpp` (`find_optimal_pins`, `find_suboptimal_pins`) and
`src/cc3d.hpp`; Crackle issue #19 (page read 2026-11-06). The general algorithmic references below are standard
textbook attributions; they were **not** re-read in full for this audit, so no "never done before" statement is made
from them. Verdicts: NOT NEW (known technique, our use is an implementation), CANDIDATE (format-specific property with a
proof and measured value; prior-art search not exhaustive), NOT CLAIMED.

| Mechanism | Problem | Prior mechanism | CAPE v3 difference | Evidence | Limitation | Verdict |
|---|---|---|---|---|---|---|
| M1a neighbour-column dedup | many candidate chains are identical | hashing + exact comparison of chains (v2.1 CAPE; generic dedup) | a proof that 4-adjacent columns with the same z-range and label have equal chains (Crackle's 2D 4-connected CCs) and are never the class representative, so they are dropped before hashing; byte-identical | Lemma 1-2 (`V3_MATHEMATICS.md`), byte identity on 36 cases x 2 policies x 64 masks, development timings | speed-up only; depends on the 4-connected labeling of the format | CANDIDATE (format-specific; not searched exhaustively) |
| M1b component CSR | per-component allocation and random chain reads | CSR adjacency (standard) | applied to the CAPE component models | identical solver inputs (tests) | engineering | NOT NEW |
| M2 eager greedy | stale-count recomputation in the greedy | Crackle issue #19 (CC -> pins bookkeeping, closed as completed 2025-01; upstream `find_suboptimal_pins` uses `component_to_pins`); accelerated / lazy greedy (Minoux 1978) | same inversion in CAPE's weighted greedy with exact tie order | equivalence proof + tests | the upstream optimal greedy (`find_optimal_pins`, allow_pins=2) at 14b39b1 still erases from per-pin hash sets of every overlapping candidate | NOT NEW |
| M5a fused scan | two passes over the input | loop fusion (standard) | - | byte identity | memory-bandwidth bound | NOT NEW |
| M5b batched CC | z-major CC volume held next to the column-major copy | blocked transpose / streaming (standard) | upstream's per-slice labeling called in 16-slice batches, written straight into the chain layout | byte identity; peak memory in development | needs the column-major path | NOT NEW (engineering) |
| M3a scaled-dual regime gate | skip a depth regime that cannot win | LP duality / dual-feasible bounds for set cover (e.g. Balas & Ho 1980; Beasley 1990) | bound transfer between Crackle depth regimes via window-in-run containment | Lemma 3; output identity tests | weak bound (factor ~0.83) | NOT NEW technique; transfer lemma format-specific (CANDIDATE only if it saved time - see development results) |
| Certificate w_D fix | v2.1 fixed-depth certificate could exceed the stream | - | the same transfer lemma closes a real defect of v2.1 | 12 invalid v1/v2 rows found by the audit; tests | weaker LB when Z > 256 | correctness fix (not a novelty claim) |
| M3b reduced-cost fixing | prove / improve components the plain DP skips | reduced-cost fixing (integer programming textbooks, e.g. Nemhauser & Wolsey 1988) | applied to the per-component CAPE model with forcing and an exact residual DP | brute-force tests (360 random models) | small component gains | NOT NEW |
| M4 bounded repair | heuristic components with a gap | large neighbourhood search (Shaw 1998) | Crackle-section acceptance (count / depth widths included) | tests; development grid | QUALITY only; small gains | NOT NEW |
| SAFE selector | never larger than flat + zstd | min-of-candidates selection (standard) | v2/v2.1 | - | engineering guard | NOT NEW |

**What could be claimed (only with the confirm results in `analysis/v3_final`):** a Crackle-v1-compatible encoder
whose implementation is byte-identical to v2.1 and faster on the measured volumes, with a format-specific duplicate
rule and a corrected restricted-model certificate. Whether this is enough for a research claim depends on the
independent-volume evidence (currently one acquisition) and on a fuller prior-art search; neither is assumed here.
