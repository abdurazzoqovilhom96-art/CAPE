# Contribution and prior art

| Mechanism | Known before | CAPE / Q1 difference | Evidence | Limitation |
|---|---|---|---|---|
| Crackle crack codes + PINS labels | Crackle (seung-lab, commit 14b39b1) | CAPE selects PINS records by a certified set-cover solver; stream unchanged in format | v1-v3 reports; T03 C3 | size gain small vs matched greedy |
| Equal-coverage dedup by hashing | standard (hash grouping) | M1a: neighbour-column twins dropped at generation, proved exact for 4-connected 2D CCs | mathematics/m1a_proposition.md; ablation F06 | M1a is v3, not Q1 |
| Inverted incidence / eager greedy | Crackle issue #19 (2024-07, closed 2025-01); lazy greedy (Minoux 1978) | v3 M2 rejected (no gain) | v3 selection | not used |
| Batched CC straight into column-major chains | common blocking/transposition practice | M5b (v3) | v3 | - |
| O1 lean CC | cc3d relabel numbering (first raster pixel) | removes two per-voxel passes; proof that start_label offsets commute | q1_output_preserving.md | tested and rejected in development (S_T 0.993, 95% CI lower 0.986); not part of Eθ |
| O2 exact run allocation | standard reserve-before-fill | exact count V - z_pairs computed in the CC pass | q1_output_preserving.md | engineering |
| O3 compact uint16 chains | standard narrow-index storage | slice-local ids + per-slice offset, exact equality/hash/subset on local ids | q1_output_preserving.md | falls back above 65536 CCs per slice |
| Integer dual lower bound / certificate | LP duality for set cover (classical) | format-coupled bound incl. w_D compaction fix | certificate_model.md | restricted model |

Conclusion: Q1 is an engineering contribution with machine-checked output equivalence (byte identity against the
frozen binary on every measured sample), not a new compression algorithm.
